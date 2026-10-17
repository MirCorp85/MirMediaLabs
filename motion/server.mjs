// MIR MOTION render daemon — 127.0.0.1:5421 only (MIR MEDIA LABS copy; MIR runs its own on 5420). Bundles the Remotion project once, then renders jobs
// posted by the Media Lab (server/remotion.py). Serves library media + MIR fonts to the headless browser.
//   GET  /health            → {ok, bundled, queue, version}
//   GET  /schema            → scene schema (inspector + AI)
//   POST /render {id, project, out, codec, crf, alpha, frameRange?, scale?}  → queued
//   GET  /job/:id           → {status, pct, stage, out, error}
//   POST /cancel/:id
//   POST /still {project, frame, out}   → renders one PNG synchronously
//   POST /rebundle                       → after user TSX comps change
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition, makeCancelSignal} from '@remotion/renderer';

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const PORT = +(process.env.MIR_MOTION_PORT || 5421);
const LIB = process.env.MIR_LIB || path.join(HERE, '..', 'data', 'library');
const REFS = process.env.MIR_REFS || path.join(HERE, '..', 'data', 'refs');
const FONTS = process.env.MIR_FONTS || path.join(HERE, '..', 'server', 'static', 'fonts', 'mir');
const EXTRA = (process.env.MIR_MEDIA_ROOTS || '').split(';').filter(Boolean); // extra readable roots (abs: paths)
const BASE = `http://127.0.0.1:${PORT}/`;
const CONC = Math.max(1, Math.min(8, +(process.env.MIR_MOTION_CONC || 0) || Math.floor((await import('node:os')).cpus().length / 2)));
const VERSION = JSON.parse(fs.readFileSync(path.join(HERE, 'node_modules/remotion/package.json'), 'utf8')).version;

let serveUrl = null;
let bundling = null;
const jobs = new Map(); // id -> {status, pct, stage, out, error, cancel, started, finished}
const queue = [];
let busy = false;

const log = (...a) => console.log(new Date().toISOString().slice(11, 19), '[motion]', ...a);

async function ensureBundle(force = false) {
	if (serveUrl && !force) return serveUrl;
	if (bundling) return bundling;
	bundling = (async () => {
		const t = Date.now();
		serveUrl = await bundle({entryPoint: path.join(HERE, 'src/index.ts'), outDir: path.join(HERE, '.bundle'), onProgress: () => {}});
		log('bundled in', Date.now() - t, 'ms');
		bundling = null;
		return serveUrl;
	})();
	return bundling;
}

const prep = (project) => ({...project, mediaBase: BASE + 'lib/', fontBase: BASE + 'fonts/'});

const CODECS = {
	mp4: {codec: 'h264', ext: 'mp4'},
	h265: {codec: 'h265', ext: 'mp4'},
	webm: {codec: 'vp8', ext: 'webm'},
	alpha: {codec: 'vp8', ext: 'webm', pixelFormat: 'yuva420p', imageFormat: 'png'},
	prores: {codec: 'prores', ext: 'mov', proResProfile: '4444', pixelFormat: 'yuva444p10le', imageFormat: 'png'},
	gif: {codec: 'gif', ext: 'gif'},
	mp3: {codec: 'mp3', ext: 'mp3'},
	wav: {codec: 'wav', ext: 'wav'},
};

async function runJob(id, spec) {
	const j = jobs.get(id);
	try {
		j.stage = 'bundling';
		const su = await ensureBundle();
		const inputProps = {project: prep(spec.project)};
		j.stage = 'preparing';
		const comp = await selectComposition({serveUrl: su, id: 'Project', inputProps});
		const c = CODECS[spec.codec] || CODECS.mp4;
		const {cancelSignal, cancel} = makeCancelSignal();
		j.cancel = cancel;
		j.stage = 'rendering';
		j.frames = comp.durationInFrames;
		fs.mkdirSync(path.dirname(spec.out), {recursive: true});
		await renderMedia({
			serveUrl: su,
			composition: comp,
			inputProps,
			codec: c.codec,
			outputLocation: spec.out,
			crf: c.codec === 'h264' || c.codec === 'h265' ? spec.crf ?? 20 : undefined,
			pixelFormat: c.pixelFormat,
			imageFormat: c.imageFormat || 'jpeg',
			proResProfile: c.proResProfile,
			frameRange: Array.isArray(spec.frameRange) ? spec.frameRange : undefined,
			scale: spec.scale || 1,
			muted: !!spec.muted,
			concurrency: spec.concurrency || CONC,
			cancelSignal,
			onProgress: ({progress, stitchStage}) => {
				j.pct = Math.round(progress * 1000) / 10;
				j.stage = stitchStage === 'muxing' ? 'muxing' : 'rendering';
			},
			chromiumOptions: {gl: 'angle'},
			timeoutInMilliseconds: 120000,
		});
		j.status = 'done';
		j.pct = 100;
		j.stage = 'done';
	} catch (e) {
		j.status = j.status === 'cancelled' ? 'cancelled' : 'error';
		j.error = String((e && e.message) || e).slice(0, 2000);
		log('job', id, j.status, j.error.slice(0, 200));
	}
	j.finished = Date.now();
	j.cancel = null;
}

async function pump() {
	if (busy) return;
	const next = queue.shift();
	if (!next) return;
	busy = true;
	const j = jobs.get(next.id);
	if (j && j.status === 'queued') {
		j.status = 'running';
		j.started = Date.now();
		await runJob(next.id, next.spec);
	}
	busy = false;
	pump();
}

// ── static media with Range support (the renderer's compositor seeks videos over HTTP) ──
const MIME = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.mkv': 'video/x-matroska', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.flac': 'audio/flac', '.woff2': 'font/woff2', '.ttf': 'font/ttf'};
function sendFile(req, res, root, rel) {
	const p = path.resolve(root, rel);
	if (!p.toLowerCase().startsWith(path.resolve(root).toLowerCase() + path.sep) || !fs.existsSync(p) || !fs.statSync(p).isFile()) {
		res.writeHead(404).end();
		return;
	}
	const size = fs.statSync(p).size;
	const type = MIME[path.extname(p).toLowerCase()] || 'application/octet-stream';
	const r = /bytes=(\d*)-(\d*)/.exec(req.headers.range || '');
	const head = {'Content-Type': type, 'Accept-Ranges': 'bytes', 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-cache'};
	if (r) {
		const s = r[1] ? +r[1] : 0;
		const e = r[2] ? Math.min(+r[2], size - 1) : size - 1;
		res.writeHead(206, {...head, 'Content-Range': `bytes ${s}-${e}/${size}`, 'Content-Length': e - s + 1});
		fs.createReadStream(p, {start: s, end: e}).pipe(res);
	} else {
		res.writeHead(200, {...head, 'Content-Length': size});
		fs.createReadStream(p).pipe(res);
	}
}

const body = (req) =>
	new Promise((ok, bad) => {
		let b = '';
		req.on('data', (d) => {
			b += d;
			if (b.length > 16e6) req.destroy();
		});
		req.on('end', () => {
			try {
				ok(b ? JSON.parse(b) : {});
			} catch (e) {
				bad(e);
			}
		});
	});
const json = (res, code, o) => res.writeHead(code, {'Content-Type': 'application/json'}).end(JSON.stringify(o));
const outOk = (p) => typeof p === 'string' && path.isAbsolute(p) && /\.(mp4|webm|mov|gif|png|jpg|mp3|wav)$/i.test(p);

const srv = http.createServer(async (req, res) => {
	const u = new URL(req.url, BASE);
	const seg = decodeURIComponent(u.pathname).split('/').filter(Boolean);
	try {
		if (req.method === 'GET' && seg[0] === 'lib') {
			if (seg[1] === 'ref') return sendFile(req, res, REFS, seg.slice(2).join('/'));
			if (seg[1] === 'abs') {
				const p = Buffer.from(seg[2] || '', 'base64url').toString();
				const root = EXTRA.find((r) => path.resolve(p).toLowerCase().startsWith(path.resolve(r).toLowerCase() + path.sep));
				return root ? sendFile(req, res, root, path.relative(root, p)) : res.writeHead(404).end();
			}
			return sendFile(req, res, LIB, seg.slice(1).join('/'));
		}
		if (req.method === 'GET' && seg[0] === 'fonts') return sendFile(req, res, FONTS, seg.slice(1).join('/'));
		if (req.method === 'GET' && seg[0] === 'health')
			return json(res, 200, {ok: true, bundled: !!serveUrl, queue: queue.length, busy, version: VERSION, conc: CONC});
		if (req.method === 'GET' && seg[0] === 'job') {
			const j = jobs.get(seg[1]);
			if (!j) return json(res, 404, {error: 'no such job'});
			const {cancel, ...pub} = j;
			return json(res, 200, pub);
		}
		if (req.method === 'POST' && seg[0] === 'cancel') {
			const j = jobs.get(seg[1]);
			if (j) {
				j.status = 'cancelled';
				try {
					j.cancel && j.cancel();
				} catch {}
			}
			return json(res, 200, {ok: true});
		}
		if (req.method === 'POST' && seg[0] === 'render') {
			const s = await body(req);
			if (!s.project || !outOk(s.out)) return json(res, 400, {error: 'need project + absolute out path'});
			const id = String(s.id || Math.random().toString(36).slice(2));
			jobs.set(id, {status: 'queued', pct: 0, stage: 'queued', out: s.out, created: Date.now()});
			queue.push({id, spec: s});
			pump();
			for (const [k, v] of jobs) if (v.finished && Date.now() - v.finished > 6 * 3600e3) jobs.delete(k);
			return json(res, 200, {id});
		}
		if (req.method === 'POST' && seg[0] === 'still') {
			const s = await body(req);
			if (!s.project || !outOk(s.out)) return json(res, 400, {error: 'need project + absolute out path'});
			const su = await ensureBundle();
			const inputProps = {project: prep(s.project)};
			const comp = await selectComposition({serveUrl: su, id: 'Project', inputProps});
			fs.mkdirSync(path.dirname(s.out), {recursive: true});
			await renderStill({serveUrl: su, composition: comp, inputProps, output: s.out, frame: Math.max(0, Math.min(comp.durationInFrames - 1, +s.frame || 0)), scale: s.scale || 0.5, imageFormat: s.out.endsWith('.png') ? 'png' : 'jpeg'});
			return json(res, 200, {ok: true, out: s.out});
		}
		if (req.method === 'POST' && seg[0] === 'rebundle') {
			await ensureBundle(true);
			return json(res, 200, {ok: true});
		}
		json(res, 404, {error: 'not found'});
	} catch (e) {
		json(res, 500, {error: String((e && e.message) || e).slice(0, 1500)});
	}
});

srv.listen(PORT, '127.0.0.1', () => {
	log('listening on', BASE, 'remotion', VERSION, 'conc', CONC);
	ensureBundle().catch((e) => log('bundle failed', e.message));
});
