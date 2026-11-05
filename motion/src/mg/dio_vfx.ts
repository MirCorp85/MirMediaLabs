// @ts-nocheck
/* DIORAMA VFX (Oct 29 2026, user: "the motion studio is lacking VFX … explosions, fires, floods, smokes"). Part of the shared
   MOTION LIBRARY. Each effect is drawn in SCREEN space at an anchor (x, y = a point on the ground), scaled by k (pixels per world
   unit), with u = seconds since it started (one-shot effects play out and end, looping ones keep going) and t = film time.
   Beats ask for them as vfx: [{kind, at, t}]; the narration pass (motion_wizard.direct_line) adds them from what the line says. */
const PI = Math.PI;
const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x), frac = (x) => x - Math.floor(x), lerp = (a, b, u) => a + (b - a) * u;
const hash = (n) => frac(Math.sin(n * 127.1 + 311.7) * 43758.5453);
const GOLD = '#FFB547', CHAMP = '#F2D49B', EMBER = '#E0703A', BRONZE = '#7A5226', BRASS = '#B8862E', CHAR1 = '#131418';
const rad = (c, x, y, r, stops) => {const g = c.createRadialGradient(x, y, 0, x, y, Math.max(1, r)); stops.forEach(([o, col]) => g.addColorStop(o, col)); return g;};
const puff = (c, x, y, r, rgb, a) => {if (a <= 0 || r <= 0) return; c.globalAlpha = Math.min(1, a); c.fillStyle = rad(c, x, y, r, [[0, `rgba(${rgb},1)`], [.6, `rgba(${rgb},.55)`], [1, `rgba(${rgb},0)`]]); c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); c.globalAlpha = 1;};

function explosion(c, x, y, k, u, t, seed) {
	if (u < .12) {c.fillStyle = `rgba(255,248,225,${(1 - u / .12) * .8})`; c.fillRect(x - 40 * k, y - 40 * k, 80 * k, 80 * k);}
	const R = k * (.6 + 2.2 * (1 - Math.exp(-u * 4))), fa = Math.max(0, 1 - u / 1.1);
	c.strokeStyle = `rgba(255,220,160,${Math.max(0, .8 - u)})`; c.lineWidth = Math.max(2, k * .12 * (1 - Math.min(1, u))); c.beginPath(); c.ellipse(x, y, R * 1.8, R * .55, 0, 0, 7); c.stroke();
	for (let i = 0; i < 9; i++) {const a = hash(seed + i) * 2 * PI, rr = R * (.3 + hash(seed + i * 3) * .5);
		puff(c, x + Math.cos(a) * rr, y - R * .6 + Math.sin(a) * rr * .6 - u * k * .8, R * (.45 + hash(i + seed) * .3), i % 3 ? '255,150,50' : '255,230,150', fa);}
	for (let i = 0; i < 12; i++) {const a = -PI * (.1 + hash(seed + i * 7) * .8), v = k * (3 + hash(i + seed * 2) * 4), px = x + Math.cos(a) * v * u, py = y - R * .3 + Math.sin(a) * v * u + 3.4 * k * u * u;
		if (py < y + k * .2) {c.fillStyle = i % 2 ? CHAR1 : BRONZE; c.globalAlpha = Math.max(0, 1 - u / 2.4); c.fillRect(px - k * .06, py - k * .06, k * .12, k * .12); c.globalAlpha = 1;}}
	for (let i = 0; i < 8; i++) {const q = clamp((u - .3 - i * .08) / 2.6); if (q <= 0) continue; puff(c, x + (hash(seed + i * 5) - .5) * k * 2.2, y - k * (.6 + q * 3.2), k * (.7 + q * 1.4), '90,92,98', .55 * Math.sin(q * PI));}
	const gl = Math.max(0, 1 - u / 1.6); c.fillStyle = rad(c, x, y - k * .5, k * 5, [[0, `rgba(255,170,70,${.45 * gl})`], [1, 'rgba(255,140,60,0)']]); c.fillRect(x - k * 5, y - k * 5.5, k * 10, k * 10);}
function dust(c, x, y, k, u, t, seed) {for (let i = 0; i < 12; i++) {const a = hash(seed + i) * 2 * PI, q = clamp(u / 3.2);
	puff(c, x + Math.cos(a) * k * (.4 + q * 3), y + Math.sin(a) * k * .9 * (.4 + q * 2) - k * q * .6, k * (.6 + q * 1.3), '160,140,110', .55 * (1 - q));}}

export const VFX = {
	explosion: {desc: 'a blast: flash, fireball, shockwave, flying debris, then smoke', once: 3.2, shake: .5, f: explosion},
	fire: {desc: 'flames burning on the spot, embers and a warm glow', f: (c, x, y, k, u, t, seed) => {const g = Math.min(1, u / .6);
		c.fillStyle = rad(c, x, y - k * .6, k * 3.2, [[0, `rgba(255,160,60,${.4 * g})`], [1, 'rgba(255,120,40,0)']]); c.fillRect(x - k * 3.2, y - k * 3.8, k * 6.4, k * 6.4);
		for (let i = 0; i < 16; i++) {const q = frac(t * 1.6 + hash(seed + i)), sx = x + (hash(seed + i * 3) - .5) * k * 1.6 * (1 - q * .5) + Math.sin(t * 6 + i) * k * .08;
			c.fillStyle = `rgba(255,${Math.round(200 - q * 140)},${Math.round(60 - q * 40)},${(1 - q) * .9 * g})`; c.beginPath(); c.ellipse(sx, y - q * k * 2.2 * g, k * (.32 * (1 - q) + .06), k * (.5 * (1 - q) + .1), 0, 0, 7); c.fill();}
		for (let i = 0; i < 10; i++) {const q = frac(t * .5 + hash(seed + i * 9)); c.fillStyle = `rgba(255,200,110,${(1 - q) * g})`; c.fillRect(x + (hash(i + seed) - .5) * k * 2 + Math.sin(t * 2 + i) * k * .3, y - k * (1 + q * 3.5), 2.5, 2.5);}}},
	smoke: {desc: 'a thick column of grey smoke drifting up', f: (c, x, y, k, u, t, seed) => {const g = Math.min(1, u);
		for (let i = 0; i < 14; i++) {const q = frac(t * .18 + i / 14); puff(c, x + Math.sin(q * 4 + i) * k * .4 + q * k * 1.2, y - k * (.3 + q * 5), k * (.4 + q * 1.5), i % 2 ? '100,102,108' : '70,72,78', .5 * Math.sin(q * PI) * g);}}},
	flood: {desc: 'water rising over the place, waves and floating debris', ground: true, f: (c, x, y, k, u, t, seed, poly) => {const h = Math.min(1, u / 3) * k * .9;
		const pts = poly || [[x - k * 4, y], [x, y - k * 2.3], [x + k * 4, y], [x, y + k * 2.3]];
		c.beginPath(); pts.forEach((p, i) => (i ? c.lineTo(p[0], p[1] - h) : c.moveTo(p[0], p[1] - h))); c.closePath(); c.fillStyle = 'rgba(42,74,92,.62)'; c.fill(); c.save(); c.clip();
		c.strokeStyle = 'rgba(216,220,226,.5)'; c.lineWidth = 2; for (let i = 0; i < 14; i++) {const wx = x + (hash(seed + i) - .5) * k * 7 + Math.sin(t + i) * k * .3, wy = y - h + (hash(i * 3 + seed) - .5) * k * 3.5;
			c.beginPath(); c.moveTo(wx - k * .4, wy); c.quadraticCurveTo(wx, wy - k * .12 * (1 + Math.sin(t * 2 + i)), wx + k * .4, wy); c.stroke();}
		[[.3, .2], [-.4, .6], [.7, -.3]].forEach(([dx, dy], i) => {const bx = x + dx * k * 2.5 + Math.sin(t * .6 + i) * k * .3, by = y - h + dy * k * 1.2 + Math.sin(t * 1.4 + i) * 2; c.fillStyle = i === 1 ? BRONZE : BRASS; c.fillRect(bx - k * .25, by - k * .07, k * .5, k * .14);});
		c.restore();}},
	lightning: {desc: 'a lightning strike with a white flash', once: 1.4, f: (c, x, y, k, u, t, seed, poly, VW, VH) => {
		if (u < .5 && frac(u * 9) < .6) {c.fillStyle = `rgba(235,240,255,${.35 * (1 - u * 2)})`; c.fillRect(0, 0, VW, VH);
			c.strokeStyle = '#F2F6FA'; c.lineWidth = Math.max(2, k * .08); c.shadowColor = '#BFD4FF'; c.shadowBlur = 24; c.beginPath(); let px = x + k * 1.5; c.moveTo(px, 0);
			for (let i = 1; i <= 9; i++) {px += (hash(seed + i) - .5) * k * 1.6; c.lineTo(px, y * i / 9);} c.stroke(); c.shadowBlur = 0;}
		puff(c, x + k * 1.5, y, k * 1.2, '255,240,200', Math.max(0, .7 - u));}},
	sparks: {desc: 'a shower of electric sparks', f: (c, x, y, k, u, t, seed) => {for (let i = 0; i < 22; i++) {const q = frac(t * 1.3 + hash(seed + i)), a = -PI * (.15 + hash(i * 7 + seed) * .7), v = k * 3;
		const px = x + Math.cos(a) * v * q, py = y - k * 1.2 + Math.sin(a) * v * q + 4 * k * q * q; c.strokeStyle = `rgba(255,${Math.round(230 - q * 80)},140,${1 - q})`; c.lineWidth = 2;
		c.beginPath(); c.moveTo(px, py); c.lineTo(px - Math.cos(a) * k * .2, py - Math.sin(a) * k * .2 - k * q * .3); c.stroke();}
		if (frac(t * 3) < .2) puff(c, x, y - k * 1.2, k * .6, '255,250,220', .8);}},
	dust: {desc: 'a cloud of dust rolling out (a collapse, a crash, a stampede)', once: 4, f: dust},
	splash: {desc: 'a splash of water', once: 1.6, f: (c, x, y, k, u, t, seed) => {for (let i = 0; i < 18; i++) {const a = -PI * (.1 + hash(seed + i) * .8), v = k * (2 + hash(i + 3) * 2.5), px = x + Math.cos(a) * v * u, py = y + Math.sin(a) * v * u + 6 * k * u * u;
		if (py < y + 2) {c.fillStyle = `rgba(190,215,235,${1 - u / 1.6})`; c.beginPath(); c.arc(px, py, k * .07, 0, 7); c.fill();}}
		c.strokeStyle = `rgba(216,220,226,${Math.max(0, 1 - u / 1.6)})`; c.lineWidth = 2; c.beginPath(); c.ellipse(x, y, k * (.3 + u * 2), k * (.1 + u * .6), 0, 0, 7); c.stroke();}},
	fireworks: {desc: 'fireworks bursting in the sky', sky: true, f: (c, x, y, k, u, t, seed, poly, VW, VH) => {for (let n = 0; n < 4; n++) {const q = frac((t + n * .45) / 1.8), cyc = Math.floor((t + n * .45) / 1.8);
		const bx = VW * (.2 + hash(seed + n * 3 + cyc) * .6), by = VH * (.12 + hash(n + cyc * 5) * .25), col = [GOLD, CHAMP, EMBER, '#9ECAE8'][n % 4];
		if (q < .25) {c.fillStyle = col; c.fillRect(bx - 1.5, by + (1 - q / .25) * 300, 3, 10);}
		else {const r = (q - .25) / .75; c.fillStyle = col; c.globalAlpha = 1 - r; for (let i = 0; i < 24; i++) {const a = i / 24 * 2 * PI; c.beginPath(); c.arc(bx + Math.cos(a) * r * 140, by + Math.sin(a) * r * 140 + r * r * 40, 3, 0, 7); c.fill();} c.globalAlpha = 1;}}}},
	tornado: {desc: 'a twisting tornado of wind and debris', f: (c, x, y, k, u, t, seed) => {const g = Math.min(1, u / 1.2), sx = x + Math.sin(t * .7) * k * .8;
		for (let i = 0; i < 26; i++) {const q = i / 26, w = k * (.3 + q * 2.2), ang = t * 6 + i * .7; c.strokeStyle = `rgba(150,152,158,${.55 * g})`; c.lineWidth = Math.max(2, k * .1);
			c.beginPath(); c.ellipse(sx + Math.sin(q * 3 + t) * k * .3, y - q * k * 6, w, w * .25, 0, ang, ang + 2.4); c.stroke();}
		for (let i = 0; i < 8; i++) {const q = frac(t * .6 + i / 8), a = t * 5 + i; c.fillStyle = BRONZE; c.fillRect(sx + Math.cos(a) * k * (.4 + q * 1.8), y - q * k * 5.5, k * .1, k * .1);}}},
	meteor: {desc: 'a meteor streaking down and hitting the ground', once: 4.2, shake: .5, f: (c, x, y, k, u, t, seed) => {
		if (u < 1) {const mx = lerp(x - k * 12, x, u), my = lerp(y - k * 14, y, u); c.strokeStyle = 'rgba(255,200,120,.8)'; c.lineWidth = k * .25; c.lineCap = 'round';
			c.beginPath(); c.moveTo(mx - k * 3, my - k * 3.5); c.lineTo(mx, my); c.stroke(); puff(c, mx, my, k * .7, '255,240,200', 1);}
		else explosion(c, x, y, k, u - 1, t, seed + 3);}},
	magic: {desc: 'glowing magic sparkles swirling', f: (c, x, y, k, u, t, seed) => {for (let i = 0; i < 26; i++) {const a = t * 2 + i * .9, r = k * (.4 + (i % 5) * .25), py = y - k * (.5 + frac(t * .3 + i / 26) * 2.6);
		const px = x + Math.cos(a) * r, b = .5 + .5 * Math.sin(t * 5 + i); c.fillStyle = rad(c, px, py, k * .18, [[0, `rgba(255,236,170,${b})`], [1, 'rgba(255,181,71,0)']]); c.beginPath(); c.arc(px, py, k * .18, 0, 7); c.fill();}}},
	steam: {desc: 'white steam or mist rising', f: (c, x, y, k, u, t, seed) => {for (let i = 0; i < 10; i++) {const q = frac(t * .3 + i / 10); puff(c, x + Math.sin(q * 5 + i) * k * .5, y - k * (.2 + q * 3), k * (.3 + q), '230,234,240', .4 * Math.sin(q * PI));}}},
	quake: {desc: 'an earthquake: cracks spread and dust rises (the frame shakes)', shake: .35, f: (c, x, y, k, u, t, seed) => {const g = Math.min(1, u / 1.5);
		c.strokeStyle = 'rgba(11,11,13,.85)'; c.lineWidth = Math.max(2, k * .06); for (let n = 0; n < 4; n++) {c.beginPath(); let px = x, py = y; c.moveTo(px, py); const a = hash(seed + n) * 2 * PI;
			for (let i = 1; i < 1 + 6 * g; i++) {px += Math.cos(a + (hash(i + n * 9) - .5)) * k * .5; py += Math.sin(a + (hash(i * 3 + n) - .5)) * k * .28; c.lineTo(px, py);} c.stroke();}
		dust(c, x, y, k, frac(u / 3) * 3, t, seed);}},
	bubbles: {desc: 'bubbles floating up (underwater, chemistry, joy)', f: (c, x, y, k, u, t, seed) => {for (let i = 0; i < 14; i++) {const q = frac(t * .4 + hash(seed + i)); c.strokeStyle = `rgba(216,230,240,${(1 - q) * .8})`; c.lineWidth = 1.5;
		c.beginPath(); c.arc(x + (hash(i) - .5) * k * 1.8 + Math.sin(t * 2 + i) * k * .15, y - q * k * 3.5, k * (.06 + hash(i + 4) * .12), 0, 7); c.stroke();}}},
};
export const VFX_NAMES = Object.keys(VFX);
/* the frame shake an effect asks for at time u (explosions, meteors, quakes) */
export const vfxShake = (kind, u) => {const v = VFX[kind]; if (!v || !v.shake || u < 0 || (v.once && u > v.once)) return 0; return kind === 'quake' ? v.shake * Math.min(1, u) : v.shake * Math.exp(-Math.max(0, kind === 'meteor' ? u - 1 : u) * 5) * (kind === 'meteor' && u < 1 ? 0 : 1);};
export function drawVfx(c, kind, x, y, k, u, t, seed = 1, poly = null, VW = 1920, VH = 1080) {const v = VFX[kind]; if (!v || u < 0 || (v.once && u > v.once)) return; c.save(); try {v.f(c, x, y, k, u, t, seed, poly, VW, VH);} finally {c.restore();}}
