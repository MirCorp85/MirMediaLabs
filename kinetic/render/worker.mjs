// MirKinetic render worker — one headless Chrome, frames out as JPEG. No npm packages: Node's own http server serves the
// engine, the job's spec and its media; Node's WebSocket speaks the Chrome DevTools Protocol to the Chrome (or Edge)
// already installed on this PC. Everything stays on 127.0.0.1.
//
//   node worker.mjs --job <job.json> --info                       film facts (duration, cues, cuts) as JSON on stdout
//   node worker.mjs --job <job.json> --dsf 1 --from 0 --to 600    frames 0..599 to stdout:
//                                                                 per frame u32 frame, u32 n, then n x (u32 len, jpeg)
//   node worker.mjs --job <job.json> --still out.jpg --frame 120  one frame to a file
//
// job.json: { engine: <engine dir>, spec: <project>, media: { "<file>": "<abs path>" }, mirfonts: <MirFonts out dir>,
//             chrome?: <exe>, blur?: true, quality?: 95, maxSamples?: 99, gpu?: false }
// Motion blur: n sub-frames over a forward 180-degree shutter (longer in the film's smear windows), never across a hard
// cut (a cut inside the shutter slides the window back). When an effect is active on the frame, the sub-frames are
// averaged in the page and the OpenKatana stack runs there, so one JPEG comes back.
// If Chrome dies mid-run (a GPU process crash under several parallel workers, say) the worker notices (the DevTools
// socket closes, every pending call rejects), relaunches a software-rendered Chrome and carries on from the same frame.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';

const A = {};
for (let i = 2; i < process.argv.length; i++) { const k = process.argv[i]; if (k.startsWith('--')) { const v = process.argv[i + 1]; if (v == null || v.startsWith('--')) A[k.slice(2)] = true; else { A[k.slice(2)] = v; i++; } } }
if (!A.job) { console.error('usage: worker.mjs --job job.json [--info | --still out.jpg --frame k | --dsf 1 --from 0 --to N]'); process.exit(2); }
const JOB = JSON.parse(fs.readFileSync(A.job, 'utf8'));
const ENGINE = path.resolve(JOB.engine);
const DSF = +(A.dsf || 1), Q = +(A.quality || JOB.quality || 95), MAXS = +(A.maxs || JOB.maxSamples || 99);
const BLUR = JOB.blur !== false && !A.noblur;
const GPU = A.gpu != null ? A.gpu !== '0' : JOB.gpu !== false;
const log = s => process.stderr.write(s + '\n');
const dbg = s => process.stderr.write('· ' + s + '\n');
const V = !!process.env.MIR_KINETIC_VERBOSE;

// ── the film server ───────────────────────────────────────────────────────────────────────────────────────────
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css',
  '.json': 'application/json', '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.woff': 'font/woff', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.mp4': 'video/mp4', '.webm': 'video/webm' };
function sendFile(res, p) {
  fs.stat(p, (e, st) => {
    if (e || !st.isFile()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(p).toLowerCase()] || 'application/octet-stream', 'Content-Length': st.size, 'Cache-Control': 'no-store' });
    fs.createReadStream(p).pipe(res);
  });
}
const server = http.createServer((req, res) => {
  const u = decodeURIComponent((req.url || '/').split('?')[0]);
  if (u === '/spec.json') { const b = JSON.stringify(JOB.spec); res.writeHead(200, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(b) }); return res.end(b); }
  if (u.startsWith('/media/')) { const p = (JOB.media || {})[u.slice(7)]; if (!p) { res.writeHead(404); return res.end(); } return sendFile(res, p); }
  if (u.startsWith('/mirfonts/')) { const f = u.slice(10); if (!/^[a-z0-9]+\.(woff2|ttf)$/.test(f) || !JOB.mirfonts) { res.writeHead(404); return res.end(); } return sendFile(res, path.join(JOB.mirfonts, f)); }
  const rel = path.normalize(u === '/' ? '/film.html' : u).replace(/^(\.\.[\\/])+/, '');
  const p = path.join(ENGINE, rel);
  if (!p.startsWith(ENGINE)) { res.writeHead(403); return res.end(); }
  sendFile(res, p);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}`;

// ── Chrome over CDP ───────────────────────────────────────────────────────────────────────────────────────────
function findChrome() {
  const c = [JOB.chrome, process.env.MIR_CHROME, 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google\\Chrome\\Application\\chrome.exe'),
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].filter(Boolean);
  return c.find(p => { try { return fs.statSync(p).isFile(); } catch { return false; } });
}
class BrowserDied extends Error {}
class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.wait = new Map(); this.on = new Map(); this.dead = false;
    ws.onmessage = e => this.recv(JSON.parse(e.data));
    ws.onclose = () => this.die('DevTools socket closed');
    ws.onerror = () => this.die('DevTools socket error');
  }
  die(why) { if (this.dead) return; this.dead = why; for (const w of this.wait.values()) w.rej(new BrowserDied(why)); this.wait.clear(); }
  recv(m) {
    if (m.id != null) { const w = this.wait.get(m.id); if (w) { this.wait.delete(m.id); m.error ? w.rej(new Error(m.error.message)) : w.res(m.result); } return; }
    const h = this.on.get(m.method); if (h) h(m.params, m.sessionId);
  }
  send(method, params = {}, sessionId) {
    if (this.dead) return Promise.reject(new BrowserDied(this.dead));
    const id = ++this.id;
    return new Promise((res, rej) => { this.wait.set(id, { res, rej }); this.ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params })); });
  }
}
async function launch(gpu) {
  const exe = findChrome();
  if (!exe) throw new Error('no Chrome or Edge found (set MIR_CHROME to chrome.exe)');
  const udd = fs.mkdtempSync(path.join(os.tmpdir(), 'mirkinetic-'));
  const args = ['--headless=new', '--remote-debugging-port=0', '--remote-allow-origins=*', `--user-data-dir=${udd}`, '--no-first-run', '--no-default-browser-check',
    '--hide-scrollbars', '--mute-audio', '--window-size=1920,1300', '--disable-checker-imaging',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--font-render-hinting=none', '--autoplay-policy=no-user-gesture-required',
    '--disable-breakpad', '--disable-crash-reporter', '--noerrdialogs'];
  // --run-all-compositor-stages-before-draw keeps big 3D layers from being captured half rastered on the GPU path; with software
  // rendering it makes Page.captureScreenshot deadlock as soon as two Chromes run at once (and the software raster is complete anyway)
  args.push(...(gpu ? ['--ignore-gpu-blocklist', '--enable-gpu', '--use-angle=d3d11', '--run-all-compositor-stages-before-draw'] : ['--disable-gpu']));
  if (process.env.MIR_KINETIC_FLAGS) args.push(...process.env.MIR_KINETIC_FLAGS.split(' ').filter(Boolean));
  const proc = spawn(exe, args, { stdio: ['ignore', 'ignore', 'pipe'] });
  dbg('chrome spawned pid ' + proc.pid + (gpu ? ' (gpu)' : ' (software)'));
  const wsUrl = await new Promise((res, rej) => {
    let buf = ''; const to = setTimeout(() => rej(new Error('Chrome gave no DevTools endpoint in 30 s')), 30000);
    proc.stderr.on('data', d => { buf += d; const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) { clearTimeout(to); res(m[1]); } });
    proc.on('exit', c => { clearTimeout(to); rej(new Error('Chrome exited early (' + c + ')')); });
  });
  dbg('devtools ' + wsUrl);
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { const to = setTimeout(() => rej(new Error('DevTools socket did not open in 20 s')), 20000); ws.onopen = () => { clearTimeout(to); res(); }; ws.onerror = () => { clearTimeout(to); rej(new Error('DevTools socket failed')); }; });
  dbg('socket open');
  const cdp = new CDP(ws);
  proc.on('exit', c => cdp.die('Chrome exited (' + c + ')'));
  const close = async () => {
    try { if (!cdp.dead) await Promise.race([cdp.send('Browser.close'), new Promise(r => setTimeout(r, 2500))]); } catch {}
    try { proc.kill(); } catch {}
    setTimeout(() => { try { fs.rmSync(udd, { recursive: true, force: true }); } catch {} }, 800);
  };
  return { cdp, close, proc, gpu };
}
async function openFilm(cdp) {
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId: sid } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  const errs = [];
  cdp.on.set('Runtime.exceptionThrown', p => errs.push('PAGE ' + (p.exceptionDetails?.exception?.description || p.exceptionDetails?.text || '').slice(0, 300)));
  cdp.on.set('Runtime.consoleAPICalled', p => { if (p.type === 'error') errs.push('CONSOLE ' + p.args.map(a => a.value ?? a.description ?? '').join(' ').slice(0, 300)); });
  await cdp.send('Page.enable', {}, sid); await cdp.send('Runtime.enable', {}, sid);
  // headless keeps about 90 px of window chrome: a 1080-high viewport would paint only ~990 px of the stage
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1300, deviceScaleFactor: DSF, mobile: false }, sid);
  dbg('page attached');
  await cdp.send('Page.navigate', { url: BASE + '/film.html?render=1' }, sid);
  dbg('navigated');
  const ev = async (expression, awaitPromise = false) => (await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise }, sid)).result.value;
  const t0 = Date.now();
  while (!(await ev('window.__ready === true'))) { if (Date.now() - t0 > 120000) throw new Error('film never became ready: ' + errs.join(' | ')); await new Promise(r => setTimeout(r, 120)); }
  const err = await ev('window.__error || ""');
  if (err) throw new Error('film failed to build: ' + err);
  dbg('film ready in ' + (Date.now() - t0) + ' ms');
  return { sid, ev, errs };
}
// one Chrome + one film page; relaunched (software rendering) when the browser dies
async function session(gpu) {
  let b;
  try { b = await launch(gpu); } catch (e) { if (!gpu) throw e; log('GPU launch failed (' + e.message + '), retrying without GPU'); b = await launch(false); }
  const f = await openFilm(b.cdp);
  const shot = () => b.cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: Q, optimizeForSpeed: true, clip: { x: 0, y: 0, width: 1920, height: 1080, scale: DSF } }, f.sid).then(r => r.data);
  return { ...b, ...f, shot };
}

// ── main ──────────────────────────────────────────────────────────────────────────────────────────────────────
let S = await session(GPU), code = 0, relaunches = 0;
try {
  const info = await S.ev('JSON.stringify(window.__film)');
  const film = JSON.parse(info);
  if (A.info) { process.stdout.write(info + '\n'); }
  else {
    const fps = film.fps, cuts = film.cuts || [], DT = .5 / fps;
    // one output frame: its sub-frame times, and whether the effect stack is on
    async function frame(k) {
      const { ev, shot } = S, t = k / fps;
      const seek = ts => ev(`new Promise(r => { window.__seek(${ts}); requestAnimationFrame(() => requestAnimationFrame(() => r(1))); })`, true);
      let n = 1, st0 = t, end = t;
      if (BLUR) {
        const sh = await ev(`window.__shutter(${t})`);
        end = t + DT * sh;
        for (const c of cuts) if (c > t + 1e-6 && c < end) { end = c - 1e-4; st0 = Math.max(end - DT * sh, t - DT * sh); }
        for (const c of cuts) if (c > st0 && c <= t) st0 = c;
        n = Math.min(MAXS, await ev(`window.__samples(${st0}, ${end - st0})`));
      }
      if (V) dbg(`frame ${k}: n=${n} st0=${st0.toFixed(3)} end=${end.toFixed(3)}`);
      await ev(`window.__frameT = ${t}`);
      const fx = await ev(`window.__fxActive(${t})`);
      const jpegs = [];
      if (fx) await ev(`window.__fxBegin(${Math.round(1920 * DSF)}, ${Math.round(1080 * DSF)})`);
      for (let j = 0; j < n; j++) {
        const ts = n === 1 ? t : st0 + (end - st0) * j / (n - 1);
        await seek(ts); if (V) dbg(`  seek ${ts.toFixed(4)} ok`);
        const b64 = await shot(); if (V) dbg(`  shot ${b64.length} b64`);
        if (fx) await ev(`window.__fxAdd(${JSON.stringify(b64)})`, true); else jpegs.push(Buffer.from(b64, 'base64'));
      }
      if (fx) jpegs.push(Buffer.from(await ev(`window.__fxEnd(${t}, ${Q / 100})`, true), 'base64'));
      return jpegs;
    }
    // a frame, surviving a browser death: relaunch without GPU and render the same frame again
    async function frameSafe(k) {
      for (;;) {
        try { return await frame(k); }
        catch (e) {
          if (!(e instanceof BrowserDied) && !S.cdp.dead) throw e;
          if (++relaunches > 3) throw new Error('Chrome died ' + relaunches + ' times (' + (S.cdp.dead || e.message) + ')');
          log(`Chrome died at frame ${k} (${S.cdp.dead || e.message}); relaunching without GPU (${relaunches})`);
          try { await S.close(); } catch {}
          S = await session(false);
        }
      }
    }
    if (A.still) {
      const js = await frameSafe(+(A.frame || 0));
      fs.writeFileSync(A.still, js[js.length - 1]);      // a still skips the averaging: the last (sharpest) sample
    } else {
      const F0 = +(A.from || 0), F1 = +(A.to || Math.round(film.dur * fps)), out = process.stdout, st = Date.now();
      const write = buf => new Promise(r => (out.write(buf) ? r() : out.once('drain', r)));
      for (let k = F0; k < F1; k++) {
        const js = await frameSafe(k);
        const hdr = Buffer.alloc(8); hdr.writeUInt32LE(k, 0); hdr.writeUInt32LE(js.length, 4); await write(hdr);
        for (const jb of js) { const lb = Buffer.alloc(4); lb.writeUInt32LE(jb.length, 0); await write(lb); await write(jb); }
        if ((k - F0) % 60 === 0) log(`[${F0}-${F1}] frame ${k} ${((Date.now() - st) / 1000).toFixed(0)}s`);
      }
      await new Promise(r => out.end(r));
    }
  }
  if (S.errs.length) log('PAGE ERRORS ' + JSON.stringify(S.errs.slice(0, 5)));
} catch (e) { log('ERROR ' + (e && e.stack || e)); code = 1; }
finally { await S.close(); server.close(); }
process.exit(code);
