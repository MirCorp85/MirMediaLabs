// @ts-nocheck
/* DIORAMA — the engine behind the "Diorama" Motion Studio format (user's pick, Oct 28 2026).
   Micro World's isometric city + an acting professional character, Diorama palette only (charcoal · brushed steel · gold).
   Pure function of time: drawDiorama(ctx, W, H, t, P) where P = {beats, words}. Every beat says WHERE the character is
   (station), what they DO (pose), how they FEEL (mood), how the camera frames it, plus an optional gold info panel, a sound
   word and an effect. The engine derives the walks between stations, the camera glides, poses, rings and captions.
*/
const PI = Math.PI, CO = .866;
const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x), lerp = (a, b, u) => a + (b - a) * u, frac = (x) => x - Math.floor(x);
const hash = (n) => frac(Math.sin(n * 127.1 + 311.7) * 43758.5453), rg = (t, a, d) => clamp((t - a) / d);
const ss = (u) => {u = clamp(u); return u * u * (3 - 2 * u);};
const E = {io: (u) => (u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2), o: (u) => 1 - Math.pow(1 - u, 3),
	back: (u) => {const c = 1.70158; return 1 + (c + 1) * Math.pow(u - 1, 3) + c * Math.pow(u - 1, 2);}};
const C = {char0: '#0B0B0D', char1: '#131418', graph: '#1E2026', graph2: '#2A2D34', steel: '#4A4F58', steel2: '#6B717C', silver: '#A7ADB6', silver2: '#D8DCE2',
	bronze: '#7A5226', brass: '#B8862E', gold: '#FFB547', champ: '#F2D49B', pale: '#FFF3DC', white: '#F2F6FA', ember: '#E0703A', olive: '#4B5340', olive2: '#6A7458', red: '#8A3A24', char: '#16171B'};
const FX = '"MG Outfit"', HUD = '"Mir Orbit"';
import {VFX, VFX_NAMES, drawVfx, vfxShake} from './dio_vfx';
import {ACTS, ACT_NAMES, actSpec, drawItem, ITEMS, HATS, HAT_NAMES, PIECES, RIDES, drawAnimal, SPECIES, ambient} from './dio_lib';
import {useMint, drawShapes, drawArt, preloadMint, setSpriteResolver} from './dio_mint';
let K = 40, CX = 0, CY = 0;
const S = (x, y, z = 0) => [(x - y) * CO * K - CX, (x + y) * .5 * K - z * K - CY];
function poly(c, pts, fill, edge) {c.beginPath(); pts.forEach((p, i) => {const q = S(p[0], p[1], p[2]); i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]);}); c.closePath(); c.fillStyle = fill; c.fill();
	if (edge) {c.strokeStyle = edge; c.lineWidth = Math.max(1, K * .012); c.stroke();}}
function metal(c, p0, p1, a, b) {const g = c.createLinearGradient(p0[0], p0[1], p1[0], p1[1]); g.addColorStop(0, a); g.addColorStop(.55, b); g.addColorStop(1, a); return g;}
const box3 = (c, x0, y0, x1, y1, z0, z1, top, fl, fr) => {poly(c, [[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]], fl); poly(c, [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]], fr);
	poly(c, [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], top);};

/* ── the city ── */
const LOTS = [], TAKEN = ['2,2', '4,2', '2,4', '4,4', '3,3', '1,1'];
const BUILTIN_LOT = {apartment: '2,2', office: '4,2', lab: '2,4', cafe: '4,4', street: '3,3', rooftop: '1,1'};
let USED_BUILTIN = null;          // null = all six (the city); else the built-in places this film actually uses
const builtinOn = (id) => !USED_BUILTIN || USED_BUILTIN.has(id);
function buildLots(extra) {LOTS.length = 0; const taken = [...(USED_BUILTIN ? [...USED_BUILTIN].map((k) => BUILTIN_LOT[k]) : TAKEN), ...(extra || [])];                // kit places take their lots
	for (let i = 0; i < 6; i++) for (let j = 0; j < 6; j++) {if (taken.includes(i + ',' + j)) continue; const x = i * 4, y = j * 4;
		LOTS.push({x, y, w: 3, d: 3, h: 1.4 + hash(i * 13 + j * 7) * 6, plaza: false, tree: hash(i * 3 + j * 11) > .86, seed: i * 31 + j * 17});}}
const WIN = [C.gold, C.champ, C.brass, C.pale];
function building(c, b, t, lit) {const {x, y, w, d, h} = b;
	poly(c, [[x, y + d, 0], [x + w, y + d, 0], [x + w, y + d, h], [x, y + d, h]], metal(c, S(x, y + d, 0), S(x + w, y + d, 0), C.graph, C.graph2));
	poly(c, [[x + w, y, 0], [x + w, y + d, 0], [x + w, y + d, h], [x + w, y, h]], metal(c, S(x + w, y, 0), S(x + w, y + d, 0), C.char1, C.graph));
	poly(c, [[x, y, h], [x + w, y, h], [x + w, y + d, h], [x, y + d, h]], metal(c, S(x, y, h), S(x + w, y + d, h), C.steel, C.steel2), 'rgba(255,181,71,.35)');
	for (let z = .45; z < h - .3; z += .62) for (let s = .35; s < w - .2; s += .62) {const hv = hash(b.seed + z * 7 + s * 3), on = hv < lit + .12 * Math.sin(t * 1.7 + b.seed + z);
		poly(c, [[x + s, y + d, z], [x + s + .28, y + d, z], [x + s + .28, y + d, z + .32], [x + s, y + d, z + .32]], on ? WIN[Math.floor(hv * 40) % 4] : 'rgba(167,173,182,.07)');
		const h2 = hash(b.seed + z * 5 + s * 9), on2 = h2 < lit; poly(c, [[x + w, y + s, z], [x + w, y + s + .28, z], [x + w, y + s + .28, z + .32], [x + w, y + s, z + .32]], on2 ? (h2 < lit * .5 ? C.brass : C.bronze) : 'rgba(167,173,182,.05)');}}
function tree(c, x, y) {const p = S(x, y, 0), q = S(x, y, 1.1); c.fillStyle = C.char1; c.fillRect(p[0] - .05 * K, q[1], .1 * K, p[1] - q[1]);
	const g = c.createRadialGradient(q[0] - .15 * K, q[1] - .15 * K, .05 * K, q[0], q[1], .45 * K); g.addColorStop(0, C.champ); g.addColorStop(.35, C.brass); g.addColorStop(1, C.bronze);
	c.fillStyle = g; c.beginPath(); c.arc(q[0], q[1], .42 * K, 0, 7); c.fill();}
function plaza(c, b) {const {x, y, w, d} = b; poly(c, [[x, y, 0], [x + w, y, 0], [x + w, y + d, 0], [x, y + d, 0]], metal(c, S(x, y, 0), S(x + w, y + d, 0), C.graph, C.graph2));
	c.strokeStyle = 'rgba(255,181,71,.45)'; c.lineWidth = Math.max(1, K * .012); const a = S(x + .4, y + w / 2, 0), b2 = S(x + w - .4, y + w / 2, 0), e = S(x + w / 2, y + .4, 0), f = S(x + w / 2, y + d - .4, 0);
	c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b2[0], b2[1]); c.moveTo(e[0], e[1]); c.lineTo(f[0], f[1]); c.stroke(); const m = S(x + w / 2, y + d / 2, 0); c.beginPath(); c.ellipse(m[0], m[1], .6 * K, .35 * K, 0, 0, 7); c.stroke();}
function ring(c, x, y, z, r, col, a, w) {const p = S(x, y, z); c.strokeStyle = col; c.globalAlpha = a; c.lineWidth = Math.max(1.5, (w || .04) * K); c.beginPath(); c.ellipse(p[0], p[1], 1.2247 * r * K, .7071 * r * K, 0, 0, 7); c.stroke(); c.globalAlpha = 1;}
function goldText(c, txt, x, y, size, t0, t, rot, hold) {const a = rg(t, t0, .18); if (a <= 0) return; const out = hold || .8; const s = E.back(a) * (1 - .12 * rg(t, t0 + out - .1, .4));
	c.save(); c.translate(x, y); c.rotate(rot || -.07); c.scale(s, s); c.globalAlpha = 1 - rg(t, t0 + out, .35); c.font = `800 ${size}px ${FX}`; c.textAlign = 'center'; c.lineJoin = 'round';
	c.lineWidth = size * .2; c.strokeStyle = C.char0; c.strokeText(txt, 0, 0); const g = c.createLinearGradient(0, -size * .8, 0, size * .1); g.addColorStop(0, C.pale); g.addColorStop(.45, C.gold); g.addColorStop(1, C.brass);
	c.fillStyle = g; c.fillText(txt, 0, 0); c.restore();}

/* ── the character: an adult professional (graphite blazer, champagne shirt, slim gold tie) ──
   Oct 29: the rig is driven by the shared movement library (dio_lib.ts ACTS): hand targets per frame, legs (walk/run/sit/kneel/
   crouch/jump/pedal/straddle), body drop/lean/lift, held items, rides and set pieces. Arms: two-bone IK whose elbow is chosen
   per frame (outward + down), and pose changes swing the hand AROUND the shoulder (polar blend) instead of through the body. */
const P0 = {skin: '#E2C3A0', skin2: '#C9A27C', blazer: '#2A2D34', blazer2: '#4A4F58', shirt: '#F2D49B', tie: '#FFB547', pants: '#16171B', shoe: '#0B0B0D', hair: '#17181C', lip: '#8A5A3A'};
const NEU = [[-58, -188], [58, -188]];
const POSES = Object.fromEntries(ACT_NAMES.map((k) => [k, actSpec(k, .6, 0, 0).arms || NEU]));          // legacy: still targets for old callers
const MOODS = {neutral: {o: 1, b: 0, f: 0, m: 0}, surprised: {o: 1.25, b: -7, f: 0, m: 1}, stressed: {o: .45, b: 5, f: 1, m: -1}, happy: {o: .9, b: -2, f: 0, m: .4}, calm: {o: .8, b: 0, f: 0, m: .4},
	wonder: {o: 1.1, b: -4, f: 0, m: .6}, focused: {o: .9, b: 3, f: 1, m: 0}, sad: {o: .7, b: 2, f: 0, m: -.4}, scared: {o: 1.3, b: -6, f: 1, m: 1}, angry: {o: .7, b: 6, f: 1, m: -1}};
const SHO = [[-44, -318], [44, -318]];
/* two-bone IK: of the two possible elbows pick the one that points OUT from the body and DOWN (the old fixed bend folded raised
   arms inward through the face) */
function ik(sx, sy, tx, ty, a, b, side) {const dx = tx - sx, dy = ty - sy, d = Math.max(1, Math.min(Math.hypot(dx, dy), a + b - .5)), base = Math.atan2(dy, dx), al = Math.acos(clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1));
	const e1 = [sx + a * Math.cos(base + al), sy + a * Math.sin(base + al)], e2 = [sx + a * Math.cos(base - al), sy + a * Math.sin(base - al)], sc = (p) => side * (p[0] - sx) + .9 * (p[1] - sy);
	return sc(e1) >= sc(e2) ? e1 : e2;}
/* draw an arm; returns the hand {x, y, ang} so held items and hands can be drawn later (on top of a box, over the head …) */
function limb(c, sx, sy, tx, ty, a, b, side, w, col, cuff, hand, short, noHand) {const [ex, ey] = ik(sx, sy, tx, ty, a, b, side); const ang = Math.atan2(ty - ey, tx - ex), hx = ex + b * Math.cos(ang), hy = ey + b * Math.sin(ang);
	c.lineCap = 'round'; c.lineJoin = 'round';
	if (short) {c.strokeStyle = hand; c.lineWidth = w * .82; c.beginPath(); c.moveTo(sx, sy); c.lineTo(ex, ey); c.lineTo(hx - Math.cos(ang) * 10, hy - Math.sin(ang) * 10); c.stroke();
		c.strokeStyle = col; c.lineWidth = w * 1.05; c.beginPath(); c.moveTo(sx, sy); c.lineTo(lerp(sx, ex, .45), lerp(sy, ey, .45)); c.stroke();}
	else {c.strokeStyle = col; c.lineWidth = w; c.beginPath(); c.moveTo(sx, sy); c.lineTo(ex, ey); c.lineTo(hx - Math.cos(ang) * 10, hy - Math.sin(ang) * 10); c.stroke();
		c.strokeStyle = cuff; c.lineWidth = w * .8; c.beginPath(); c.moveTo(hx - Math.cos(ang) * 14, hy - Math.sin(ang) * 14); c.lineTo(hx - Math.cos(ang) * 7, hy - Math.sin(ang) * 7); c.stroke();}
	const H = {x: hx, y: hy, ang, col: hand}; if (!noHand) handDraw(c, H); return H;}
function handDraw(c, H, big) {c.fillStyle = H.col; c.beginPath(); c.ellipse(H.x, H.y, big ? 14 : 10, big ? 16 : 12, H.ang, 0, 7); c.fill();}
/* blend a hand target from pose a to pose b around the shoulder: angle (mirrored per side, 0 = straight out) and reach */
function blendHand(a, b, u, side) {if (u >= 1) return b; if (u <= 0) return a; const [sx, sy] = SHO[side < 0 ? 0 : 1];
	const pa = [Math.atan2(a[1] - sy, (a[0] - sx) * side), Math.hypot(a[0] - sx, a[1] - sy)], pb = [Math.atan2(b[1] - sy, (b[0] - sx) * side), Math.hypot(b[0] - sx, b[1] - sy)];
	const an = lerp(pa[0], pb[0], u), r = lerp(pa[1], pb[1], u); return [sx + Math.cos(an) * r * side, sy + Math.sin(an) * r];}
/* ── LOOKS: every person in the city wears the Diorama palette. look = {gender: man|woman|child, skin, hair, color, outfit, glasses,
   beard, age, hat, species}. The protagonist is the default (graphite blazer, champagne shirt, slim gold tie). ── */
const SKIN = {light: ['#EDD3B5', '#D4B091'], medium: ['#DDB592', '#C29571'], tan: ['#C3906A', '#A5734F'], deep: ['#8C5F40', '#6F4731'], hero: ['#E2C3A0', '#C9A27C']};
const CLOTH = {graphite: ['#2A2D34', '#4A4F58'], steel: ['#4A4F58', '#6B717C'], silver: ['#A7ADB6', '#D8DCE2'], bronze: ['#7A5226', '#9C6B37'],
	champagne: ['#B89A6A', '#F2D49B'], gold: ['#B8862E', '#FFB547'], charcoal: ['#16171B', '#2A2D34'], olive: ['#4B5340', '#6A7458'], teal: ['#2F5A5C', '#3F7D7A'], navy: ['#1B2232', '#2C3650'], ember: ['#A4522A', '#E0703A'], white: ['#C3C8CF', '#F2F6FA']};
const HAIRS = ['short', 'long', 'bun', 'curly', 'bald', 'ponytail', 'side', 'afro', 'braids', 'spiky'];
const OUTFITS = ['blazer', 'suit', 'dress', 'labcoat', 'apron', 'hoodie', 'sweater', 'tshirt', 'jersey', 'scrubs', 'uniform', 'chef', 'overalls', 'coat', 'robe', 'military', 'space', 'gown'];
const OUTFIT_COLOR = {scrubs: 'teal', uniform: 'navy', chef: 'white', overalls: 'navy', military: 'olive', space: 'white', robe: 'charcoal', jersey: 'gold', gown: 'gold'};
const OUTFIT_HAT = {chef: 'chef', space: 'bubble'};
export const LOOK_VOCAB = {gender: ['man', 'woman', 'child'], skin: Object.keys(SKIN).filter((k) => k !== 'hero'), hair: HAIRS, color: Object.keys(CLOTH), outfit: OUTFITS, hat: HAT_NAMES};
function lookOf(L) {L = L || {}; const kid = L.gender === 'child', wom = L.gender === 'woman';
	const outfit = OUTFITS.includes(L.outfit) ? L.outfit : 'blazer', sk = SKIN[L.skin] || SKIN.hero, cl = CLOTH[L.color] || CLOTH[OUTFIT_COLOR[outfit]] || CLOTH.graphite;
	const hair = HAIRS.includes(L.hair) ? L.hair : (wom ? 'long' : 'short'), hc = L.age === 'older' ? '#A7ADB6' : L.hairColor === 'brown' ? '#3A2A1E' : L.hairColor === 'blonde' ? '#C9A45C' : L.hairColor === 'red' ? '#8A3A1E' : '#17181C';
	const white = ['labcoat', 'chef'].includes(outfit);
	return {skin: sk[0], skin2: sk[1], c1: cl[0], c2: cl[1], outfit, hair, hc, wom, kid, glasses: !!L.glasses, beard: !!L.beard && !wom && !kid, hat: HATS[L.hat] ? L.hat : OUTFIT_HAT[outfit] || '',
		shirt: white ? '#D8DCE2' : outfit === 'uniform' ? '#2C3650' : outfit === 'military' ? '#4B5340' : '#F2D49B', tie: (outfit === 'suit' || outfit === 'uniform' || (outfit === 'blazer' && !wom && !L.noTie)) ? (outfit === 'uniform' ? '#16171B' : '#FFB547') : '',
		pants: outfit === 'labcoat' ? '#2A2D34' : outfit === 'scrubs' ? cl[0] : outfit === 'military' ? '#3C4333' : outfit === 'overalls' ? cl[0] : outfit === 'jersey' ? '#16171B' : outfit === 'chef' ? '#2A2D34' : outfit === 'space' ? '#C3C8CF' : '#16171B',
		short: ['tshirt', 'jersey', 'scrubs'].includes(outfit), shorts: outfit === 'jersey', long: ['coat', 'robe', 'labcoat', 'gown'].includes(outfit), num: L.num || '', scale: kid ? .62 : (+L.height || 1), wide: wom ? .92 : kid ? .95 : 1, species: L.species || ''};}
const HERO = lookOf({});
const HERO_LK = new WeakMap();      // the film's own main-character look (P.hero), fitted to its world
const heroLook = (P) => {if (!P || !P.hero || !Object.keys(P.hero).length) return HERO; let L = HERO_LK.get(P); if (!L) {L = lookOf({noTie: false, ...P.hero}); HERO_LK.set(P, L);} return L;};
function person(c, t, x, y, sc, rot, R) {
	const L = R.lk || HERO, asleep = R.lie > .5, A = R.act || {}, moving = R.walk && !A.ride && !A.move, spd = moving ? (A.legs === 'run' ? 13 : 8.5) : (A.speed || 8.5), ph = t * spd + (R.phase || 0);
	const wa = asleep ? 0 : moving ? 1 : (A.walk || 0), legs = asleep ? 'stand' : moving ? (A.legs === 'run' ? 'run' : 'walk') : (A.legs || 'stand');
	const drop = asleep || moving ? 0 : (A.drop || 0), lift = asleep ? 0 : (A.lift || 0), lean = asleep ? 0 : (A.lean || 0) + (moving && A.legs === 'run' ? .14 : 0);
	let arm = R.arms; if (moving && !R.holdArms && !A.two && !A.hold) {const s = Math.sin(ph) * (legs === 'run' ? 1.5 : 1); arm = [blendHand(NEU[0], [-30, -260], (s * .5 + .5) * .35, -1), blendHand(NEU[1], [30, -260], (-s * .5 + .5) * .35, 1)];}
	if (asleep) arm = [[-30, -175], [30, -175]];
	const mv = R.walk ? 1 : A.ride === 'wheelchair' || A.ride === 'bus' ? 0 : .8;
	c.save(); c.translate(x + R.shake * sc + (A.shake || 0) * sc + (R.walk ? 0 : (A.shift || 0) * sc * L.scale * (asleep ? 1 : R.dir || 1)), y); c.rotate(rot || 0); c.scale(sc * L.scale * (asleep ? 1 : R.dir), sc * L.scale);
	if (!asleep && !A.ride && !A.rot) {c.fillStyle = 'rgba(0,0,0,.38)'; c.beginPath(); c.ellipse(0, 4, 62, 13, 0, 0, 7); c.fill();}
	if (!asleep && A.piece && PIECES[A.piece]) PIECES[A.piece].back(c, t, A);
	if (!asleep && A.ride && RIDES[A.ride]) RIDES[A.ride].back(c, t, mv, R);
	c.save(); if (A.rot && !asleep) {const k = Math.abs(Math.sin(A.rot)); c.translate(A.ride ? 0 : (A.rot > 0 ? -210 : 0) * k, -52 * k); c.rotate(A.rot);}
	c.save(); c.translate(0, -lift);
	c.scale(L.wide / Math.sqrt(R.sq), R.sq); c.translate(0, wa && legs !== 'pedal' ? -Math.abs(Math.sin(ph)) * (legs === 'run' ? 10 : 6) : 0);
	const SY = -330 - R.shrug - (A.shrug || 0), dress = L.outfit === 'dress' || L.outfit === 'gown', coat = L.outfit === 'labcoat', longc = L.long && !coat, hipY = -182 + drop;
	// legs (in the body frame BEFORE the drop: the hips come down to sit / kneel / crouch)
	if (legs !== 'hidden') [[-17, 1], [17, -1]].forEach(([hx, s], li) => {const near = li === 1;
		let K1, F; const swing = Math.sin(ph) * .42 * wa * s * (legs === 'run' ? 1.6 : 1);
		if (legs === 'sit') {K1 = [hx + 72, hipY + 4]; F = [hx + 76, -10];}
		else if (legs === 'kneel') {K1 = near ? [hx + 56, -72] : [hx + 8, -14]; F = near ? [hx + 60, -10] : [hx - 70, -14];}
		else if (legs === 'crouch') {K1 = [hx + 54 + li * 8, (hipY - 10) / 2 - 18]; F = [hx + 10 + li * 6, -10];}
		else if (legs === 'jump') {K1 = [hx + 48, hipY + 48]; F = [hx + 6, hipY + 104];}
		else if (legs === 'pedal') {const a2 = t * 7 * Math.max(mv, .6) + (near ? PI : 0); F = [20 + Math.cos(a2) * 40, -96 + Math.sin(a2) * 40]; K1 = ik(hx, hipY, F[0], F[1], 96, 96, 1);}
		else if (legs === 'straddle') {K1 = [hx + 46 + (near ? 6 : 0), hipY + 70]; F = [hx + 34, hipY + 150];}
		else if (legs === 'kick' && near) {const q = A.kick ?? 0, k = q < .22 ? -ss(q / .22) : q < .32 ? -1 + 2.4 * ss((q - .22) / .1) : 1.4 - 1.4 * ss((q - .32) / .3); K1 = [hx + Math.sin(k * .9) * 60 + 8, -100 + Math.abs(k) * -20]; F = [hx + Math.sin(k * 1.2) * 150, -10 - Math.max(0, k) * 60];}
		else if (legs === 'step') {const up = Math.max(0, Math.sin(ph + (near ? PI : 0))) * wa; K1 = [hx + 6 + up * 40, -92 - up * 50]; F = [hx + up * 18, -10 - up * 34];}
		else {const a2 = swing; F = [hx + Math.sin(a2) * 96, -10]; K1 = null; c.strokeStyle = dress || longc ? L.skin2 : L.pants; c.lineWidth = dress ? 16 : 27; c.lineCap = 'round'; c.beginPath(); c.moveTo(hx, -182); c.quadraticCurveTo(hx + Math.sin(a2) * 44 + 6, -92 + Math.abs(Math.sin(a2)) * 6, F[0], F[1]); c.stroke();
			if (L.shorts) {c.strokeStyle = L.pants; c.lineWidth = 30; c.beginPath(); c.moveTo(hx, -182); c.lineTo(hx + Math.sin(a2) * 20, -128); c.stroke(); c.strokeStyle = L.skin2; c.lineWidth = 20; c.beginPath(); c.moveTo(hx + Math.sin(a2) * 22, -124); c.quadraticCurveTo(hx + Math.sin(a2) * 44 + 6, -92, F[0], F[1]); c.stroke();}}
		if (K1) {c.strokeStyle = dress || longc ? L.skin2 : L.pants; c.lineWidth = dress ? 16 : 27; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(hx, hipY); c.lineTo(K1[0], K1[1]); c.lineTo(F[0], F[1]); c.stroke();}
		c.fillStyle = '#0B0B0D'; c.beginPath(); c.ellipse(F[0] + 12, F[1] + 4, dress ? 18 : 24, 9, 0, 0, 7); c.fill();});
	// the upper body: lowered for sitting / kneeling and leaned about the hips
	c.save(); c.translate(0, drop); c.translate(0, -182); c.rotate(lean); c.translate(0, 182);
	if (L.hair === 'long' || L.hair === 'braids') {c.fillStyle = L.hc; c.beginPath(); c.roundRect(-40, SY - 100, 80, L.hair === 'braids' ? 150 : 132, 30); c.fill();}
	const sleeve = L.outfit === 'hoodie' || L.outfit === 'sweater' ? L.c1 : coat ? '#C3C8CF' : shade(L.c1), gl = A.hat === 'gloves';
	const hands = [];
	hands[0] = limb(c, SHO[0][0], SY + 12, arm[0][0], arm[0][1], 82, 76, -1, 21, sleeve, L.shirt, gl ? C.gold : L.skin2, L.short, true);
	const atHead = (h) => h.y < SY - 22 && Math.abs(h.x) < 64, held = A.hold || [null, null], hA = (i) => (A.hang != null ? (+A.hang - lean) / .35 : hands[i].ang), h2 = A.hang != null ? (+A.hang - lean) / .35 : 0;
	if (!atHead(hands[0])) {if (held[0]) drawItem(c, held[0], hands[0].x, hands[0].y, hA(0), t); handDraw(c, hands[0], gl);}
	const bg = c.createLinearGradient(-56, 0, 56, 0); bg.addColorStop(0, coat ? '#D8DCE2' : L.c1); bg.addColorStop(.7, coat ? '#D8DCE2' : L.c1); bg.addColorStop(1, coat ? '#F2F6FA' : L.c2); c.fillStyle = bg;
	const hem = coat || longc ? (L.outfit === 'robe' || L.outfit === 'gown' ? -24 : -95) : dress ? -92 : -172, wideHem = dress || coat || longc;
	c.beginPath(); c.moveTo(-50, SY + 4); c.quadraticCurveTo(-58, SY + 6, -56, SY + 30); c.lineTo(dress ? -40 : -44, -190); c.lineTo(wideHem ? -60 : -44, hem); c.lineTo(wideHem ? 60 : 44, hem); c.lineTo(dress ? 40 : 44, -190);
	c.lineTo(56, SY + 30); c.quadraticCurveTo(58, SY + 6, 50, SY + 4); c.closePath(); c.fill();
	const O = L.outfit;
	if (O === 'blazer' || O === 'suit' || coat || O === 'uniform' || O === 'coat') {c.fillStyle = L.shirt; c.beginPath(); c.moveTo(-17, SY + 2); c.lineTo(17, SY + 2); c.lineTo(0, SY + 78); c.closePath(); c.fill();
		if (L.tie) {c.fillStyle = L.tie; c.beginPath(); c.moveTo(-4, SY + 8); c.lineTo(4, SY + 8); c.lineTo(7, SY + 62); c.lineTo(0, SY + 80); c.lineTo(-7, SY + 62); c.closePath(); c.fill();}
		c.strokeStyle = coat ? '#A7ADB6' : '#17191E'; c.lineWidth = 5; c.beginPath(); c.moveTo(-18, SY + 2); c.lineTo(-6, SY + 86); c.moveTo(18, SY + 2); c.lineTo(6, SY + 86); c.stroke();
		if (!coat) {c.fillStyle = C.gold; c.beginPath(); c.arc(0, SY + 104, 3.6, 0, 7); c.fill();}}
	if (O === 'uniform') {c.fillStyle = C.gold; c.beginPath(); c.moveTo(-34, SY + 40); c.lineTo(-24, SY + 34); c.lineTo(-16, SY + 42); c.lineTo(-20, SY + 56); c.lineTo(-30, SY + 56); c.closePath(); c.fill(); c.fillStyle = C.char0; c.fillRect(-46, -196, 92, 12); c.fillStyle = C.brass; c.fillRect(-6, -196, 12, 12);}
	if (O === 'coat') {c.fillStyle = shade(L.c1); c.fillRect(-56, -196, 112, 10);}
	if (O === 'military') {c.fillStyle = shade(L.c1); [[-34, SY + 40], [10, SY + 40]].forEach(([px, py]) => c.fillRect(px, py, 24, 20)); c.fillStyle = '#2B2F24'; c.fillRect(-46, -196, 92, 12);}
	if (O === 'chef') {c.fillStyle = C.steel2; [0, 1, 2].forEach((i) => {c.beginPath(); c.arc(-10, SY + 30 + i * 30, 3.5, 0, 7); c.arc(14, SY + 30 + i * 30, 3.5, 0, 7); c.fill();}); c.fillStyle = C.char1; c.fillRect(-30, SY - 2, 60, 10);}
	if (O === 'overalls') {c.fillStyle = L.shirt; c.fillRect(-48, SY + 4, 96, 40); c.fillStyle = L.c1; c.fillRect(-32, SY + 36, 64, 120); c.strokeStyle = L.c1; c.lineWidth = 9; c.beginPath(); c.moveTo(-26, SY + 40); c.lineTo(-30, SY + 6); c.moveTo(26, SY + 40); c.lineTo(30, SY + 6); c.stroke(); c.fillStyle = C.gold; [-24, 24].forEach((bx) => {c.beginPath(); c.arc(bx, SY + 44, 4, 0, 7); c.fill();});}
	if (O === 'jersey' || O === 'tshirt') {c.strokeStyle = L.c2; c.lineWidth = 6; c.beginPath(); c.arc(0, SY - 2, 17, .25, PI - .25); c.stroke(); if (O === 'jersey') {c.fillStyle = C.char0; c.font = '900 52px "MG Outfit", sans-serif'; c.textAlign = 'center'; c.fillText(String(L.num || '10').slice(0, 2), 2, SY + 92); c.textAlign = 'left';}}
	if (O === 'scrubs') {c.fillStyle = L.c2; c.beginPath(); c.moveTo(-16, SY + 2); c.lineTo(16, SY + 2); c.lineTo(0, SY + 34); c.closePath(); c.fill(); c.fillStyle = shade(L.c1); c.fillRect(14, SY + 40, 22, 18);}
	if (O === 'space') {c.fillStyle = C.gold; c.fillRect(-20, SY + 30, 40, 28); c.fillStyle = C.char1; c.fillRect(-46, -200, 92, 14); [-14, 0, 14].forEach((bx, i) => {c.fillStyle = [C.ember, C.gold, C.steel2][i]; c.beginPath(); c.arc(bx, SY + 44, 4, 0, 7); c.fill();});}
	if (O === 'robe') {c.strokeStyle = C.gold; c.lineWidth = 4; c.beginPath(); c.moveTo(-14, SY + 2); c.lineTo(-10, -30); c.moveTo(14, SY + 2); c.lineTo(10, -30); c.stroke();}
	if (O === 'apron') {c.fillStyle = C.bronze; c.beginPath(); c.roundRect(-36, SY + 40, 72, 150, 10); c.fill(); c.strokeStyle = C.brass; c.lineWidth = 3; c.beginPath(); c.moveTo(-36, SY + 80); c.lineTo(36, SY + 80); c.stroke();}
	if (O === 'hoodie') {c.fillStyle = shade(L.c1); c.beginPath(); c.ellipse(0, SY + 4, 34, 16, 0, 0, 7); c.fill(); c.strokeStyle = C.gold; c.lineWidth = 3; c.beginPath(); c.moveTo(-8, SY + 8); c.lineTo(-10, SY + 50); c.moveTo(8, SY + 8); c.lineTo(10, SY + 50); c.stroke();}
	if (O === 'sweater') {c.strokeStyle = L.c2; c.lineWidth = 6; c.beginPath(); c.arc(0, SY - 2, 18, .2, PI - .2); c.stroke();}
	if (dress) {c.strokeStyle = 'rgba(255,181,71,.6)'; c.lineWidth = 3; c.beginPath(); c.moveTo(-42, -190); c.lineTo(42, -190); c.stroke();}
	if (R.heart > 0 && !asleep) {const s = 1 + R.heart * .4 + .12; c.save(); c.translate(-12, SY + 48); c.scale(s, s); c.fillStyle = C.pale; c.shadowColor = C.gold; c.shadowBlur = 28; c.beginPath();
		c.moveTo(0, 9); c.bezierCurveTo(-22, -6, -12, -24, 0, -13); c.bezierCurveTo(12, -24, 22, -6, 0, 9); c.fill(); c.restore(); c.shadowBlur = 0;}
	const sleeve2 = coat ? '#EDEFF2' : L.outfit === 'hoodie' || L.outfit === 'sweater' ? L.c2 : L.c2;
	hands[1] = limb(c, SHO[1][0], SY + 12, arm[1][0], arm[1][1], 82, 76, 1, 21, sleeve2, L.shirt, gl ? C.gold : L.skin, L.short, true);
	if (!atHead(hands[1])) {if (held[1]) drawItem(c, held[1], hands[1].x, hands[1].y, hA(1), t); if (held[1] === 'thumb') thumb(c, hands[1], L.skin); handDraw(c, hands[1], gl);}
	if (A.two && !atHead(hands[0])) {drawItem(c, A.two, (hands[0].x + hands[1].x) / 2, (hands[0].y + hands[1].y) / 2, h2, t); handDraw(c, hands[0], gl); handDraw(c, hands[1], gl);}
	if (A.muzzle > 0 && A.two === 'rifle') {const mx = (hands[0].x + hands[1].x) / 2 + 112, my = (hands[0].y + hands[1].y) / 2 - 22; c.fillStyle = `rgba(255,220,150,${A.muzzle})`; c.beginPath(); c.moveTo(mx, my); c.lineTo(mx + 60, my - 18); c.lineTo(mx + 40, my); c.lineTo(mx + 60, my + 18); c.closePath(); c.fill();}
	c.fillStyle = L.skin2; c.fillRect(-10, SY - 26, 20, 30);
	c.save(); c.translate(0, SY - 62); c.rotate(R.tilt + (A.tilt || 0)); if (L.kid) c.scale(1.18, 1.18);
	if (L.hair === 'bun' || L.hair === 'ponytail') {c.fillStyle = L.hc; c.beginPath(); c.arc(L.hair === 'bun' ? -8 : -36, L.hair === 'bun' ? -50 : -20, L.hair === 'bun' ? 20 : 14, 0, 7); c.fill();
		if (L.hair === 'ponytail') {c.beginPath(); c.ellipse(-44, 6, 11, 26, .2, 0, 7); c.fill();}}
	if (L.hair === 'afro') {c.fillStyle = L.hc; c.beginPath(); c.arc(-4, -20, 52, 0, 7); c.fill();}
	const hg = c.createRadialGradient(10, -12, 6, 0, 0, 50); hg.addColorStop(0, lighten(L.skin)); hg.addColorStop(1, L.skin); c.fillStyle = hg; c.beginPath(); c.ellipse(0, 0, L.wom ? 33 : 35, L.wom ? 41 : 43, 0, 0, 7); c.fill();
	c.fillStyle = L.skin2; c.beginPath(); c.ellipse(-30, 2, 6, 10, 0, 0, 7); c.fill();
	c.fillStyle = L.hc;
	if (L.hair === 'curly') {for (let i = 0; i < 9; i++) {const a = PI * (1.02 + i * .11); c.beginPath(); c.arc(Math.cos(a) * 34, -6 + Math.sin(a) * 40, 13, 0, 7); c.fill();}}
	else if (L.hair === 'bald') {c.fillStyle = 'rgba(255,255,255,.18)'; c.beginPath(); c.ellipse(8, -28, 12, 6, -.3, 0, 7); c.fill();}
	else if (L.hair === 'spiky') {for (let i = 0; i < 6; i++) {const a = PI * (1.05 + i * .17); c.beginPath(); c.moveTo(Math.cos(a - .2) * 34, Math.sin(a - .2) * 38); c.lineTo(Math.cos(a) * 54, Math.sin(a) * 56); c.lineTo(Math.cos(a + .2) * 34, Math.sin(a + .2) * 38); c.fill();}}
	else if (L.hair === 'afro') {}
	else if (L.hair === 'long' || L.hair === 'bun' || L.hair === 'ponytail' || L.hair === 'braids') {c.beginPath(); c.moveTo(-37, 10); c.quadraticCurveTo(-44, -44, 0, -47); c.quadraticCurveTo(36, -46, 37, -12); c.quadraticCurveTo(20, -32, 2, -30); c.quadraticCurveTo(-20, -26, -28, 4); c.closePath(); c.fill();}
	else {c.beginPath(); c.moveTo(-36, 6); c.quadraticCurveTo(-42, -40, -6, -46); c.quadraticCurveTo(30, -50, 37, -18); c.quadraticCurveTo(22, -30, 4, -27); c.quadraticCurveTo(-18, -24, -26, -6); c.quadraticCurveTo(-30, 0, -36, 6); c.fill();}
	if (L.beard) {c.fillStyle = L.hc; c.globalAlpha = .85; c.beginPath(); c.moveTo(-28, 8); c.quadraticCurveTo(-24, 44, 12, 46); c.quadraticCurveTo(34, 42, 34, 12); c.quadraticCurveTo(20, 28, 2, 28); c.quadraticCurveTo(-16, 26, -28, 8); c.fill(); c.globalAlpha = 1;}
	const F = {...R.face, ...(A.face || {})}, blink = frac(t / 3.6 + (R.phase || 0) * .13) > .965 ? .1 : 1, open = (asleep ? 0 : F.o ?? 1) * blink, lk = A.look || R.look || [0, 0], eyesShut = asleep || F.eyes === 'closed';
	[[4, 1], [24, -1]].forEach(([ex, side]) => {c.strokeStyle = '#17181C'; c.lineCap = 'round';
		if (F.eyes === 'laugh') {c.lineWidth = 3.4; c.beginPath(); c.arc(ex, -2, 6, PI + .3, -.3); c.stroke();}
		else if (eyesShut || open < .15) {c.lineWidth = 3; c.beginPath(); c.arc(ex, -4, 5, .25, PI - .25); c.stroke();}
		else {c.fillStyle = '#F7F2EA'; c.beginPath(); c.ellipse(ex, -4, 6.5, 4.6 * Math.min(1.4, open) + .6, 0, 0, 7); c.fill(); c.fillStyle = '#17181C'; c.beginPath(); c.arc(ex + lk[0] + 1, -4 + lk[1], 3.4 * Math.min(1, open + .2), 0, 7); c.fill();}
		const br = asleep ? 0 : (F.b || 0); c.lineWidth = 3.2; c.beginPath(); c.moveTo(ex - 7, -15 + br + (F.f && side > 0 ? -2 : 0)); c.lineTo(ex + 7, -15 + br + (F.f ? (side > 0 ? 3 : -2) : 0)); c.stroke();
		if (F.tears) {c.fillStyle = 'rgba(190,215,235,.85)'; for (let i = 0; i < 2; i++) {const q = frac(t * 1.2 + i * .5 + ex * .03); c.beginPath(); c.ellipse(ex + 2, 4 + q * 40, 2.6, 4, 0, 0, 7); c.fill();}}});
	if (L.glasses) {c.strokeStyle = C.brass; c.lineWidth = 2.4; c.beginPath(); c.arc(4, -4, 9, 0, 7); c.moveTo(33, -4); c.arc(24, -4, 9, 0, 7); c.moveTo(13, -4); c.lineTo(15, -4); c.stroke();}
	c.strokeStyle = L.skin2; c.lineWidth = 2.6; c.beginPath(); c.moveTo(31, -6); c.lineTo(35, 8); c.lineTo(30, 10); c.stroke();
	let mo = asleep ? 0 : (F.m || 0); if (R.talk || A.talk) mo = frac(t * 5.5 + (R.phase || 0)) > .5 ? .7 : 0;
	c.strokeStyle = L.wom ? '#9A5A4A' : '#8A5A3A'; c.fillStyle = c.strokeStyle; c.lineWidth = 3;
	if (F.yawn) {c.fillStyle = '#3A1E18'; c.beginPath(); c.ellipse(18, 24, 8, 12, 0, 0, 7); c.fill();}
	else if (mo >= .9) {c.beginPath(); c.ellipse(18, 22, 4.5, 6, 0, 0, 7); c.fill();} else if (mo <= -.9) {c.fillStyle = '#F7F2EA'; c.fillRect(10, 19, 16, 6); c.strokeRect(10, 19, 16, 6);}
	else if (mo > .5) {c.beginPath(); c.ellipse(18, 22, 5, 4, 0, 0, 7); c.fill();} else if (mo > .3) {c.beginPath(); c.arc(18, 15, 9, .4, PI - .6); c.stroke();}
	else if (mo < -.3) {c.beginPath(); c.arc(18, 30, 8, PI + .5, -.5); c.stroke();} else {c.beginPath(); c.moveTo(11, 22); c.lineTo(24, 21); c.stroke();}
	const hat = A.hat && HATS[A.hat] ? A.hat : L.hat; if (hat && HATS[hat]) HATS[hat](c);
	c.restore();
	// hands (and what they hold) that are up at the face draw OVER the head: phone at the ear, cup at the mouth, camera at the eye
	[0, 1].forEach((i) => {if (!atHead(hands[i])) return; if (held[i]) drawItem(c, held[i], hands[i].x, hands[i].y, hA(i), t); handDraw(c, hands[i], gl);});
	if (A.two && atHead(hands[0])) {drawItem(c, A.two, (hands[0].x + hands[1].x) / 2, (hands[0].y + hands[1].y) / 2, h2, t); handDraw(c, hands[0], gl); handDraw(c, hands[1], gl);}
	if (A.flash > 0) {const g = c.createRadialGradient(60, SY - 70, 4, 60, SY - 70, 160); g.addColorStop(0, `rgba(255,243,220,${A.flash})`); g.addColorStop(1, 'rgba(255,243,220,0)'); c.fillStyle = g; c.beginPath(); c.arc(60, SY - 70, 160, 0, 7); c.fill();}
	if (A.ballFly >= 0 && A.ballFly != null) {const q = A.ballFly; c.save(); c.translate(130 + q * 520, -360 - Math.sin(q * PI) * 160 + q * 200); ITEMS.ball(c, t); c.restore();}
	if (A.ball === 'feet') {const q = Math.abs(Math.sin(ph * .5)); c.save(); c.translate(70 + q * 30, -18 - q * 8 - drop); ITEMS.ball(c, t); c.restore();}
	c.restore(); c.restore(); c.restore();
	if (!asleep && A.ride && RIDES[A.ride]) RIDES[A.ride].front(c, t, mv, R);
	if (!asleep && A.piece && PIECES[A.piece]) PIECES[A.piece].front(c, t, A);
	c.restore();}
function thumb(c, H, skin) {c.fillStyle = skin; c.beginPath(); c.roundRect(H.x - 4, H.y - 30, 9, 22, 4); c.fill();}
function shade(hex) {const n = parseInt(hex.slice(1), 16), f = .82; return '#' + [16, 8, 0].map((s) => Math.round(((n >> s) & 255) * f).toString(16).padStart(2, '0')).join('');}
function lighten(hex) {const n = parseInt(hex.slice(1), 16); return '#' + [16, 8, 0].map((s) => Math.min(255, Math.round(((n >> s) & 255) * 1.08 + 8)).toString(16).padStart(2, '0')).join('');}

/* ── the apartment: stations the story can use ── */
const RX = 8, RY = 8, RW = 4, RD = 4, RH = 2.6;
export const STATIONS = {bed: {pos: [10.8, 10.55], dir: 1, prop: [9.3, 11, .7]}, desk: {pos: [9.05, 9.55], dir: -1, prop: [8.7, 8.55, 1.1]}, fridge: {pos: [10.95, 9.45], dir: 1, prop: [11.2, 8.6, 1.2]},
	clock: {pos: [9.75, 9.2], dir: 1, prop: [9.7, 8, 1.85]}, center: {pos: [11.1, 10.3], dir: 1, prop: null}, window: {pos: [8.6, 9.95], dir: -1, prop: [8, 10.05, 1.5]}};
export const CAMERAS = ['close', 'medium', 'wide', 'aerial', 'city'];
export const POSE_NAMES = Object.keys(POSES).filter((k) => k !== 'walk');
export const MOOD_NAMES = Object.keys(MOODS);
const BED = {x: RX + .38, y: RY + 2.25, w: 1.95, d: 1.42};
function room(c, t, R, beat, cue) {const x = RX, y = RY, w = RW, d = RD, H = RH;
	poly(c, [[x, y, 0], [x + w, y, 0], [x + w, y + d, 0], [x, y + d, 0]], metal(c, S(x, y, 0), S(x + w, y + d, 0), C.graph2, C.steel));
	c.strokeStyle = 'rgba(216,220,226,.08)'; c.lineWidth = 1; for (let i = 1; i < 8; i++) {const a = S(x + i * w / 8, y, 0), b = S(x + i * w / 8, y + d, 0); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();}
	poly(c, [[x, y, 0], [x + w, y, 0], [x + w, y, H], [x, y, H]], metal(c, S(x, y, H), S(x + w, y, 0), C.graph, C.graph2)); poly(c, [[x, y, 0], [x, y + d, 0], [x, y + d, H], [x, y, H]], metal(c, S(x, y, H), S(x, y + d, 0), C.char1, C.graph));
	poly(c, [[x, y, H], [x + w, y, H], [x + w, y, H + .06], [x, y, H + .06]], C.brass); poly(c, [[x, y, H], [x, y + d, H], [x, y + d, H + .06], [x, y, H + .06]], C.bronze);
	// window + moon (left wall)
	poly(c, [[x, y + 1.1, .95], [x, y + 2.5, .95], [x, y + 2.5, 2.05], [x, y + 1.1, 2.05]], C.brass); poly(c, [[x, y + 1.17, 1.02], [x, y + 2.43, 1.02], [x, y + 2.43, 1.98], [x, y + 1.17, 1.98]], '#08090C');
	const mp = S(x, y + 2.05, 1.72); c.fillStyle = C.pale; c.shadowColor = C.gold; c.shadowBlur = .4 * K; c.beginPath(); c.arc(mp[0], mp[1], .15 * K, 0, 7); c.fill(); c.shadowBlur = 0;
	poly(c, [[x, y + 1.78, 1.02], [x, y + 1.82, 1.02], [x, y + 1.82, 1.98], [x, y + 1.78, 1.98]], C.brass);
	// clock (back wall): ticks every second; an impact on the clock kicks it
	const kick = beat && beat.station === 'clock' && beat.fx === 'impact' ? Math.exp(-frac(Math.max(0, t - cue) / .5) * 9) : beat && beat.station === 'clock' ? Math.exp(-frac(t) * 9) * .5 : 0;
	const cp = S(x + 1.7, y, 1.85); c.save(); c.translate(cp[0], cp[1]); c.scale(1 + kick * .22, 1 + kick * .22);
	c.fillStyle = metal(c, [-.4 * K, 0], [.4 * K, 0], C.bronze, C.champ); c.beginPath(); c.ellipse(0, 0, .44 * K, .52 * K, -.52, 0, 7); c.fill(); c.fillStyle = C.char1; c.beginPath(); c.ellipse(0, 0, .35 * K, .42 * K, -.52, 0, 7); c.fill();
	const tk = Math.floor(t); c.strokeStyle = C.gold; c.lineCap = 'round'; c.lineWidth = .05 * K; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.sin(tk * PI / 30) * .26 * K, -Math.cos(tk * PI / 30) * .3 * K); c.stroke();
	c.lineWidth = .07 * K; c.beginPath(); c.moveTo(0, 0); c.lineTo(.2 * K, .06 * K); c.stroke(); c.restore();
	const parts = [];
	// desk + monitor (back-left corner)
	parts.push({d: 17.6, f: () => {box3(c, x + .12, y + .15, x + 1.3, y + .9, 0, .74, metal(c, S(x, y, .74), S(x + 1.3, y + .9, .74), C.steel, C.silver), C.graph2, C.graph);
		box3(c, x + .3, y + .22, x + 1.1, y + .3, .74, 1.36, C.steel2, C.char1, C.graph);
		const on = beat && beat.station === 'desk'; poly(c, [[x + .34, y + .3, .79], [x + 1.06, y + .3, .79], [x + 1.06, y + .3, 1.32], [x + .34, y + .3, 1.32]], on ? '#2B2210' : '#141518');
		for (let i = 0; i < 5; i++) {const z = 1.24 - i * .09, ww = .25 + hash(i + 3) * .4 * (on ? 1 : .5); poly(c, [[x + .42, y + .3, z], [x + .42 + ww, y + .3, z], [x + .42 + ww, y + .3, z + .03], [x + .42, y + .3, z + .03]], on ? (i % 2 ? C.champ : C.gold) : 'rgba(167,173,182,.25)');}
		box3(c, x + .55, y + 1.05, x + 1.0, y + 1.5, 0, .46, C.graph2, C.char1, C.graph); box3(c, x + .55, y + 1.42, x + 1.0, y + 1.5, .46, 1.0, C.graph2, C.char1, C.graph);}});
	// the bed: headboard behind, frame, mattress, pillow, duvet
	const b = BED;
	const duvet = () => {box3(c, b.x + .78, b.y - .03, b.x + b.w + .04, b.y + b.d + .03, .5, .6, metal(c, S(b.x + .78, b.y, .6), S(b.x + b.w, b.y + b.d, .6), C.brass, C.gold), C.brass, C.bronze);
		poly(c, [[b.x + .78, b.y - .03, .6], [b.x + .95, b.y - .03, .6], [b.x + .95, b.y + b.d + .03, .6], [b.x + .78, b.y + b.d + .03, .6]], C.pale);};
	parts.push({d: b.x + b.y + 1.4, f: () => {
		box3(c, b.x - .1, b.y - .04, b.x, b.y + b.d + .04, 0, 1.05, C.champ, metal(c, S(b.x - .1, b.y + b.d, 0), S(b.x, b.y + b.d, 1), C.bronze, C.brass), metal(c, S(b.x, b.y, 1.05), S(b.x, b.y + b.d, 0), C.bronze, C.brass));
		box3(c, b.x, b.y, b.x + b.w, b.y + b.d, 0, .24, C.graph2, C.graph, C.char1);
		box3(c, b.x + .03, b.y + .03, b.x + b.w - .03, b.y + b.d - .03, .24, .5, metal(c, S(b.x, b.y, .5), S(b.x + b.w, b.y + b.d, .5), C.silver, C.silver2), metal(c, S(b.x, b.y + b.d, .24), S(b.x + b.w, b.y + b.d, .5), C.steel2, C.silver), C.steel);
		box3(c, b.x + .1, b.y + .18, b.x + .56, b.y + b.d - .18, .5, .64, C.pale, C.champ, '#D9BC86');
		if (R.lie <= .05) duvet();}});
	// fridge (shakes with fx shake, spins a gold turbine with fx spin)
	const foc = beat && beat.station === 'fridge', fs = foc && beat.fx === 'shake' ? Math.sin(t * 70) * .03 : 0, f = {x: x + 2.75 + fs, y: y + .2, w: .95, d: .8, h: 2};
	parts.push({d: f.x + f.y + .8, f: () => {
		poly(c, [[f.x, f.y + f.d, 0], [f.x + f.w, f.y + f.d, 0], [f.x + f.w, f.y + f.d, f.h], [f.x, f.y + f.d, f.h]], metal(c, S(f.x, f.y + f.d, f.h), S(f.x + f.w, f.y + f.d, 0), C.steel2, C.silver2));
		poly(c, [[f.x + f.w, f.y, 0], [f.x + f.w, f.y + f.d, 0], [f.x + f.w, f.y + f.d, f.h], [f.x + f.w, f.y, f.h]], metal(c, S(f.x + f.w, f.y, f.h), S(f.x + f.w, f.y + f.d, 0), C.steel, C.silver));
		poly(c, [[f.x, f.y, f.h], [f.x + f.w, f.y, f.h], [f.x + f.w, f.y + f.d, f.h], [f.x, f.y + f.d, f.h]], C.silver2);
		poly(c, [[f.x, f.y + f.d, 1.25], [f.x + f.w, f.y + f.d, 1.25], [f.x + f.w, f.y + f.d, 1.28], [f.x, f.y + f.d, 1.28]], C.steel); poly(c, [[f.x + .75, f.y + f.d, .7], [f.x + .8, f.y + f.d, .7], [f.x + .8, f.y + f.d, 1.1], [f.x + .75, f.y + f.d, 1.1]], C.gold);
		if (foc && beat.fx === 'spin' && t >= cue - .05) {const a = E.back(rg(t, cue - .05, .35)), p = S(f.x + f.w / 2, f.y + f.d, .62); c.save(); c.translate(p[0], p[1]); c.scale(a, a); c.fillStyle = C.char0; c.beginPath(); c.ellipse(0, 0, .36 * K, .42 * K, -.5, 0, 7); c.fill();
			c.fillStyle = C.champ; for (let i = 0; i < 9; i++) {c.save(); c.rotate(t * 24 + i * 2 * PI / 9); c.beginPath(); c.ellipse(0, -.2 * K, .05 * K, .16 * K, .3, 0, 7); c.fill(); c.restore();} c.fillStyle = C.gold; c.beginPath(); c.arc(0, 0, .07 * K, 0, 7); c.fill(); c.restore();}}});
	// the character: on the floor, or lying ALONG the bed under the duvet
	const p = R.pos, sc = 2.1 * K / 400, Fp = S(b.x + b.w - .12, b.y + b.d / 2, .62), Hd = S(b.x + .3, b.y + b.d / 2, .66), fl = S(p[0], p[1], 0);
	const lrot = Math.atan2(Hd[1] - Fp[1], Hd[0] - Fp[0]) + PI / 2, lsc = Math.hypot(Hd[0] - Fp[0], Hd[1] - Fp[1]) / 400 * 1.06, L = R.lie;
	if (R.place === 'apartment') parts.push({d: L > .5 ? b.x + b.y + 1.6 : p[0] + p[1], f: () => {person(c, t, lerp(fl[0], Fp[0], L), lerp(fl[1], Fp[1], L), lerp(sc, lsc, L), lrot * L, R); if (L > .05) {c.globalAlpha = clamp(L * 1.6); duvet(); c.globalAlpha = 1;}}});
	crowd(c, t, parts, 'apartment'); parts.sort((a, b2) => a.d - b2.d).forEach((q) => q.f());}


/* ── PLACES: the apartment + five more, each on its own city lot. Station positions are relative to the place origin. ── */
const PL = {
	apartment: {o: [8, 8], z: 0, door: [11.5, 11.5], st: {bed: [[2.8, 2.55], 1, [1.3, 3, .7]], desk: [[1.05, 1.55], -1, [.7, .55, 1.1]], fridge: [[2.95, 1.45], 1, [3.2, .6, 1.2]],
		clock: [[1.75, 1.2], 1, [1.7, 0, 1.85]], window: [[.6, 1.95], -1, [0, 2.05, 1.5]], center: [[3.1, 2.3], 1, null]}},
	office: {o: [16, 8], z: 0, door: [19.5, 11.5], st: {desk: [[3.1, 1.55], -1, [3.15, .6, 1.1]], screen: [[.95, 2.0], -1, [0, 2, 1.5]], table: [[2.9, 2.6], -1, [1.7, 2.75, .9]],
		coffee: [[1.1, 1.25], -1, [.5, .5, 1.3]], window: [[2.0, 1.05], 1, [2, 0, 1.5]], center: [[2.4, 3.3], 1, null]}},
	lab: {o: [8, 16], z: 0, door: [11.5, 19.5], st: {bench: [[1.5, 1.5], -1, [1.5, .5, 1.2]], microscope: [[3.0, 1.6], -1, [3.35, .6, 1.3]], machine: [[1.45, 2.2], -1, [.55, 2.1, 1.6]],
		screen: [[2.2, 1.3], 1, [2.2, 0, 1.8]], center: [[2.7, 2.9], 1, null]}},
	cafe: {o: [16, 16], z: 0, door: [19.5, 19.5], st: {counter: [[1.6, 1.5], -1, [1.5, .55, 1.4]], table: [[2.3, 2.9], -1, [1.4, 2.4, .9]], window: [[.7, 2.3], -1, [0, 2.2, 1.4]], center: [[3.0, 2.0], 1, null]}},
	street: {o: [12, 12], z: 0, door: [15.5, 15.5], st: {lamp: [[.9, .95], 1, [.85, .45, 2.3]], car: [[2.75, 1.6], 1, [3.5, 1.5, .8]], bench: [[1.1, 2.0], 1, [1.1, 2.5, .6]],
		crossing: [[1.6, 3.5], 1, [1.5, 3.5, .1]], stop: [[2.3, .8], 1, [2.5, .4, 1.9]], center: [[1.8, 1.5], 1, null]}},
	rooftop: {o: [4, 4], z: 7, door: [7.5, 7.5], lift: [6.85, 6.85], st: {edge: [[2.5, 2.55], 1, [3, 3, 7.6]], dish: [[1.55, 1.15], 1, [1.9, .6, 7.8]], tank: [[1.5, 1.65], -1, [.65, .65, 8]], center: [[1.9, 2.0], 1, null]}},
};
export const PLACES = Object.fromEntries(Object.entries(PL).map(([k, v]) => [k, Object.keys(v.st)]));
function spot(place, st) {const P = PL[place] || PL.apartment, s = P.st[st] || P.st.center, o = P.o;
	return {pos: [o[0] + s[0][0], o[1] + s[0][1], P.z], dir: s[1], prop: s[2] ? [o[0] + s[2][0], o[1] + s[2][1], s[2][2]] : null};}
function placeAt(x, y, z) {if (z > .5) return 'rooftop'; for (const [k, v] of Object.entries(PL)) {if (k === 'rooftop') continue; const [ox, oy] = v.o; if (x >= ox - .02 && x <= ox + 4 && y >= oy - .02 && y <= oy + 4) return k;} return '';}
function shell(c, ox, oy, floorA, floorB, flat) {const w = 4, d = 4, H = flat ? .18 : 2.6;   // flattened (in the way of the story): floor + a low curb, no walls
	poly(c, [[ox, oy, 0], [ox + w, oy, 0], [ox + w, oy + d, 0], [ox, oy + d, 0]], metal(c, S(ox, oy, 0), S(ox + w, oy + d, 0), floorA || C.graph2, floorB || C.steel));
	c.strokeStyle = 'rgba(216,220,226,.07)'; c.lineWidth = 1; for (let i = 1; i < 8; i++) {const a = S(ox + i * w / 8, oy, 0), b = S(ox + i * w / 8, oy + d, 0); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();}
	poly(c, [[ox, oy, 0], [ox + w, oy, 0], [ox + w, oy, H], [ox, oy, H]], metal(c, S(ox, oy, H), S(ox + w, oy, 0), C.graph, C.graph2));
	poly(c, [[ox, oy, 0], [ox, oy + d, 0], [ox, oy + d, H], [ox, oy, H]], metal(c, S(ox, oy, H), S(ox, oy + d, 0), C.char1, C.graph));
	poly(c, [[ox, oy, H], [ox + w, oy, H], [ox + w, oy, H + .06], [ox, oy, H + .06]], C.brass); poly(c, [[ox, oy, H], [ox, oy + d, H], [ox, oy + d, H + .06], [ox, oy, H + .06]], C.bronze);}
const wallX = (c, x, y0, y1, z0, z1, fill, edge) => poly(c, [[x, y0, z0], [x, y1, z0], [x, y1, z1], [x, y0, z1]], fill, edge);
const wallY = (c, y, x0, x1, z0, z1, fill, edge) => poly(c, [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]], fill, edge);
function steam(c, x, y, z, t, on) {if (!on) return; for (let i = 0; i < 4; i++) {const q = frac(t * .7 + i / 4), p = S(x, y, z + q * .9); c.globalAlpha = Math.sin(q * PI) * .5; c.fillStyle = C.silver2; c.beginPath(); c.arc(p[0] + Math.sin(t * 3 + i) * .06 * K, p[1], (.06 + q * .12) * K, 0, 7); c.fill();} c.globalAlpha = 1;}
function charPart(c, t, R, parts, z) {if (!R.draw) return; const p = R.pos, sc = 2.1 * K / 400, fl = S(p[0], p[1], z ?? p[2] ?? 0);
	parts.push({d: p[0] + p[1], f: () => person(c, t, fl[0], fl[1], sc, 0, R)});}
function office(c, t, R, B, flat) {const [ox, oy] = PL.office.o, foc = (s) => B && B.place === 'office' && B.station === s;
	shell(c, ox, oy, undefined, undefined, flat); if (flat) return;
	for (let i = 0; i < 3; i++) {const x0 = ox + .45 + i * 1.08; wallY(c, oy, x0, x0 + .92, .72, 2.2, '#0B0E13', 'rgba(184,134,46,.8)');
		for (let j = 0; j < 7; j++) {const xx = x0 + .1 + hash(i * 9 + j) * .7, zz = .85 + hash(i * 5 + j * 3) * 1.1; wallY(c, oy, xx, xx + .06, zz, zz + .08, j % 3 ? C.champ : C.gold);}}
	wallX(c, ox, oy + 1, oy + 3, .9, 2.05, '#121316', 'rgba(255,181,71,.8)');
	for (let i = 0; i < 5; i++) {const y = oy + 1.25 + i * .34, h = (.25 + .55 * hash(i + 2)) * (foc('screen') ? .55 + .45 * (.5 + .5 * Math.sin(t * 2.2 + i)) : .8); wallX(c, ox, y, y + .2, 1.0, 1.0 + h * .9, i % 2 ? C.champ : C.gold);}
	const parts = [];
	parts.push({d: ox + oy + 1.3, f: () => {box3(c, ox + .2, oy + .2, ox + .95, oy + .85, 0, .95, C.steel, C.graph2, C.graph); box3(c, ox + .3, oy + .3, ox + .7, oy + .6, .95, 1.35, C.champ, C.brass, C.bronze); steam(c, ox + .5, oy + .45, 1.4, t, foc('coffee'));}});
	parts.push({d: ox + oy + 4.6, f: () => {box3(c, ox + 2.6, oy + .3, ox + 3.7, oy + 1.0, 0, .74, metal(c, S(ox + 2.6, oy + .3, .74), S(ox + 3.7, oy + 1, .74), C.steel, C.silver), C.graph2, C.graph);
		[ox + 2.7, ox + 3.2].forEach((mx) => box3(c, mx, oy + .35, mx + .42, oy + .42, .74, 1.25, C.steel2, foc('desk') ? '#3A2C10' : '#141518', C.graph));
		box3(c, ox + 2.9, oy + 1.2, ox + 3.35, oy + 1.6, 0, .45, C.graph2, C.char1, C.graph); box3(c, ox + 2.9, oy + 1.52, ox + 3.35, oy + 1.6, .45, 1.0, C.graph2, C.char1, C.graph);}});
	parts.push({d: ox + oy + 5.5, f: () => {box3(c, ox + 1.6, oy + 2.65, ox + 1.8, oy + 2.85, 0, .62, C.graph2, C.char1, C.graph); box3(c, ox + .9, oy + 2.3, ox + 2.5, oy + 3.2, .62, .72, metal(c, S(ox + .9, oy + 2.3, .72), S(ox + 2.5, oy + 3.2, .72), C.silver, C.silver2), C.steel2, C.steel);
		[[1.0, 3.35], [1.9, 3.35], [2.6, 2.6]].forEach(([a, b]) => box3(c, ox + a, oy + b, ox + a + .35, oy + b + .35, 0, .42, C.graph2, C.char1, C.graph));}});
	parts.push({d: ox + oy + 7.1, f: () => {box3(c, ox + 3.4, oy + 3.3, ox + 3.75, oy + 3.65, 0, .4, C.bronze, C.brass, C.bronze); const q = S(ox + 3.57, oy + 3.47, .78); const g = c.createRadialGradient(q[0] - .1 * K, q[1] - .1 * K, .03 * K, q[0], q[1], .34 * K); g.addColorStop(0, C.champ); g.addColorStop(1, C.bronze); c.fillStyle = g; c.beginPath(); c.arc(q[0], q[1], .32 * K, 0, 7); c.fill();}});
	if (R.place === 'office') charPart(c, t, R, parts, 0); crowd(c, t, parts, 'office'); parts.sort((a, b) => a.d - b.d).forEach((q) => q.f());}
function lab(c, t, R, B, flat) {const [ox, oy] = PL.lab.o, foc = (s) => B && B.place === 'lab' && B.station === s;
	shell(c, ox, oy, C.graph, C.graph2, flat); if (flat) return;
	wallY(c, oy, ox + 1.4, ox + 3.0, 1.35, 2.15, '#101114', 'rgba(255,181,71,.8)');
	c.strokeStyle = C.gold; c.lineWidth = Math.max(1.5, .025 * K); c.beginPath(); for (let i = 0; i <= 40; i++) {const u = i / 40, p = S(ox + 1.5 + u * 1.4, oy, 1.75 + Math.sin(u * 20 + t * 4) * .22 * (foc('screen') ? 1 : .35) * Math.sin(u * PI)); i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1]);} c.stroke();
	const parts = [];
	parts.push({d: ox + oy + 2.5, f: () => {box3(c, ox + .3, oy + .2, ox + 2.6, oy + .85, 0, .9, metal(c, S(ox + .3, oy + .2, .9), S(ox + 2.6, oy + .85, .9), C.steel, C.silver), C.graph2, C.graph);
		for (let i = 0; i < 4; i++) {const p = S(ox + .65 + i * .5, oy + .5, 1.05), r = .13 * K; c.fillStyle = 'rgba(216,220,226,.35)'; c.beginPath(); c.arc(p[0], p[1], r, 0, 7); c.fill(); c.fillRect(p[0] - r * .3, p[1] - r * 2.2, r * .6, r * 1.4);
			c.fillStyle = i % 2 ? C.gold : C.champ; c.beginPath(); c.arc(p[0], p[1], r * .85, .2, PI - .2); c.fill();
			if (foc('bench')) for (let k = 0; k < 2; k++) {const q = frac(t * 1.3 + i * .3 + k * .5); c.globalAlpha = 1 - q; c.fillStyle = C.pale; c.beginPath(); c.arc(p[0] + Math.sin(i + k) * r * .3, p[1] - q * r * 3, r * .15, 0, 7); c.fill(); c.globalAlpha = 1;}}}});
	parts.push({d: ox + oy + 3.6, f: () => {box3(c, ox + .2, oy + 1.6, ox + .9, oy + 2.6, 0, 2.2, C.graph2, C.char1, C.graph);
		for (let z = .3; z < 2.05; z += .25) for (let y = oy + 1.72; y < oy + 2.5; y += .2) {const on = frac(t * (foc('machine') ? 3 : 1) + hash(z * 9 + y)) > .45; poly(c, [[ox + .9, y, z], [ox + .9, y + .08, z], [ox + .9, y + .08, z + .06], [ox + .9, y, z + .06]], on ? (hash(y * 3 + z) > .5 ? C.gold : C.champ) : 'rgba(167,173,182,.15)');}}});
	parts.push({d: ox + oy + 4.5, f: () => {box3(c, ox + 2.9, oy + .3, ox + 3.75, oy + 1.0, 0, .8, metal(c, S(ox + 2.9, oy + .3, .8), S(ox + 3.75, oy + 1, .8), C.steel, C.silver), C.graph2, C.graph);
		box3(c, ox + 3.2, oy + .45, ox + 3.5, oy + .75, .8, .87, C.steel2, C.graph2, C.graph); const a = S(ox + 3.35, oy + .62, .87), b = S(ox + 3.3, oy + .5, 1.35), e = S(ox + 3.42, oy + .7, 1.08);
		c.strokeStyle = C.brass; c.lineCap = 'round'; c.lineWidth = .07 * K; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); c.strokeStyle = C.gold; c.lineWidth = .09 * K; c.beginPath(); c.moveTo(b[0], b[1]); c.lineTo(e[0], e[1]); c.stroke();
		if (foc('microscope')) {c.fillStyle = C.pale; c.shadowColor = C.gold; c.shadowBlur = .4 * K; c.beginPath(); c.arc(e[0], e[1], .05 * K, 0, 7); c.fill(); c.shadowBlur = 0;}}});
	if (R.place === 'lab') charPart(c, t, R, parts, 0); crowd(c, t, parts, 'lab'); parts.sort((a, b) => a.d - b.d).forEach((q) => q.f());}
function cafe(c, t, R, B, flat) {const [ox, oy] = PL.cafe.o, foc = (s) => B && B.place === 'cafe' && B.station === s;
	shell(c, ox, oy, C.bronze, C.graph2, flat); if (flat) return;
	wallX(c, ox, oy + 1.0, oy + 3.4, .7, 2.1, 'rgba(242,212,155,.16)', C.brass); [1.8, 2.6].forEach((y) => wallX(c, ox, oy + y, oy + y + .04, .7, 2.1, C.brass));
	wallY(c, oy, ox + 2.9, ox + 3.8, 1.4, 2.2, C.char0, 'rgba(255,181,71,.7)'); for (let i = 0; i < 4; i++) wallY(c, oy, ox + 3.0, ox + 3.0 + .3 + hash(i) * .4, 2.05 - i * .17, 2.09 - i * .17, i ? C.champ : C.gold);
	const parts = [], tables = [[1.4, 2.4], [3.0, 3.1]];
	parts.push({d: ox + oy + 2.5, f: () => {box3(c, ox + .4, oy + .25, ox + 2.7, oy + .9, 0, 1.0, metal(c, S(ox + .4, oy + .25, 1), S(ox + 2.7, oy + .9, 1), C.steel2, C.silver), metal(c, S(ox + .4, oy + .9, 0), S(ox + 2.7, oy + .9, 1), C.bronze, C.brass), C.bronze);
		box3(c, ox + 1.2, oy + .32, ox + 1.75, oy + .65, 1.0, 1.45, C.champ, metal(c, S(ox + 1.2, oy + .65, 1), S(ox + 1.75, oy + .65, 1.45), C.steel2, C.silver2), C.steel); steam(c, ox + 1.45, oy + .5, 1.5, t, foc('counter') || true);}});
	tables.forEach(([a, b]) => parts.push({d: ox + oy + a + b + .5, f: () => {const x = ox + a, y = oy + b, p = S(x, y, .75), q = S(x, y, 0);
		c.strokeStyle = C.graph2; c.lineWidth = .08 * K; c.beginPath(); c.moveTo(q[0], q[1]); c.lineTo(p[0], p[1]); c.stroke(); c.fillStyle = metal(c, [p[0] - .5 * K, p[1]], [p[0] + .5 * K, p[1]], C.silver, C.silver2); c.beginPath(); c.ellipse(p[0], p[1], .45 * 1.2247 * K, .45 * .7071 * K, 0, 0, 7); c.fill();
		box3(c, x + .45, y - .15, x + .8, y + .2, 0, .42, C.graph2, C.char1, C.graph); const l0 = S(x, y, 2.6), l1 = S(x, y, 1.95); c.strokeStyle = C.champ; c.lineWidth = 1.5; c.beginPath(); c.moveTo(l0[0], l0[1]); c.lineTo(l1[0], l1[1]); c.stroke();
		const g = c.createRadialGradient(l1[0], l1[1], 1, l1[0], l1[1], .5 * K); g.addColorStop(0, 'rgba(255,181,71,.9)'); g.addColorStop(1, 'rgba(255,181,71,0)'); c.fillStyle = g; c.beginPath(); c.arc(l1[0], l1[1], .5 * K, 0, 7); c.fill();}}));
	if (R.place === 'cafe') charPart(c, t, R, parts, 0); crowd(c, t, parts, 'cafe'); parts.sort((a, b) => a.d - b.d).forEach((q) => q.f());}
function street(c, t, R, B, flat) {const [ox, oy] = PL.street.o, foc = (s) => B && B.place === 'street' && B.station === s;
	poly(c, [[ox, oy, 0], [ox + 3, oy, 0], [ox + 3, oy + 3, 0], [ox, oy + 3, 0]], metal(c, S(ox, oy, 0), S(ox + 3, oy + 3, 0), C.graph, C.graph2), 'rgba(184,134,46,.35)');
	for (let i = 0; i < 6; i++) poly(c, [[ox + .3 + i * .42, oy + 3.15, .01], [ox + .5 + i * .42, oy + 3.15, .01], [ox + .5 + i * .42, oy + 3.85, .01], [ox + .3 + i * .42, oy + 3.85, .01]], 'rgba(242,212,155,.55)');
	const lg = S(ox + .85, oy + .45, 0), gl = c.createRadialGradient(lg[0], lg[1], 2, lg[0], lg[1], 1.4 * K); gl.addColorStop(0, `rgba(255,181,71,${.28 + (foc('lamp') ? .12 * Math.sin(t * 18) : 0)})`); gl.addColorStop(1, 'rgba(255,181,71,0)');
	c.fillStyle = gl; c.beginPath(); c.ellipse(lg[0], lg[1], 1.4 * K, .8 * K, 0, 0, 7); c.fill(); if (flat) return;
	const parts = [];
	parts.push({d: ox + oy + .9, f: () => {box3(c, ox + .4, oy + .4, ox + .5, oy + .5, 0, 2.4, C.steel, C.graph2, C.graph); box3(c, ox + .4, oy + .4, ox + .95, oy + .5, 2.35, 2.45, C.steel2, C.graph2, C.graph);
		const h = S(ox + .88, oy + .45, 2.3), g = c.createRadialGradient(h[0], h[1], 1, h[0], h[1], .6 * K); g.addColorStop(0, C.pale); g.addColorStop(.3, 'rgba(255,181,71,.8)'); g.addColorStop(1, 'rgba(255,181,71,0)'); c.fillStyle = g; c.beginPath(); c.arc(h[0], h[1], .6 * K, 0, 7); c.fill();}});
	parts.push({d: ox + oy + 2.85, f: () => {box3(c, ox + 2.45, oy + .35, ox + 2.51, oy + .41, 0, 2.0, C.steel, C.graph2, C.graph); box3(c, ox + 2.35, oy + .35, ox + 2.61, oy + .41, 1.65, 2.05, C.gold, C.brass, C.bronze);}});
	parts.push({d: ox + oy + 4.7, f: () => {box3(c, ox + .6, oy + 2.3, ox + 1.6, oy + 2.7, .35, .45, C.brass, C.bronze, C.bronze); box3(c, ox + .6, oy + 2.62, ox + 1.6, oy + 2.7, .45, .8, C.brass, C.bronze, C.bronze);
		[[.65, 2.35], [1.5, 2.35]].forEach(([a, b]) => box3(c, ox + a, oy + b, ox + a + .06, oy + b + .3, 0, .35, C.graph2, C.char1, C.graph));}});
	parts.push({d: ox + oy + 5.3, f: () => {const x = ox + 3.15, y = oy + .7; box3(c, x, y, x + .7, y + 1.6, .12, .55, metal(c, S(x, y, .55), S(x + .7, y + 1.6, .55), C.steel2, C.silver2), C.steel, C.graph2);
		box3(c, x + .05, y + .4, x + .65, y + 1.2, .55, .9, '#1A1C21', C.char1, C.graph); poly(c, [[x + .08, y + 1.6, .32], [x + .22, y + 1.6, .32], [x + .22, y + 1.6, .42], [x + .08, y + 1.6, .42]], foc('car') && frac(t * 1.5) > .5 ? C.pale : C.gold);
		poly(c, [[x + .48, y + 1.6, .32], [x + .62, y + 1.6, .32], [x + .62, y + 1.6, .42], [x + .48, y + 1.6, .42]], foc('car') && frac(t * 1.5) > .5 ? C.pale : C.gold);}});
	if (R.place === 'street') charPart(c, t, R, parts, 0); crowd(c, t, parts, 'street'); parts.sort((a, b) => a.d - b.d).forEach((q) => q.f());}
function rooftop(c, t, R, B, lit) {const [ox, oy] = PL.rooftop.o, Z = PL.rooftop.z, foc = (s) => B && B.place === 'rooftop' && B.station === s;
	building(c, {x: ox, y: oy, w: 3, d: 3, h: Z, seed: 99}, t, lit);
	const m = S(ox + 1.5, oy + 1.5, Z); c.strokeStyle = 'rgba(255,181,71,.7)'; c.lineWidth = Math.max(1.5, .03 * K); c.beginPath(); c.ellipse(m[0], m[1], .9 * K, .52 * K, 0, 0, 7); c.stroke();
	const parts = [];
	parts.push({d: ox + oy + 1.3, f: () => {box3(c, ox + .25, oy + .25, ox + 1.05, oy + 1.05, Z, Z + 1.2, C.bronze, metal(c, S(ox + .25, oy + 1.05, Z), S(ox + 1.05, oy + 1.05, Z + 1.2), C.bronze, C.brass), C.bronze);
		[Z + .35, Z + .8].forEach((z) => poly(c, [[ox + .25, oy + 1.05, z], [ox + 1.05, oy + 1.05, z], [ox + 1.05, oy + 1.05, z + .04], [ox + .25, oy + 1.05, z + .04]], C.champ));}});
	parts.push({d: ox + oy + 2.6, f: () => {const a = S(ox + 1.9, oy + .6, Z), b = S(ox + 1.9, oy + .6, Z + .6); c.strokeStyle = C.steel; c.lineWidth = .06 * K; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();
		c.save(); c.translate(b[0], b[1] - .1 * K); c.rotate(-.5 + (foc('dish') ? Math.sin(t * 1.5) * .3 : 0)); c.fillStyle = metal(c, [-.4 * K, 0], [.4 * K, 0], C.silver, C.silver2); c.beginPath(); c.ellipse(0, 0, .42 * K, .2 * K, 0, 0, 7); c.fill(); c.restore();
		const p0 = S(ox + .4, oy + 2.5, Z), p1 = S(ox + .4, oy + 2.5, Z + 2); c.strokeStyle = C.steel2; c.lineWidth = .04 * K; c.beginPath(); c.moveTo(p0[0], p0[1]); c.lineTo(p1[0], p1[1]); c.stroke();
		if (frac(t * .8) > .5) {c.fillStyle = C.gold; c.shadowColor = C.gold; c.shadowBlur = .4 * K; c.beginPath(); c.arc(p1[0], p1[1], .06 * K, 0, 7); c.fill(); c.shadowBlur = 0;}}});
	const rail = () => {c.strokeStyle = C.gold; c.lineWidth = Math.max(1.2, .025 * K); const pts = [[ox, oy + 3], [ox + 3, oy + 3], [ox + 3, oy]];
		c.beginPath(); pts.forEach((p, i) => {const q = S(p[0], p[1], Z + .45); i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]);}); c.stroke();
		for (let i = 0; i <= 6; i++) [[ox + i * .5, oy + 3], [ox + 3, oy + i * .5]].forEach(([x, y]) => {const a = S(x, y, Z), b = S(x, y, Z + .45); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();});};
	if (R.place === 'rooftop') charPart(c, t, R, parts, Z); crowd(c, t, parts, 'rooftop', Z); parts.sort((a, b) => a.d - b.d).forEach((q) => q.f()); rail();}

/* ── KIT PLACES: places beyond the six, drawn from data — a library kit, or one the set designer made for this film.
   A kit = floor + walls + props from the vocabulary below (sizes in city units, x/y from the place's back corner). ── */
export const PROP_TYPES = ['box', 'table', 'desk', 'counter', 'shelf', 'bed', 'chair', 'sofa', 'bench', 'screen', 'board', 'window', 'rack', 'machine', 'console', 'tank', 'pillar',
	'pipe', 'lamp', 'light', 'plant', 'tree', 'bush', 'rail', 'sign', 'sphere', 'crate', 'stage', 'podium', 'ring', 'dish', 'car', 'boat', 'patch', 'court'];
const PDEF = {box: [.8, .8, .8], table: [1.2, .8, .72], desk: [1.1, .6, .74], counter: [2, .6, 1], shelf: [1.2, .4, 1.8], bed: [1.9, 1, .55], chair: [.42, .42, .9], sofa: [1.4, .6, .8],
	bench: [1, .35, .45], screen: [1.2, .1, .8], board: [1.4, .05, .9], window: [1.2, .05, 1], rack: [.6, .6, 2], machine: [1, .8, 1.4], console: [1.4, .6, .9], tank: [.8, .8, 1.6],
	pillar: [.3, .3, 2.6], pipe: [2, .15, .15], lamp: [.3, .3, 1.8], light: [.3, .3, .3], plant: [.4, .4, .8], tree: [.8, .8, 2.2], bush: [.6, .6, .5], rail: [2, .06, .5],
	sign: [.6, .1, 1.6], sphere: [.6, .6, .6], crate: [.5, .5, .5], stage: [2, 1.2, .25], podium: [.5, .4, 1.1], ring: [1.2, .3, 1.4], dish: [.8, .8, 1.2], car: [.7, 1.6, .9],
	boat: [.9, 2.2, .6], patch: [1.5, 1.5, 0], court: [3, 3, 0]};
export const FLOOR_KINDS = {tile: [C.graph2, C.steel], wood: ['#3A2A18', '#5A4024'], carpet: ['#2A2018', '#3A2C1E'], concrete: [C.graph, C.graph2], grass: ['#1E231B', '#2B3226'],
	sand: ['#4A3C26', '#6A5634'], water: ['#1A2833', '#2A3F4C']};
const WALL_PROPS = ['screen', 'board', 'window'];
const tok = (n, d) => (typeof n === 'string' && n[0] === '#' ? n : C[n] || d);
const B3 = (c, x0, y0, x1, y1, z0, z1, col) => box3(c, x0, y0, x1, y1, z0, z1, lighten(col), col, shade(col));
function glow(c, x, y, z, r, a) {const q = S(x, y, z), g = c.createRadialGradient(q[0], q[1], 1, q[0], q[1], r * K); g.addColorStop(0, `rgba(255,243,220,${a})`); g.addColorStop(.3, `rgba(255,181,71,${a * .8})`); g.addColorStop(1, 'rgba(255,181,71,0)');
	c.fillStyle = g; c.beginPath(); c.arc(q[0], q[1], r * K, 0, 7); c.fill();}
function cyl(c, x, y, z0, z1, r, col) {const a = S(x, y, z0), b = S(x, y, z1), rx = r * 1.2247 * K, ry = r * .7071 * K;
	c.fillStyle = metal(c, [a[0] - rx, a[1]], [a[0] + rx, a[1]], shade(col), lighten(col)); c.beginPath(); c.ellipse(a[0], a[1], rx, ry, 0, 0, PI); c.lineTo(b[0] - rx, b[1]); c.ellipse(b[0], b[1], rx, ry, 0, PI, 0, true); c.closePath(); c.fill();
	c.fillStyle = lighten(lighten(col)); c.beginPath(); c.ellipse(b[0], b[1], rx, ry, 0, 0, 7); c.fill();}
function blob(c, x, y, z, r, hot) {const q = S(x, y, z), g = c.createRadialGradient(q[0] - r * .3 * K, q[1] - r * .3 * K, .05 * K, q[0], q[1], r * K);
	const green = typeof WORLD !== 'undefined' && WORLD.id !== 'city';           // gold foliage is the city's; every other world grows green
	if (green) {g.addColorStop(0, hot ? '#9AAE6A' : '#6E8048'); g.addColorStop(.45, '#4B5A34'); g.addColorStop(1, '#2C3620');} else {g.addColorStop(0, hot ? C.pale : C.champ); g.addColorStop(.35, C.brass); g.addColorStop(1, C.bronze);} c.fillStyle = g; c.beginPath(); c.arc(q[0], q[1], r * K, 0, 7); c.fill();}
// a picture on a wall plane (back wall: along x at y = oy, left wall: along y at x = ox) or on its own stand
function wallFace(c, side, ox, oy, a, w, z0, z1, fill, edge) {side === 'left' ? wallX(c, ox, oy + a, oy + a + w, z0, z1, fill, edge) : wallY(c, oy, ox + a, ox + a + w, z0, z1, fill, edge);}
function wallArt(c, t, p, ox, oy, hot) {const side = p.wall === 'left' ? 'left' : 'back', a = side === 'left' ? p.y : p.x, w = p.w, z0 = p.z ?? (p.t === 'window' ? .8 : 1), z1 = z0 + p.h;
	const at = (u, z) => (side === 'left' ? [ox, oy + a + u * w, z] : [ox + a + u * w, oy, z]);
	if (p.t === 'window') {wallFace(c, side, ox, oy, a, w, z0, z1, 'rgba(242,212,155,.14)', C.brass); for (let i = 1; i < 3; i++) wallFace(c, side, ox, oy, a + i * w / 3, .03, z0, z1, C.brass);
		for (let i = 0; i < 9; i++) {const u = .08 + hash(i + a * 7) * .84, z = z0 + .1 + hash(i * 3 + a) * (p.h - .25), q = S(...at(u, z)); c.fillStyle = hash(i + 9) > .5 ? C.gold : C.champ; c.globalAlpha = .5 + .5 * frac(Math.sin(t + i)); c.fillRect(q[0], q[1], 3, 3);} c.globalAlpha = 1; return;}
	if (p.t === 'board') {wallFace(c, side, ox, oy, a, w, z0, z1, '#15171B', tok(p.col, C.silver)); c.strokeStyle = C.champ; c.lineWidth = Math.max(1, .02 * K);
		for (let i = 0; i < 4; i++) {const z = z1 - .2 - i * p.h * .2, l = .3 + hash(i + a) * .55; const s0 = S(...at(.08, z)), s1 = S(...at(.08 + l * (hot ? clamp(frac(t * .4) * 2) : 1), z)); c.beginPath(); c.moveTo(s0[0], s0[1]); c.lineTo(s1[0], s1[1]); c.stroke();} return;}
	wallFace(c, side, ox, oy, a, w, z0, z1, '#0B0E13', 'rgba(184,134,46,.85)'); screenBars(c, t, at, p.h, z0, hot);}
function screenBars(c, t, at, h, z0, hot) {const n = 6; for (let i = 0; i < n; i++) {const u0 = .1 + i * .8 / n, u1 = u0 + .8 / n * .6, v = (.3 + .55 * hash(i + 3)) * (hot ? .6 + .4 * (.5 + .5 * Math.sin(t * 2.4 + i)) : .85 + .15 * Math.sin(t * .6 + i));
	poly(c, [at(u0, z0 + .08), at(u1, z0 + .08), at(u1, z0 + .08 + v * (h - .16)), at(u0, z0 + .08 + v * (h - .16))], i % 2 ? C.champ : C.gold);}}
function floorArt(c, t, p, X, Y) {const {w, d} = p;
	if (p.t === 'patch') {const f = FLOOR_KINDS[p.kind] || FLOOR_KINDS.grass; poly(c, [[X, Y, .01], [X + w, Y, .01], [X + w, Y + d, .01], [X, Y + d, .01]], metal(c, S(X, Y, 0), S(X + w, Y + d, 0), f[0], f[1]));
		if (p.kind === 'water') waves(c, t, X, Y, w, d); return;}
	c.strokeStyle = 'rgba(255,181,71,.55)'; c.lineWidth = Math.max(1, .02 * K); const r = [[X, Y], [X + w, Y], [X + w, Y + d], [X, Y + d]];   // court: boundary, half line, centre circle
	c.beginPath(); r.forEach((q, i) => {const s = S(q[0], q[1], .01); i ? c.lineTo(s[0], s[1]) : c.moveTo(s[0], s[1]);}); c.closePath(); c.stroke();
	const a = S(X + w / 2, Y, .01), b = S(X + w / 2, Y + d, .01), m = S(X + w / 2, Y + d / 2, .01); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); c.beginPath(); c.ellipse(m[0], m[1], .5 * 1.2247 * K, .5 * .7071 * K, 0, 0, 7); c.stroke();}
function waves(c, t, X, Y, w, d) {c.strokeStyle = 'rgba(242,212,155,.6)'; c.lineWidth = Math.max(1.2, .025 * K); for (let i = 0; i < Math.round(6 * w * d / 4) + 4; i++) {const u = frac(hash(i) + t * .05 * (1 + hash(i + 4))), v = hash(i + 7);
	const a = S(X + u * w * .85, Y + v * d, .01), b = S(X + u * w * .85 + .25, Y + v * d, .01); c.globalAlpha = Math.sin(u * PI); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();} c.globalAlpha = 1;}
function propDraw(c, t, p, X, Y, hot) {const {w, d, h} = p, z = p.z || 0, col = tok(p.col, ''), cx = X + w / 2, cy = Y + d / 2;
	switch (p.t) {
	case 'box': B3(c, X, Y, X + w, Y + d, z, z + h, col || C.graph2); break;
	case 'crate': B3(c, X, Y, X + w, Y + d, z, z + h, col || C.bronze); c.strokeStyle = C.brass; c.lineWidth = Math.max(1, .015 * K); {const a = S(X, Y + d, z), b = S(X + w, Y + d, z + h), e = S(X + w, Y + d, z), f = S(X, Y + d, z + h); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.moveTo(e[0], e[1]); c.lineTo(f[0], f[1]); c.stroke();} break;
	case 'table': case 'desk': {const top = col || (p.t === 'desk' ? C.steel : C.silver); [[X + .05, Y + .05], [X + w - .12, Y + .05], [X + .05, Y + d - .12], [X + w - .12, Y + d - .12]].forEach(([a, b]) => B3(c, a, b, a + .07, b + .07, 0, h - .06, C.graph2));
		box3(c, X, Y, X + w, Y + d, h - .06, h, metal(c, S(X, Y, h), S(X + w, Y + d, h), top, lighten(top)), shade(top), shade(shade(top)));
		if (p.t === 'desk') {B3(c, X + w * .3, Y + .08, X + w * .7, Y + .14, h, h + .45, C.graph); poly(c, [[X + w * .32, Y + .14, h + .05], [X + w * .68, Y + .14, h + .05], [X + w * .68, Y + .14, h + .42], [X + w * .32, Y + .14, h + .42]], hot ? (frac(t * 1.5) > .3 ? '#5A4416' : '#3A2C10') : '#16181C');}
		break;}
	case 'counter': B3(c, X, Y, X + w, Y + d, 0, h - .06, col || C.bronze); box3(c, X - .03, Y - .03, X + w + .03, Y + d + .03, h - .06, h, metal(c, S(X, Y, h), S(X + w, Y + d, h), C.silver, C.silver2), C.steel2, C.steel); break;
	case 'shelf': B3(c, X, Y, X + w, Y + d, 0, h, col || C.graph2); for (let z2 = .25, r = 0; z2 < h - .2; z2 += .42, r++) for (let s = .06; s < w - .1; s += .11) {const hv = hash(r * 13 + s * 31 + X), bh = .22 + hv * .12;
		poly(c, [[X + s, Y + d + .005, z2], [X + s + .08, Y + d + .005, z2], [X + s + .08, Y + d + .005, z2 + bh], [X + s, Y + d + .005, z2 + bh]], WIN[Math.floor(hv * 40) % 4]);} break;
	case 'bed': B3(c, X, Y, X + w, Y + d, 0, .32, col || C.steel); B3(c, X + .05, Y + .05, X + w - .05, Y + d - .05, .32, h, C.silver2); B3(c, X + .08, Y + .15, X + .45, Y + d - .15, h, h + .12, C.pale);
		B3(c, X + w * .45, Y + .04, X + w - .06, Y + d - .04, h, h + .06, tok(p.col2, C.champ)); break;
	case 'chair': B3(c, X, Y, X + w, Y + d, .4, .47, col || C.graph2); B3(c, X, Y, X + w, Y + .07, .47, h, col || C.graph2); [[X + .03, Y + .03], [X + w - .08, Y + d - .08]].forEach(([a, b]) => B3(c, a, b, a + .05, b + .05, 0, .4, C.char1)); break;
	case 'sofa': B3(c, X, Y, X + w, Y + d, 0, .42, col || C.bronze); B3(c, X, Y, X + w, Y + .18, .42, h, col || C.bronze); B3(c, X, Y, X + .16, Y + d, .42, .62, col || C.bronze); B3(c, X + w - .16, Y, X + w, Y + d, .42, .62, col || C.bronze); break;
	case 'bench': B3(c, X, Y, X + w, Y + d, .38, .45, col || C.brass); [[X + .05, Y + .05], [X + w - .1, Y + .05]].forEach(([a, b]) => B3(c, a, b, a + .05, b + d - .1, 0, .38, C.graph2)); break;
	case 'screen': B3(c, cx - .03, cy - .03, cx + .03, cy + .03, 0, (p.z ?? .9), C.steel); {const z0 = p.z ?? .9; B3(c, X, Y, X + w, Y + d, z0, z0 + h, C.graph); screenBars(c, t, (u, zz) => [X + u * w, Y + d + .004, zz], h, z0, hot);} break;
	case 'rack': B3(c, X, Y, X + w, Y + d, 0, h, col || C.char1); for (let z2 = .15; z2 < h - .1; z2 += .14) for (let s = .08; s < w - .06; s += .1) {const on = frac(t * (hot ? 4 : 1.3) + hash(z2 * 9 + s * 5 + X)) > .45;
		poly(c, [[X + s, Y + d + .005, z2], [X + s + .05, Y + d + .005, z2], [X + s + .05, Y + d + .005, z2 + .04], [X + s, Y + d + .005, z2 + .04]], on ? (hash(s + z2) > .5 ? C.gold : C.champ) : 'rgba(167,173,182,.15)');} break;
	case 'machine': B3(c, X, Y, X + w, Y + d, 0, h, col || C.graph2); B3(c, X + w * .1, Y + d * .2, X + w * .45, Y + d * .5, h, h + .35, C.steel); for (let i = 0; i < 4; i++) {const on = frac(t * (hot ? 3 : 1) + i * .27) > .5;
		poly(c, [[X + .15 + i * .18, Y + d + .005, h * .6], [X + .27 + i * .18, Y + d + .005, h * .6], [X + .27 + i * .18, Y + d + .005, h * .6 + .1], [X + .15 + i * .18, Y + d + .005, h * .6 + .1]], on ? C.gold : '#2A2418');}
		steam(c, X + w * .27, Y + d * .35, h + .4, t, hot); break;
	case 'console': B3(c, X, Y, X + w, Y + d, 0, h * .8, col || C.graph2); poly(c, [[X, Y + d * .1, h * .8], [X + w, Y + d * .1, h * .8], [X + w, Y + d * .1, h], [X, Y + d * .1, h]], C.graph);
		for (let i = 0; i < 9; i++) {const s = .08 + i * (w - .16) / 9, on = frac(t * (hot ? 2.5 : .8) + hash(i + X)) > .35; poly(c, [[X + s, Y + d * .5, h * .8 + .005], [X + s + .08, Y + d * .5, h * .8 + .005], [X + s + .08, Y + d * .8, h * .8 + .005], [X + s, Y + d * .8, h * .8 + .005]], on ? (i % 3 ? C.champ : C.gold) : '#2A2418');} break;
	case 'tank': cyl(c, cx, cy, z, z + h, w / 2, col || C.steel); [.3, .7].forEach((f) => {const a = S(cx, cy, z + h * f); c.strokeStyle = C.brass; c.lineWidth = Math.max(1, .025 * K); c.beginPath(); c.ellipse(a[0], a[1], w / 2 * 1.2247 * K, w / 2 * .7071 * K, 0, 0, PI); c.stroke();});
		if (hot) glow(c, cx, cy, z + h + .1, .5, .5 + .3 * Math.sin(t * 6)); break;
	case 'pillar': cyl(c, cx, cy, 0, h, w / 2, col || C.graph2); break;
	case 'pipe': (w >= d ? B3(c, X, cy - .07, X + w, cy + .07, z || 1.6, (z || 1.6) + .14, col || C.brass) : B3(c, cx - .07, Y, cx + .07, Y + d, z || 1.6, (z || 1.6) + .14, col || C.brass)); break;
	case 'lamp': B3(c, cx - .04, cy - .04, cx + .04, cy + .04, 0, h, C.steel); glow(c, cx, cy, h, .6, hot ? .9 + .1 * Math.sin(t * 18) : .75); break;
	case 'light': {const a = S(cx, cy, 2.6), b = S(cx, cy, z || 2); c.strokeStyle = C.champ; c.lineWidth = 1.5; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); glow(c, cx, cy, z || 2, .5, hot ? .95 : .8); break;}
	case 'plant': B3(c, cx - .12, cy - .12, cx + .12, cy + .12, 0, .3, C.bronze); blob(c, cx, cy, h * .75, Math.max(.2, w * .5), hot); break;
	case 'tree': {const p0 = S(cx, cy, 0), p1 = S(cx, cy, h * .55); c.fillStyle = C.char1; c.fillRect(p0[0] - .06 * K, p1[1], .12 * K, p0[1] - p1[1]); blob(c, cx, cy, h * .7, Math.max(.35, w * .6), hot); blob(c, cx + .15, cy - .1, h * .88, Math.max(.25, w * .42), hot); break;}
	case 'bush': blob(c, cx, cy, h * .5, Math.max(.2, w * .5), hot); break;
	case 'rail': {const along = w >= d, L = along ? w : d; c.strokeStyle = col || C.gold; c.lineWidth = Math.max(1.2, .025 * K); const pt = (u, zz) => S(along ? X + u * L : cx, along ? cy : Y + u * L, zz);
		const a = pt(0, h), b = pt(1, h); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); for (let u = 0; u <= 1.001; u += .5 / L) {const q0 = pt(u, 0), q1 = pt(u, h); c.beginPath(); c.moveTo(q0[0], q0[1]); c.lineTo(q1[0], q1[1]); c.stroke();} break;}
	case 'sign': B3(c, cx - .03, cy - .03, cx + .03, cy + .03, 0, h - .4, C.steel); B3(c, X, cy - .04, X + w, cy + .04, h - .45, h, col || C.gold); if (hot) glow(c, cx, cy, h - .2, .45, .6); break;
	case 'sphere': {const r = w / 2, q = S(cx, cy, z + r + (p.z ? 0 : .02)), g = c.createRadialGradient(q[0] - r * .35 * K, q[1] - r * .35 * K, .03 * K, q[0], q[1], r * 1.2 * K); g.addColorStop(0, C.pale); g.addColorStop(.4, tok(p.col, C.gold)); g.addColorStop(1, C.bronze);
		c.fillStyle = g; c.beginPath(); c.arc(q[0], q[1], r * 1.2 * K, 0, 7); c.fill(); c.strokeStyle = 'rgba(11,11,13,.35)'; c.lineWidth = 1; c.beginPath(); c.ellipse(q[0], q[1], Math.abs(Math.cos(t * (hot ? 1.5 : .4))) * r * 1.2 * K, r * 1.2 * K, 0, 0, 7); c.stroke(); break;}
	case 'stage': box3(c, X, Y, X + w, Y + d, 0, h, metal(c, S(X, Y, h), S(X + w, Y + d, h), C.graph2, C.steel), C.graph, C.char1); poly(c, [[X, Y + d, h], [X + w, Y + d, h], [X + w, Y + d, h - .03], [X, Y + d, h - .03]], C.gold); break;
	case 'podium': B3(c, X, Y, X + w, Y + d, 0, h - .1, col || C.bronze); poly(c, [[X - .03, Y, h - .1], [X + w + .03, Y, h - .1], [X + w + .03, Y + d + .05, h - .2], [X - .03, Y + d + .05, h - .2]], C.brass); break;
	case 'ring': {const q = S(cx, cy, h / 2 + .05); c.strokeStyle = hot ? C.pale : C.gold; c.lineWidth = Math.max(3, .12 * K); c.shadowColor = C.gold; c.shadowBlur = hot ? (.4 + .3 * Math.sin(t * 5)) * K : .15 * K;
		c.beginPath(); c.ellipse(q[0], q[1], w / 2 * .9 * K, h / 2 * K, 0, 0, 7); c.stroke(); c.shadowBlur = 0; B3(c, X, Y, X + w, Y + d, 0, .12, C.graph2); break;}
	case 'dish': {const a = S(cx, cy, 0), b = S(cx, cy, h * .55); c.strokeStyle = C.steel; c.lineWidth = .06 * K; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();
		c.save(); c.translate(b[0], b[1] - .1 * K); c.rotate(-.5 + (hot ? Math.sin(t * 1.5) * .3 : 0)); c.fillStyle = metal(c, [-.4 * K, 0], [.4 * K, 0], C.silver, C.silver2); c.beginPath(); c.ellipse(0, 0, w * .55 * K, w * .26 * K, 0, 0, 7); c.fill(); c.restore(); break;}
	case 'car': {box3(c, X, Y, X + w, Y + d, .12, h * .6, metal(c, S(X, Y, h * .6), S(X + w, Y + d, h * .6), C.steel2, C.silver2), tok(p.col, C.steel), C.graph2); B3(c, X + .05, Y + d * .25, X + w - .05, Y + d * .75, h * .6, h, '#1A1C21');
		[.08, .48].forEach((u) => poly(c, [[X + u * w, Y + d, .3], [X + u * w + .14, Y + d, .3], [X + u * w + .14, Y + d, .4], [X + u * w, Y + d, .4]], hot && frac(t * 1.5) > .5 ? C.pale : C.gold)); break;}
	case 'boat': {const z0 = p.z ?? .05; poly(c, [[X, Y, z0 + h], [X + w, Y, z0 + h], [X + w, Y + d * .8, z0 + h], [cx, Y + d, z0 + h], [X, Y + d * .8, z0 + h]], metal(c, S(X, Y, z0 + h), S(X + w, Y + d, z0 + h), C.bronze, C.brass));
		poly(c, [[X, Y + d * .8, z0], [cx, Y + d, z0], [cx, Y + d, z0 + h], [X, Y + d * .8, z0 + h]], tok(p.col, C.graph2)); poly(c, [[X + w, Y, z0], [X + w, Y + d * .8, z0], [cx, Y + d, z0], [cx, Y + d, z0 + h], [X + w, Y + d * .8, z0 + h], [X + w, Y, z0 + h]], C.char1);
		B3(c, cx - .03, cy - .03, cx + .03, cy + .03, z0 + h, z0 + h + 1.6, C.steel); break;}
	default: if (!worldProp(c, t, p, X, Y, hot, col)) B3(c, X, Y, X + w, Y + d, z, z + h, col || C.graph2);}}
// one kit place: floor, walls, wall pictures, floor markings, then props + people sorted by depth
function kitPlace(c, t, R, B, flat, id) {const P = PL[id], kit = P.kit, [ox, oy] = P.o, f = FLOOR_KINDS[kit.floor] || FLOOR_KINDS.tile, walls = flat ? 'none' : kit.walls || 'both', H = clamp(+kit.wallH || 2.6, .4, 3);
	poly(c, [[ox, oy, 0], [ox + 4, oy, 0], [ox + 4, oy + 4, 0], [ox, oy + 4, 0]], metal(c, S(ox, oy, 0), S(ox + 4, oy + 4, 0), f[0], f[1]), 'rgba(184,134,46,.35)');
	if (kit.floor === 'water') waves(c, t, ox, oy, 4, 4);
	else if (kit.floor !== 'grass' && kit.floor !== 'sand') {c.strokeStyle = 'rgba(216,220,226,.07)'; c.lineWidth = 1; for (let i = 1; i < 8; i++) {const a = S(ox + i / 2, oy, 0), b = S(ox + i / 2, oy + 4, 0); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();}}
	else for (let i = 0; i < 26; i++) {const q = S(ox + .2 + hash(i + ox) * 3.6, oy + .2 + hash(i * 3 + oy) * 3.6, 0); c.fillStyle = kit.floor === 'grass' ? 'rgba(184,134,46,.22)' : 'rgba(255,243,220,.12)'; c.fillRect(q[0], q[1], 3, 2);}
	if (flat) {[[[ox, oy, 0], [ox + 4, oy, 0], [ox + 4, oy, .18], [ox, oy, .18]], [[ox, oy, 0], [ox, oy + 4, 0], [ox, oy + 4, .18], [ox, oy, .18]]].forEach((q) => poly(c, q, C.graph));}
	if (walls === 'both' || walls === 'back') {wallY(c, oy, ox, ox + 4, 0, H, metal(c, S(ox, oy, H), S(ox + 4, oy, 0), C.graph, C.graph2)); wallY(c, oy, ox, ox + 4, H, H + .06, C.brass);}
	if (walls === 'both' || walls === 'left') {wallX(c, ox, oy, oy + 4, 0, H, metal(c, S(ox, oy, H), S(ox, oy + 4, 0), C.char1, C.graph)); wallX(c, ox, oy, oy + 4, H, H + .06, C.bronze);}
	if (flat) return;
	const fs = B && B.place === id ? P.st[B.station] : null, fp = fs && fs[2] ? [ox + fs[2][0], oy + fs[2][1]] : null;
	const hotAt = (x, y, r) => !!fp && Math.hypot(fp[0] - x, fp[1] - y) < Math.max(.9, r + .4);
	const props = kit._props || (kit._props = (kit.props || []).filter((p) => p && PROP_TYPES.includes(p.t)).slice(0, 24).map((p) => {const D = PDEF[p.t];
		return {...p, x: clamp(+p.x || 0, 0, 3.9), y: clamp(+p.y || 0, 0, 3.9), w: clamp(+p.w || D[0], .05, 4), d: clamp(+p.d || D[1], .05, 4), h: clamp(+p.h || D[2], 0, 4), z: p.z == null ? undefined : clamp(+p.z, 0, 3)};}));
	for (const p of props) if (WALL_PROPS.includes(p.t) && p.wall && walls !== 'none' && (walls === 'both' || walls === (p.wall === 'left' ? 'left' : 'back'))) wallArt(c, t, p, ox, oy, hotAt(p.wall === 'left' ? ox : ox + p.x + p.w / 2, p.wall === 'left' ? oy + p.y + p.w / 2 : oy, p.w / 2));
	for (const p of props) if (p.t === 'patch' || p.t === 'court') floorArt(c, t, p, ox + p.x, oy + p.y);
	const parts = [];
	for (const p of props) {if (p.t === 'patch' || p.t === 'court' || (WALL_PROPS.includes(p.t) && p.wall && walls !== 'none')) continue; if (p.t === 'board' || p.t === 'window') continue;
		const X = ox + p.x, Y = oy + p.y; if (p.h > .35 && COMP_AT.some(([ax, ay, r]) => X + Y + (p.w + p.d) / 2 > ax + ay + .2 && Math.abs((X + p.w / 2 - Y - p.d / 2) - (ax - ay)) < r + (p.w + p.d) / 2 + .3 && X + Y - (ax + ay) < 3)) continue; parts.push({d: X + Y + (p.w + p.d) / 2, f: () => propDraw(c, t, p, X, Y, hotAt(X + p.w / 2, Y + p.d / 2, Math.max(p.w, p.d) / 2))});}
	if (R.place === id) charPart(c, t, R, parts, 0); crowd(c, t, parts, id); parts.sort((a, b) => a.d - b.d).forEach((q) => q.f());}
// this film's extra places: registered into the city when the project changes (slots come from the server)
let KIT_P = null; const KIT_IDS = [];
function useKits(P) {if (KIT_P === P) return; KIT_P = P; useMint(P.mint, FREG); SCEN = (P.scenery || []).filter((k) => FPROPS[k] || PDEF[k]).slice(0, 6);      // minted acts / objects / animals / worlds first (dio_mint.ts)
	const wid = WORLDS[P.world] ? P.world : 'city'; WORLD = {...WORLDS[wid], id: wid}; WALK_CACHE.id = '';
	USED_BUILTIN = wid === 'city' ? null : new Set((P.beats || []).map((b) => b && b.place).filter((k) => BUILTIN_LOT[k]));
	for (const id of KIT_IDS) {delete PL[id]; delete GUESTS[id]; delete REGULARS[id]; delete ANIM[id];} KIT_IDS.length = 0;
	for (const k of (P.kits || []).slice(0, 8)) {if (!k || !k.id || PL[k.id] || !Array.isArray(k.o)) continue; const st = {};
		for (const [n, s] of Object.entries(k.st || {})) if (Array.isArray(s) && Array.isArray(s[0])) st[n] = [[clamp(+s[0][0], .2, 3.8), clamp(+s[0][1], .2, 3.8)], s[1] === -1 ? -1 : 1, Array.isArray(s[2]) ? s[2].map(Number) : null];
		if (!st.center) st.center = [[2, 2.6], 1, null];
		PL[k.id] = {o: k.o, z: 0, door: k.door || [k.o[0] + 3.5, k.o[1] + 3.5], st, kit: {...k}};
		GUESTS[k.id] = (k.guests || []).filter((g) => Array.isArray(g)).slice(0, 5).map((g) => [clamp(+g[0], .2, 3.8), clamp(+g[1], .2, 3.8)]);
		REGULARS[k.id] = (k.regulars || []).filter((r) => Array.isArray(r) && GUESTS[k.id][r[0]]).slice(0, 4);
		ANIM[k.id] = (k.animals || []).filter((a) => Array.isArray(a) && SPECIES[a[0]]).slice(0, 6).map((a) => [a[0], clamp(+a[1], .2, 3.8), clamp(+a[2], .2, 3.8), a[3] || 'idle']); KIT_IDS.push(k.id);}
	buildLots(KIT_IDS.map((id) => PL[id].o[0] / 4 + ',' + PL[id].o[1] / 4));}


/* ── WORLDS (Oct 29 2026, user: "all the samples still happen in the city — make new worlds, the videos need other places").
   A film picks ONE world (P.world). The world sets the ground, the paths between lots, the sky (moon / sun / planet), what fills
   the empty lots (towers in the city, fields and barns in the countryside, dunes and cacti in the desert, craters and ruins on a
   battlefield …), who and what passes by, and the ambience. The story's places are kits (diorama_kits/*.json, tagged with their
   world); the six city built-ins are only drawn in the city or when the film uses them. ── */
const WP = ['rock', 'cactus', 'palm', 'pine', 'tent', 'campfire', 'fence', 'hay', 'barrel', 'crater', 'wire', 'sandbag', 'ruin', 'dome', 'rocket', 'flag', 'torch', 'well', 'cart', 'log',
	'hut', 'house', 'tower', 'wallc', 'snowman', 'parasol', 'crop', 'ship', 'fountain', 'stump', 'mushroom', 'dune', 'armor', 'stall', 'statue', 'iceberg', 'lighthouse', 'windmill', 'temple', 'bigtree'];
const WPDEF = {rock: [.6, .5, .45], cactus: [.3, .3, 1.4], palm: [.5, .5, 2.4], pine: [.8, .8, 2.2], tent: [1.4, 1.2, 1.1], campfire: [.6, .6, .2], fence: [2, .08, .5], hay: [.6, .8, .6], barrel: [.4, .4, .6],
	crater: [1.4, 1.4, 0], wire: [2, .2, .45], sandbag: [1.6, .4, .5], ruin: [1.6, 1.4, 1.8], dome: [1.6, 1.6, .9], rocket: [.6, .6, 3], flag: [.4, .1, 1.8], torch: [.12, .12, 1.3], well: [.8, .8, 1],
	cart: [1, .6, .6], log: [1.2, .3, .3], hut: [1.4, 1.2, 1.4], house: [1.8, 1.4, 2.2], tower: [1, 1, 3.4], wallc: [2.4, .4, 1.4], snowman: [.5, .5, 1.1], parasol: [.9, .9, 1.4], crop: [2, 1.6, .25],
	ship: [1.1, 3, 1], fountain: [1.2, 1.2, .9], stump: [.4, .4, .3], mushroom: [.3, .3, .3], dune: [2.4, 2, .7], armor: [1.4, 2, .9], stall: [1.2, .8, 1.5], statue: [.6, .6, 2], iceberg: [1.4, 1.4, 1.2],
	lighthouse: [.9, .9, 4], windmill: [1, 1, 2.6], temple: [2.4, 2.4, 2], bigtree: [1.4, 1.4, 3.4]};
const G = {olive: '#4B5340', olive2: '#6A7458', leaf: '#3E4A30', leaf2: '#5B6B3E', pine: '#23302A', pine2: '#35473C', snow: '#D8DCE2', snow2: '#F2F6FA', stone: '#5A5650', stone2: '#7A746A',
	sand: '#8C7348', sand2: '#B8986A', mud: '#2E2618', mud2: '#433826', wood: '#5A4024', wood2: '#7A5226', red: '#8A3A24', ember: '#E0703A', moon: '#3A3B40', moon2: '#5A5C62'};
function cone(c, x, y, z0, z1, r, a, b) {const p0 = S(x, y, z1), l = S(x - r, y + r, z0), rr2 = S(x + r, y - r, z0), q = S(x, y, z0); c.fillStyle = a; c.beginPath(); c.moveTo(p0[0], p0[1]); c.lineTo(l[0], l[1]);
	c.ellipse(q[0], q[1], r * 1.2247 * K, r * .7071 * K, 0, PI, 0, true); c.closePath(); c.fill(); c.fillStyle = b; c.beginPath(); c.moveTo(p0[0], p0[1]); c.lineTo(q[0], q[1] + r * .7071 * K); c.lineTo(S(x + r, y - r * .2, z0)[0], q[1]); c.closePath(); c.globalAlpha = .45; c.fill(); c.globalAlpha = 1;}
function roof(c, X, Y, w, d, z, h, col) {const m = Y + d / 2; poly(c, [[X, Y, z], [X + w, Y, z], [X + w, m, z + h], [X, m, z + h]], shade(col)); poly(c, [[X, Y + d, z], [X + w, Y + d, z], [X + w, m, z + h], [X, m, z + h]], col);
	poly(c, [[X + w, Y, z], [X + w, Y + d, z], [X + w, m, z + h]], shade(shade(col)));}
function worldProp(c, t, p, X, Y, hot, col) {const {w, d, h} = p, z = p.z || 0, cx = X + w / 2, cy = Y + d / 2, snowy = WORLD && WORLD.id === 'snow';
	switch (p.t) {
	case 'rock': {const q = S(cx, cy, h * .4), g = c.createRadialGradient(q[0] - .1 * K, q[1] - .15 * K, .02 * K, q[0], q[1], w * .7 * K); g.addColorStop(0, col || G.stone2); g.addColorStop(1, shade(col || G.stone)); c.fillStyle = g;
		c.beginPath(); c.ellipse(q[0], q[1], w * .62 * K, h * .7 * K, 0, PI * .95, PI * 2.05); c.lineTo(q[0] + w * .62 * K, q[1] + h * .3 * K); c.lineTo(q[0] - w * .62 * K, q[1] + h * .3 * K); c.fill(); if (snowy) {c.fillStyle = G.snow2; c.beginPath(); c.ellipse(q[0], q[1] - h * .45 * K, w * .45 * K, h * .2 * K, 0, 0, 7); c.fill();} return true;}
	case 'cactus': {const s = Math.sin(t * .6 + X) * .02; B3(c, cx - .08, cy - .08, cx + .08, cy + .08, 0, h, G.olive2); B3(c, cx - .26 + s, cy - .05, cx - .1, cy + .05, h * .45, h * .52, G.olive); B3(c, cx - .26 + s, cy - .05, cx - .18 + s, cy + .05, h * .52, h * .8, G.olive2);
		B3(c, cx + .1, cy - .05, cx + .26, cy + .05, h * .3, h * .37, G.olive); B3(c, cx + .18, cy - .05, cx + .26, cy + .05, h * .37, h * .62, G.olive2); return true;}
	case 'palm': {const sw = Math.sin(t * .9 + X * 3) * .08; c.strokeStyle = G.wood2; c.lineWidth = .1 * K; c.lineCap = 'round'; const a = S(cx, cy, 0), b = S(cx + .25 + sw, cy, h); c.beginPath(); c.moveTo(a[0], a[1]); c.quadraticCurveTo(a[0] + .1 * K, (a[1] + b[1]) / 2, b[0], b[1]); c.stroke();
		for (let i = 0; i < 7; i++) {const an = i / 7 * 2 * PI + sw; c.strokeStyle = i % 2 ? G.leaf2 : G.leaf; c.lineWidth = .09 * K; c.beginPath(); c.moveTo(b[0], b[1]); c.quadraticCurveTo(b[0] + Math.cos(an) * .5 * K, b[1] - .3 * K, b[0] + Math.cos(an) * .9 * K, b[1] + Math.sin(an) * .25 * K + .2 * K); c.stroke();}
		c.fillStyle = G.wood; c.beginPath(); c.arc(b[0], b[1] + .05 * K, .07 * K, 0, 7); c.fill(); return true;}
	case 'pine': {const tr = S(cx, cy, 0), tt = S(cx, cy, h * .25); c.fillStyle = G.wood; c.fillRect(tr[0] - .05 * K, tt[1], .1 * K, tr[1] - tt[1]);
		[[.2, .7, w * .55], [.45, .9, w * .42], [.68, 1.0, w * .28]].forEach(([a0, a1, r]) => {cone(c, cx, cy, h * a0, h * a1, r, G.pine2, G.pine); if (snowy) {const q = S(cx, cy, h * a1 - .02); c.fillStyle = G.snow2; c.beginPath(); c.ellipse(q[0], q[1] + .06 * K, r * .45 * K, .08 * K, 0, 0, 7); c.fill();}}); return true;}
	case 'bigtree': {const p0 = S(cx, cy, 0), p1 = S(cx, cy, h * .5); c.fillStyle = G.wood; c.fillRect(p0[0] - .12 * K, p1[1], .24 * K, p0[1] - p1[1]);
		[[0, 0, .75, .9], [-.35, .2, .62, .55], [.3, -.25, .8, .5], [.1, .15, .95, .5]].forEach(([dx, dy, zz, r]) => {const q = S(cx + dx, cy + dy, h * zz), g = c.createRadialGradient(q[0] - .2 * K, q[1] - .25 * K, .05 * K, q[0], q[1], r * K); g.addColorStop(0, G.leaf2); g.addColorStop(1, G.leaf); c.fillStyle = g; c.beginPath(); c.arc(q[0], q[1], r * K, 0, 7); c.fill();});
		if (hot) glow(c, cx, cy, h * .8, .5, .4); return true;}
	case 'tent': {const m = X + w / 2; poly(c, [[X, Y, 0], [X, Y + d, 0], [m, Y + d, h], [m, Y, h]], shade(col || G.olive2)); poly(c, [[X + w, Y, 0], [X + w, Y + d, 0], [m, Y + d, h], [m, Y, h]], col || G.olive2);
		poly(c, [[X, Y + d, 0], [X + w, Y + d, 0], [m, Y + d, h]], shade(shade(col || G.olive2))); poly(c, [[m - .18, Y + d + .005, 0], [m + .18, Y + d + .005, 0], [m, Y + d + .005, h * .55]], hot ? C.gold : '#1A1810'); return true;}
	case 'campfire': {[[-.2, .3], [.2, -.3]].forEach(([dx, a]) => B3(c, cx - .25, cy + dx * .3 - .04, cx + .25, cy + dx * .3 + .04, 0, .08, G.wood));
		for (let i = 0; i < 7; i++) {const q = frac(t * 1.8 + i / 7), pp = S(cx + Math.sin(i * 2 + t * 4) * .06 * (1 - q), cy, .1 + q * .8); c.fillStyle = `rgba(255,${190 - q * 120},60,${(1 - q) * .9})`; c.beginPath(); c.ellipse(pp[0], pp[1], (.12 * (1 - q) + .03) * K, (.18 * (1 - q) + .04) * K, 0, 0, 7); c.fill();}
		glow(c, cx, cy, .3, 1.6, .55 + .1 * Math.sin(t * 9)); return true;}
	case 'fence': {const along = w >= d, L = along ? w : d, pt = (u, zz) => S(along ? X + u * L : cx, along ? cy : Y + u * L, zz); c.strokeStyle = col || G.wood2; c.lineWidth = Math.max(2, .05 * K); c.lineCap = 'round';
		[h * .45, h * .85].forEach((zz) => {const a = pt(0, zz), b = pt(1, zz); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();}); for (let u = 0; u <= 1.001; u += .4 / L) {const a = pt(u, 0), b = pt(u, h); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();} return true;}
	case 'hay': cyl(c, cx, cy, 0, h, w / 2, C.champ); {const a = S(cx, cy, h); c.strokeStyle = C.brass; c.lineWidth = 1.5; c.beginPath(); c.ellipse(a[0], a[1], w / 2 * .7 * K, w / 2 * .4 * K, 0, 0, 7); c.stroke();} return true;
	case 'barrel': cyl(c, cx, cy, 0, h, w / 2, col || G.wood2); [.25, .75].forEach((f) => {const a = S(cx, cy, h * f); c.strokeStyle = C.steel2; c.lineWidth = Math.max(1, .03 * K); c.beginPath(); c.ellipse(a[0], a[1], w / 2 * 1.2247 * K, w / 2 * .7071 * K, 0, 0, PI); c.stroke();}); return true;
	case 'crater': {const q = S(cx, cy, 0); c.fillStyle = 'rgba(0,0,0,.45)'; c.beginPath(); c.ellipse(q[0], q[1], w / 2 * 1.2247 * K, d / 2 * .7071 * K, 0, 0, 7); c.fill(); c.strokeStyle = WORLD && WORLD.id === 'moon' ? G.moon2 : G.mud2; c.lineWidth = Math.max(2, .08 * K);
		c.beginPath(); c.ellipse(q[0], q[1] - .03 * K, w / 2 * 1.2247 * K, d / 2 * .7071 * K, 0, PI, 2 * PI); c.stroke(); if (WORLD && WORLD.id === 'war') for (let i = 0; i < 3; i++) {const s = frac(t * .15 + i / 3), pp = S(cx, cy, .2 + s * 1.4); c.fillStyle = `rgba(110,112,118,${.25 * (1 - s)})`; c.beginPath(); c.arc(pp[0], pp[1], (.2 + s * .5) * K, 0, 7); c.fill();} return true;}
	case 'wire': {const along = w >= d, L = along ? w : d; c.strokeStyle = C.silver; c.lineWidth = Math.max(1, .015 * K); for (let i = 0; i < L * 6; i++) {const u = i / (L * 6), q = S(along ? X + u * L : cx, along ? cy : Y + u * L, h * .5); c.beginPath(); c.ellipse(q[0], q[1], .1 * K, h * .45 * K, .3, 0, 7); c.stroke();}
		for (let u = 0; u <= 1.001; u += .5 / L) {const a = S(along ? X + u * L : cx, along ? cy : Y + u * L, 0), b = S(along ? X + u * L : cx, along ? cy : Y + u * L, h); c.strokeStyle = G.wood; c.lineWidth = Math.max(2, .04 * K); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();} return true;}
	case 'sandbag': {const along = w >= d, L = along ? w : d; for (let r = 0; r < 3; r++) for (let u = 0; u < L - .1; u += .34) {const q = S(along ? X + u + .17 + (r % 2) * .17 : cx, along ? cy : Y + u + .17 + (r % 2) * .17, r * h / 3 + .08); c.fillStyle = r % 2 ? '#8E7A55' : '#7A6848'; c.beginPath(); c.ellipse(q[0], q[1], .2 * K, .1 * K, 0, 0, 7); c.fill();} return true;}
	case 'ruin': {B3(c, X, Y, X + w, Y + d, 0, h * .55, col || C.graph2); const jag = [[X, Y + d, h * .55], [X + w * .2, Y + d, h * .9], [X + w * .35, Y + d, h * .6], [X + w * .55, Y + d, h], [X + w * .7, Y + d, h * .5], [X + w, Y + d, h * .75], [X + w, Y + d, h * .55]];
		poly(c, [...jag, [X + w, Y + d, h * .5], [X, Y + d, h * .5]], C.graph); for (let i = 0; i < 4; i++) poly(c, [[X + .2 + i * .36, Y + d + .005, .5], [X + .4 + i * .36, Y + d + .005, .5], [X + .4 + i * .36, Y + d + .005, .85], [X + .2 + i * .36, Y + d + .005, .85]], '#0B0B0D');
		if (WORLD && WORLD.id === 'war') {const pp = S(X + w * .5, Y + d * .5, h * .7); for (let i = 0; i < 4; i++) {const s = frac(t * .3 + i / 4); c.fillStyle = `rgba(255,${130 + s * 60},60,${(1 - s) * .5})`; c.beginPath(); c.arc(pp[0] + Math.sin(i * 3) * .2 * K, pp[1] - s * .8 * K, (.12 + s * .1) * K, 0, 7); c.fill();}} return true;}
	case 'dome': {const r = w / 2, q = S(cx, cy, 0), g = c.createRadialGradient(q[0] - r * .4 * K, q[1] - r * .9 * K, .05 * K, q[0], q[1] - r * .3 * K, r * 1.3 * K); g.addColorStop(0, C.silver2); g.addColorStop(1, C.steel); c.fillStyle = g;
		c.beginPath(); c.ellipse(q[0], q[1], r * 1.2247 * K, r * .7071 * K, 0, 0, PI); c.ellipse(q[0], q[1], r * 1.2247 * K, h * K, 0, PI, 2 * PI); c.fill(); for (let i = 0; i < 5; i++) {c.fillStyle = frac(t * .5 + i * .3) > .3 ? C.gold : C.brass; c.beginPath(); c.arc(q[0] + (i - 2) * r * .4 * K, q[1] - h * .35 * K, .05 * K, 0, 7); c.fill();} return true;}
	case 'rocket': {cyl(c, cx, cy, .3, h * .8, w / 2, C.silver2); cone(c, cx, cy, h * .8, h, w / 2, C.silver, C.steel); [[-1, 0], [1, 0], [0, 1]].forEach(([a, b]) => B3(c, cx + a * w * .45, cy + b * w * .45, cx + a * w * .45 + .06, cy + b * w * .45 + .06, 0, h * .3, C.ember));
		const wq = S(cx, cy + w / 2, h * .6); c.fillStyle = C.gold; c.beginPath(); c.arc(wq[0], wq[1], .08 * K, 0, 7); c.fill(); if (hot) for (let i = 0; i < 6; i++) {const s = frac(t * 3 + i / 6), pp = S(cx, cy, .3 - s * .3); c.fillStyle = `rgba(255,${200 - s * 120},80,${1 - s})`; c.beginPath(); c.arc(pp[0] + Math.sin(i) * s * .3 * K, pp[1] + s * .3 * K, (.1 + s * .3) * K, 0, 7); c.fill();} return true;}
	case 'flag': {const a = S(cx, cy, 0), b = S(cx, cy, h); c.strokeStyle = C.silver; c.lineWidth = Math.max(1.5, .03 * K); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); c.fillStyle = col || C.gold; c.beginPath(); c.moveTo(b[0], b[1]);
		for (let i = 0; i <= 8; i++) {const u = i / 8; c.lineTo(b[0] + u * .7 * K, b[1] + Math.sin(u * 6 - t * 5) * .06 * K + u * .04 * K);} for (let i = 8; i >= 0; i--) {const u = i / 8; c.lineTo(b[0] + u * .7 * K, b[1] + .4 * K + Math.sin(u * 6 - t * 5) * .06 * K);} c.closePath(); c.fill(); return true;}
	case 'torch': B3(c, cx - .03, cy - .03, cx + .03, cy + .03, 0, h, G.wood); {for (let i = 0; i < 5; i++) {const q = frac(t * 2.2 + i / 5), pp = S(cx, cy, h + q * .4); c.fillStyle = `rgba(255,${190 - q * 100},60,${1 - q})`; c.beginPath(); c.ellipse(pp[0], pp[1], .06 * (1 - q) * K + 2, .1 * (1 - q) * K + 3, 0, 0, 7); c.fill();} glow(c, cx, cy, h + .1, 1, .6);} return true;
	case 'well': cyl(c, cx, cy, 0, .55, w * .42, G.stone2); [[-1], [1]].forEach(([a]) => B3(c, cx + a * w * .38, cy - .03, cx + a * w * .38 + .05, cy + .03, .55, h, G.wood)); roof(c, X, Y + d * .2, w, d * .6, h, .3, G.red); return true;
	case 'cart': B3(c, X, Y, X + w, Y + d, .25, .5, G.wood2); [[X + .15, Y + d], [X + w - .15, Y + d]].forEach(([a, b]) => {const q = S(a, b, .2); c.strokeStyle = G.wood; c.lineWidth = Math.max(2, .05 * K); c.beginPath(); c.ellipse(q[0], q[1], .22 * K, .22 * K, 0, 0, 7); c.stroke();}); if (p.load !== false) B3(c, X + .1, Y + .1, X + w * .5, Y + d - .1, .5, .8, C.champ); return true;
	case 'log': (w >= d ? B3(c, X, cy - .14, X + w, cy + .14, 0, .28, G.wood2) : B3(c, cx - .14, Y, cx + .14, Y + d, 0, .28, G.wood2)); return true;
	case 'stump': cyl(c, cx, cy, 0, h, w / 2, G.wood2); {const a = S(cx, cy, h); c.fillStyle = C.champ; c.beginPath(); c.ellipse(a[0], a[1], w / 2 * 1.1 * K, w / 2 * .6 * K, 0, 0, 7); c.fill();} return true;
	case 'mushroom': B3(c, cx - .03, cy - .03, cx + .03, cy + .03, 0, h * .7, C.pale); {const a = S(cx, cy, h * .7); c.fillStyle = C.ember; c.beginPath(); c.ellipse(a[0], a[1], w * .7 * K, w * .35 * K, 0, PI, 0); c.fill(); c.fillStyle = C.pale; c.beginPath(); c.arc(a[0] - .04 * K, a[1] - .06 * K, .02 * K, 0, 7); c.fill(); if (hot || WORLD && WORLD.id === 'forest') glow(c, cx, cy, h, .3, .3);} return true;
	case 'hut': case 'house': {const wall = col || (p.t === 'hut' ? G.wood2 : (WORLD && WORLD.id === 'medieval' ? C.champ : C.silver)), hh = h * .55; B3(c, X, Y, X + w, Y + d, 0, hh, wall); roof(c, X - .05, Y - .05, w + .1, d + .1, hh, h - hh, p.t === 'hut' ? C.brass : G.red);
		const lit = hot || hash(X * 7 + Y) > .3; poly(c, [[X + w * .2, Y + d + .005, hh * .35], [X + w * .38, Y + d + .005, hh * .35], [X + w * .38, Y + d + .005, hh * .7], [X + w * .2, Y + d + .005, hh * .7]], lit ? C.gold : '#141518');
		poly(c, [[X + w * .55, Y + d + .005, 0], [X + w * .75, Y + d + .005, 0], [X + w * .75, Y + d + .005, hh * .7], [X + w * .55, Y + d + .005, hh * .7]], G.wood); if (snowy) poly(c, [[X - .05, Y + d / 2, h + .02], [X + w + .05, Y + d / 2, h + .02], [X + w + .05, Y + d * .75, h - (h - hh) * .5], [X - .05, Y + d * .75, h - (h - hh) * .5]], G.snow2); return true;}
	case 'tower': cyl(c, cx, cy, 0, h, w / 2, col || G.stone2); for (let i = 0; i < 6; i++) {const an = i / 6 * PI, q = S(cx + Math.cos(an) * w * .45, cy + Math.sin(an) * w * .45, h); B3(c, cx + Math.cos(an) * w * .42 - .06, cy + Math.sin(an) * w * .42 - .06, cx + Math.cos(an) * w * .42 + .06, cy + Math.sin(an) * w * .42 + .06, h, h + .2, G.stone);}
		{const q = S(cx, cy + w / 2, h * .6); c.fillStyle = hot || frac(t * .3) > .2 ? C.gold : C.brass; c.fillRect(q[0] - .05 * K, q[1] - .12 * K, .1 * K, .2 * K);} return true;
	case 'wallc': {const along = w >= d; B3(c, X, Y, X + w, Y + d, 0, h, col || G.stone2); const L = along ? w : d; for (let u = 0; u < L - .1; u += .4) B3(c, along ? X + u : X, along ? Y : Y + u, along ? X + u + .2 : X + w, along ? Y + d : Y + u + .2, h, h + .2, G.stone); return true;}
	case 'snowman': [[.0, .22], [.36, .16], [.62, .11]].forEach(([zz, r]) => {const q = S(cx, cy, zz + r), g = c.createRadialGradient(q[0] - r * .4 * K, q[1] - r * .4 * K, 1, q[0], q[1], r * 1.2 * K); g.addColorStop(0, C.white); g.addColorStop(1, C.silver); c.fillStyle = g; c.beginPath(); c.arc(q[0], q[1], r * 1.2 * K, 0, 7); c.fill();});
		{const q = S(cx, cy, .73); c.fillStyle = C.ember; c.beginPath(); c.moveTo(q[0], q[1]); c.lineTo(q[0] + .15 * K, q[1] + .02 * K); c.lineTo(q[0], q[1] + .04 * K); c.fill(); B3(c, cx - .08, cy - .08, cx + .08, cy + .08, .82, 1.0, C.char0);} return true;
	case 'parasol': {const a = S(cx, cy, 0), b = S(cx, cy, h); c.strokeStyle = C.silver; c.lineWidth = Math.max(1.5, .03 * K); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();
		for (let i = 0; i < 8; i++) {const a0 = i / 8 * 2 * PI, a1 = (i + 1) / 8 * 2 * PI; c.fillStyle = i % 2 ? (col || C.gold) : C.pale; c.beginPath(); c.moveTo(b[0], b[1] - .12 * K); c.lineTo(b[0] + Math.cos(a0) * w * .7 * K, b[1] + Math.sin(a0) * w * .4 * K); c.lineTo(b[0] + Math.cos(a1) * w * .7 * K, b[1] + Math.sin(a1) * w * .4 * K); c.closePath(); c.fill();} return true;}
	case 'crop': for (let r = 0; r < d / .25; r++) for (let u = 0; u < w / .2; u++) {const q = S(X + u * .2 + .1, Y + r * .25 + .12, 0), sw = Math.sin(t * 1.5 + u * .4 + r) * .02 * K; c.strokeStyle = (r + u) % 3 ? G.leaf2 : C.brass; c.lineWidth = Math.max(1.5, .03 * K); c.beginPath(); c.moveTo(q[0], q[1]); c.lineTo(q[0] + sw, q[1] - h * K); c.stroke();} return true;
	case 'ship': {const z0 = .02 + Math.sin(t * 1.2 + X) * .03; poly(c, [[X, Y, z0 + .5], [X + w, Y, z0 + .5], [X + w, Y + d * .8, z0 + .5], [cx, Y + d, z0 + .5], [X, Y + d * .8, z0 + .5]], metal(c, S(X, Y, .5), S(X + w, Y + d, .5), G.wood, G.wood2));
		poly(c, [[X + w, Y, z0], [X + w, Y + d * .8, z0], [cx, Y + d, z0], [cx, Y + d, z0 + .5], [X + w, Y + d * .8, z0 + .5], [X + w, Y, z0 + .5]], C.char1);
		[[.3, 2.4], [.65, 2.0]].forEach(([u, hh]) => {const a = S(cx, Y + u * d, z0 + .5), b = S(cx, Y + u * d, z0 + .5 + hh); c.strokeStyle = G.wood; c.lineWidth = Math.max(2, .05 * K); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke();
			c.fillStyle = C.pale; c.beginPath(); c.moveTo(b[0], b[1] + .1 * K); c.quadraticCurveTo(b[0] + .5 * K + Math.sin(t) * .05 * K, (a[1] + b[1]) / 2, a[0], a[1] - .3 * K); c.lineTo(b[0], b[1] + .1 * K); c.fill();}); return true;}
	case 'fountain': cyl(c, cx, cy, 0, .35, w / 2, G.stone2); {const a = S(cx, cy, .36); c.fillStyle = '#2A3F4C'; c.beginPath(); c.ellipse(a[0], a[1], w / 2 * 1.1 * K, w / 2 * .6 * K, 0, 0, 7); c.fill(); B3(c, cx - .06, cy - .06, cx + .06, cy + .06, .35, h, G.stone2);
		for (let i = 0; i < 8; i++) {const q = frac(t * 1.2 + i / 8), an = i / 8 * 2 * PI, pp = S(cx + Math.cos(an) * q * w * .4, cy + Math.sin(an) * q * w * .4, h + Math.sin(q * PI) * .3 - q * .3); c.fillStyle = 'rgba(216,220,226,.7)'; c.beginPath(); c.arc(pp[0], pp[1], .03 * K, 0, 7); c.fill();}} return true;
	case 'dune': {const q = S(cx, cy, 0), g = c.createLinearGradient(q[0], q[1] - h * K, q[0], q[1] + d * .3 * K); g.addColorStop(0, G.sand2); g.addColorStop(1, G.sand); c.fillStyle = g; c.beginPath(); c.ellipse(q[0], q[1], w * .62 * K, h * K, 0, PI, 0); c.ellipse(q[0], q[1], w * .62 * K, d * .3 * K, 0, 0, PI); c.fill();
		c.strokeStyle = 'rgba(255,243,220,.25)'; c.lineWidth = 1.5; c.beginPath(); c.moveTo(q[0] - w * .4 * K, q[1] - h * .2 * K); c.quadraticCurveTo(q[0], q[1] - h * 1.1 * K, q[0] + w * .3 * K, q[1] - h * .3 * K); c.stroke(); return true;}
	case 'armor': {box3(c, X, Y, X + w, Y + d, .15, h * .55, metal(c, S(X, Y, h * .55), S(X + w, Y + d, h * .55), G.olive2, G.olive), G.olive, '#3C4333'); B3(c, X + .2, Y + d * .3, X + w - .2, Y + d * .7, h * .55, h, G.olive2);
		const a = S(cx, Y + d * .5, h * .8), b = S(cx, Y + d + .6, h * .85); c.strokeStyle = G.olive; c.lineWidth = .1 * K; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); for (let i = 0; i < 4; i++) {const q = S(X + w + .01, Y + .3 + i * (d - .6) / 3, .15); c.fillStyle = C.char0; c.beginPath(); c.arc(q[0], q[1], .13 * K, 0, 7); c.fill();} return true;}
	case 'stall': B3(c, X, Y, X + w, Y + d, 0, .9, G.wood2); [[X, Y], [X + w - .05, Y]].forEach(([a, b]) => B3(c, a, b, a + .05, b + .05, .9, h, G.wood)); poly(c, [[X - .05, Y - .05, h], [X + w + .05, Y - .05, h], [X + w + .05, Y + d + .2, h - .25], [X - .05, Y + d + .2, h - .25]], col || C.ember);
		for (let i = 0; i < 4; i++) {const q = S(X + .2 + i * (w - .3) / 3, Y + d * .5, .95); c.fillStyle = [C.gold, C.ember, C.champ, G.leaf2][i]; c.beginPath(); c.arc(q[0], q[1], .08 * K, 0, 7); c.fill();} return true;
	case 'statue': B3(c, X, Y, X + w, Y + d, 0, .5, G.stone2); {const q = S(cx, cy, .5), sc2 = (h - .5) * K / 400; c.save(); c.globalAlpha = .95; person(c, t * 0, q[0], q[1], sc2, 0, {...rigFor(0, lookOf({color: 'gold', outfit: 'robe'}), 'point', 0, 1, false, 'calm', .6), face: {o: 0, b: 0, f: 0, m: 0}}); c.restore();} return true;
	case 'iceberg': {const q = S(cx, cy, 0); c.fillStyle = C.silver2; c.beginPath(); c.moveTo(q[0] - w * .6 * K, q[1]); c.lineTo(q[0] - w * .3 * K, q[1] - h * .8 * K); c.lineTo(q[0] - .05 * K, q[1] - h * K); c.lineTo(q[0] + w * .3 * K, q[1] - h * .6 * K); c.lineTo(q[0] + w * .6 * K, q[1]); c.closePath(); c.fill();
		c.fillStyle = C.silver; c.beginPath(); c.moveTo(q[0] - .05 * K, q[1] - h * K); c.lineTo(q[0] + w * .3 * K, q[1] - h * .6 * K); c.lineTo(q[0] + w * .6 * K, q[1]); c.lineTo(q[0], q[1]); c.closePath(); c.fill(); return true;}
	case 'lighthouse': {cyl(c, cx, cy, 0, h * .85, w * .4, C.silver2); [.2, .5].forEach((f) => {const a = S(cx, cy, h * f); c.strokeStyle = G.red; c.lineWidth = .18 * K; c.beginPath(); c.ellipse(a[0], a[1] - .1 * K, w * .4 * 1.2247 * K, w * .4 * .7071 * K, 0, 0, PI); c.stroke();});
		B3(c, cx - .2, cy - .2, cx + .2, cy + .2, h * .85, h, C.char1); glow(c, cx, cy, h * .93, 1.4, .8); const a = S(cx, cy, h * .93), an = t * 1.2; c.fillStyle = 'rgba(255,243,220,.14)'; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(a[0] + Math.cos(an) * 8 * K, a[1] + Math.sin(an) * 2 * K - .5 * K); c.lineTo(a[0] + Math.cos(an) * 8 * K, a[1] + Math.sin(an) * 2 * K + .5 * K); c.fill(); return true;}
	case 'windmill': {cyl(c, cx, cy, 0, h * .8, w * .4, C.champ); cone(c, cx, cy, h * .8, h, w * .45, G.red, shade(G.red)); const a = S(cx, cy + w * .45, h * .75); c.strokeStyle = G.wood; c.lineWidth = .06 * K;
		for (let i = 0; i < 4; i++) {const an = t * .8 + i * PI / 2; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(a[0] + Math.cos(an) * 1.1 * K, a[1] + Math.sin(an) * 1.1 * K); c.stroke(); c.fillStyle = 'rgba(242,212,155,.8)'; c.save(); c.translate(a[0], a[1]); c.rotate(an); c.fillRect(.3 * K, 0, .8 * K, .18 * K); c.restore();} return true;}
	case 'temple': {B3(c, X, Y, X + w, Y + d, 0, .3, G.stone); B3(c, X + .25, Y + .25, X + w - .25, Y + d - .25, .3, .6, G.stone2); B3(c, X + .5, Y + .5, X + w - .5, Y + d - .5, .6, h * .8, G.stone);
		poly(c, [[X + w * .42, Y + d - .5 + .005, .6], [X + w * .58, Y + d - .5 + .005, .6], [X + w * .58, Y + d - .5 + .005, h * .55], [X + w * .42, Y + d - .5 + .005, h * .55]], hot ? C.gold : '#0B0B0D'); [.2, .7].forEach((u) => blob(c, X + u * w, Y + d - .2, .7, .3, false)); return true;}
	}
	if (FPROPS[p.t]) {const q = S(cx, cy, z); c.save(); c.translate(q[0], q[1]); c.scale(K / 100, K / 100); drawArt(c, FPROPS[p.t], t, X * 3 + Y); c.restore(); return true;}     // a minted scenery prop (billboard)
	return false;}
FLOOR_KINDS.mud = [G.mud, G.mud2]; FLOOR_KINDS.snow = ['#8E959F', '#B7BDC6']; FLOOR_KINDS.dirt = ['#3A2C1A', '#4E3C24']; FLOOR_KINDS.cobble = ['#2E2A24', '#3E3830']; FLOOR_KINDS.moon = [G.moon, G.moon2]; FLOOR_KINDS.ice = ['#5E6E7C', '#8E9EAC']; FLOOR_KINDS.leaf = ['#18241A', '#24331F']; FLOOR_KINDS.deck = [G.wood, G.wood2];
WP.forEach((k) => {if (!PROP_TYPES.includes(k)) PROP_TYPES.push(k); PDEF[k] = WPDEF[k];});

/* the worlds. fill = what grows on an empty lot (weighted list of lot recipes) · walk = passers-by (people looks and/or animals) */
export const WORLDS = {
	city: {name: 'Night city', about: 'a tiny isometric night city: towers, streets, an apartment, an office, a lab, a cafe, a rooftop', ground: '#0F1013', lot: C.char1, edge: 'rgba(184,134,46,.18)', sky: [C.char0, C.char1, '#1B1712'], haze: 'rgba(255,181,71,.16)', moon: false, stars: 70, fill: ['tower'], walk: {people: 14}, floor: 'concrete'},
	countryside: {name: 'Countryside', about: 'farmland at dusk: fields, barns, hay, fences, windmills, a farmhouse, cows and chickens', ground: '#1A2116', lot: '#222B1C', edge: 'rgba(184,134,46,.14)', path: '#3A2C1A', sky: ['#121726', '#2E2A36', '#6A4428'], haze: 'rgba(255,140,60,.22)', sun: true, stars: 20,
		fill: ['field', 'field', 'field', 'farm', 'trees', 'trees', 'hay', 'windmill', 'pond'], walk: {people: 4, look: {outfit: 'overalls', hat: 'cowboy'}, animals: ['cow', 'sheep', 'chicken', 'horse', 'dog']}, floor: 'grass'},
	forest: {name: 'Forest', about: 'a deep forest at night: tall pines, a river, a campsite, a cabin, logs, mushrooms, fireflies, deer and owls', ground: '#101810', lot: '#152016', edge: 'rgba(184,134,46,.10)', path: '#2E2418', sky: ['#070B0E', '#0E1814', '#1A2418'], haze: 'rgba(160,190,120,.10)', moon: true, stars: 60,
		fill: ['pines', 'pines', 'pines', 'trees', 'rocks', 'clearing'], walk: {people: 2, look: {outfit: 'coat', color: 'olive'}, animals: ['deer', 'fox', 'rabbit', 'wolf', 'owl']}, amb: 'fireflies', floor: 'leaf'},
	beach: {name: 'Beach & coast', about: 'a sunset coast: sand, the sea, palm trees, parasols, a pier, a lighthouse, boats, gulls', ground: '#3A3122', lot: '#4A3C26', edge: 'rgba(255,243,220,.12)', path: '#5A4A30', sky: ['#1A1A2E', '#4A2E3A', '#C46A3A'], haze: 'rgba(255,150,70,.3)', sun: true, stars: 0, water: 'edge',
		fill: ['beach', 'beach', 'palms', 'beach', 'lighthouse'], walk: {people: 8, look: {outfit: 'tshirt'}, animals: ['pigeon', 'dog']}, floor: 'sand'},
	desert: {name: 'Desert', about: 'a desert at golden hour: dunes, cacti, rocks, an oasis, tents, camels', ground: '#3A2C1A', lot: '#45341E', edge: 'rgba(255,243,220,.10)', path: '#5A4630', sky: ['#1A1420', '#5A3424', '#D88A3A'], haze: 'rgba(255,170,80,.35)', sun: true, stars: 10,
		fill: ['dunes', 'dunes', 'cacti', 'rocks', 'camp'], walk: {people: 2, look: {outfit: 'robe', color: 'champagne'}, animals: ['camel', 'snake']}, floor: 'sand'},
	snow: {name: 'Snowy mountains', about: 'snowy mountains in winter: pines under snow, a ski lodge, cabins, frozen lake, snowmen, wolves', ground: '#7E858F', lot: '#9AA1AA', edge: 'rgba(255,255,255,.2)', path: '#6B717C', sky: ['#0E1220', '#22283A', '#4A5468'], haze: 'rgba(200,215,235,.18)', moon: true, stars: 50,
		fill: ['pines', 'pines', 'cabins', 'rocks', 'snowmen', 'lake'], walk: {people: 4, look: {outfit: 'coat', hat: 'beanie', color: 'ember'}, animals: ['wolf', 'deer', 'penguin']}, amb: 'snow', floor: 'snow'},
	war: {name: 'Battlefield', about: 'a war-torn battlefield: trenches, craters, ruins, barbed wire, sandbags, tanks, smoke and distant flashes', ground: '#1A1610', lot: '#211C14', edge: 'rgba(255,140,60,.12)', path: '#2E2618', sky: ['#0B0B0D', '#1E1A16', '#4A2A18'], haze: 'rgba(255,120,50,.22)', stars: 0,
		fill: ['ruins', 'craters', 'trench', 'ruins', 'armor', 'craters'], walk: {people: 8, look: {outfit: 'military', hat: 'helmet'}, act: 'march'}, amb: 'war', floor: 'mud'},
	moon: {name: 'Moon base', about: 'the surface of the moon: grey dust, craters, domes, a rocket, antennas, flags, Earth in the black sky, astronauts', ground: '#26272B', lot: '#303136', edge: 'rgba(216,220,226,.12)', path: '#3A3B40', sky: ['#000000', '#05060A', '#0B0D14'], planet: true, stars: 160,
		fill: ['craters', 'domes', 'rocks', 'craters', 'rocket'], walk: {people: 4, look: {outfit: 'space'}, slow: true}, floor: 'moon'},
	medieval: {name: 'Medieval kingdom', about: 'a medieval town at night: cottages, a castle with towers and walls, a market, a well, torches, horses, knights and villagers', ground: '#1E1A16', lot: '#26211B', edge: 'rgba(184,134,46,.16)', path: '#3A3028', sky: ['#0A0C14', '#161A26', '#2A2418'], haze: 'rgba(255,160,70,.14)', moon: true, stars: 70,
		fill: ['village', 'village', 'castle', 'market', 'trees'], walk: {people: 8, look: {outfit: 'robe', color: 'bronze'}, animals: ['horse', 'chicken', 'dog']}, floor: 'cobble'},
	jungle: {name: 'Jungle', about: 'a steamy jungle: giant trees, a river, ancient temple ruins, vines, monkeys, parrots, tigers, snakes', ground: '#111A12', lot: '#162418', edge: 'rgba(184,134,46,.10)', path: '#2E2418', sky: ['#081010', '#10201A', '#2A3A20'], haze: 'rgba(180,220,120,.12)', moon: true, stars: 20,
		fill: ['jungle', 'jungle', 'temple', 'jungle', 'river'], walk: {people: 1, look: {outfit: 'tshirt', color: 'olive', hat: 'cowboy'}, animals: ['monkey', 'parrot', 'tiger', 'snake', 'frog']}, amb: 'fireflies', floor: 'leaf'},
	ocean: {name: 'Open ocean', about: 'the open sea: islands with palms, ships, a lighthouse, icebergs, whales and sharks', ground: '#16242E', lot: '#1A2833', edge: 'rgba(216,220,226,.08)', path: '#16242E', sky: ['#0A1018', '#16243A', '#3A4A5A'], haze: 'rgba(160,200,230,.16)', moon: true, stars: 50, water: 'all',
		fill: ['island', 'ships', 'sea', 'sea', 'island', 'icebergs'], walk: {animals: ['shark', 'whale', 'fish'], swim: true}, floor: 'water'},
};
export const WORLD_IDS = Object.keys(WORLDS);
const FPROPS = {}, FREG = {ACTS, ITEMS, HATS, PIECES, SPECIES, WORLDS, prop: (id, D) => {FPROPS[id] = D; PDEF[id] = [+D.w || 1, +D.d || 1, +D.h || 1]; if (!PROP_TYPES.includes(id)) PROP_TYPES.push(id);}};
let WORLD = {...WORLDS.city, id: 'city'};
function useWorld(id) {const w = WORLDS[id] ? id : 'city'; if (WORLD.id !== w) {WORLD = {...WORLDS[w], id: w}; buildLots(KIT_IDS.map((k) => PL[k].o[0] / 4 + ',' + PL[k].o[1] / 4)); WALK_CACHE.id = '';}}
/* what one empty lot holds in this world: a list of props in lot coordinates (stable per lot seed) */
const LOT_CACHE = {};
let SCEN = [];      // scenery the narration mentions (minted props): some empty lots show it
function lotRecipe(b) {const key = WORLD.id + ':' + b.seed + ':' + SCEN.join(','); if (LOT_CACHE[key]) return LOT_CACHE[key];
	const h = (n) => hash(b.seed * 3.1 + n), r = WORLD.fill[Math.floor(h(1) * WORLD.fill.length)], P = [], add = (t, x, y, o) => P.push({t, x, y, ...(PDEF[t] ? {w: PDEF[t][0], d: PDEF[t][1], h: PDEF[t][2]} : {}), ...(o || {})});
	const scatter = (t, n, o) => {for (let i = 0; i < n; i++) add(t, .2 + h(10 + i) * 2.3, .2 + h(30 + i) * 2.3, o);};
	let floor = WORLD.floor;
	if (WORLD.water === 'edge' && (b.x === 0 || b.y === 0)) {floor = 'water'; if (h(2) > .6) add('ship', 1, .2); else if (h(2) > .4) add('boat', 1.2, .6);}
	else if (r === 'field') {floor = 'dirt'; add('crop', .2, .2, {w: 2.6, d: 2.6}); if (h(3) > .5) add('fence', 0, 2.9, {w: 3}); if (h(4) > .6) add('hay', 2.3, 2.3);}
	else if (r === 'farm') {add('house', .5, .4, {w: 2, d: 1.5, h: 2.4, col: G.red}); add('hay', 2.3, 2.2); add('fence', 0, 2.95, {w: 3}); add('cart', .6, 2.2);}
	else if (r === 'trees') scatter('tree', 3 + Math.floor(h(5) * 3), {w: .8, h: 1.8 + h(6)});
	else if (r === 'hay') {scatter('hay', 4); add('fence', 0, 0, {w: 3});}
	else if (r === 'windmill') {add('windmill', 1, 1); scatter('bush', 2);}
	else if (r === 'pond' || r === 'lake') {add('patch', .3, .3, {kind: r === 'lake' ? 'ice' : 'water', w: 2.4, d: 2.2}); scatter(r === 'lake' ? 'rock' : 'bush', 3);}
	else if (r === 'pines') scatter('pine', 4 + Math.floor(h(5) * 3), {w: .7 + h(7) * .4, h: 1.8 + h(8) * 1.2});
	else if (r === 'rocks') {scatter('rock', 3 + Math.floor(h(5) * 3), {w: .5 + h(9) * .5}); if (WORLD.id !== 'moon') scatter(WORLD.id === 'desert' ? 'cactus' : 'pine', 1);}
	else if (r === 'clearing') {add('campfire', 1.3, 1.3); add('log', .6, .8); add('tent', 1.8, .3); scatter('mushroom', 3);}
	else if (r === 'beach') {scatter('parasol', 2, {col: h(11) > .5 ? C.gold : G.red}); add('patch', 1.6, .9, {kind: 'sand', w: .5, d: .9}); scatter('palm', 1);}
	else if (r === 'palms') scatter('palm', 3 + Math.floor(h(5) * 2), {h: 2 + h(6)});
	else if (r === 'lighthouse') {add('lighthouse', 1, 1); scatter('rock', 3);}
	else if (r === 'dunes') {add('dune', .2, .3); if (h(5) > .4) add('dune', 1.2, 1.4, {w: 1.8, h: .5}); if (h(6) > .5) add('cactus', 2.4, .4);}
	else if (r === 'cacti') {scatter('cactus', 4, {h: .9 + h(7) * .9}); scatter('rock', 2);}
	else if (r === 'camp') {add('tent', .3, .3, {col: C.champ}); add('campfire', 1.9, 1.5); add('barrel', 2.4, .4);}
	else if (r === 'cabins') {add('hut', .6, .6, {w: 1.6, d: 1.4, h: 1.7}); scatter('pine', 2);}
	else if (r === 'snowmen') {scatter('snowman', 2); scatter('pine', 2);}
	else if (r === 'ruins') {add('ruin', .3, .3, {h: 1.2 + h(5) * 1.5}); add('sandbag', .3, 2.4, {w: 2}); scatter('rock', 2);}
	else if (r === 'craters') {floor = WORLD.floor; scatter('crater', 2 + Math.floor(h(5) * 2), {w: .8 + h(6) * .8, d: .8 + h(6) * .8}); scatter('rock', 2); if (WORLD.id === 'war' && h(7) > .5) add('wire', .1, 2.6, {w: 2.8});}
	else if (r === 'trench') {add('patch', .2, 1.1, {kind: 'mud', w: 2.6, d: .7}); add('sandbag', .2, .8, {w: 2.6}); add('wire', .2, .2, {w: 2.6}); add('flag', 2.5, 2.4, {col: G.red});}
	else if (r === 'armor') {add('armor', .6, .5); add('crater', 2, 2.2); add('barrel', .3, 2.4);}
	else if (r === 'domes') {add('dome', .4, .4); if (h(5) > .4) add('dome', 1.8, 1.8, {w: 1, d: 1, h: .55}); add('dish', 2.3, .4); add('flag', .4, 2.4, {col: C.gold});}
	else if (r === 'rocket') {add('rocket', 1.2, 1.2); scatter('crater', 2, {w: .7, d: .7});}
	else if (r === 'village') {add('house', .3, .3, {w: 1.4, d: 1.2, h: 2}); add('house', 1.6, 1.6, {w: 1.2, d: 1.1, h: 1.8}); add('torch', 2.7, .3); if (h(5) > .5) add('well', .4, 2.2);}
	else if (r === 'castle') {add('tower', .2, .2); add('wallc', 1.2, .4, {w: 1.8}); add('tower', 2.1, 2.1, {w: .8, d: .8, h: 2.8}); add('wallc', .4, 1.2, {w: .4, d: 1.8}); add('flag', .5, .5, {z: 3.4, col: G.red});}
	else if (r === 'market') {add('stall', .3, .4); add('stall', 1.8, .4, {col: C.gold}); add('fountain', 1, 1.8); add('cart', 2.1, 2.3);}
	else if (r === 'jungle') {add('bigtree', .4, .4, {h: 2.8 + h(5)}); scatter('palm', 1); scatter('bush', 3, {w: .7}); if (h(6) > .5) add('bigtree', 1.9, 1.8, {w: 1, h: 2.4});}
	else if (r === 'temple') {add('temple', .3, .3); scatter('bush', 2);}
	else if (r === 'river') {add('patch', .2, .8, {kind: 'water', w: 2.6, d: 1.3}); scatter('bush', 2); add('log', .8, 2.4);}
	else if (r === 'island') {add('patch', .6, .6, {kind: 'sand', w: 1.8, d: 1.8}); add('palm', 1.2, 1.1); if (h(5) > .5) add('hut', 1.5, 1.5, {w: .8, d: .7, h: 1});}
	else if (r === 'ships') add('ship', .9, .1);
	else if (r === 'icebergs') {add('iceberg', .5, .5); if (h(5) > .5) add('iceberg', 1.9, 1.8, {w: .8, h: .7});}
	else if (r === 'sea') {}
	else if (typeof r === 'string' && r.startsWith('props:')) {const ks = r.slice(6).split(',').filter((k) => PDEF[k]); ks.forEach((k, i) => scatter(k, 1 + Math.floor(h(40 + i) * 2)));}     // a minted world's lot
	if (SCEN.length && h(77) < .22) {P.length = 0; add(SCEN[Math.floor(h(78) * SCEN.length)], .6 + h(79) * .6, .6 + h(80) * .6);}
	const out = {floor, props: P.map((p) => ({...p, w: p.w ?? 1, d: p.d ?? p.w ?? 1, h: p.h ?? 1}))}; LOT_CACHE[key] = out; return out;}
function lotDraw(c, t, b, flat) {const R0 = lotRecipe(b), f = FLOOR_KINDS[R0.floor] || FLOOR_KINDS.grass, {x, y, w, d} = b;
	poly(c, [[x, y, 0], [x + w, y, 0], [x + w, y + d, 0], [x, y + d, 0]], metal(c, S(x, y, 0), S(x + w, y + d, 0), f[0], f[1]), WORLD.edge);
	if (R0.floor === 'water') waves(c, t, x, y, w, d);
	else for (let i = 0; i < 14; i++) {const q = S(x + .15 + hash(i + b.seed) * (w - .3), y + .15 + hash(i * 3 + b.seed) * (d - .3), 0); c.fillStyle = R0.floor === 'snow' ? 'rgba(255,255,255,.35)' : 'rgba(184,134,46,.16)'; c.fillRect(q[0], q[1], 3, 2);}
	const parts = [];
	for (const p of R0.props) {if (p.t === 'patch' || p.t === 'court') {floorArt(c, t, p, x + p.x, y + p.y); continue;} if (flat && (FLASH_NOW || (p.h || 0) > .5)) continue; parts.push({d: x + p.x + y + p.y + (p.w + p.d) / 2, f: () => propDraw(c, t, p, x + p.x, y + p.y, false)});}
	parts.sort((a, b2) => a.d - b2.d).forEach((q) => q.f());}
/* ground, paths and sky for this world */
function worldSky(c, t, VW, VH) {const W2 = WORLD, g = c.createLinearGradient(0, 0, 0, VH); g.addColorStop(0, W2.sky[0]); g.addColorStop(.6, W2.sky[1]); g.addColorStop(1, W2.sky[2]); c.fillStyle = g; c.fillRect(0, 0, VW, VH);
	if (W2.haze) {const hz = c.createRadialGradient(VW / 2, VH * 1.06, 100, VW / 2, VH * 1.06, VW * .6); hz.addColorStop(0, W2.haze); hz.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = hz; c.fillRect(0, 0, VW, VH);}
	for (let i = 0; i < (W2.stars ?? 70); i++) {c.globalAlpha = .25 + .6 * frac(Math.sin(i * 7.7 + t)); c.fillStyle = i % 5 ? C.silver : C.champ; c.fillRect(hash(i) * VW, hash(i + 40) * VH * .5, 2, 2);} c.globalAlpha = 1;
	if (W2.sun) {const sx = VW * .78, sy = VH * .3, sg = c.createRadialGradient(sx, sy, 10, sx, sy, 260); sg.addColorStop(0, 'rgba(255,230,170,.95)'); sg.addColorStop(.18, 'rgba(255,170,80,.6)'); sg.addColorStop(1, 'rgba(255,140,60,0)'); c.fillStyle = sg; c.fillRect(sx - 300, sy - 300, 600, 600);
		c.fillStyle = '#FFE2A8'; c.beginPath(); c.arc(sx, sy, 46, 0, 7); c.fill();}
	if (W2.moon) {const mx = VW * .82, my = VH * .16; c.fillStyle = C.pale; c.shadowColor = C.gold; c.shadowBlur = 40; c.beginPath(); c.arc(mx, my, 34, 0, 7); c.fill(); c.shadowBlur = 0; c.fillStyle = W2.sky[0]; c.beginPath(); c.arc(mx + 14, my - 8, 30, 0, 7); c.fill();}
	if (W2.planet) {const px = VW * .8, py = VH * .2, r = 90, pg = c.createRadialGradient(px - 30, py - 30, 10, px, py, r); pg.addColorStop(0, '#9ECAE8'); pg.addColorStop(.6, '#3A6A9A'); pg.addColorStop(1, '#16243A'); c.fillStyle = pg; c.beginPath(); c.arc(px, py, r, 0, 7); c.fill();
		c.fillStyle = 'rgba(120,160,90,.7)'; [[-20, -10, 30, 18], [25, 20, 22, 14], [-35, 30, 18, 10]].forEach(([a, b2, w2, h2]) => {c.beginPath(); c.ellipse(px + a, py + b2, w2, h2, .4, 0, 7); c.fill();}); c.strokeStyle = 'rgba(158,202,232,.4)'; c.lineWidth = 6; c.beginPath(); c.arc(px, py, r + 4, 0, 7); c.stroke();}}
function worldGround(c, t) {const W2 = WORLD; poly(c, [[-2, -2, 0], [25, -2, 0], [25, 25, 0], [-2, 25, 0]], W2.water === 'all' ? '#16242E' : (W2.path || W2.ground));
	if (W2.water === 'all') {waves(c, t, -2, -2, 27, 27); return;}
	for (let i = 0; i < 6; i++) for (let j = 0; j < 6; j++) poly(c, [[i * 4 - .15, j * 4 - .15, 0], [i * 4 + 3.15, j * 4 - .15, 0], [i * 4 + 3.15, j * 4 + 3.15, 0], [i * 4 - .15, j * 4 + 3.15, 0]], W2.lot, W2.edge);
	if (W2.water === 'edge') {poly(c, [[-2, -2, .005], [25, -2, .005], [25, 3.4, .005], [-2, 3.4, .005]], '#1A2833'); poly(c, [[-2, -2, .005], [3.4, -2, .005], [3.4, 25, .005], [-2, 25, .005]], '#1A2833'); waves(c, t, -2, -2, 27, 5.4); waves(c, t, -2, -2, 5.4, 27);}}
/* passers-by for this world (people in the world's clothes, animals, ships) */
const WALK_CACHE = {id: '', list: []};
function worldWalkers() {if (WALK_CACHE.id === WORLD.id) return WALK_CACHE.list; const W2 = WORLD.walk || {}, list = [], nP = W2.people ?? 0, an = W2.animals || [];
	for (let i = 0; i < nP + an.length * 2; i++) {const isA = i >= nP, g = hash(i * 7.3), look = {gender: g < .45 ? 'man' : g < .9 ? 'woman' : 'child', skin: LOOK_VOCAB.skin[Math.floor(hash(i + 2) * 4)], hair: HAIRS[Math.floor(hash(i + 5) * 6)],
			color: LOOK_VOCAB.color[Math.floor(hash(i + 9) * 7)], outfit: ['blazer', 'hoodie', 'sweater', 'dress', 'suit'][Math.floor(hash(i + 11) * 5)], ...(W2.look || {})};
		if (look.gender === 'man' && look.outfit === 'dress') look.outfit = 'sweater';
		list.push({axis: i % 2, line: [3.5, 7.5, 15.5, 23.5][Math.floor(hash(i + 13) * 4)] + (hash(i + 17) > .5 ? .28 : -.28), v: (.55 + hash(i + 19) * .45) * (hash(i + 23) > .5 ? 1 : -1) * (W2.slow ? .5 : 1), s0: hash(i + 29) * 26, lk: lookOf(look), ph: hash(i + 31) * 6,
			animal: isA ? an[(i - nP) % an.length] : '', act: W2.act || ''});}
	WALK_CACHE.id = WORLD.id; WALK_CACHE.list = list; return list;}

buildLots();

/* ── icons for the info panels: Lucide nodes [tag, attrs] drawn as gold strokes ── */
function icon(c, nodes, x, y, size, col) {if (!nodes || !nodes.length) return; c.save(); c.translate(x, y); c.scale(size / 24, size / 24); c.strokeStyle = col; c.lineWidth = 1.8; c.lineCap = 'round'; c.lineJoin = 'round'; c.fillStyle = 'none';
	for (const [tag, a] of nodes) {c.beginPath(); try {
		if (tag === 'path') {c.stroke(new Path2D(a.d)); continue;}
		if (tag === 'circle') c.arc(+a.cx, +a.cy, +a.r, 0, 7); else if (tag === 'ellipse') c.ellipse(+a.cx, +a.cy, +a.rx, +a.ry, 0, 0, 7);
		else if (tag === 'line') {c.moveTo(+a.x1, +a.y1); c.lineTo(+a.x2, +a.y2);} else if (tag === 'rect') c.roundRect(+a.x || 0, +a.y || 0, +a.width, +a.height, +(a.rx || 0));
		else if (tag === 'polyline' || tag === 'polygon') {String(a.points).trim().split(/[\s,]+/).map(Number).reduce((acc, v, i, arr) => {if (i % 2 === 0) (i ? c.lineTo(v, arr[i + 1]) : c.moveTo(v, arr[i + 1])); return acc;}, 0); if (tag === 'polygon') c.closePath();}
		c.stroke();} catch (e) {}}
	c.restore();}
function panel(c, x, y, pn, a, VW) {if (a <= 0 || !pn) return;
	// the card fits its text: measure label + value, widen up to 640 px, then shrink the type if it still doesn't fit
	const label = String(pn.label || '').toUpperCase().slice(0, 28), value = String(pn.value || '').slice(0, 18), pad = 130;
	let ls = pn.value ? 26 : 30, vs = 60; c.font = `${ls}px ${HUD}`; let lw = c.measureText(label).width; c.font = `800 ${vs}px ${FX}`; let vw = value ? c.measureText(value).width : 0;
	const w = clamp(Math.max(lw, vw) + pad + 24, 340, 640), room = w - pad - 24;
	if (lw > room) {ls = Math.max(16, ls * room / lw); lw = room;} if (vw > room) {vs = Math.max(28, vs * room / vw); vw = room;}
	const h = pn.value ? 150 : 112; x = clamp(x, 40, VW - w - 40); const s = E.back(clamp(a * 1.4));
	c.save(); c.translate(x + w / 2, y + h / 2); c.scale(s, s); c.translate(-w / 2, -h / 2); c.globalAlpha = clamp(a * 2);
	c.fillStyle = 'rgba(19,20,24,.86)'; c.beginPath(); c.roundRect(0, 0, w, h, 14); c.fill(); c.strokeStyle = 'rgba(255,181,71,.75)'; c.lineWidth = 2; c.stroke();
	c.strokeStyle = C.gold; c.lineWidth = 4; [[0, 0, 1, 1], [w, 0, -1, 1], [0, h, 1, -1], [w, h, -1, -1]].forEach(([px, py, sx, sy]) => {c.beginPath(); c.moveTo(px, py + sy * 18); c.lineTo(px, py); c.lineTo(px + sx * 18, py); c.stroke();});
	icon(c, pn.nodes, 22, h / 2 - 34, 68, C.gold);
	c.save(); c.beginPath(); c.rect(100, 0, w - 112, h); c.clip();                  // never past the card's edge
	c.textAlign = 'left'; c.fillStyle = C.champ; c.font = `${ls}px ${HUD}`; c.fillText(label, 112, pn.value ? 52 : h / 2 + ls * .35);
	if (pn.value) {c.font = `800 ${vs}px ${FX}`; const g = c.createLinearGradient(0, 70, 0, 130); g.addColorStop(0, C.pale); g.addColorStop(1, C.gold); c.fillStyle = g; c.fillText(value, 110, 98 + vs * .4);}
	c.restore(); c.restore();}



/* ── PEOPLE: the story's cast (P.cast + each beat's "with"/"talker") at guest spots, the regulars of each place, pedestrians ── */
const GUESTS = {apartment: [[3.45, 3.1], [1.9, 2.75]], office: [[1.2, 3.6], [2.25, 3.65], [2.0, 1.55], [.85, 2.55], [3.55, 2.35]], lab: [[3.3, 2.45], [2.25, 2.2], [1.0, 1.2]],
	cafe: [[2.95, .6], [1.05, 2.95], [2.55, 3.5], [3.55, 2.6]], street: [[2.35, 2.35], [.75, 3.35], [2.65, .95], [1.6, .5]], rooftop: [[2.3, 1.45], [1.25, 2.55]]};
const REGULARS = {office: [[0, 'explain', {gender: 'woman', color: 'steel', skin: 'tan', hair: 'bun'}], [1, 'stand', {gender: 'man', color: 'bronze', skin: 'deep', outfit: 'sweater'}],
		[2, 'type', {gender: 'man', color: 'charcoal', skin: 'light', outfit: 'hoodie', hairColor: 'brown'}]],
	cafe: [[0, 'stand', {gender: 'woman', outfit: 'apron', color: 'champagne', skin: 'medium', hair: 'ponytail'}], [1, 'explain', {gender: 'man', color: 'silver', skin: 'light', outfit: 'sweater', beard: true}],
		[2, 'stand', {gender: 'woman', color: 'bronze', skin: 'deep', hair: 'curly', outfit: 'dress'}], [3, 'explain', {gender: 'man', color: 'graphite', skin: 'tan', outfit: 'hoodie'}]],
	lab: [[2, 'think', {gender: 'man', outfit: 'labcoat', skin: 'medium', glasses: true, age: 'older', hair: 'bald'}]],
	street: [[3, 'stand', {gender: 'woman', color: 'graphite', outfit: 'dress', skin: 'deep', hair: 'curly'}]], apartment: [], rooftop: []};
const WALKERS = Array.from({length: 14}, (_, i) => {const g = hash(i * 7.3), look = {gender: g < .45 ? 'man' : g < .9 ? 'woman' : 'child', skin: LOOK_VOCAB.skin[Math.floor(hash(i + 2) * 4)],
	hair: HAIRS[Math.floor(hash(i + 5) * 6)], color: LOOK_VOCAB.color[Math.floor(hash(i + 9) * 7)], outfit: ['blazer', 'hoodie', 'sweater', 'dress', 'suit'][Math.floor(hash(i + 11) * 5)]};
	if (look.gender === 'man' && look.outfit === 'dress') look.outfit = 'sweater';
	return {axis: i % 2, line: [3.5, 7.5, 15.5, 23.5][Math.floor(hash(i + 13) * 4)] + (hash(i + 17) > .5 ? .28 : -.28), v: (.55 + hash(i + 19) * .45) * (hash(i + 23) > .5 ? 1 : -1), s0: hash(i + 29) * 26, lk: lookOf(look), ph: hash(i + 31) * 6};});
let PEOPLE = {};
/* animals that live in a place (kit "animals": [[kind, x, y, act]]) + a few in the built-ins */
const ANIM = {street: [['pigeon', 1.35, 2.85, 'eat'], ['pigeon', 1.7, 3.0, 'idle']], rooftop: [['pigeon', 2.6, .7, 'idle']], cafe: [['cat', 3.5, .55, 'sleep']]};
/* Oct 29 (user: "when he passes in front of other characters they disappear until he moves away"): nobody is removed because the
   hero comes near. Someone standing right IN FRONT of the hero on screen eases to see-through while they overlap; everyone else
   stays solid and the depth sort does the rest. */
let HERO_AT = null, FLASH_NOW = false, COMP_AT = [];      // FLASH_NOW: a memory - the world outside the place is bare ground
function seeThrough(x, y) {const h = HERO_AT; if (!h) return 1; const dx = Math.abs((x - y) - (h[0] - h[1])), dd = (x + y) - (h[0] + h[1]);
	if (dd <= .05 || dd > 2.8) return 1; return lerp(.38, 1, ss(Math.max(0, dx - .35) / .55));}
function crowd(c, t, parts, place, z) {for (const q of PEOPLE[place] || []) {const p = S(q.x, q.y, z ?? 0);
	parts.push({d: q.x + q.y, f: () => {c.globalAlpha = q.a * seeThrough(q.x, q.y); if (q.animal) {c.save(); c.translate(p[0], p[1]); c.scale(2.1 * K / 400, 2.1 * K / 400); drawAnimal(c, t, q.animal); c.restore();} else person(c, t, p[0], p[1], 2.1 * K / 400, 0, q.R); c.globalAlpha = 1;}});}}
/* a rig for anyone (cast, regulars, walkers, insets, library previews): an action from the movement library at u seconds in */
function rigFor(t, lk, pose, phase, dir, talk, mood, u) {const act = actSpec(ACTS[pose] ? pose : 'stand', u ?? t + (phase || 0), phase || 0, t), md = MOODS[mood] || MOODS.neutral;
	return {walk: 0, dir, lie: 0, arms: act.arms || NEU, act, holdArms: false, face: {o: md.o, b: md.b, f: md.f, m: md.m}, look: act.look || [0, 0], shake: 0, shrug: 0, sq: 1 + Math.sin(t * 3 + (phase || 0)) * .006 + (act.sq || 0), heart: 0, tilt: 0, lk, talk: talk || !!act.talk, phase: phase || 0};}
/* a spot that would put someone in front of the hero (or crowd right behind them) on screen is not used */
const blocks = (x, y, hp) => {if (!hp) return false; const dx = (x - y) - (hp[0] - hp[1]), dd = (x + y) - (hp[0] + hp[1]); return Math.abs(dx) < .9 && dd > -1.3 && dd < 3.2;};
/* who stands where, beat by beat: a cast member keeps their spot in a place; regulars fill the spots nobody from the story needs.
   Oct 29: someone the line only TALKS TO ON THE PHONE, SEES FAR AWAY, HEARS or REMEMBERS (beat.remote) is never put in the room —
   they appear in an inset instead (the "ghost" bug: a caller used to materialise next to the hero). */
/* (pets in a beat walk at the hero's side - companions() - and never take a far guest spot) */
function castPlan(T, P) {if (T.castDone) return; const cast = {}; (P.cast || []).forEach((m, i) => {if (m && m.id && m.id !== 'hero') cast[m.id] = {lk: lookOf(m.look), i, name: m.name || m.id, species: (m.look && m.look.species) || m.species || ''};});
	let mem = {};
	T.beats.forEach((b) => {const pl = b.charPlace, spots = GUESTS[pl] || [], far = new Set((Array.isArray(b.remote) ? b.remote : []).map((r) => r && r.id)),
		ids = (Array.isArray(b.with) ? b.with : []).filter((id) => cast[id] && !far.has(id) && !cast[id].species).slice(0, spots.length), used = {}, g = [];
		const hp = spot(pl, b.charAt).pos, ok = (k) => !used[k] && !blocks(PL[pl].o[0] + spots[k][0], PL[pl].o[1] + spots[k][1], hp);
		const atSt = b.at && typeof b.at === 'object' ? b.at : {};                    // "Father is at the window": he stands at that station
		ids.forEach((id) => {const st = atSt[id], S0 = st && PL[pl] && PL[pl].st[st]; if (S0 && st !== b.charAt) g.push([id, 'st:' + st]);});
		ids.forEach((id) => {if (g.find((x) => x[0] === id)) return; const keep = mem[pl] && mem[pl][id]; if (typeof keep === 'number' && ok(keep)) {used[keep] = id; g.push([id, keep]);}});
		ids.forEach((id) => {if (g.find((x) => x[0] === id)) return; const s = spots.findIndex((_, k) => ok(k)); if (s >= 0) {used[s] = id; g.push([id, s]);}});
		const nx = clamp(+(b.extras && b.extras.n) || 0, 0, 4); b.extraSpots = []; for (let n = 0; n < nx; n++) {const s = spots.findIndex((_, k) => ok(k)); if (s < 0) break; used[s] = '_x'; b.extraSpots.push(s);}
		mem = {...mem, [pl]: Object.fromEntries(g)}; b.guests = g; b.used = used;});
	T.cast = cast; T.castDone = true;}
/* what a cast member does in a beat: the writer's per-person action (beat.acts[id]), else talk when they speak, else react with the hero */
function guestAct(b, id) {const a = b.acts && b.acts[id]; if (a && ACTS[a]) return a; if (b.talker === id) return 'explain';
	const h = b.pose; if (['shock', 'celebrate', 'cheer', 'clap', 'laugh', 'dance', 'panic', 'worry'].includes(h)) return h; if (ACTS[h] && ['war', 'sport'].includes(ACTS[h].cat)) return h; return 'stand';}
function buildPeople(T, t, k, B, cs, cam) {PEOPLE = {};
	const hx = cs.pos[0] - cs.pos[1];
	const face = (x, y) => (hx - (x - y) >= 0 ? 1 : -1);
	for (const [pl, list] of Object.entries(REGULARS)) {const P = PL[pl]; if (!P || (B.flash && pl === B.charPlace)) continue; const taken = pl === B.charPlace ? B.used || {} : {};
		const hp = pl === B.charPlace ? spot(B.charPlace, B.charAt).pos : null;        // the beat's own spot only - never the live (walking) position
		list.forEach(([s, pose, look], n) => {if (taken[s]) return; const sp = GUESTS[pl][s]; if (!sp) return; const x = P.o[0] + sp[0], y = P.o[1] + sp[1]; if (blocks(x, y, hp)) return;
			const lk = REG_LOOKS[pl + n] || (REG_LOOKS[pl + n] = lookOf(look)), ph = n * 1.7 + pl.length;
			const dir = pl === 'cafe' && s === 0 ? 1 : (n % 2 ? -1 : 1);
			if (look && look.species) {(PEOPLE[pl] = PEOPLE[pl] || []).push({x, y, a: 1, animal: {kind: look.species, act: pose, ph, dir}}); return;}
			(PEOPLE[pl] = PEOPLE[pl] || []).push({x, y, a: 1, R: rigFor(t, lk, pose, ph, dir, pose === 'explain' && frac(t * .12 + n * .4) < .5, 'neutral')});});}
	for (const [pl, list] of Object.entries(ANIM)) {const P = PL[pl]; if (!P) continue; const hp = pl === B.charPlace ? spot(B.charPlace, B.charAt).pos : null;
		list.forEach(([kind, ax, ay, act], n) => {const x = P.o[0] + ax, y = P.o[1] + ay; if (blocks(x, y, hp) || !SPECIES[kind]) return; (PEOPLE[pl] = PEOPLE[pl] || []).push({x, y, a: 1, animal: {kind, act: act || 'idle', ph: n * 2.1, dir: n % 2 ? -1 : 1}});});}
	// the story's cast in this beat (fading in with the beat, out with the next one that doesn't need them)
	const show = (b, a) => {if (!b) return; const P = PL[b.charPlace]; (b.guests || []).forEach(([id, s]) => {const m = T.cast[id], st = typeof s === 'string' ? P.st[s.slice(3)] : null, sp = st ? st[0] : (GUESTS[b.charPlace] || [])[s]; if (!m || !sp) return;
		let x = P.o[0] + sp[0], y = P.o[1] + sp[1], walking = 0, wdir = 0; const talk = b.talker === id;
		// someone who moves to a new spot in the same place WALKS there (1.2 s) instead of appearing
		const pb = b === B ? T.beats[k - 1] : null, pg = pb && pb.charPlace === b.charPlace ? (pb.guests || []).find((g) => g[0] === id) : null;
		if (pg) {const pst = typeof pg[1] === 'string' ? P.st[pg[1].slice(3)] : null, psp = pst ? pst[0] : (GUESTS[b.charPlace] || [])[pg[1]];
			if (psp && Math.hypot(psp[0] - sp[0], psp[1] - sp[1]) > .2) {const u = E.io(clamp((t - b.t0) / 1.2)), x0 = P.o[0] + psp[0], y0 = P.o[1] + psp[1];
				wdir = ((x - y) - (x0 - y0)) >= 0 ? 1 : -1; x = lerp(x0, x, u); y = lerp(y0, y, u); walking = u < 1 ? 1 : 0;}}
		if (m.species) {(PEOPLE[b.charPlace] = PEOPLE[b.charPlace] || []).push({x, y, a, animal: {kind: m.species, act: (b.acts && b.acts[id]) || (talk ? 'speak' : 'idle'), ph: m.i * 2.3, dir: face(x, y)}}); return;}
		const act = guestAct(b, id);
		const Rg = rigFor(t, m.lk, act, m.i * 2.3, walking ? wdir : st ? st[1] : face(x, y), talk, talk ? b.mood : 'neutral', t - b.t0); Rg.walk = walking;
		(PEOPLE[b.charPlace] = PEOPLE[b.charPlace] || []).push({x, y, a: walking ? 1 : a, R: Rg});});
		const ex = b.extras; if (ex && b.extraSpots) b.extraSpots.forEach((s, n) => {const sp = (GUESTS[b.charPlace] || [])[s]; if (!sp) return; const x = P.o[0] + sp[0], y = P.o[1] + sp[1];
			const lk = REG_LOOKS['x' + JSON.stringify(ex.look || {}) + n] || (REG_LOOKS['x' + JSON.stringify(ex.look || {}) + n] = lookOf({...(ex.look || {}), skin: LOOK_VOCAB.skin[n % 4], gender: (ex.look && ex.look.gender) || (n % 3 === 2 ? 'woman' : 'man')}));
			(PEOPLE[b.charPlace] = PEOPLE[b.charPlace] || []).push({x, y, a, R: rigFor(t, lk, ACTS[ex.act] ? ex.act : guestAct(b, ''), n * 1.9 + 4, face(x, y), false, b.mood, t - b.t0 + n * .3)});});};
	const fin = E.io(rg(t, B.t0 - .1, .35)); show(B, fin);
	const Bp = T.beats[k - 1]; if (Bp && fin < 1) show({...Bp, guests: (Bp.guests || []).filter(([id]) => !(B.guests || []).find(([j]) => j === id)), extraSpots: B.extras ? [] : Bp.extraSpots}, 1 - fin);}
/* animals that go WITH the hero in a beat (beat.animals [{kind, act}]): they trail the hero's path a moment behind */
function companions(T, t, B, items) {const placed = new Set((B.guests || []).map((g) => g[0])), pets = (Array.isArray(B.with) ? B.with : []).filter((id) => T.cast[id] && T.cast[id].species && !placed.has(id)).map((id) => ({kind: T.cast[id].species, act: (B.acts && B.acts[id]) || 'wag'}));
	const list = [...pets, ...(Array.isArray(B.animals) ? B.animals : [])].filter((a) => a && SPECIES[a.kind]).slice(0, 3); if (!list.length) return;
	list.forEach((a, i) => {const lag = .45 + i * .3, c0 = charState(T, t - lag), c1 = charState(T, t - lag - .08), moving = Math.hypot(c0.pos[0] - c1.pos[0], c0.pos[1] - c1.pos[1]) > .002;
		const S0 = SPECIES[a.kind], fly = S0.type === 'bird' || S0.type === 'fly', half = (S0.type === 'quad' ? S0.len : S0.type === 'sprite' ? S0.len : (S0.size || 40) * 1.6) / 400 * 2.1 / 2, off = [Math.max(.55, half + .25) + i * .28, .22 - i * .3 - Math.max(0, half - .5) * .5], x = c0.pos[0] + off[0], y = c0.pos[1] + off[1], z = c0.pos[2] || 0, pl = placeAt(x, y, z); COMP_AT.push([x, y, Math.max(.5, half)]);
		const dir = moving ? ((c0.pos[0] - c0.pos[1]) - (c1.pos[0] - c1.pos[1]) >= 0 ? 1 : -1) : ((cs0) => (cs0.pos[0] - cs0.pos[1]) - (x - y) >= 0 ? 1 : -1)(charState(T, t));
		const q = {x, y, a: 1, animal: {kind: a.kind, act: moving ? (a.act === 'run' ? 'run' : fly ? 'fly' : 'walk') : (a.act || 'idle'), mv: moving ? 1 : 0, ph: i * 1.7, dir}};
		if (pl && PL[pl]) (PEOPLE[pl] = PEOPLE[pl] || []).push(q); else items.push({d: x + y + .5, f: () => {const p = S(x, y, z); c_.save(); c_.translate(p[0], p[1]); c_.scale(2.1 * K / 400, 2.1 * K / 400); drawAnimal(c_, t, q.animal); c_.restore();}});});}
let c_ = null;
const REG_LOOKS = {};
function walkers(c, t, items, cam, hero, B) {if (B && B.flash) return;
	const rects = Object.entries(PL).filter(([id, p]) => id !== 'street' && (KIT_IDS.includes(id) || (BUILTIN_LOT[id] && builtinOn(id)))).map(([, p]) => p.o);
	for (const w of worldWalkers()) {const u = ((w.s0 + w.v * t) % 26 + 26) % 26 - 1, x = w.axis ? u : w.line, y = w.axis ? w.line : u;
	let inside = 1; for (const [ox, oy] of rects) {const de = Math.min(x - ox, ox + 4 - x, y - oy, oy + 4 - y); if (de > -.35) inside = Math.min(inside, 1 - ss((de + .35) / .35));}   // fade out at a place's edge
	if (inside <= .02) continue;
	let fa = 1; if (K > 55) {const e1 = (x + y) - (cam[0] + cam[1] + .5), e2 = 7.5 - Math.abs((x - y) - (cam[0] - cam[1])); if (e1 > 0 && e2 > 0 && e1 < 16) fa = 1 - ss(Math.min(e1, e2) / 1.2);}   // fade at the edge of the foreground zone, never pop
	fa *= inside; if (fa <= .02) continue;
	items.push({d: x + y + .6, f: () => {const p = S(x, y, 0), dx = w.axis ? w.v : -w.v; c.globalAlpha = fa * seeThrough(x, y);
		if (w.animal) {c.save(); c.translate(p[0], p[1]); c.scale(2.1 * K / 400, 2.1 * K / 400); drawAnimal(c, t, {kind: w.animal, act: SPECIES[w.animal] && SPECIES[w.animal].type === 'fish' ? 'swim' : 'walk', mv: 1, ph: w.ph, dir: dx > 0 ? 1 : -1}); c.restore(); c.globalAlpha = 1; return;}
		const R = rigFor(t, w.lk, w.act || 'stand', w.ph, dx > 0 ? 1 : -1, false, 'neutral'); R.walk = w.act ? 0 : 1; person(c, t + w.ph, p[0], p[1], 2.1 * K / 400, 0, R); c.globalAlpha = 1;}});}}

/* ── the plan → a timeline (cached per props object): where the character is, every walk between spots and places ── */
const CACHE = new WeakMap();
function doorPath(place) {const P = PL[place]; return place === 'rooftop' ? [[P.lift[0], P.lift[1], P.z], [P.lift[0], P.lift[1], 0], [P.door[0], P.door[1], 0]] : [[P.door[0], P.door[1], 0]];}
function route(pa, pb, A, B) {if (pa === pb) return [A, B];
	const da = doorPath(pa), db = doorPath(pb).reverse(), a = da[da.length - 1], b = db[0], pts = [A, ...da];
	if (a[0] !== b[0] && a[1] !== b[1]) pts.push([b[0], a[1], 0]);           // along a street, turn at the crossing, along the next
	return [...pts, ...db, B];}
/* movements that GO somewhere: on a spot they cross the place's open floor (Oct 29, user: "the hero still running into walls") */
const LOCO = new Set(['run', 'jog', 'charge', 'dribble', 'panic', 'crawl', 'limp', 'sneak']);
function timeline(P) {let T = CACHE.get(P); if (T) return T;
	const beats = (P.beats || []).map((b) => ({...b, t0: +b.t0 || 0, t1: +b.t1 || 0}));
	let place = 'apartment', st = 'center', end = -1;
	const walks = [];
	beats.forEach((b, i) => {
		const pl = PL[b.place] ? b.place : (b.place ? 'apartment' : place), s = PL[pl].st[b.station] ? b.station : (pl === place && PL[pl].st[st] ? st : 'center');
		b.charPlace = pl; b.charAt = s; b.cue = b.cue ?? b.t0 + .25;
		if (i === 0) {place = pl; st = s; return;}
		if ((pl !== place || s !== st) && (!!b.flash !== !!beats[i - 1].flash || (b.flash && pl !== place))) {const A = spot(place, st).pos, Bq = spot(pl, s).pos;   // into / out of a flashback = a CUT, never a walk
			walks.push({a: b.t0 - .02, b: b.t0, pts: [A, Bq], cum: [0, Math.hypot(Bq[0] - A[0], Bq[1] - A[1]) || .01], far: false, place: pl, st: s, cut: true}); end = b.t0; place = pl; st = s; return;}
		if (pl !== place || s !== st) {const A = spot(place, st).pos, Bp = spot(pl, s).pos, pts = route(place, pl, A, Bp);
			const cum = [0]; for (let j = 1; j < pts.length; j++) cum.push(cum[j - 1] + Math.hypot(pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1], pts[j][2] - pts[j - 1][2]));
			const far = pl !== place, ride = ACTS[b.pose] && ACTS[b.pose].cat === 'ride', run = ['run', 'jog', 'charge', 'dribble', 'panic'].includes(b.pose), sp2 = ride ? 2.6 : run ? 1.7 : 1, d = far ? clamp(cum[cum.length - 1] / 6.5 / sp2, ride ? 1.2 : 1.6, 5) : clamp(cum[cum.length - 1] / 2.4 / sp2, .45, 1.2);
			const a = Math.max(end + .05, beats[i - 1].t0 + .2, b.t0 - .25); walks.push({a, b: a + d, pts, cum, far, place: pl, st: s}); end = a + d;}
		else if (LOCO.has(b.pose) && PL[pl].st) {const A = spot(pl, s).pos, cands = Object.keys(PL[pl].st).filter((k) => k !== s).map((k) => [k, spot(pl, k).pos]);
			if (cands.length) {const pick = cands.find(([k, p]) => k === 'center' && Math.hypot(p[0] - A[0], p[1] - A[1]) > 1.1) || cands.sort((x, y) => Math.hypot(y[1][0] - A[0], y[1][1] - A[1]) - Math.hypot(x[1][0] - A[0], x[1][1] - A[1]))[0];
				const Bq = pick[1], L = Math.hypot(Bq[0] - A[0], Bq[1] - A[1]), a = Math.max(end + .05, b.t0 + .1), d = clamp((b.t1 - b.t0) - .3, 1.2, b.pose === 'crawl' || b.pose === 'limp' ? 6 : Math.max(1.2, L / 1.6));
				walks.push({a, b: a + d, pts: [A, Bq], cum: [0, L || .01], far: false, place: pl, st: pick[0], loco: b.pose}); end = a + d; place = pl; st = pick[0]; return;}}
		place = pl; st = s;});
	T = {beats, walks, first: beats[0] ? [beats[0].charPlace, beats[0].charAt] : ['apartment', 'center']}; CACHE.set(P, T); return T;}
function beatAt(T, t) {let k = 0; for (let i = 0; i < T.beats.length; i++) if (t >= T.beats[i].t0 - .001) k = i; return k;}
function charState(T, t) {let [pl, st] = T.first, s0 = spot(pl, st), pos = s0.pos, walk = 0, dir = s0.dir, travel = 0, inPlace = pl;
	for (const w of T.walks) {
		if (t >= w.b) {const s = spot(w.place, w.st); pos = s.pos; dir = s.dir; pl = w.place; inPlace = pl; continue;}
		if (t >= w.a) {const u = (t - w.a) / (w.b - w.a), e = w.far ? clamp(u * 1.08 - .04) : E.io(u), L = w.cum[w.cum.length - 1], dd = e * L; let j = 1; while (j < w.cum.length - 1 && w.cum[j] < dd) j++;
			const p0 = w.pts[j - 1], p1 = w.pts[j], sl = (dd - w.cum[j - 1]) / ((w.cum[j] - w.cum[j - 1]) || 1); pos = [lerp(p0[0], p1[0], sl), lerp(p1[1] === p0[1] ? p0[1] : p0[1], p1[1], sl), lerp(p0[2], p1[2], sl)];
			const lift = Math.abs(p1[2] - p0[2]) > .01; walk = lift ? 0 : 1; const dx = (p1[0] - p1[1]) - (p0[0] - p0[1]); if (!lift && Math.abs(dx) > .01) dir = dx > 0 ? 1 : -1;
			travel = w.far ? Math.min(1, (t - w.a) / .6, (w.b - t) / .6) : 0; inPlace = placeAt(pos[0], pos[1], pos[2]); pl = w.place; break;}
		break;}
	return {pos, walk, dir, travel, place: inPlace, target: pl};}
function camOf(type, cs, B, port) {const p = cs.pos, pl = PL[(B && B.charPlace) || cs.target] || PL.apartment, cx = pl.o[0] + (pl === PL.rooftop ? 1.5 : 2), cy = pl.o[1] + (pl === PL.rooftop ? 1.5 : 2); let v;
	if (type === 'close') v = [p[0], p[1], p[2] + 1.55, 265]; else if (type === 'wide') v = [cx, cy, pl.z + .7, pl === PL.street ? 140 : 165];
	else if (type === 'city') v = [11, 11, 0, 24]; else if (type === 'aerial' || type === 'street') v = [cx, cy, pl.z * .6, 55]; else if (type === 'follow') v = [p[0], p[1], p[2] + .9, 85];
	else v = [p[0] + .15, p[1] + .15, p[2] + .95, 210];
	if (port) v[3] *= {close: .85, medium: .8, wide: .62, city: .55, aerial: .6, street: .6, follow: .8}[type] || .8; return v;}
const inFront = (x, y, cam) => K > 55 && x + y > cam[0] + cam[1] + .5 && x + y - cam[0] - cam[1] < 16 && Math.abs((x - y) - (cam[0] - cam[1])) < 7.5;

/* ── one frame ── */
export function drawDiorama(c, W, H, t, P) {
	const port = H > W, VW = port ? 1080 : 1920, VH = port ? 1920 : 1080, sc0 = W / VW;
	c_ = c;
	c.setTransform(sc0, 0, 0, sc0, 0, 0);
	useKits(P);
	const T = timeline(P), k = beatAt(T, t), B = T.beats[k] || {t0: 0, t1: 1, camera: 'wide', pose: 'stand', mood: 'neutral', charPlace: 'apartment', charAt: 'center'}, Bp = T.beats[Math.max(0, k - 1)] || B, cue = B.cue ?? B.t0 + .25;
	const cs = charState(T, t), dur = Math.max(.4, B.t1 - B.t0);
	// camera: glide from the last beat's framing to this one; on a walk across town it follows the character
	const flashCut = k && (!!B.flash !== !!Bp.flash || (B.flash && B.charPlace !== Bp.charPlace));      // the camera cuts into / out of a memory
	const mv = clamp(dur * .5, .35, .9), u = k && !flashCut ? E.io(rg(t, B.t0 - .05, mv)) : 1, ca = camOf(Bp.camera || 'medium', cs, Bp, port), cb = camOf(B.camera || 'medium', cs, B, port);
	let cam = [lerp(ca[0], cb[0], u), lerp(ca[1], cb[1], u), lerp(ca[2], cb[2], u), Math.exp(lerp(Math.log(ca[3]), Math.log(cb[3]), u)) * (1 + .03 * rg(t, B.t0, dur))];
	if (cs.travel > 0) {const f = camOf('follow', cs, B, port), w = E.io(cs.travel); cam = [lerp(cam[0], f[0], w), lerp(cam[1], f[1], w), lerp(cam[2], f[2], w), Math.exp(lerp(Math.log(cam[3]), Math.log(f[3]), w))];}
	const shake = (B.fx === 'impact' && t >= cue ? Math.exp(-(t - cue) * 6) * 12 : 0) + vfxList(T, k).reduce((m, [v, b0]) => Math.max(m, vfxShake(v.kind, t - vfxStart(v, b0)) * 26), 0);
	K = cam[3]; CX = (cam[0] - cam[1]) * CO * K - Math.sin(t * 50) * shake; CY = (cam[0] + cam[1]) * .5 * K - cam[2] * K - Math.cos(t * 47) * shake;
	// the character's rig for this moment: the beat's movement set (dio_lib ACTS), blended from where the last beat's ended —
	// the hands swing round the shoulders (polar blend), body drop/lean/lift ease, rides and held items switch half-way
	const atBed = (b) => (b && b.charPlace === 'apartment' && b.charAt === 'bed' && b.pose === 'sleep' ? 1 : 0);
	const lie = lerp(atBed(Bp), atBed(B), k ? E.io(rg(t, B.t0, .35)) : 1) * (cs.walk || cs.travel ? 0 : 1);
	const nA = heroAct(B), nP = heroAct(Bp), pu = k ? E.io(rg(t, B.t0, .4)) : 1;
	const sA = actSpec(nA, t - B.t0, 0, t), sP = actSpec(nP, Math.max(0, (+Bp.t1 || B.t0) - (+Bp.t0 || 0)), 0, t);
	const arms = [blendHand((sP.arms || NEU)[0], (sA.arms || NEU)[0], pu, -1), blendHand((sP.arms || NEU)[1], (sA.arms || NEU)[1], pu, 1)];
	const act = {...(pu < .5 ? sP : sA)}; ['drop', 'lean', 'lift', 'tilt', 'rot', 'shift'].forEach((f) => (act[f] = lerp(+sP[f] || 0, +sA[f] || 0, pu)));
	if ((cs.walk || cs.travel) && !act.move) {act.piece = null; act.rot = 0; if (!act.ride) {act.lift = 0; act.lean = 0;}}
	const md = MOODS[B.mood] || MOODS.neutral, pop = nA === 'shock' ? Math.exp(-(t - B.t0) * 5) * Math.sin((t - B.t0) * 22) : 0;
	const hb = nA === 'heart' ? Math.pow(Math.max(0, Math.sin((t - B.t0) * PI * 2.4)), 10) : 0;
	const here = spot(B.charPlace, B.charAt), prop = here.prop;
	const R = {lk: heroLook(P), pos: cs.pos, place: cs.place, draw: true, walk: cs.walk, dir: cs.walk ? cs.dir : (['type', 'sitdesk'].includes(nA) ? -1 : here.dir), lie, arms, act, holdArms: ['listen', 'ears', 'cover', 'phone'].includes(nA),
		face: {o: md.o, b: md.b, f: md.f, m: md.m}, look: act.look || (B.camera === 'city' ? [2.5, -2] : [0, 0]),
		shake: B.fx === 'shake' && !cs.walk ? Math.sin(t * 80) * 3 : 0, shrug: nA === 'cover' ? 6 : 0,
		sq: 1 + (lie > .5 ? Math.sin(t * 2.2) * .012 : Math.sin(t * 3) * .006) + pop * .07 - hb * .015 + (act.sq || 0), heart: hb, tilt: (B.camera === 'city' ? .06 : 0) + pop * .05, phase: 0};
	if (cs.walk || cs.travel) R.holdArms = false;
	// sky + ground of this film's world (night city by default)
	worldSky(c, t, VW, VH);
	c.save(); c.translate(VW / 2, VH * (port ? .5 : .52));
	worldGround(c, t);
	const cityK = T.beats.findIndex((b) => b.camera === 'city'), cityT = cityK >= 0 ? T.beats[cityK].t0 : 1e9, lit = .2 + (B.camera === 'city' ? .6 * E.o(rg(t, B.t0, 2.5)) : t > cityT ? .5 : 0);
	const apB = B.charPlace === 'apartment' ? B : null, live = (pl) => pl === R.place || pl === cs.target || pl === B.charPlace;   // never flatten where the story is
	// sightline: in ANY shot (not only close-ups), a building or place that would be drawn over the hero or someone in this beat is flattened
	castPlan(T, P); const gO = (PL[B.charPlace] || {}).o, keep = [cs.pos, ...((B.animals || []).length ? [[cs.pos[0] + 1.3, cs.pos[1] - .1, 0], [cs.pos[0] + 2.2, cs.pos[1] - .3, 0], [cs.pos[0] + 1.2, cs.pos[1] + .7, 0], [cs.pos[0] + .5, cs.pos[1] + 1.2, 0]] : []), ...(gO ? (B.guests || []).map(([, s]) => (GUESTS[B.charPlace] || [])[s]).filter(Boolean).map((g) => [gO[0] + g[0], gO[1] + g[1], 0]) : [])];
	const covers = (x, y, w, dd, h) => keep.some(([hx, hy, hz]) => x + y + (w + dd) / 2 > hx + hy && Math.abs((x + w / 2 - y - dd / 2) - (hx - hy)) < (w + dd) / 2 + .5 && (x + y) / 2 - h < (hx + hy) / 2 - (hz || 0) - .2);
	const cull = (pl, x, y) => !live(pl) && (B.flash || inFront(x, y, cam) || covers(PL[pl].o[0], PL[pl].o[1], 4, 4, 2.4));
	const items = LOTS.map((b) => ({d: b.x + b.y + 3, f: () => WORLD.id !== 'city' ? lotDraw(c, t, b, B.flash || inFront(b.x + 1.5, b.y + 1.5, cam) || covers(b.x, b.y, b.w, b.d, 2.5)) : (B.flash || inFront(b.x + 1.5, b.y + 1.5, cam) || (!b.tree && covers(b.x, b.y, b.w, b.d, b.h)) ? plaza(c, b) : b.tree ? (tree(c, b.x + .8, b.y + .8), tree(c, b.x + 2.2, b.y + 1.6), tree(c, b.x + 1.2, b.y + 2.4)) : building(c, b, t, lit))}));
	if (builtinOn('apartment')) items.push({d: 20, f: () => (cull('apartment', 10, 10) ? shell(c, 8, 8, undefined, undefined, true) : room(c, t, R, apB, cue))});
	if (builtinOn('office')) items.push({d: 28, f: () => office(c, t, R, B, cull('office', 18, 10))}); if (builtinOn('lab')) items.push({d: 28.1, f: () => lab(c, t, R, B, cull('lab', 10, 18))}); if (builtinOn('cafe')) items.push({d: 36, f: () => cafe(c, t, R, B, cull('cafe', 18, 18))});
	if (builtinOn('street')) items.push({d: 27, f: () => street(c, t, R, B, cull('street', 13.5, 13.5))}); if (builtinOn('rooftop')) items.push({d: 11, f: () => rooftop(c, t, R, B, lit)});
	for (const id of KIT_IDS) {const [kx, ky] = PL[id].o; items.push({d: kx + ky + 4, f: () => kitPlace(c, t, R, B, cull(id, kx + 2, ky + 2), id)});}
	FLASH_NOW = !!B.flash; HERO_AT = cs.pos; COMP_AT = []; castPlan(T, P); buildPeople(T, t, k, B, cs, cam); companions(T, t, B, items); walkers(c, t, items, cam, cs.pos, B);
	if (!R.place) items.push({d: cs.pos[0] + cs.pos[1] + .5, f: () => {const q = S(cs.pos[0], cs.pos[1], cs.pos[2]); person(c, t, q[0], q[1], 2.1 * K / 400, 0, R);}});
	items.sort((a, b) => a.d - b.d).forEach((it) => it.f());
	// a signal across town (fx route, or the old "street" camera): a gold route from a far building to the character
	if (B.fx === 'route' || (B.camera === 'street' && !B.place)) {const dp = PL[B.charPlace] || PL.apartment, wp = [[1.5, 19], [1.5, dp.door[1]], [dp.door[0], dp.door[1]], [cs.pos[0], cs.pos[1]]], a = rg(t, B.t0, .4) * (1 - rg(t, B.t1 - .2, .3));
		c.globalAlpha = a; c.setLineDash([.22 * K, .2 * K]); c.strokeStyle = C.gold; c.lineWidth = Math.max(2, .16 * K); c.shadowColor = C.gold; c.shadowBlur = 18; c.beginPath();
		wp.forEach((p, i) => {const q = S(p[0], p[1], .02); i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]);}); c.stroke(); c.setLineDash([]); c.shadowBlur = 0;
		const q = frac(t * .55); let Lt = 0; const seg = []; for (let i = 0; i < wp.length - 1; i++) {const l = Math.hypot(wp[i + 1][0] - wp[i][0], wp[i + 1][1] - wp[i][1]); seg.push(l); Lt += l;}
		let dd = q * Lt, i = 0; while (i < seg.length - 1 && dd > seg[i]) {dd -= seg[i]; i++;} const uu = dd / (seg[i] || 1), pp = S(lerp(wp[i][0], wp[i + 1][0], uu), lerp(wp[i][1], wp[i + 1][1], uu), .3);
		c.fillStyle = C.pale; c.shadowColor = C.gold; c.shadowBlur = 24; c.beginPath(); c.arc(pp[0], pp[1], Math.max(5, .24 * K), 0, 7); c.fill(); c.shadowBlur = 0; c.globalAlpha = 1;}
	// rings: sound around the head, pulses around the focused prop, the whole city answering
	const pp = cs.pos, rs = (x, y, z, col, per, n, max, w) => {for (let i = 0; i < n; i++) {const q = frac((t - B.t0) / per + i / n); ring(c, x, y, z, .2 + q * max, col, (1 - q) * .85 * rg(t, B.t0, .3), w);}};
	if (B.rings === 'sound') rs(pp[0], pp[1], pp[2] + 1.7, C.gold, 1.1, B.pose === 'ears' ? 10 : 4, 1.4, .02);
	if (B.rings === 'pulse') prop ? rs(prop[0], prop[1], prop[2], C.champ, .45, 3, 1.2) : rs(pp[0], pp[1], pp[2] + 1, C.gold, .42, 3, 1.1);
	if (B.camera === 'city') LOTS.forEach((b, i) => {if (b.tree) return; const t0 = B.t0 + .4 + hash(i) * 2.2; if (t < t0) return; const q = frac((t - t0) / 1.6); ring(c, b.x + 1.5, b.y + 1.5, b.h, .3 + q * 1.6, i % 3 ? C.champ : C.gold, (1 - q) * .75);});
	c.restore();
	// sound words, info panel, sleep z's — in screen space, tied to what they belong to
	const OX = VW / 2, OY = VH * (port ? .5 : .52), PS = (x, y, z) => {const q = S(x, y, z); return [q[0] + OX, q[1] + OY];};
	// VFX (explosions, fire, smoke, floods …): this beat's, plus one-shot effects from the last beat still playing out
	vfxList(T, k).forEach(([v, b0], n) => {const u = t - vfxStart(v, b0); if (u < 0) return; const pl = PL[b0.charPlace] || PL.apartment, at = v.at || 'hero', o = pl.o, z = pl.z || 0;
		let w = [cs.pos[0] + .9, cs.pos[1] + .35, cs.pos[2] || 0];
		if (at === 'place' || VFX[v.kind] && VFX[v.kind].ground) w = [o[0] + 2, o[1] + 2, z]; else if (at === 'here' || at === 'self') w = [cs.pos[0], cs.pos[1], cs.pos[2] || 0];
		else if (pl.st && pl.st[at]) {const sp = pl.st[at][2] || pl.st[at][0]; w = [o[0] + sp[0], o[1] + sp[1], z];}
		else if (at === 'far') w = [cs.pos[0] + 1.9, cs.pos[1] - 1.1, cs.pos[2] || 0];      // off to the side, still inside a medium shot
		const q = PS(w[0], w[1], w[2]), poly = [[o[0], o[1]], [o[0] + 4, o[1]], [o[0] + 4, o[1] + 4], [o[0], o[1] + 4]].map(([a, b]) => PS(a, b, z));
		const fade = b0 === B ? 1 : 1;
		c.globalAlpha = fade; drawVfx(c, v.kind, q[0], q[1], K, u, t, 7 + n * 13 + (b0.t0 | 0), poly, VW, VH); c.globalAlpha = 1;});
	const head = PS(pp[0], pp[1], pp[2] + 2.05), anchor = prop && B.charAt !== 'bed' ? PS(prop[0], prop[1], prop[2] + .8) : head;
	if (lie > .5) for (let i = 0; i < 3; i++) {const q = frac(t * .45 + i / 3); const hp = PS(BED.x + .3, BED.y + .7, 1.1); c.globalAlpha = Math.sin(q * PI) * .9; c.fillStyle = C.silver2; c.font = `800 ${30 + i * 9}px ${FX}`; c.textAlign = 'left'; c.fillText('z', hp[0] + 30 + q * 50 + i * 20, hp[1] - q * 140 - i * 18);} c.globalAlpha = 1;
	if (B.sfx) {const hold = Math.min(1.1, Math.max(.6, B.t1 - cue - .2)); goldText(c, String(B.sfx).toUpperCase().slice(0, 14), anchor[0] + (port ? 0 : 60), anchor[1] - 40, port ? 64 : 76, cue, t, -.07, hold);}
	if (B.panel) {const pa2 = rg(t, cue + .05, .3) * (1 - rg(t, B.t1 - .25, .25)), big = B.camera === 'city' || B.camera === 'aerial' || B.camera === 'street' || cs.travel > .5;
		panel(c, big ? VW / 2 - 200 : head[0] + (head[0] > VW * .6 ? -470 : 110), big ? (port ? 220 : 120) : head[1] - 120, B.panel, pa2, VW);}
	// scenario ambience (rain / snow / war / confetti / speed) from the beat or its movement set, and the people who are NOT here
	const ambOf = (b) => (b && (b.amb || actSpec(heroAct(b), 1, 0, t).amb)) || WORLD.amb || '', am = ambOf(B);
	if (am) ambient(c, am, t, VW, VH, (ambOf(Bp) === am && k ? 1 : rg(t, B.t0, .6)) * (ambOf(T.beats[k + 1]) === am ? 1 : 1 - rg(t, B.t1 - .5, .5)));
	memoryTint(c, t, T, k, B, VW, VH);
	remoteLayer(c, t, T, k, B, VW, VH, port, head, head[0] > VW * .5 ? -1 : 1);
	const cb2 = c.createLinearGradient(0, VH - 220, 0, VH); cb2.addColorStop(0, 'rgba(11,11,13,0)'); cb2.addColorStop(1, 'rgba(11,11,13,.92)'); c.fillStyle = cb2; c.fillRect(0, VH - 220, VW, 220);
	if (P.captions !== false) caption(c, t, P.words || [], B, VW, VH, port);
	c.strokeStyle = 'rgba(255,181,71,.55)'; c.lineWidth = 3; [[40, 40, 1, 1], [VW - 40, 40, -1, 1], [40, VH - 40, 1, -1], [VW - 40, VH - 40, -1, -1]].forEach(([x, y, sx, sy]) => {c.beginPath(); c.moveTo(x, y + sy * 60); c.lineTo(x, y); c.lineTo(x + sx * 60, y); c.stroke();});}

/* ── what the HERO does in a beat: the writer's pose (any movement set), adjusted to who they reach off-screen ── */
const GENERIC = ['stand', 'explain', 'talk', 'listen', 'center', ''];
function heroAct(b) {if (!b) return 'stand'; let a = ACTS[b.pose] ? b.pose : 'stand'; const rem = Array.isArray(b.remote) ? b.remote : [];
	if (GENERIC.includes(a) && rem.length) {const h = rem[0].how; a = h === 'phone' ? 'phone' : h === 'video' ? 'text' : h === 'far' ? 'look' : h === 'heard' ? 'listen' : h === 'thought' ? 'think' : h === 'tv' ? 'stand' : a;}
	return a;}

/* ── OFF-SCREEN PEOPLE (beat.remote [{id, how}]): never placed in the room. how = phone | video (a call bubble wired to the hero's
   phone) · tv (on a screen) · far (seen in the distance: a spyglass bubble + sightline) · heard (a voice from off-frame: a chip at
   the frame edge with a waveform) · thought (remembered / imagined: a thought cloud over the hero's head) ── */
const HOW_LABEL = {phone: 'ON THE PHONE', video: 'VIDEO CALL', tv: 'ON TV', far: 'FAR AWAY', heard: 'OFF-SCREEN VOICE', thought: 'REMEMBERED', mention: 'MENTIONED'};
const HOWS = Object.keys(HOW_LABEL);
/* the effects to draw at this beat: its own (looping ones end with the beat), and the last beat's one-shots that are still going */
function vfxList(T, k) {const B = T.beats[k], P = T.beats[k - 1], out = [];
	(Array.isArray(B && B.vfx) ? B.vfx : []).filter((v) => v && VFX[v.kind]).slice(0, 3).forEach((v) => out.push([v, B]));
	(Array.isArray(P && P.vfx) ? P.vfx : []).filter((v) => v && VFX[v.kind] && VFX[v.kind].once && !out.find(([w]) => w.kind === v.kind)).forEach((v) => out.push([v, P]));
	return out;}
const vfxStart = (v, b) => (v.t != null ? b.t0 + +v.t : b.cue ?? b.t0 + .3);
/* a FLASHBACK beat (beat.flash, set by the narration pass): warm memory wash, soft dreamy vignette, a bloom on the cut, a MEMORY tag */
function memoryTint(c, t, T, k, B, VW, VH) {const P = T.beats[k - 1], N = T.beats[k + 1];
	const a = B.flash ? (P && P.flash ? 1 : E.o(rg(t, B.t0, .45))) * (N && N.flash ? 1 : 1 - rg(t, B.t1 - .35, .35)) : 0, bloom = (B.flash && !(P && P.flash)) || (!B.flash && P && P.flash) ? Math.exp(-Math.max(0, t - B.t0) * 7) : 0;
	if (a > 0) {c.save(); c.globalCompositeOperation = 'color'; c.fillStyle = `rgba(196,150,96,${.62 * a})`; c.fillRect(0, 0, VW, VH); c.globalCompositeOperation = 'source-over';
		const v = c.createRadialGradient(VW / 2, VH / 2, VH * .3, VW / 2, VH / 2, VW * .7); v.addColorStop(0, 'rgba(255,236,200,0)'); v.addColorStop(1, `rgba(255,236,200,${.22 * a})`); c.fillStyle = v; c.fillRect(0, 0, VW, VH);
		for (let i = 0; i < 40; i++) {c.globalAlpha = a * .25 * (.5 + .5 * Math.sin(t * 1.3 + i)); c.fillStyle = '#FFF3DC'; c.fillRect(hash(i * 3.3) * VW, frac(hash(i) - t * .02) * VH, 2, 2);} c.globalAlpha = 1;
		c.font = `700 22px ${HUD}`; const w = c.measureText('MEMORY').width + 34; c.globalAlpha = a; c.fillStyle = 'rgba(11,11,13,.7)'; c.strokeStyle = C.champ; c.lineWidth = 2; c.beginPath(); c.roundRect(70, 66, w, 40, 20); c.fill(); c.stroke();
		c.fillStyle = C.champ; c.textAlign = 'left'; c.fillText('MEMORY', 87, 93); c.restore();}
	if (bloom > .01) {c.fillStyle = `rgba(255,243,220,${bloom * .85})`; c.fillRect(0, 0, VW, VH);}}
function remoteLayer(c, t, T, k, B, VW, VH, port, head, side) {const list = (Array.isArray(B.remote) ? B.remote : []).filter((r) => r && T.cast[r.id] && HOWS.includes(r.how)).slice(0, 2); if (!list.length) return;
	const prev = T.beats[k - 1], next = T.beats[k + 1], has = (b, r) => b && Array.isArray(b.remote) && b.remote.some((x) => x && x.id === r.id && x.how === r.how);
	let slot = 0;
	list.forEach((r) => {const m = T.cast[r.id], a = (has(prev, r) ? 1 : E.o(rg(t, B.t0, .35))) * (has(next, r) ? 1 : 1 - rg(t, B.t1 - .3, .3)); if (a <= 0) return;
		const talk = B.talker === r.id, ph = m.i * 2.3, name = String(m.name || r.id).toUpperCase().slice(0, 16);
		if (r.how === 'heard') {const x = side > 0 ? VW - 60 : 60, y = port ? 560 + slot * 170 : 300 + slot * 150; c.save(); c.globalAlpha = a;
			for (let i = 0; i < 4; i++) {const q = frac(t * .9 + i / 4); c.strokeStyle = C.gold; c.globalAlpha = a * (1 - q); c.lineWidth = 4; c.beginPath(); c.arc(x + side * 30, y, 30 + q * 220, side > 0 ? PI * .75 : -PI * .25, side > 0 ? PI * 1.25 : PI * .25); c.stroke();}
			c.globalAlpha = a; const w = 300, bx = side > 0 ? x - w : x; c.fillStyle = 'rgba(11,11,13,.88)'; c.strokeStyle = C.gold; c.lineWidth = 2.5; c.beginPath(); c.roundRect(bx, y - 44, w, 88, 44); c.fill(); c.stroke();
			for (let i = 0; i < 14; i++) {const h = (talk ? .35 + .65 * Math.abs(Math.sin(t * 9 + i * 1.7)) : .2 + .15 * Math.sin(t * 2 + i)) * 46; c.fillStyle = i % 3 ? C.champ : C.gold; c.fillRect(bx + 28 + i * 9, y - h / 2 - 8, 5, h);}
			c.font = `700 24px ${HUD}`; c.fillStyle = C.pale; c.textAlign = 'left'; c.fillText(name, bx + 166, y - 4); c.font = `600 15px ${HUD}`; c.fillStyle = C.gold; c.fillText(HOW_LABEL.heard, bx + 166, y + 22); c.restore(); slot++; return;}
		// a bubble (phone / video / tv / far) or a thought cloud
		const thought = r.how === 'thought' || r.how === 'mention', rad = (port ? 160 : 140) * (.85 + .15 * E.back(clamp(a))), cx = thought ? clamp(head[0] + side * 230, rad + 30, VW - rad - 30) : (side > 0 ? VW - rad - 70 - slot * (rad * 2 + 40) : rad + 70 + slot * (rad * 2 + 40)),
			cy = thought ? clamp(head[1] - 260, rad + 40, VH * .6) : (port ? 360 : rad + 80) + (port ? slot * (rad * 2 + 70) : 0);
		c.save(); c.globalAlpha = a;
		if (thought) {[[.25, 14], [.5, 22]].forEach(([u, rr2]) => {c.fillStyle = 'rgba(242,212,155,.85)'; c.beginPath(); c.arc(lerp(head[0] + side * 40, cx, u), lerp(head[1] - 60, cy + rad * .8, u), rr2, 0, 7); c.fill();});}
		else if (r.how === 'phone' || r.how === 'video') {const hp = [head[0] + side * 40, head[1] + 10], q0 = [cx - side * rad * .9, cy + rad * .35]; c.strokeStyle = C.gold; c.lineWidth = 3; c.setLineDash([3, 12]); c.beginPath(); c.moveTo(hp[0], hp[1]);
			const mx = (hp[0] + q0[0]) / 2, my = Math.min(hp[1], q0[1]) - 120; c.quadraticCurveTo(mx, my, q0[0], q0[1]); c.stroke(); c.setLineDash([]);
			for (let i = 0; i < 3; i++) {const u = frac(t * .7 + i / 3), uu = talk ? 1 - u : u, bx = (1 - uu) * (1 - uu) * hp[0] + 2 * (1 - uu) * uu * mx + uu * uu * q0[0], by = (1 - uu) * (1 - uu) * hp[1] + 2 * (1 - uu) * uu * my + uu * uu * q0[1];
				c.fillStyle = C.pale; c.shadowColor = C.gold; c.shadowBlur = 16; c.beginPath(); c.arc(bx, by, 6, 0, 7); c.fill(); c.shadowBlur = 0;}}
		else if (r.how === 'far') {c.strokeStyle = 'rgba(255,181,71,.6)'; c.lineWidth = 2; c.setLineDash([10, 10]); c.lineDashOffset = -t * 40; c.beginPath(); c.moveTo(head[0] + side * 30, head[1] - 10); c.lineTo(cx - side * rad, cy); c.stroke(); c.setLineDash([]); c.lineDashOffset = 0;}
		// the frame
		const rect = r.how === 'video' || r.how === 'tv', shape = () => {c.beginPath(); if (thought) {for (let i = 0; i < 9; i++) {const an = i / 9 * 2 * PI; c.moveTo(cx + Math.cos(an) * rad * .78 + rad * .28, cy + Math.sin(an) * rad * .62); c.arc(cx + Math.cos(an) * rad * .78, cy + Math.sin(an) * rad * .62, rad * .28, 0, 7);} c.moveTo(cx + rad * .82, cy); c.ellipse(cx, cy, rad * .82, rad * .66, 0, 0, 7);}
			else if (rect) c.roundRect(cx - rad * 1.15, cy - rad * .8, rad * 2.3, rad * 1.6, 18); else c.arc(cx, cy, rad, 0, 7);};
		c.save(); shape(); c.clip();
		const bg = c.createLinearGradient(0, cy - rad, 0, cy + rad); bg.addColorStop(0, thought ? '#4A4F58' : C.char1); bg.addColorStop(1, thought ? '#6B717C' : C.graph2);       // a cool dreamy backdrop: warm figures read on it c.fillStyle = bg; c.fillRect(cx - rad * 1.3, cy - rad, rad * 2.6, rad * 2);
		for (let i = 0; i < 18; i++) {const wx = cx - rad * 1.2 + hash(i + m.i * 9) * rad * 2.4, wy = cy - rad + hash(i + 3) * rad * 1.1; c.fillStyle = thought ? 'rgba(255,243,220,.10)' : hash(i + 7) > .5 ? 'rgba(255,181,71,.55)' : 'rgba(242,212,155,.3)'; c.fillRect(wx, wy, 10, 14);}
		const farV = r.how === 'far', s = farV ? rad / 380 : rad / 200, fy = farV ? cy + rad * .72 : cy + rad * 1.78;
		if (farV) {c.fillStyle = C.graph; c.fillRect(cx - rad * 1.3, cy + rad * .72, rad * 2.6, rad);}
		const lkAct = r.how === 'phone' ? 'phone' : r.how === 'far' ? (talk ? 'wave' : 'stand') : talk ? 'talk' : 'stand', Rr = rigFor(t, m.lk, ACTS[r.act] ? r.act : lkAct, ph, -side, talk, talk ? B.mood : 'neutral', t - B.t0);
		if (m.species) {const S0 = SPECIES[m.species] || {}, tall = S0.type === 'quad' ? (S0.leg + S0.h + (S0.neck || 0) * .6 + S0.head) : (S0.size || 40) * 3, k2 = rad * 1.1 / Math.max(80, tall);   // an animal fills its bubble
			c.save(); c.translate(cx, cy + rad * .62); c.scale(k2, k2); drawAnimal(c, t, {kind: m.species, act: talk ? 'speak' : (r.act && ['sit', 'sleep', 'eat', 'wag'].includes(r.act) ? r.act : 'wag'), dir: -side}); c.restore();}
		else person(c, t, cx, fy, s, 0, Rr);
		if (thought) {const gl = c.createRadialGradient(cx, cy, rad * .2, cx, cy, rad); gl.addColorStop(0, 'rgba(255,243,220,0)'); gl.addColorStop(1, 'rgba(255,243,220,.28)'); c.fillStyle = gl; c.fillRect(cx - rad * 1.3, cy - rad, rad * 2.6, rad * 2);}
		if (rect) {c.strokeStyle = 'rgba(255,255,255,.05)'; c.lineWidth = 2; for (let y = cy - rad; y < cy + rad; y += 6) {c.beginPath(); c.moveTo(cx - rad * 1.2, y); c.lineTo(cx + rad * 1.2, y); c.stroke();}}
		c.restore();
		c.strokeStyle = C.gold; c.lineWidth = 4; c.shadowColor = C.gold; c.shadowBlur = 18; shape(); c.stroke(); c.shadowBlur = 0;
		if (r.how === 'tv' || r.how === 'video') {c.fillStyle = r.how === 'tv' ? C.ember : C.gold; c.beginPath(); c.roundRect(cx - rad * 1.1, cy - rad * .74, 70, 26, 6); c.fill(); c.fillStyle = C.char0; c.font = `800 15px ${HUD}`; c.textAlign = 'center'; c.fillText(r.how === 'tv' ? 'LIVE' : 'CALL', cx - rad * 1.1 + 35, cy - rad * .74 + 18);}
		if (r.how === 'phone' && talk) for (let i = 0; i < 3; i++) {const q = frac(t * 1.4 + i / 3); c.strokeStyle = C.gold; c.globalAlpha = a * (1 - q); c.lineWidth = 3; c.beginPath(); c.arc(cx, cy, rad + 6 + q * 40, 0, 7); c.stroke();} c.globalAlpha = a;
		const ly = thought ? cy + rad * .78 : rect ? cy + rad * .8 + 16 : cy + rad + 16, lw = Math.max(200, name.length * 15 + 40);   // (mention = the same cloud, labelled MENTIONED)
		c.fillStyle = 'rgba(11,11,13,.9)'; c.strokeStyle = 'rgba(255,181,71,.7)'; c.lineWidth = 2; c.beginPath(); c.roundRect(cx - lw / 2, ly, lw, 54, 12); c.fill(); c.stroke();
		c.textAlign = 'center'; c.font = `700 22px ${HUD}`; c.fillStyle = C.pale; c.fillText(name, cx, ly + 25); c.font = `600 13px ${HUD}`; c.fillStyle = C.gold; c.fillText(HOW_LABEL[r.how], cx, ly + 44);
		c.restore(); if (!thought) slot++;});
	c.textAlign = 'left';}

/* ── LIBRARY PREVIEWS: draw one library item on its own (library thumbnails, Explainer "dio" pictures, EXPLAINED figures).
   item = {type: char|act|animal|ride|obj|prop|place, look, act, kind, name, id, kit}; t = seconds (they animate) ── */
export function drawLibItem(c, W, H, t, item, opt) {item = item || {}; opt = opt || {}; const k0 = K, cx0 = CX, cy0 = CY;
	c.save(); if (opt.bg !== false) {const g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, C.char1); g.addColorStop(1, '#1B1712'); c.fillStyle = g; c.fillRect(0, 0, W, H);}
	const ty = item.type || 'char';
	try {
		if (ty === 'char' || ty === 'act' || ty === 'ride') {const name = ACTS[item.act] ? item.act : ty === 'ride' ? 'drive' : 'stand', sp = actSpec(name, t, 0, t), wide = sp.ride || sp.piece ? (sp.ride === 'plane' ? 1500 : sp.piece === 'goal' || sp.piece === 'hoop' ? 1100 : 900) : 300;
			const sc = Math.min(H * .78 / (sp.piece === 'hoop' ? 860 : 520), W * .9 / wide), x = W / 2 - (sp.piece === 'goal' || sp.piece === 'hoop' ? 380 * sc : 0), y = H * .9;
			c.fillStyle = 'rgba(255,181,71,.18)'; c.fillRect(0, y, W, 2);
			const R = rigFor(t, lookOf(item.look || {}), name, 0, 1, !!sp.talk, item.mood || 'neutral', t); R.walk = item.walk ? 1 : 0; person(c, t, x, y, sc, 0, R);}
		else if (ty === 'animal') {const S0 = SPECIES[item.kind] || SPECIES.dog, big = S0.type === 'quad' ? Math.max(S0.leg + S0.h + (S0.neck || 0) * .8 + S0.head, S0.len * .62) : S0.type === 'bird' ? S0.size * 3.5 : S0.type === 'fish' ? S0.size * 1.6 : S0.type === 'sprite' ? S0.h * 1.25 + (S0.swim ? 160 : 0) : 140;
			const sc = Math.min(H * .7 / Math.max(60, big), W * .8 / Math.max(80, (S0.len || S0.size * 3 || 140) * 1.5)); c.translate(W / 2, S0.type === 'fly' ? H * .5 + 260 * sc : S0.type === 'bird' && item.act === 'fly' ? H * .5 + S0.size * 4 * sc : H * .86); c.scale(sc, sc); drawAnimal(c, t, {kind: item.kind, act: item.act || 'idle', mv: ['walk', 'run'].includes(item.act) ? 1 : 0});}
		else if (ty === 'vfx') {const k2 = Math.min(W, H) / 7, once = (VFX[item.kind] || {}).once || 0, u = once ? (t % (once + .4)) : t + 2; c.fillStyle = 'rgba(255,181,71,.14)'; c.beginPath(); c.ellipse(W / 2, H * .8, k2 * 2.6, k2 * .8, 0, 0, 7); c.fill();
			drawVfx(c, item.kind, W / 2, H * .8, k2, u, t + 2, 3, [[W * .1, H * .8], [W / 2, H * .62], [W * .9, H * .8], [W / 2, H * .98]], W, H);}
		else if (ty === 'obj') {const bb = (ITEMS[item.name] || {}).bb; if (bb) {const s = Math.min(W / (bb[2] - bb[0]), H / (bb[3] - bb[1])) * .8; c.translate(W / 2, H / 2); c.scale(s, s); c.translate(-(bb[0] + bb[2]) / 2, -(bb[1] + bb[3]) / 2);} else {c.translate(W / 2, H / 2); const s = Math.min(W, H) / 110; c.scale(s, s);} drawItem(c, item.name, 0, 0, 0, t);}
		else if (ty === 'prop' || ty === 'place') {const pid = item.id || item.name;
			if (ty === 'prop') {const D = PDEF[pid] || [1, 1, 1], p = {t: pid, w: D[0], d: D[1], h: D[2]}, SP = (FPROPS[pid] || {}).sprite; CX = 0; CY = 0; if (SP) {K = Math.min(W / (SP.w / 100), H / (SP.h / 100)) * .82; c.translate(W / 2, H * .91); const q = S(D[0] / 2, D[1] / 2, 0); c.translate(-q[0], -q[1]);} else {K = Math.min(W, H) / 2.8; c.translate(W / 2, H * .62); const q = S(D[0] / 2, D[1] / 2, D[2] / 2); c.translate(-q[0], -q[1]);} propDraw(c, t, p, 0, 0, true);}
			else {let P = PL[pid]; if (!P && item.kit) {useKits({kits: [{...item.kit, o: [0, 0]}], world: item.kit.world}); P = PL[item.kit.id];} if (P) {const o = P.o, z = P.z || 0; K = Math.min(W / 7.2, H / 4.6); CX = (o[0] + 2 - (o[1] + 2)) * CO * K; CY = (o[0] + 2 + o[1] + 2) * .5 * K - (z + .9) * K;
				c.translate(W / 2, H / 2); const R = {pos: [-99, -99, 0], place: '', draw: false, lie: 0}; const fn = {apartment: () => room(c, t, R, null, 0), office: () => office(c, t, R, null, false), lab: () => lab(c, t, R, null, false), cafe: () => cafe(c, t, R, null, false), street: () => street(c, t, R, null, false), rooftop: () => rooftop(c, t, R, null, .4)}[pid];
				PEOPLE = {}; if (fn) fn(); else kitPlace(c, t, R, null, false, P.kit ? P.kit.id || pid : pid);}}}
	} finally {K = k0; CX = cx0; CY = cy0; c.restore();}}
export {ACT_NAMES, SPECIES, VFX_NAMES, VFX};
export const setWorld = (id) => useKits({world: id, beats: []});
export const registerMint = (F) => useMint(F, FREG);
export {preloadMint, setSpriteResolver};      // previews / thumbnails of minted assets (motion_mint.preview)

function caption(c, t, words, B, VW, VH, port) {
	const ws = words.filter((w) => w.s >= B.t0 - .05 && w.s < B.t1 - .02); if (!ws.length) return;
	const size = port ? 52 : 46, max = VW - (port ? 140 : 360); c.save(); c.textAlign = 'left'; c.font = `700 ${size}px ${FX}`;
	const sp = size * .3, lines = [[]]; let lw = 0;
	for (const w of ws) {const wd = c.measureText(w.w).width; if (lw + wd > max && lines[lines.length - 1].length) {lines.push([]); lw = 0;} lines[lines.length - 1].push({...w, wd}); lw += wd + sp;}
	const lh = size * 1.22, y0 = VH - (port ? 200 : 70) - (lines.length - 1) * lh, fade = rg(t, B.t0, .2);
	lines.forEach((ln, li) => {const tot = ln.reduce((s, x) => s + x.wd, 0) + sp * (ln.length - 1); let x = VW / 2 - tot / 2;
		for (const w of ln) {const on = t >= w.s, cur = on && t < w.e + .12; c.shadowColor = 'rgba(0,0,0,.6)'; c.shadowBlur = 14; c.globalAlpha = fade * (on ? 1 : .42); c.fillStyle = cur ? C.gold : C.white; c.fillText(w.w, x, y0 + li * lh); x += w.wd + sp;}});
	c.restore();}
