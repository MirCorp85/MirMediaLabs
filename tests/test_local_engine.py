"""Local-engine behaviour against a fake Ollama: every MirAI step must ask for the SAME context window (Ollama reloads
the model when num_ctx changes), local JSON asks must request JSON mode, and the model list must be cached.

    python -m unittest discover tests
"""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CALLS = []
MODELS = [{"name": "gemma4:12b", "details": {"context_length": 131072}}]


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        CALLS.append(("GET", self.path, None))
        if self.path == "/api/tags":
            return self._send({"models": MODELS})
        if self.path == "/api/ps":
            return self._send({"models": []})
        return self._send({"version": "0.40.0"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        CALLS.append(("POST", self.path, body))
        if self.path == "/api/show":
            return self._send({"capabilities": ["completion", "vision"]})
        if self.path == "/api/chat":
            content = json.dumps({"action": "chat", "prompt": "", "why": "talk"}) if body.get("format") == "json" else "hi"
            return self._send({"message": {"content": content}, "done": True, "prompt_eval_count": 10, "eval_count": 2})
        return self._send({"response": '{"ok": true}' if body.get("format") == "json" else "a prompt", "done": True})


SRV = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
threading.Thread(target=SRV.serve_forever, daemon=True).start()
os.environ["OLLAMA_HOST_URL"] = "http://127.0.0.1:%d" % SRV.server_port
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

import core  # noqa: E402
import router  # noqa: E402


def ctx_of(path):
    return [(b.get("options") or {}).get("num_ctx") for m, p, b in CALLS if m == "POST" and p == path]


class LocalEngine(unittest.TestCase):
    def setUp(self):
        CALLS.clear()
        core.CTX_OK.clear()
        core._TAGS.update(t=0.0, models=None)

    def test_uses_configured_host(self):
        self.assertEqual(core.OLLAMA, os.environ["OLLAMA_HOST_URL"])

    def test_director_and_prompt_writer_share_one_window(self):
        router.decide("tell me about verses and choruses", [], [], model=core.engine_model())
        core.ask("a cabin in the snow", "write a prompt")
        chat, gen = ctx_of("/api/chat"), ctx_of("/api/generate")
        self.assertTrue(chat and gen)
        self.assertEqual(len(set(chat + gen)), 1, (chat, gen))
        self.assertGreaterEqual(chat[0], 8192)       # the Director's ~3.2K-token prompt + output must fit

    def test_learned_window_is_used_everywhere(self):
        core.CTX_OK["gemma4:12b"] = 32768
        router.decide("hello there", [], [], model="gemma4:12b")
        core.ask("x", "y")
        self.assertEqual(set(ctx_of("/api/chat") + ctx_of("/api/generate")), {32768})

    def test_json_mode_for_local_asks(self):
        core.ask("plan it", "reply JSON", want_json=True)
        core.ask("plain", "reply text")
        fmts = [b.get("format") for m, p, b in CALLS if p == "/api/generate"]
        self.assertEqual(fmts, ["json", None])

    def test_model_list_is_cached(self):
        for _ in range(5):
            core.engine_model()
            core.model_max_ctx("gemma4:12b")
        self.assertEqual(sum(1 for m, p, b in CALLS if p == "/api/tags"), 1)


if __name__ == "__main__":
    unittest.main()
