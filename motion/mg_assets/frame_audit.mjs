// Framing audit for story shots: action × shot on one set → stills in out/frame_audit. Usage: node mg_assets/frame_audit.mjs [style] [set] [aspect]
import fs from 'node:fs';
import path from 'node:path';
const st = process.argv[2] || 'dusk', set = process.argv[3] || 'cafe', asp = process.argv[4] || '16:9';
const [w, h] = {'16:9': [1920, 1080], '9:16': [1080, 1920]}[asp];
const OUT = path.resolve('out/frame_audit');
fs.mkdirSync(OUT, {recursive: true});
const words = 'Why is the fridge screaming at me right now'.split(' ').map((x, i) => ({w: x, s: 0.2 + i * 0.3, e: 0.45 + i * 0.3}));
const CASES = [['chat', 'medium'], ['chat', 'close'], ['talk', 'close'], ['react', 'xclose'], ['point', 'close'], ['think', 'xclose'], ['sad', 'close'], ['handshake', 'close']];
for (const [action, shot] of CASES) {
	const project = {w, h, fps: 30, style: st, tracks: [{kind: 'scene', clips: [{id: 'b', type: 'mg-action', start: 0, dur: 5, props: {style: st, n: 3, words, action, shot, set, mood: 'surprised', at: 0}}]}]};
	const out = path.join(OUT, `${st}_${set}_${action}_${shot}_${asp.replace(':', 'x')}.jpg`);
	const j = await (await fetch('http://127.0.0.1:5420/still', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({project, frame: 75, out, scale: 0.35})})).json();
	console.log(action, shot, j.ok ? 'ok' : JSON.stringify(j).slice(0, 160));
}
