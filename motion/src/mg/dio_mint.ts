// @ts-nocheck
/* DIORAMA MINT (Nov 2 2026, user: "the motion videos keep making motions that have nothing to do with what the narrator
   is saying … if there are no motion samples in the assets, it should create new ones customized to the video's words and
   topics, including new characters, new worlds, new objects or new scenes").
   The server (server/motion_mint.py) audits every line against the library and, for anything missing, has the brain DESIGN
   it as plain data, saved to public/mg/library/mint/<kind>/<id>.json and handed to the film as P.mint. Nothing here evaluates
   code: minted things are
     acts    = keyframes in the person rig frame (feet 0,0, up -y, 400 tall, facing +x) → interpolated like a built-in act
     items   = shape lists held at a hand (centre 0,0, ~±40)        hats  = shape lists in head coords (centre 0,0, r ~40)
     pieces  = shape lists beside the actor (x 100..360, floor y 0) species = a built-in animal + overrides
     worlds  = a built-in world + overrides                          props = scenery shape lists (box 100 = one lot unit)
   Shapes: {s: rect|circle|ellipse|poly|line|curve|arc|text, …coords, fill, stroke, lw, a (alpha), anim {k: spin|bob|sway|pulse|
   flicker|blink|flow, sp, amp, px, py}}. Colours: an LC palette key, a hex, or [top, bottom] for a vertical gradient. */
import {LC} from './dio_lib';
const PI = Math.PI;
const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x), frac = (x) => x - Math.floor(x), lerp = (a, b, u) => a + (b - a) * u;
const ss = (u) => {u = clamp(u); return u * u * (3 - 2 * u);};
const XC = {red: '#8A3A24', leaf: '#3E4A30', leaf2: '#5B6B3E', wood: '#5A4024', wood2: '#7A5226', stone: '#5A5650', stone2: '#7A746A', sand: '#B8986A', sky: '#3A5A7A',
	water: '#2E5A6E', blue: '#3A6A9A', green: '#4E7A3E', purple: '#5A3A6A', pink: '#C98F9A', black: '#0B0B0D', glass: 'rgba(120,140,160,.35)', fire: '#FF8A3A', light: 'rgba(255,243,220,.85)'};
const col = (v) => (typeof v === 'string' ? LC[v] || XC[v] || (/^#[0-9a-fA-F]{3,8}$/.test(v) || /^rgba?\([\d.,\s]+\)$/.test(v) ? v : null) : null);
function paint(c, v, y0, y1) {if (Array.isArray(v)) {const a = col(v[0]), b = col(v[1]); if (!a || !b) return a || b; const g = c.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, a); g.addColorStop(1, b); return g;} return col(v);}
const box = (s) => {const n = (k) => +s[k] || 0;
	if (s.s === 'rect') return [n('y'), n('y') + n('h')]; if (s.s === 'circle' || s.s === 'arc') return [n('y') - n('r'), n('y') + n('r')]; if (s.s === 'ellipse') return [n('y') - n('ry'), n('y') + n('ry')];
	if (s.s === 'text') return [n('y') - (+s.size || 20), n('y')]; const ys = (s.p || []).map((q) => +q[1] || 0); return ys.length ? [Math.min(...ys), Math.max(...ys)] : [0, 1];};

/* [x0, y0, x1, y1] around a shape list (a preview frames the whole object with it) */
export function extent(shapes) {let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
	for (const s of shapes || []) {if (!s || !s.s) continue; const n = (k) => +s[k] || 0, [a, b] = box(s); let xa, xb;
		if (s.s === 'rect') {xa = n('x'); xb = n('x') + n('w');} else if (s.s === 'circle' || s.s === 'arc') {xa = n('x') - n('r'); xb = n('x') + n('r');} else if (s.s === 'ellipse') {xa = n('x') - n('rx'); xb = n('x') + n('rx');}
		else if (s.s === 'text') {xa = n('x'); xb = n('x') + (+s.size || 20) * String(s.text || '').length * .6;} else {const xs = (s.p || []).map((q) => +q[0] || 0); xa = xs.length ? Math.min(...xs) : 0; xb = xs.length ? Math.max(...xs) : 0;}
		x0 = Math.min(x0, xa, xb); x1 = Math.max(x1, xa, xb); y0 = Math.min(y0, a, b); y1 = Math.max(y1, a, b);}
	return x1 > x0 ? [x0, y0, x1, y1] : [-50, -50, 50, 50];}

/* one shape list, drawn at the current transform (unit = 1 rig unit). t = seconds; ph = a per-instance phase */
export function drawShapes(c, shapes, t, ph = 0) {if (!Array.isArray(shapes)) return;
	for (const s of shapes) {if (!s || !s.s) continue; c.save();
		const A = s.anim, px = +(A && A.px) || 0, py = +(A && A.py) || 0;
		if (A && A.k) {const sp = +A.sp || 1, amp = A.amp == null ? 1 : +A.amp, w = t * sp + ph; c.translate(px, py);
			if (A.k === 'spin') c.rotate(w * 2 * PI * .25);
			else if (A.k === 'sway') c.rotate(Math.sin(w * 2) * .15 * amp);
			else if (A.k === 'bob') c.translate(0, Math.sin(w * 3) * 6 * amp);
			else if (A.k === 'pulse') {const k = 1 + Math.sin(w * 4) * .08 * amp; c.scale(k, k);}
			else if (A.k === 'flicker') c.globalAlpha *= .65 + .35 * Math.abs(Math.sin(w * 11 + Math.sin(w * 7)));
			else if (A.k === 'blink') c.globalAlpha *= frac(w * .8) < .5 ? 1 : .15;
			else if (A.k === 'flow') c.translate(Math.sin(w * 2.2) * 5 * amp, -frac(w * .6) * 14 * amp);
			c.translate(-px, -py);}
		if (s.a != null) c.globalAlpha *= clamp(+s.a);
		const [y0, y1] = box(s), fill = s.fill != null ? paint(c, s.fill, y0, y1) : null, stroke = s.stroke != null ? paint(c, s.stroke, y0, y1) : null;
		c.lineWidth = clamp(+s.lw || 3, .5, 40); c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath();
		const n = (k) => +s[k] || 0, P = Array.isArray(s.p) ? s.p.filter((q) => Array.isArray(q)) : [];
		switch (s.s) {
			case 'rect': c.roundRect(n('x'), n('y'), n('w'), n('h'), clamp(n('r'), 0, Math.min(Math.abs(n('w')), Math.abs(n('h'))) / 2)); break;
			case 'circle': c.arc(n('x'), n('y'), Math.abs(n('r')), 0, 2 * PI); break;
			case 'ellipse': c.ellipse(n('x'), n('y'), Math.abs(n('rx')), Math.abs(n('ry')), n('rot'), 0, 2 * PI); break;
			case 'arc': c.arc(n('x'), n('y'), Math.abs(n('r')), n('a0'), s.a1 == null ? PI : n('a1')); break;
			case 'poly': case 'line': if (P.length) {c.moveTo(+P[0][0], +P[0][1]); for (const q of P.slice(1)) c.lineTo(+q[0], +q[1]); if (s.s === 'poly') c.closePath();} break;
			case 'curve': if (P.length >= 3) {c.moveTo(+P[0][0], +P[0][1]); for (let i = 1; i + 1 < P.length; i += 2) c.quadraticCurveTo(+P[i][0], +P[i][1], +P[i + 1][0], +P[i + 1][1]); if (s.close) c.closePath();} break;
			case 'text': c.font = `800 ${clamp(+s.size || 20, 6, 120)}px "MG Outfit", sans-serif`; c.textAlign = 'center'; if (fill) {c.fillStyle = fill; c.fillText(String(s.text || '').slice(0, 24), n('x'), n('y'));} c.restore(); continue;
		}
		if (fill && s.s !== 'line') {c.fillStyle = fill; c.fill();}
		if (stroke || s.s === 'line') {c.strokeStyle = stroke || fill || LC.silver; c.stroke();}
		c.restore();}}

/* a minted movement set → the same f(u, ph, t) a built-in act has. keys [{u 0..1, far [x,y], near [x,y], lean, lift, drop, rot, tilt,
   look [x,y], walk}] over `loop` seconds (`once` = play through once and hold the last key) */
const NUM = ['lean', 'lift', 'drop', 'rot', 'tilt', 'walk', 'shrug', 'shift'];
export function mintAct(D) {const keys = (D.keys || []).filter((k) => k && Array.isArray(k.far) && Array.isArray(k.near)).sort((a, b) => (+a.u || 0) - (+b.u || 0));
	if (!keys.length) keys.push({u: 0, far: [-58, -188], near: [58, -188]});
	const loop = clamp(+D.loop || 1.6, .3, 8);
	const f = (u, ph) => {let q = D.once ? clamp(u / loop) : frac((u + (ph || 0) * .37) / loop); if (!D.once && D.pingpong) q = 1 - Math.abs(1 - 2 * q);
		let i = 0; while (i + 1 < keys.length && q >= (+keys[i + 1].u || 0)) i++;
		const a = keys[i], b = keys[Math.min(i + 1, keys.length - 1)] === a && !D.once && !D.pingpong ? {...keys[0], u: 1} : keys[Math.min(i + 1, keys.length - 1)];
		const span = Math.max(1e-3, (+b.u || 0) - (+a.u || 0)), k = b === a ? 0 : ss((q - (+a.u || 0)) / span), L = (x, y) => lerp(+x || 0, +y || 0, k);
		const out = {arms: [[L(a.far[0], b.far[0]), L(a.far[1], b.far[1])], [L(a.near[0], b.near[0]), L(a.near[1], b.near[1])]]};
		for (const n of NUM) if (a[n] != null || b[n] != null) out[n] = L(a[n] ?? b[n], b[n] ?? a[n]);
		if (a.look || b.look) {const la = a.look || b.look, lb = b.look || a.look; out.look = [L(la[0], lb[0]), L(la[1], lb[1])];}
		for (const n of ['legs', 'hold', 'hang', 'two', 'piece', 'ride', 'hat', 'amb', 'speed', 'talk', 'face', 'move']) if (D[n] != null) out[n] = D[n];
		if ((a.legs || b.legs)) out.legs = (k < .5 ? a.legs : b.legs) || out.legs; if (a.face) out.face = {...(out.face || {}), ...a.face};
		return out;};
	return {cat: D.cat || 'minted', desc: D.desc || 'a minted movement', f, minted: true};}

/* a minted creature the built-in rigs can't draw (dinosaurs, dolphins, robots, aliens): shape-drawn PARTS in the rig frame (feet at 0,0,
   up -y, facing +x, an adult person is 400 tall) that move by role: body bobs, legA/legB swing in opposite phase, head nods, jaw opens on
   speak/eat, tail sways, wing flaps, fin sways. swim/fly creatures hover at `alt`. */
export function drawSprite(c, t, D, a, ph, mv) {const run = a === 'run', sp = run ? 13 : 7, w = t * sp + (ph || 0), m = mv || (['walk', 'run', 'follow', 'swim', 'fly'].includes(a) ? 1 : 0);
	const air = D.swim || D.fly, alt = air ? -(+D.alt || 140) + Math.sin(t * 1.6 + ph) * 10 : 0, sleep = a === 'sleep', sit = a === 'sit' || sleep;
	c.save(); c.translate(0, alt + (sit && !air ? 12 : 0)); if (D.swim) c.rotate(Math.sin(t * 2 + ph) * .05 * (m ? 1.6 : 1));
	for (const P of D.parts || []) {const pv = P.pivot || [0, 0], r = P.move; let rot = 0, dy = 0;
		if (r === 'legA' || r === 'legB') {rot = air ? 0 : Math.sin(w + (r === 'legB' ? Math.PI : 0)) * (run ? .55 : .38) * m; if (sit && !air) rot = .9 * (r === 'legA' ? -1 : 1);}
		else if (r === 'head') rot = (a === 'eat' ? .35 + Math.sin(t * 6) * .08 : Math.sin(t * 1.3 + ph) * .05) + (a === 'speak' ? Math.sin(t * 9) * .06 : 0);
		else if (r === 'jaw') rot = (a === 'speak' || a === 'eat') ? Math.abs(Math.sin(t * 8)) * .35 : 0;
		else if (r === 'tail') rot = Math.sin(t * (a === 'wag' ? 14 : 3) + ph) * (a === 'wag' ? .35 : .16);
		else if (r === 'wing') rot = D.fly && (a === 'fly' || m) ? Math.sin(t * 14 + ph) * .7 : Math.sin(t * 2 + ph) * .06;
		else if (r === 'fin') rot = Math.sin(t * 5 + ph) * (m ? .32 : .16);
		if (r !== 'legA' && r !== 'legB') dy = -Math.abs(Math.sin(w)) * 4 * m + Math.sin(t * 2.2 + ph) * 1.5;
		c.save(); c.translate(pv[0], pv[1] + dy); c.rotate(rot); c.translate(-pv[0], -pv[1]); drawShapes(c, P.shapes, t, ph); c.restore();}
	if (sleep) {c.fillStyle = LC.silver2; c.font = '800 26px sans-serif'; c.globalAlpha = .8; c.fillText('z', (+D.len || 120) * .3, -(+D.h || 120) - 10 - (t * 20) % 30); c.globalAlpha = 1;}
	c.restore();}

/* IMAGE SPRITES (Nov 2 2026, user approved: LLM shape art plateaus ~5/10 → minted items/props/animals are Qwen-Image cut-outs).
   spec.sprite = {src: 'mg/library/mint/sprites/<id>.png', w, h (rig units), ax, ay (anchor as 0..1 of the image: item = hand grip,
   prop/animal = ground point)}. Images are loaded by preloadMint() (Remotion holds the frame with delayRender until they're in);
   a sprite that is not loaded draws the spec's shape list instead, so the shape path stays the fallback. */
const IMG = {};
let RES = (u) => u;
export const setSpriteResolver = (f) => {RES = f || ((u) => u);};
const img = (src) => {const k = RES(src); if (!IMG[k] && typeof Image !== 'undefined') {const im = new Image(); im.src = k; IMG[k] = im;} return IMG[k];};
const ok = (S) => {if (!S || !S.src) return null; const im = img(S.src); return im && im.complete && im.naturalWidth ? im : null;};
export function preloadMint(F) {const srcs = []; for (const k of ['items', 'props', 'species']) for (const D of Object.values((F && F[k]) || {})) if (D && D.sprite && D.sprite.src) srcs.push(D.sprite.src);
	return Promise.all(srcs.map((s) => {const im = img(s); return !im || (im.complete && im.naturalWidth) ? null : new Promise((r) => {im.onload = im.onerror = () => r(null);});}));}
export const spriteBox = (S) => [-(+S.ax || .5) * S.w, -(S.ay ?? 1) * S.h, (1 - (+S.ax || .5)) * S.w, (1 - (S.ay ?? 1)) * S.h];
/* the sprite (anchor at 0,0) or, if it can't be drawn, the shape list */
export function drawArt(c, D, t, ph = 0) {const im = ok(D.sprite); if (!im) return drawShapes(c, D.shapes, t, ph); const b = spriteBox(D.sprite);
	c.save(); if (D.sprite.sway) c.rotate(Math.sin(t * 1.3 + ph) * .03 * D.sprite.sway); c.drawImage(im, b[0], b[1], D.sprite.w, D.sprite.h); c.restore();}
/* a sprite creature: whole-body bob + slight sway while moving, gentle breathing idle; swimmers/fliers hover at alt; flip comes from drawAnimal's dir */
function drawSpriteImg(c, t, D, a, ph, mv) {const im = ok(D.sprite); if (!im) return drawSprite(c, t, D, a, ph, mv);
	const m = mv || (['walk', 'run', 'follow', 'swim', 'fly'].includes(a) ? 1 : 0), run = a === 'run', w = t * (run ? 13 : 7) + (ph || 0), air = D.swim || D.fly,
		alt = air ? -(+D.alt || 140) + Math.sin(t * 1.6 + ph) * 10 : 0, b = spriteBox(D.sprite);
	c.save(); c.translate(0, alt - Math.abs(Math.sin(w)) * 7 * m * (air ? 0 : 1)); c.rotate(air ? Math.sin(t * 2 + ph) * (m ? .08 : .04) : Math.sin(w) * .035 * m);
	const br = 1 + Math.sin(t * 2.2 + ph) * .012; c.scale(1, br); if (a === 'eat') c.rotate(.06);
	c.drawImage(im, b[0], b[1], D.sprite.w, D.sprite.h); c.restore();
	if (a === 'sleep') {c.fillStyle = LC.silver2; c.font = '800 26px sans-serif'; c.globalAlpha = .8; c.fillText('z', D.sprite.w * .3, -D.sprite.h - 10 - (t * 20) % 30); c.globalAlpha = 1;}}

export const mintItem = (D) => (c, t) => drawArt(c, D, t);
export const mintHat = (D) => (c) => drawShapes(c, D.shapes, 0);
export const mintPiece = (D) => ({back: (c, t) => drawShapes(c, D.back, t), front: (c, t) => drawShapes(c, D.shapes || D.front, t)});

/* register a film's mint bundle into the engine's tables. regs = {ACTS, ITEMS, HATS, PIECES, SPECIES, WORLDS, prop(id, D)} */
let LAST = null;
export function useMint(F, R) {if (!F || F === LAST) return; LAST = F;
	for (const [id, D] of Object.entries(F.items || {})) if (!R.ITEMS[id] || R.ITEMS[id].minted) {R.ITEMS[id] = Object.assign(mintItem(D), {minted: true, bb: D.sprite ? spriteBox(D.sprite) : extent(D.shapes)});}
	for (const [id, D] of Object.entries(F.hats || {})) if (!R.HATS[id] || R.HATS[id].minted) R.HATS[id] = Object.assign(mintHat(D), {minted: true});
	for (const [id, D] of Object.entries(F.pieces || {})) if (!R.PIECES[id] || R.PIECES[id].minted) R.PIECES[id] = {...mintPiece(D), minted: true};
	for (const [id, D] of Object.entries(F.acts || {})) if (!R.ACTS[id] || R.ACTS[id].minted) R.ACTS[id] = mintAct(D);
	for (const [id, D] of Object.entries(F.species || {})) if (!R.SPECIES[id] || R.SPECIES[id].minted) {
		if (D.sprite || (Array.isArray(D.parts) && D.parts.length)) {R.SPECIES[id] = {type: 'sprite', name: D.name || id, tags: D.tags || id, h: +D.h || 120, len: +D.len || 160, size: +D.h || 120, ground: !(D.swim || D.fly), swim: !!D.swim, minted: true, draw: (c, t, a, ph, mv) => D.sprite ? drawSpriteImg(c, t, D, a, ph, mv) : drawSprite(c, t, D, a, ph, mv)}; continue;}
		const base = R.SPECIES[D.base] || R.SPECIES.dog; R.SPECIES[id] = {...base, ...(D.o || {}), name: D.name || id, tags: D.tags || id, minted: true};}
	for (const [id, D] of Object.entries(F.props || {})) R.prop(id, D);
	for (const [id, D] of Object.entries(F.worlds || {})) if (!R.WORLDS[id] || R.WORLDS[id].minted) {const base = R.WORLDS[D.base] || R.WORLDS.city; R.WORLDS[id] = {...base, ...(D.o || {}), name: D.name || id, about: D.about || base.about, minted: true};}}
