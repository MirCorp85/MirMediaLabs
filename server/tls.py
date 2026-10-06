"""HTTPS for the remote address (Let's Encrypt, http-01).

A tiny ACME v2 client built on `cryptography` (no openssl / certbot needed, so it also works
in the compiled PC edition). Everything lives in data/tls/:
  tls.json       {"domain": "my-lab.example.com", "https_port": 443, "http_port": 80, "enabled": true}
  account.pem    ACME account key (EC P-256)      domain.pem   certificate key
  cert.pem       full chain from Let's Encrypt     challenges/  http-01 tokens while issuing

Runtime (start()): a port-80 helper serves /.well-known/acme-challenge/* and redirects
everything else to https; the same Flask app is served with TLS on :443 (real client IPs,
so the loopback-is-owner rule in the gate stays correct); a loop renews 30 days before expiry
and swaps the cert into the live SSL context without a restart.

Issue once from the server folder:  python tls.py issue [--staging]
"""
import base64
import datetime
import hashlib
import http.server
import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.x509.oid import NameOID

import core

DIR = os.path.join(core.DATA, "tls")
CHAL = os.path.join(DIR, "challenges")
CFG_FILE = os.path.join(DIR, "tls.json")
ACCOUNT, DOMAIN_KEY, CERT = (os.path.join(DIR, f) for f in ("account.pem", "domain.pem", "cert.pem"))
LE = "https://acme-v02.api.letsencrypt.org/directory"
LE_STAGING = "https://acme-staging-v02.api.letsencrypt.org/directory"
RENEW_DAYS = 30
STATE = {"https": False, "error": None, "expires": None}
_CTX = None


def cfg():
    c = {"domain": "", "https_port": 443, "http_port": 80, "enabled": True}   # domain set per install in data/tls/tls.json
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            c.update(json.load(f))
    except (OSError, ValueError):
        pass
    return c


# ── keys / encoding ──────────────────────────────────────────────────────────
def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _key(path):
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), None)
    k = ec.generate_private_key(ec.SECP256R1())
    os.makedirs(DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()))
    return k


def _jwk(k):
    n = k.public_key().public_numbers()
    return {"crv": "P-256", "kty": "EC", "x": _b64(n.x.to_bytes(32, "big")), "y": _b64(n.y.to_bytes(32, "big"))}


def _thumb(k):
    return _b64(hashlib.sha256(json.dumps(_jwk(k), sort_keys=True, separators=(",", ":")).encode()).digest())


# ── ACME client ──────────────────────────────────────────────────────────────
class Acme:
    def __init__(self, directory, log=print):
        self.log, self.key, self.kid = log, _key(ACCOUNT), None
        self.dir = json.loads(urllib.request.urlopen(directory, timeout=30).read())
        self.nonce = None

    def _req(self, url, data=None, method="GET"):
        r = urllib.request.Request(url, data=data, method=method, headers={
            "Content-Type": "application/jose+json", "User-Agent": "MirMediaLabs-acme"})
        try:
            resp = urllib.request.urlopen(r, timeout=30)
        except urllib.error.HTTPError as e:
            resp = e
        self.nonce = resp.headers.get("Replay-Nonce") or self.nonce
        body = resp.read()
        return resp.status if hasattr(resp, "status") else resp.code, resp.headers, body

    def post(self, url, payload):
        """Signed POST; payload None = POST-as-GET. Retries once on badNonce."""
        for _ in range(2):
            if not self.nonce:
                self._req(self.dir["newNonce"], method="HEAD")
            prot = {"alg": "ES256", "nonce": self.nonce, "url": url}
            prot.update({"kid": self.kid} if self.kid else {"jwk": _jwk(self.key)})
            p64 = _b64(json.dumps(prot).encode())
            b64 = "" if payload is None else _b64(json.dumps(payload).encode())
            r, s = decode_dss_signature(self.key.sign(("%s.%s" % (p64, b64)).encode(), ec.ECDSA(hashes.SHA256())))
            sig = _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
            self.nonce = None
            code, hdrs, body = self._req(url, json.dumps({"protected": p64, "payload": b64, "signature": sig}).encode(), "POST")
            if code == 400 and b"badNonce" in body:
                continue
            if code >= 400:
                raise RuntimeError("ACME %s %s: %s" % (code, url, body[:400].decode(errors="replace")))
            return hdrs, body
        raise RuntimeError("ACME: repeated badNonce")

    def _poll(self, url, done=("valid",), bad=("invalid",)):
        for _ in range(60):
            _, body = self.post(url, None)
            obj = json.loads(body)
            if obj.get("status") in done:
                return obj
            if obj.get("status") in bad:
                raise RuntimeError("ACME failed: %s" % json.dumps(obj)[:600])
            time.sleep(2)
        raise RuntimeError("ACME timed out at " + url)

    def issue(self, domain):
        hdrs, _ = self.post(self.dir["newAccount"], {"termsOfServiceAgreed": True})
        self.kid = hdrs["Location"]
        hdrs, body = self.post(self.dir["newOrder"], {"identifiers": [{"type": "dns", "value": domain}]})
        order_url, order = hdrs["Location"], json.loads(body)
        os.makedirs(CHAL, exist_ok=True)
        for az in order["authorizations"]:
            _, body = self.post(az, None)
            auth = json.loads(body)
            if auth["status"] == "valid":
                continue
            ch = next(c for c in auth["challenges"] if c["type"] == "http-01")
            tok = ch["token"]
            with open(os.path.join(CHAL, tok), "w", encoding="ascii") as f:
                f.write(tok + "." + _thumb(self.key))
            self.log("validating http://%s/.well-known/acme-challenge/%s" % (domain, tok))
            try:
                self.post(ch["url"], {})
                self._poll(az)
            finally:
                try:
                    os.remove(os.path.join(CHAL, tok))
                except OSError:
                    pass
        dkey = _key(DOMAIN_KEY)
        csr = (x509.CertificateSigningRequestBuilder()
               .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain)]))
               .add_extension(x509.SubjectAlternativeName([x509.DNSName(domain)]), critical=False)
               .sign(dkey, hashes.SHA256()))
        self.post(order["finalize"], {"csr": _b64(csr.public_bytes(serialization.Encoding.DER))})
        order = self._poll(order_url, bad=("invalid",))
        _, pem = self.post(order["certificate"], None)
        tmp = CERT + ".new"
        with open(tmp, "wb") as f:
            f.write(pem)
        os.replace(tmp, CERT)
        self.log("certificate saved: " + CERT)


def expires():
    try:
        with open(CERT, "rb") as f:
            c = x509.load_pem_x509_certificate(f.read())
        return c.not_valid_after_utc
    except (OSError, ValueError):
        return None


def have_cert():
    return os.path.isfile(CERT) and os.path.isfile(DOMAIN_KEY) and expires() is not None


# ── runtime ──────────────────────────────────────────────────────────────────
class _Http80(http.server.BaseHTTPRequestHandler):
    """Port 80: ACME tokens + redirect to https. Never touches the app or its data."""
    def do_GET(self):
        p = self.path.split("?")[0]
        if p.startswith("/.well-known/acme-challenge/"):
            tok = os.path.basename(p)
            fp = os.path.join(CHAL, tok)
            if tok and os.path.isfile(fp):
                data = open(fp, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_error(404)
            return
        c = cfg()
        host = (self.headers.get("Host") or c["domain"]).split(":")[0]
        if STATE["https"]:
            port = "" if c["https_port"] == 443 else ":%d" % c["https_port"]
            loc = "https://%s%s%s" % (host, port, self.path)
        else:
            loc = "http://%s:%d%s" % (host, core.PORT, self.path)
        self.send_response(301)
        self.send_header("Location", loc)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_HEAD = do_GET

    def log_message(self, *a):
        pass


def _serve80(port):
    try:
        srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), _Http80)
    except OSError as e:
        STATE["error"] = "port %d busy: %s" % (port, e)
        return
    srv.serve_forever()


def _serve443(app, port):
    global _CTX
    from werkzeug.serving import make_server
    _CTX = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    _CTX.minimum_version = ssl.TLSVersion.TLSv1_2
    _CTX.load_cert_chain(CERT, DOMAIN_KEY)
    try:
        srv = make_server("0.0.0.0", port, app, threaded=True, ssl_context=_CTX)
    except OSError as e:
        STATE["error"] = "port %d busy: %s" % (port, e)
        return
    STATE["https"] = True
    srv.serve_forever()


def _renew_loop():
    while True:
        time.sleep(12 * 3600)
        exp = expires()
        if not exp or exp - datetime.datetime.now(datetime.timezone.utc) > datetime.timedelta(days=RENEW_DAYS):
            continue
        try:
            Acme(LE).issue(cfg()["domain"])
            if _CTX:
                _CTX.load_cert_chain(CERT, DOMAIN_KEY)    # new handshakes get the new cert
            STATE["error"], STATE["expires"] = None, str(expires())
        except Exception as e:                            # keep serving the old cert; retry in 12 h
            STATE["error"] = "renew failed: %s" % e


def start(app):
    c = cfg()
    if not c.get("enabled") or not c.get("domain"):   # no domain configured → plain http only
        return
    threading.Thread(target=_serve80, args=(c["http_port"],), daemon=True, name="mml-http80").start()
    if have_cert():
        STATE["expires"] = str(expires())
        threading.Thread(target=_serve443, args=(app, c["https_port"]), daemon=True, name="mml-https").start()
        threading.Thread(target=_renew_loop, daemon=True, name="mml-tls-renew").start()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "issue":
        staging = "--staging" in sys.argv
        if staging:                                       # staging certs must never overwrite a real one
            CERT = os.path.join(DIR, "cert-staging.pem")
        Acme(LE_STAGING if staging else LE).issue(cfg()["domain"])
        print("expires:", expires() if not staging else "(staging)")
    else:
        print(__doc__)
