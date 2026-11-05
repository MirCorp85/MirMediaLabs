// MIR MOTION GRAPHICS — animated characters. A 2D puppet (forward-kinematics skeleton + face) that ACTS: gives a speech at
// a podium with its mouth moving on the spoken words, runs and scores a goal, shoots a basket, waves, celebrates… Every
// action is a pure function of time (seek-safe, preview == render) and every part is drawn by the style's materials, so
// one storyboard gives a silver line-art studio figure (signature), a Swiss pictogram (grid), a glossy chibi (liquid) or a
// cut-paper puppet on split pins animated on twos (paper).
//
// Figure space: feet on y=0, ~240 units tall, facing +x. An action returns poses (one per figure) + props + its stage size.
import React from 'react';
import {S, backOut, c01, inOut, lerp, rnd} from './style';

export type Figure = {skin?: string; hair?: string; hairColor?: string; outfit?: string; color?: string; color2?: string; number?: string | number;
	accessory?: string; beard?: boolean; build?: string};
type Arm = [number, number];
type Pose = {x: number; y: number; view: 'side' | 'front'; face: 1 | -1; lean: number; head: number; armB: Arm; armF: Arm; legB: Arm; legF: Arm;
	mouth: number; seated?: boolean; hold?: string; smile?: number; show?: number; mood?: string};
type Words = {w: string; s: number; e: number}[];
type Ctx = {t: number; T: number; words: Words; at: number; seed: number};
type Out = {w: number; h: number; ground: number; figs: Pose[]; props: React.ReactNode[]; back?: React.ReactNode[]; looks?: Figure[]};

const D = Math.PI / 180;
const L = {hip: 104, torso: 64, neck: 9, head: 24, upper: 36, fore: 33, thigh: 48, shin: 48};
const sin = Math.sin, cos = Math.cos;

// ── talking: the mouth opens while a word is being spoken (beat-relative word timings), with a syllable flutter ──
const talk = (c: Ctx, k = 1) => {
	const tt = c.t;
	if (c.words.length) {
		const w = c.words.find((x) => tt >= x.s - 0.02 && tt <= x.e + 0.02);
		if (!w) return 0;
		const sy = Math.max(1, Math.round((w.w || '').length / 3));
		return k * (0.35 + 0.65 * Math.abs(sin(((tt - w.s) / Math.max(0.08, w.e - w.s)) * Math.PI * sy)));
	}
	return k * Math.max(0, sin(tt * 13) * 0.6 + sin(tt * 7.3) * 0.4) * (sin(tt * 1.7) > -0.6 ? 1 : 0);
};

const base = (p: Partial<Pose>): Pose => ({x: 0, y: 0, view: 'side', face: 1, lean: 0, head: 0, armB: [10, 10], armF: [-10, 10], legB: [-4, 4], legF: [4, 4], mouth: 0, ...p});

// ── gait cycles ──
const runPose = (ph: number, amp = 1): Partial<Pose> => ({
	lean: 14 * amp, y: -Math.abs(sin(ph)) * 7 * amp,
	legF: [38 * sin(ph) * amp, 18 + 62 * c01(0.5 + 0.6 * sin(ph + 1.9))], legB: [38 * sin(ph + Math.PI) * amp, 18 + 62 * c01(0.5 + 0.6 * sin(ph + Math.PI + 1.9))],
	armF: [-42 * sin(ph) * amp, 95], armB: [42 * sin(ph) * amp, 95],
});
const walkPose = (ph: number): Partial<Pose> => ({
	lean: 3, y: -Math.abs(sin(ph)) * 3,
	legF: [24 * sin(ph), 6 + 30 * c01(0.4 + 0.7 * sin(ph + 1.7))], legB: [24 * sin(ph + Math.PI), 6 + 30 * c01(0.4 + 0.7 * sin(ph + Math.PI + 1.7))],
	armF: [-22 * sin(ph), 18], armB: [22 * sin(ph), 18],
});

// ── actions ──
type Act = (c: Ctx, s: S) => Out;
export const ACTIONS: Record<string, {label: string; wide?: boolean; act: Act}> = {
	speech: {label: 'Gives a speech at a podium', act: (c, s) => {
		const g = c.t * 1.25, beat = sin(g * Math.PI * 2);
		const fig = base({view: 'front', head: sin(c.t * 1.1) * 4 + (beat > 0.6 ? 3 : 0), mouth: talk(c),
			armF: [lerp(25, 95, 0.5 + 0.5 * beat), lerp(85, 40, 0.5 + 0.5 * beat)], armB: [24, 78], legF: [6, 0], legB: [6, 0]});
		return {w: 400, h: 420, ground: 330, figs: [fig], back: [<Flag key="f1" s={s} x={-150} t={c.t} />, <Flag key="f2" s={s} x={150} t={c.t + 0.7} />],
			props: [<Podium key="p" s={s} />, <Crowd key="c" s={s} t={c.t} />]};
	}},
	talk: {label: 'Talks and explains with gestures', act: (c) => {
		const g = c.t * 1.1;
		return {w: 380, h: 400, ground: 370, props: [], figs: [base({view: 'front', mouth: talk(c), head: sin(g * 2.3) * 5,
			armF: [lerp(20, 80, 0.5 + 0.5 * sin(g * 4)), lerp(70, 30, 0.5 + 0.5 * sin(g * 4))], armB: [lerp(15, 60, 0.5 + 0.5 * sin(g * 3 + 2)), 60], legF: [8, 0], legB: [8, 0]})]};
	}},
	wave: {label: 'Waves hello', act: (c) => ({w: 380, h: 400, ground: 370, props: [], figs: [base({view: 'front', smile: 1, mouth: talk(c, 0.6),
		armF: [150, 20 + 28 * sin(c.t * 9)], armB: [12, 8], legF: [8, 0], legB: [8, 0], head: sin(c.t * 2) * 4})]})},
	celebrate: {label: 'Celebrates, arms up', act: (c, s) => {
		const j = Math.abs(sin(c.t * 4.2));
		return {w: 400, h: 420, ground: 380, figs: [base({view: 'front', y: -j * 26, smile: 1, mouth: 0.8, armF: [160 - 10 * j, 10], armB: [160 - 10 * j, 10],
			legF: [10 + 8 * (1 - j), 18 * (1 - j)], legB: [10 + 8 * (1 - j), 18 * (1 - j)]})], props: [<Confetti key="c" s={s} t={c.t} />]};
	}},
	dance: {label: 'Dances', act: (c) => {
		const g = c.t * 2.2 * Math.PI;
		return {w: 380, h: 400, ground: 370, props: [], figs: [base({view: 'front', x: sin(g / 2) * 14, y: -Math.abs(sin(g)) * 8, smile: 1, head: sin(g / 2) * 10,
			armF: [lerp(40, 160, 0.5 + 0.5 * sin(g)), 40], armB: [lerp(160, 40, 0.5 + 0.5 * sin(g)), 40], legF: [12 + 10 * sin(g), 20 * c01(sin(g))], legB: [12 - 10 * sin(g), 20 * c01(-sin(g))]})]};
	}},
	jump: {label: 'Jumps for joy', act: (c) => {
		const ph = (c.t % 1.4) / 1.4, up = ph < 0.25 ? 0 : sin(((ph - 0.25) / 0.75) * Math.PI), crouch = ph < 0.25 ? sin((ph / 0.25) * Math.PI) : 0;
		return {w: 380, h: 440, ground: 400, props: [], figs: [base({view: 'front', y: -up * 90 + crouch * 14, smile: 1, armF: [40 + 120 * up, 10], armB: [40 + 120 * up, 10],
			legF: [8 + 10 * up, 40 * crouch + 25 * up], legB: [8 + 10 * up, 40 * crouch + 25 * up]})]};
	}},
	lift: {label: 'Lifts weights', act: (c, s) => {
		const k = 0.5 + 0.5 * sin(c.t * 2.6 - Math.PI / 2);
		const fig = base({view: 'front', y: (1 - k) * 10, armF: [lerp(40, 168, k), lerp(140, 8, k)], armB: [lerp(40, 168, k), lerp(140, 8, k)], legF: [14, (1 - k) * 30], legB: [14, (1 - k) * 30], mouth: 0.2});
		return {w: 400, h: 440, ground: 400, figs: [fig], props: [<Barbell key="b" s={s} y={-lerp(150, 250, k)} />]};
	}},
	sad: {label: 'Is sad, head down', act: (c) => ({w: 360, h: 400, ground: 370, props: [], figs: [base({view: 'front', head: -14 + sin(c.t) * 2, y: 4,
		armF: [8, 4], armB: [8, 4], legF: [5, 0], legB: [5, 0], smile: -1})]})},
	think: {label: 'Thinks, hand on chin', act: (c, s) => ({w: 400, h: 420, ground: 380, figs: [base({lean: -3, head: 6 + sin(c.t * 1.3) * 3, armF: [38, 135 + 4 * sin(c.t * 2)], armB: [10, 70],
		legF: [3, 2], legB: [-3, 2]})], props: [<Thought key="t" s={s} t={c.t} />]})},
	walk: {label: 'Walks', act: (c, s) => ({w: 420, h: 400, ground: 360, figs: [base({...walkPose(c.t * 5.2)})], props: [<Ground key="g" s={s} t={c.t} speed={60} />]})},
	run: {label: 'Runs fast', act: (c, s) => ({w: 420, h: 400, ground: 360, figs: [base({...runPose(c.t * 10)})], props: [<Ground key="g" s={s} t={c.t} speed={220} />, <SpeedLines key="l" s={s} t={c.t} />]})},
	point: {label: 'Presents and points at a chart', wide: true, act: (c, s) => ({w: 640, h: 420, ground: 380, figs: [base({x: -150, mouth: talk(c), head: 4,
		armF: [118 + 6 * sin(c.t * 3), 8], armB: [10, 40], legF: [4, 2], legB: [-4, 2]})], props: [<Board key="b" s={s} t={c.t} />]})},
	read: {label: 'Reads a book', act: (c, s) => ({w: 380, h: 400, ground: 370, figs: [base({head: -12, armF: [52, 82], armB: [48, 86], legF: [3, 2], legB: [-3, 2], hold: 'book'})],
		props: [<Book key="b" s={s} t={c.t} />]})},
	type: {label: 'Types at a laptop', act: (c, s) => {
		const j = sin(c.t * 22) * 4;
		return {w: 440, h: 400, ground: 370, figs: [base({x: -60, seated: true, y: -2, head: -6, armF: [70 + j, 60], armB: [66 - j, 64], legF: [88, 88], legB: [84, 84]})],
			props: [<Desk key="d" s={s} />]};
	}},
	catch: {label: 'Catches something flying in, lightning fast', wide: true, act: (c, s) => {
		const P = 3.2, t = c.t % P, grab = c01((t - 0.9) / 0.14), hold = t > 1.04;
		const ox = hold ? 70 : lerp(330, 70, c01(t / 1.04)), oy = hold ? -168 : -168 - Math.sin(c01(t / 1.04) * Math.PI) * 30;
		const fig = base({x: -40, lean: lerp(0, 8, grab), head: 6, mood: t < 0.9 ? 'determined' : 'happy', armF: [lerp(20, 82, grab), lerp(70, 8, grab)], armB: [8, 20], legF: [10, 6], legB: [-8, 6]});
		const m0 = c01((t - 1.04) / 0.2) * (1 - c01((t - 1.5) / 0.3));
		return {w: 560, h: 420, ground: 380, figs: [fig], props: [<g key="o" opacity={hold && t > 2.4 ? 0 : 1}><circle cx={ox} cy={oy} r={9} fill={s.pal.acc3 || s.pal.acc} />
			{!hold ? <path d={`M${ox + 12} ${oy} l40 -4 M${ox + 12} ${oy + 5} l30 4`} stroke={s.pal.line} strokeWidth={2} opacity={0.6} /> : null}</g>,
			<circle key="r" cx={70} cy={-168} r={30 * m0 + 6} fill="none" stroke={s.pal.acc} strokeWidth={3} opacity={m0} />]};
	}},
	react: {label: 'Startled — steps back, hands up', act: (c) => {
		const k = backOut(c01(c.t / 0.35), 2);
		return {w: 380, h: 400, ground: 370, props: [], figs: [base({view: 'front', x: -14 * k, y: -6 * Math.max(0, Math.sin(c.t * 3)), mood: 'surprised', armF: [lerp(10, 120, k), lerp(10, 70, k)], armB: [lerp(10, 120, k), lerp(10, 70, k)],
			legF: [8, 6], legB: [8, 6], mouth: talk(c)})]};
	}},
	evolve: {label: 'Humans evolving: a march of progress from hunched to upright, fur to suit', wide: true, act: (c, s) => {
		const N = 5;
		const figs = Array.from({length: N}, (_, k) => {
			const q = k / (N - 1), w = walkPose(c.t * 4.4 + k * 0.9);
			return base({...w, x: -280 + k * 140, lean: lerp(34, 2, q) + (w.lean || 0), head: lerp(-16, 0, q), armF: [lerp(-8, -22, q) + (w.armF as Arm)[0] * lerp(0.4, 1, q), lerp(40, 18, q)],
				armB: [lerp(8, 22, q) + (w.armB as Arm)[0] * lerp(0.4, 1, q), lerp(40, 18, q)], show: c01((c.t - k * 0.55) / 0.5)});
		});
		return {w: 760, h: 420, ground: 380, figs, props: [<Ground key="g" s={s} t={c.t} speed={30} />],
			looks: [{outfit: 'fur', hair: 'long', beard: true}, {outfit: 'fur', hair: 'curly', beard: true}, {outfit: 'robe', hair: 'long', beard: true},
				{outfit: 'casual', hair: 'short'}, {outfit: 'suit', hair: 'side', accessory: 'tie'}]};
	}},
	score: {label: 'Runs in and scores a goal (soccer)', wide: true, act: (c, s) => {
		const P = 4.4, t = c.t % P;
		const runIn = c01(t / 1.4), kick = c01((t - 1.4) / 0.35), after = c01((t - 1.75) / 0.4), cel = c01((t - 2.4) / 0.4);
		let pose: Partial<Pose>;
		if (t < 1.4) pose = runPose(t * 10);
		else if (t < 2.4) pose = {lean: lerp(6, -8, kick), legF: [lerp(-45, 85, backOut(kick)), lerp(70, 0, kick)], legB: [-8, 6], armF: [-50, 30], armB: [60, 30]};
		else pose = {lean: -6, y: -Math.abs(sin((t - 2.4) * 6)) * 22 * cel, smile: 1, mouth: 0.8, armF: [lerp(-20, 165, cel), 10], armB: [lerp(20, 165, cel), 10], legF: [8, 10], legB: [-8, 10]};
		const fx = lerp(-260, -95, inOut(runIn));
		const bt = c01((t - 1.62) / 0.55);
		const ball = t < 1.62 ? {x: -70, y: -12} : {x: lerp(-70, 240, bt), y: -12 - sin(bt * Math.PI) * 120 * (1 - bt * 0.3) - bt * 30};
		const net = c01((t - 2.15) / 0.12) * (1 - c01((t - 2.4) / 0.5));
		return {w: 700, h: 420, ground: 370, figs: [base({x: fx, ...pose})], props: [<Pitch key="p" s={s} />, <Goal key="g" s={s} x={250} bulge={net} />, <Ball key="b" s={s} x={ball.x} y={ball.y} spin={t * 9} />]};
	}},
	shoot: {label: 'Jump-shoots a basketball', wide: true, act: (c, s) => {
		const P = 3.6, t = c.t % P, dr = t < 1.3, up = c01((t - 1.3) / 0.45), rel = c01((t - 1.75) / 0.9);
		const fig = dr ? base({x: -120, y: 0, lean: 6, armF: [50 + 20 * Math.abs(sin(t * 8)), 20], armB: [10, 30], legF: [10, 25], legB: [-10, 25]})
			: base({x: -120, y: -sin(c01((t - 1.3) / 0.9) * Math.PI) * 60, armF: [150, 20 - 30 * up], armB: [140, 30], legF: [4, 10], legB: [-4, 10]});
		const ball = dr ? {x: -80, y: -20 - Math.abs(sin(t * 8)) * 60} : t < 1.75 ? {x: -100, y: -250 + (1 - up) * 140} : {x: lerp(-100, 210, rel), y: -250 - sin(rel * Math.PI) * 110 + rel * 60};
		return {w: 640, h: 440, ground: 400, figs: [fig], props: [<Hoop key="h" s={s} x={220} swish={c01((t - 2.6) / 0.3) * (1 - c01((t - 3.1) / 0.3))} />, <Ball key="b" s={s} x={ball.x} y={ball.y} spin={t * 6} basket />]};
	}},
	throw: {label: 'Throws a ball', wide: true, act: (c, s) => {
		const P = 3, t = c.t % P, wind = c01(t / 0.9), th = c01((t - 0.9) / 0.25), fl = c01((t - 1.1) / 1.3);
		const fig = base({x: -160, lean: lerp(-8, 14, th), armF: [lerp(-20, -120, wind) + 230 * th, lerp(40, 90, wind) - 80 * th], armB: [lerp(20, 70, wind), 30], legF: [20, 6], legB: [-20, 6]});
		const ball = t < 1.1 ? null : {x: lerp(-120, 300, fl), y: -220 - sin(fl * Math.PI) * 90 + fl * 120};
		return {w: 640, h: 420, ground: 380, figs: [fig], props: ball ? [<Ball key="b" s={s} x={ball.x} y={ball.y} spin={t * 8} />] : []};
	}},
	handshake: {label: 'Two people shake hands', wide: true, act: (c) => {
		const sh = sin(c.t * 9) * 8;
		return {w: 560, h: 400, ground: 370, props: [], figs: [base({x: -62, smile: 1, mouth: talk(c, 0.5), armF: [62 + sh, 18], armB: [8, 8]}), base({x: 62, face: -1, smile: 1, armF: [62 + sh, 18], armB: [8, 8]})]};
	}},
	chat: {label: 'Two people talk', wide: true, act: (c) => {
		const who = Math.floor(c.t / 1.6) % 2;
		const m = talk(c);
		return {w: 560, h: 400, ground: 370, props: [], figs: [
			base({x: -90, mouth: who === 0 ? m : 0, armF: who === 0 ? [40 + 30 * sin(c.t * 5), 60] : [10, 20], armB: [8, 10], head: who === 0 ? 4 : -2}),
			base({x: 90, face: -1, mouth: who === 1 ? m : 0, armF: who === 1 ? [40 + 30 * sin(c.t * 5), 60] : [10, 20], armB: [8, 10], head: who === 1 ? 4 : -2})]};
	}},
};

// ── materials: how each style draws flesh, cloth, hair, props ──
type Mat = {pupil?: string; blush?: boolean; skin: string; top: string; bottom: string; shoe: string; hair: string; face: string; line?: string; lw: number; out: number; headR: number;
	filter?: string; pin?: string; accent: string; prop: string; propDark: string; propLight: string};
const SKINS = ['#F1C7A4', '#D9A27C', '#B07A55', '#7C5236', '#F6D6BD'];
const mat = (s: S, f: Figure, i: number): Mat => {
	const p = s.pal;
	const skin = f.skin || SKINS[i % SKINS.length];
	const hairC = f.hairColor || ['#3B2A1E', '#7A4E2A', '#1D1A18', '#C99A5B'][i % 4];
	if (s.key === 'dusk') {
		const cols = [p.acc2, p.acc3, p.acc4, '#F2EDE4'];
		return {skin: '#061416', top: f.color || cols[i % 4], bottom: f.color2 || '#0C262B', shoe: '#061416', hair: '#061416', face: '#FFFFFF', pupil: '#061416', lw: 15, out: 0, headR: 31,
			filter: 'drop-shadow(-3px -2px 0 rgba(255,138,76,.9)) drop-shadow(0 0 16px rgba(255,122,61,.22))', accent: p.acc3, prop: '#123338', propDark: '#071C20', propLight: '#FFE0C2'};
	}
	if (s.id === 'signature')
		return {skin: '#2C2C31', top: '#232328', bottom: '#1B1B1F', shoe: '#101012', hair: '#3A3A40', face: p.line, line: p.line, lw: 14, out: 2.6, headR: 24,
			filter: `drop-shadow(0 0 10px ${p.acc}33)`, accent: p.acc, prop: '#26262B', propDark: '#141417', propLight: p.line};
	if (s.id === 'grid')
		return {skin: p.ink, top: f.color === 'ink' ? p.ink : p.acc, bottom: p.ink, shoe: p.ink, hair: p.ink, face: p.bg, lw: 17, out: 0, headR: 25,
			accent: p.acc, prop: p.ink, propDark: p.ink, propLight: p.bg};
	if (s.id === 'liquid') {
		const cols = [p.acc, p.acc2, p.acc3, p.acc4 || p.acc];
		return {blush: true, skin, top: f.color || cols[i % 4], bottom: f.color2 || '#3B3470', shoe: '#2A2550', hair: hairC, face: '#2A2140', lw: 19, out: 0, headR: 33,
			filter: `drop-shadow(0 14px 18px rgba(0,0,0,.35))`, accent: cols[(i + 1) % 4], prop: '#2B2552', propDark: '#1E1A3D', propLight: '#FFFFFF'};
	}
	return {skin, top: f.color || [p.acc, p.acc2, p.acc3][i % 3], bottom: f.color2 || p.acc2, shoe: p.dark, hair: hairC, face: p.dark, lw: 17, out: 0, headR: 25,
		filter: `drop-shadow(5px 6px 0 rgba(59,42,23,.32))`, pin: '#E8D6B9', accent: p.acc3, prop: p.acc4 || '#FBF4E6', propDark: p.acc2, propLight: p.acc4 || '#FBF4E6'};
};

// ── forward kinematics ──
type Pt = [number, number];
const limb = (o: Pt, a: number, len: number, fx: number): Pt => [o[0] + sin(a * D) * len * fx, o[1] + cos(a * D) * len];
function rig(p: Pose, m: Mat) {
	const f = p.face;
	const hip: Pt = [p.x, -L.hip + p.y + (p.seated ? 44 : 0)];
	const neck: Pt = [hip[0] + sin(p.lean * D) * L.torso * f, hip[1] - cos(p.lean * D) * L.torso];
	const head: Pt = [neck[0] + sin((p.lean + p.head * 0.4) * D) * (L.neck + m.headR) * f, neck[1] - cos((p.lean + p.head * 0.4) * D) * (L.neck + m.headR)];
	const sh = (side: number): Pt => (p.view === 'front' ? [neck[0] + side * 19, neck[1] + 8] : [neck[0] - sin(p.lean * D) * 6 * f, neck[1] + 8]);
	const hp = (side: number): Pt => (p.view === 'front' ? [hip[0] + side * 11, hip[1]] : hip);
	const arm = (a: Arm, side: number) => {
		const o = sh(side);
		if (p.view === 'front') {
			const e = limb(o, a[0], L.upper, side), h = limb(e, a[0] + a[1], L.fore, side);
			return [o, e, h] as Pt[];
		}
		const e = limb(o, a[0] + p.lean, L.upper, f), h = limb(e, a[0] + p.lean + a[1], L.fore, f);
		return [o, e, h] as Pt[];
	};
	const leg = (a: Arm, side: number) => {
		const o = hp(side);
		if (p.view === 'front') {
			const k = limb(o, a[0] * 0.35, L.thigh, side), an = limb(k, a[0] * 0.35 - a[1] * 0.5, L.shin, side);
			const kk: Pt = [k[0], k[1] - a[1] * 0.25];
			return [o, kk, [an[0], Math.min(an[1], 0)]] as Pt[];
		}
		const k = limb(o, a[0], L.thigh, f), an = limb(k, a[0] - a[1], L.shin, f);
		return [o, k, an] as Pt[];
	};
	return {hip, neck, head, armB: arm(p.armB, -1), armF: arm(p.armF, 1), legB: leg(p.legB, -1), legF: leg(p.legF, 1)};
}

const poly = (pts: Pt[]) => pts.map((q, i) => `${i ? 'L' : 'M'}${q[0].toFixed(1)} ${q[1].toFixed(1)}`).join(' ');

// one stroke part, outlined in the signature style
const Part: React.FC<{d: string; c: string; w: number; m: Mat}> = ({d, c, w, m}) => (
	<>
		{m.out ? <path d={d} stroke={m.line} strokeWidth={w + m.out * 2} fill="none" strokeLinecap="round" strokeLinejoin="round" /> : null}
		<path d={d} stroke={c} strokeWidth={w} fill="none" strokeLinecap="round" strokeLinejoin="round" />
	</>
);

const Hair: React.FC<{p: Pose; f: Figure; m: Mat; h: Pt}> = ({p, f, m, h}) => {
	const r = m.headR, type = f.hair || 'short', fc = p.face, [x, y] = h;
	if (type === 'bald') return null;
	const col = m.hair;
	const st = m.out ? {stroke: m.line, strokeWidth: m.out} : {};
	if (p.view === 'front') {
		const cap = `M${x - r - 2} ${y + (type === 'long' ? r * 1.4 : -r * 0.1)} Q${x - r - 3} ${y - r * 1.25} ${x} ${y - r - 4} Q${x + r + 3} ${y - r * 1.25} ${x + r + 2} ${y + (type === 'long' ? r * 1.4 : -r * 0.1)} L${x + r * 0.7} ${y - r * 0.35} Q${x + (type === 'side' ? r * 0.2 : 0)} ${y - r * 0.75} ${x - r * 0.7} ${y - r * 0.35} Z`;
		return (
			<g>
				<path d={cap} fill={col} {...st} />
				{type === 'bun' ? <circle cx={x} cy={y - r - 8} r={r * 0.42} fill={col} {...st} /> : null}
				{type === 'curly' ? [-0.8, -0.4, 0, 0.4, 0.8].map((k, i) => <circle key={i} cx={x + k * r} cy={y - r * 0.92 + Math.abs(k) * r * 0.3} r={r * 0.32} fill={col} />) : null}
			</g>
		);
	}
	const back = type === 'long' ? r * 1.5 : r * 0.35;
	const cap = `M${x + fc * r * 0.95} ${y - r * 0.35} Q${x + fc * r * 0.7} ${y - r * 1.2} ${x - fc * r * 0.2} ${y - r - 4} Q${x - fc * (r + 5)} ${y - r * 0.8} ${x - fc * (r + 2)} ${y + back} L${x - fc * r * 0.45} ${y + back * 0.6} L${x - fc * r * 0.2} ${y - r * 0.2} Z`;
	return (
		<g>
			<path d={cap} fill={col} {...st} />
			{type === 'bun' ? <circle cx={x - fc * r * 0.8} cy={y - r * 0.7} r={r * 0.42} fill={col} {...st} /> : null}
		</g>
	);
};

// moods: happy · surprised · angry · determined · sad · scared (default: from smile)
const Face: React.FC<{p: Pose; m: Mat; h: Pt; t: number; f: Figure}> = ({p, m, h, t, f}) => {
	const r = m.headR, [x, y] = h, blink = (t % 3.3) < 0.12 ? 0.15 : 1, big = m.headR > 28;
	const mo = c01(p.mouth);
	const mood = p.mood || (p.smile && p.smile > 0 ? 'happy' : p.smile && p.smile < 0 ? 'sad' : '');
	const wide = mood === 'surprised' || mood === 'scared' ? 1.3 : 1;
	const pup = mood === 'scared' ? 0.55 : mood === 'surprised' ? 0.75 : 1;
	const eye = (ex: number, side: number) =>
		big ? (
			<g>
				<ellipse cx={ex} cy={y - 2} rx={5.5 * wide} ry={7 * blink * wide} fill="#fff" />
				<circle cx={ex + 1.2 * p.face} cy={y - 1} r={3.4 * blink * pup} fill={m.pupil || m.face} />
			</g>
		) : (
			<ellipse cx={ex} cy={y - 3} rx={2.6 * wide} ry={3.2 * blink * wide} fill={m.face} />
		);
	// brows: angry/determined slant down to the middle, sad/scared slant up
	const brow = (ex: number, side: number) => {
		const k = mood === 'angry' || mood === 'determined' ? 1 : mood === 'sad' || mood === 'scared' ? -1 : 0;
		if (!k) return null;
		const by = y - (big ? 13 : 9) * wide, d = (big ? 7 : 5);
		return <path d={`M${ex - d} ${by - k * 2.5 * side} L${ex + d} ${by + k * 2.5 * side}`} stroke={m.face} strokeWidth={big ? 3 : 2.2} strokeLinecap="round" />;
	};
	const mouthY = y + r * 0.42;
	const mouth = (mx: number) => {
		if (mo > 0.05) return <ellipse cx={mx} cy={mouthY + mo * 2} rx={big ? 6 : 5} ry={1.2 + mo * (big ? 6 : 5)} fill={m.face === '#fff' ? '#000' : m.face} />;
		if (mood === 'surprised') return <ellipse cx={mx} cy={mouthY + 2} rx={big ? 5 : 3.5} ry={big ? 7 : 5} fill={m.face} />;
		if (mood === 'scared') return <path d={`M${mx - 6} ${mouthY + 2} q3 -3 6 0 q3 3 6 0`} stroke={m.face} strokeWidth={2.2} fill="none" strokeLinecap="round" />;
		const cur = mood === 'happy' ? 5 : mood === 'sad' ? -4 : mood === 'angry' ? -2 : mood === 'determined' ? 0 : (p.smile || 0) * 5;
		return <path d={`M${mx - 5} ${mouthY} Q${mx} ${mouthY + cur} ${mx + 5} ${mouthY}`} stroke={m.face} strokeWidth={2.2} fill="none" strokeLinecap="round" />;
	};
	if (p.view === 'front')
		return (
			<g>
				{eye(x - r * 0.36, -1)}
				{eye(x + r * 0.36, 1)}
				{brow(x - r * 0.36, -1)}
				{brow(x + r * 0.36, 1)}
				{m.blush ? <><circle cx={x - r * 0.6} cy={y + r * 0.25} r={4.5} fill="#FF6FB5" opacity={0.45} /><circle cx={x + r * 0.6} cy={y + r * 0.25} r={4.5} fill="#FF6FB5" opacity={0.45} /></> : null}
				{mouth(x)}
				{f.accessory === 'glasses' ? <g stroke={m.face} strokeWidth={2} fill="none"><circle cx={x - r * 0.36} cy={y - 3} r={7} /><circle cx={x + r * 0.36} cy={y - 3} r={7} /><path d={`M${x - r * 0.1} ${y - 3}H${x + r * 0.1}`} /></g> : null}
			</g>
		);
	const ex = x + p.face * r * 0.45;
	return (
		<g>
			{eye(ex, p.face)}
			{brow(ex, p.face)}
			{mouth(x + p.face * r * 0.55)}
			{f.accessory === 'glasses' ? <circle cx={ex} cy={y - 3} r={7} stroke={m.face} strokeWidth={2} fill="none" /> : null}
		</g>
	);
};

const Hat: React.FC<{p: Pose; f: Figure; m: Mat; h: Pt}> = ({p, f, m, h}) => {
	const r = m.headR, [x, y] = h, a = f.accessory, fc = p.view === 'front' ? 0 : p.face;
	if (a === 'cap') return <g fill={m.accent}><path d={`M${x - r} ${y - r * 0.3} Q${x} ${y - r * 1.5} ${x + r} ${y - r * 0.3} Z`} /><rect x={fc >= 0 ? x : x - r * 1.5} y={y - r * 0.4} width={fc ? r * 1.5 : 0} height={5} /></g>;
	if (a === 'crown') return <path d={`M${x - r * 0.8} ${y - r * 0.8} L${x - r * 0.8} ${y - r * 1.6} L${x - r * 0.4} ${y - r * 1.15} L${x} ${y - r * 1.7} L${x + r * 0.4} ${y - r * 1.15} L${x + r * 0.8} ${y - r * 1.6} L${x + r * 0.8} ${y - r * 0.8} Z`} fill={m.accent} />;
	if (a === 'tophat') return <g fill={m.top}><rect x={x - r * 0.75} y={y - r * 2.1} width={r * 1.5} height={r * 1.3} /><rect x={x - r * 1.15} y={y - r * 0.9} width={r * 2.3} height={5} /></g>;
	if (a === 'helmet') return <path d={`M${x - r - 3} ${y} Q${x - r} ${y - r * 1.5} ${x} ${y - r * 1.25} Q${x + r} ${y - r * 1.5} ${x + r + 3} ${y} Z`} fill={m.accent} />;
	return null;
};

// one character
const Person: React.FC<{p: Pose; f: Figure; s: S; i: number; t: number}> = ({p, f, s, i, t}) => {
	const m0 = mat(s, f, i);
	const tinted = s.id === 'liquid' || s.id === 'paper';
	const m = {...m0,
		...(f.outfit === 'fur' ? {top: tinted ? (f.color || '#8B5A2B') : m0.top, bottom: m0.skin} : {}),
		...(f.outfit === 'space' ? (tinted ? {top: '#E9EDF2', bottom: '#D5DBE3'} : {}) : {}),
		...(f.outfit === 'robe' && tinted && !f.color ? {top: s.id === 'paper' ? s.pal.acc3 : s.pal.acc2} : {})};
	const R = rig(p, m);
	const lw = m.lw * (f.build === 'big' ? 1.2 : f.build === 'small' ? 0.85 : 1);
	const torsoW = lw * 1.9;
	const outfit = f.outfit || 'casual';
	const bare = outfit === 'jersey' || outfit === 'casual' || outfit === 'fur';
	const legs = (pts: Pt[]) => <Part d={poly([...pts, [pts[2][0] + 12 * (p.view === 'front' ? 0 : p.face), pts[2][1]]])} c={m.bottom} w={lw} m={m} />;
	const arms = (pts: Pt[], back: boolean) => (
		<g opacity={back && s.id === 'grid' ? 1 : 1}>
			<Part d={poly(pts)} c={bare ? m.skin : m.top} w={lw * 0.82} m={m} />
			{bare ? <Part d={poly([pts[0], [lerp(pts[0][0], pts[1][0], 0.55), lerp(pts[0][1], pts[1][1], 0.55)]])} c={m.top} w={lw * 0.95} m={m} /> : null}
			<circle cx={pts[2][0]} cy={pts[2][1]} r={lw * 0.45} fill={m.skin} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} />
		</g>
	);
	const torso = poly([R.hip, R.neck]);
	const skirt = outfit === 'dress' ? `M${R.hip[0] - 16} ${R.hip[1] - 6} L${R.hip[0] + 16} ${R.hip[1] - 6} L${R.hip[0] + 30} ${R.hip[1] + 46} L${R.hip[0] - 30} ${R.hip[1] + 46} Z` : '';
	const coat = outfit === 'lab' || outfit === 'robe' ? poly([R.neck, [R.hip[0], R.hip[1] + (outfit === 'robe' ? 62 : 30)]]) : '';
	const coatC = outfit === 'robe' ? m.top : '#F4F4F4';
	// fur: a tunic with a jagged hem down to mid-thigh
	const fur = outfit === 'fur' ? (() => {
		const [hx, hy] = R.hip, n = 7, w = 26, d = 30;
		const hem = Array.from({length: n + 1}, (_, k) => {
			const kk = n - k;                                   // right → left along the jagged hem
			return `L${(hx - w + (2 * w * kk) / n).toFixed(1)} ${(hy + d + (kk % 2 ? 9 : 0)).toFixed(1)}`;
		}).join(' ');
		return `M${hx - w * 0.7} ${hy - 30} L${hx + w * 0.7} ${hy - 30} ${hem} Z`;
	})() : '';
	const front = p.view === 'front';
	const nx = R.neck[0], ny = R.neck[1];
	const pins = m.pin ? [R.armF[1], R.armB[1], R.legF[1], R.legB[1]] : [];
	const order = front ? (
		<>
			{legs(R.legB)}
			{legs(R.legF)}
			{skirt ? <path d={skirt} fill={m.top} /> : null}
			{coat ? <Part d={coat} c={coatC} w={torsoW * 1.05} m={m} /> : null}
			{outfit === 'space' ? <rect x={nx - 22} y={ny + 4} width={44} height={48} rx={8} fill={m.propDark} /> : null}
			<Part d={torso} c={m.top} w={torsoW} m={m} />
			{fur ? <path d={fur} fill={m.top} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} /> : null}
			{outfit === 'robe' ? <rect x={R.hip[0] - 20} y={R.hip[1] - 6} width={40} height={6} fill={m.accent} /> : null}
			{outfit === 'suit' ? <path d={`M${nx - 9} ${ny + 2} L${nx} ${ny + 26} L${nx + 9} ${ny + 2}`} fill={m.out ? m.line : '#F2F2F2'} opacity={0.9} /> : null}
			{outfit === 'suit' || f.accessory === 'tie' ? <path d={`M${nx - 3} ${ny + 6} L${nx + 3} ${ny + 6} L${nx + 4} ${ny + 30} L${nx} ${ny + 36} L${nx - 4} ${ny + 30} Z`} fill={m.accent} /> : null}
			{outfit === 'jersey' && f.number != null ? <text x={nx} y={ny + 34} textAnchor="middle" fontSize={20} fontWeight={800} fill={s.id === 'grid' ? s.pal.bg : '#fff'} fontFamily="Arial Black, sans-serif">{String(f.number).slice(0, 2)}</text> : null}
			{arms(R.armB, true)}
			{arms(R.armF, false)}
		</>
	) : (
		<>
			{arms(R.armB, true)}
			{legs(R.legB)}
			{skirt ? <path d={skirt} fill={m.top} /> : null}
			{coat ? <Part d={coat} c={coatC} w={torsoW * 0.9} m={m} /> : null}
			{outfit === 'space' ? <rect x={nx - p.face * 34} y={ny + 6} width={18} height={44} rx={6} fill={m.propDark} /> : null}
			<Part d={torso} c={m.top} w={torsoW * 0.8} m={m} />
			{fur ? <path d={fur} fill={m.top} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} /> : null}
			{outfit === 'robe' ? <rect x={R.hip[0] - 14} y={R.hip[1] - 6} width={28} height={6} fill={m.accent} /> : null}
			{outfit === 'suit' || f.accessory === 'tie' ? <path d={`M${nx + p.face * 7} ${ny + 6} l${p.face * 4} 22 l${-p.face * 3} 6 z`} fill={m.accent} /> : null}
			{outfit === 'jersey' && f.number != null ? <text x={lerp(R.hip[0], nx, 0.5) - p.face * 2} y={lerp(R.hip[1], ny, 0.45)} textAnchor="middle" fontSize={16} fontWeight={800} fill={s.id === 'grid' ? s.pal.bg : '#fff'} fontFamily="Arial Black, sans-serif">{String(f.number).slice(0, 2)}</text> : null}
			{legs(R.legF)}
			{arms(R.armF, false)}
		</>
	);
	const hd = R.head;
	return (
		<g style={{filter: m.filter}} opacity={p.show == null ? 1 : c01(p.show * 1.5)} transform={p.show == null ? undefined : `translate(${p.x} 0) scale(${0.6 + 0.4 * backOut(c01(p.show))}) translate(${-p.x} 0)`}>
			{order}
			{pins.map((q, k) => <circle key={k} cx={q[0]} cy={q[1]} r={3} fill={m.pin} stroke="#3B2A17" strokeWidth={1} />)}
			<g transform={`rotate(${p.head * (front ? 0.5 : 1) * (front ? 1 : p.face)} ${hd[0]} ${hd[1] + m.headR})`}>
				<Hair p={p} f={{...f, hair: f.hair === 'long' ? 'long' : f.hair}} m={m} h={hd} />
				<circle cx={hd[0]} cy={hd[1]} r={m.headR} fill={m.skin} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} />
				{s.id === 'liquid' ? <ellipse cx={hd[0] - m.headR * 0.35} cy={hd[1] - m.headR * 0.45} rx={m.headR * 0.35} ry={m.headR * 0.2} fill="#fff" opacity={0.35} /> : null}
				<Hair p={p} f={f} m={m} h={hd} />
				{f.beard ? <path d={`M${hd[0] - m.headR * 0.8} ${hd[1] + 2} Q${hd[0]} ${hd[1] + m.headR * 1.4} ${hd[0] + m.headR * 0.8} ${hd[1] + 2} Q${hd[0]} ${hd[1] + m.headR * 0.7} ${hd[0] - m.headR * 0.8} ${hd[1] + 2}Z`} fill={m.hair} /> : null}
				<Face p={p} m={m} h={hd} t={t} f={f} />
				<Hat p={p} f={f} m={m} h={hd} />
				{outfit === 'space' ? <circle cx={hd[0]} cy={hd[1]} r={m.headR * 1.38} fill="#BFE9FF" fillOpacity={0.18} stroke={m.out ? m.line : '#FFFFFF'} strokeWidth={3} /> : null}
			</g>
		</g>
	);
};

// ── props (style materials) ──
const pm = (s: S) => mat(s, {}, 0);
const PS: React.FC<{s: S; children: React.ReactNode}> = ({s, children}) => <g style={{filter: pm(s).filter}}>{children}</g>;
const Podium: React.FC<{s: S}> = ({s}) => {
	const m = pm(s);
	return (
		<PS s={s}>
			<path d="M-70 -118 L70 -118 L58 0 L-58 0 Z" fill={m.prop} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} />
			<rect x={-78} y={-128} width={156} height={14} fill={m.propDark} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} />
			<circle cx={0} cy={-66} r={22} fill="none" stroke={m.accent} strokeWidth={5} />
			<circle cx={0} cy={-66} r={8} fill={m.accent} />
			{[-14, 14].map((x, i) => <g key={i}><path d={`M${x} -128 Q${x * 1.4} -160 ${x * 1.6} -176`} stroke={m.propLight} strokeWidth={3} fill="none" /><ellipse cx={x * 1.6} cy={-180} rx={5} ry={8} fill={m.propDark} stroke={m.propLight} strokeWidth={2} /></g>)}
		</PS>
	);
};
const Flag: React.FC<{s: S; x: number; t: number}> = ({s, x, t}) => {
	const m = pm(s);
	const w = (k: number) => sin(t * 3 + k) * 6;
	return (
		<g opacity={0.9}>
			<rect x={x - 2} y={-300} width={4} height={300} fill={s.id === 'grid' ? m.propDark : m.propLight} opacity={0.7} />
			<path d={`M${x + 2} -296 Q${x + 30} ${-296 + w(0)} ${x + 60} ${-294 + w(1)} L${x + 60} ${-246 + w(1)} Q${x + 30} ${-248 + w(0)} ${x + 2} -250 Z`} fill={m.accent} />
			<path d={`M${x + 2} -280 Q${x + 30} ${-280 + w(0)} ${x + 60} ${-278 + w(1)}`} stroke={m.propLight} strokeWidth={5} fill="none" opacity={0.8} />
		</g>
	);
};
const Crowd: React.FC<{s: S; t: number}> = ({s, t}) => {
	const m = pm(s);
	return (
		<g>
			{Array.from({length: 9}, (_, i) => {
				const x = -200 + i * 50 + (i % 2) * 8, b = sin(t * 2.4 + i * 1.7) * 2;
				return <g key={i}><circle cx={x} cy={36 + b} r={17} fill={m.propDark} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} opacity={0.95} /><rect x={x - 22} y={52 + b} width={44} height={40} rx={14} fill={m.propDark} /></g>;
			})}
		</g>
	);
};
const Confetti: React.FC<{s: S; t: number}> = ({s, t}) => {
	const p = s.pal, cols = [p.acc, p.acc2, p.acc3, p.acc4 || p.ink];
	return (
		<g>
			{Array.from({length: 26}, (_, i) => {
				const x0 = (rnd(i) - 0.5) * 380, sp = 60 + rnd(i + 9) * 80, y = -360 + ((t * sp + rnd(i + 3) * 360) % 380);
				return <rect key={i} x={x0 + sin(t * 3 + i) * 12} y={y} width={8} height={13} fill={cols[i % 4]} transform={`rotate(${t * 200 + i * 40} ${x0} ${y})`} />;
			})}
		</g>
	);
};
const Thought: React.FC<{s: S; t: number}> = ({s, t}) => {
	const m = pm(s);
	return (
		<g>
			{[[34, -238, 6], [52, -262, 9]].map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} fill={m.propLight} opacity={0.9} />)}
			<ellipse cx={100} cy={-312} rx={62} ry={40} fill={m.propLight} stroke={m.out ? m.accent : 'none'} strokeWidth={2} />
			<text x={100} y={-298} textAnchor="middle" fontSize={44} fontWeight={800} fill={m.accent} fontFamily="Arial Black, sans-serif" opacity={0.6 + 0.4 * Math.abs(sin(t * 2))}>?</text>
		</g>
	);
};
const Ground: React.FC<{s: S; t: number; speed: number}> = ({s, t, speed}) => {
	const m = pm(s);
	return (
		<g>
			<rect x={-260} y={0} width={520} height={4} fill={m.propLight} opacity={0.5} />
			{Array.from({length: 10}, (_, i) => {
				const x = ((i * 70 - t * speed) % 700 + 700) % 700 - 350;
				return <rect key={i} x={x} y={14} width={34} height={4} fill={m.propLight} opacity={0.35} />;
			})}
		</g>
	);
};
const SpeedLines: React.FC<{s: S; t: number}> = ({s, t}) => (
	<g>
		{Array.from({length: 6}, (_, i) => {
			const y = -200 + i * 32, x = -120 - ((t * 500 + i * 90) % 220);
			return <rect key={i} x={x} y={y} width={70} height={3} fill={pm(s).accent} opacity={0.5} />;
		})}
	</g>
);
const Board: React.FC<{s: S; t: number}> = ({s, t}) => {
	const m = pm(s);
	return (
		<PS s={s}>
			<rect x={-20} y={-330} width={300} height={200} rx={s.id === 'liquid' ? 16 : 2} fill={m.prop} stroke={m.out ? m.line : m.propDark} strokeWidth={m.out || 6} />
			{[0.4, 0.65, 0.5, 0.9].map((h, i) => {
				const g = c01(t * 0.9 - i * 0.18), bh = 150 * h * backOut(g);
				return <rect key={i} x={20 + i * 62} y={-150 - bh} width={40} height={bh} fill={i === 3 ? m.accent : m.propDark} opacity={i === 3 ? 1 : 0.75} />;   // propDark: cream bars vanished on the paper board
			})}
			<rect x={120} y={-130} width={8} height={130} fill={m.propDark} />
		</PS>
	);
};
const Book: React.FC<{s: S; t: number}> = ({s, t}) => {
	const m = pm(s), fl = (t % 2.4) / 2.4;
	return (
		<g transform="translate(46 -150)">
			<path d="M-30 0 L0 6 L30 0 L30 -34 L0 -28 L-30 -34 Z" fill={m.propLight} stroke={m.accent} strokeWidth={3} />
			{fl > 0.8 ? <path d={`M0 -28 Q${lerp(28, -28, (fl - 0.8) / 0.2)} -40 ${lerp(30, -30, (fl - 0.8) / 0.2)} -34`} fill="none" stroke={m.accent} strokeWidth={2} /> : null}
		</g>
	);
};
const Desk: React.FC<{s: S}> = ({s}) => {
	const m = pm(s);
	return (
		<PS s={s}>
			<rect x={-150} y={-60} width={44} height={8} fill={m.propDark} />
			<rect x={-132} y={-60} width={8} height={60} fill={m.propDark} />
			<rect x={-20} y={-120} width={200} height={10} fill={m.prop} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} />
			<rect x={160} y={-112} width={10} height={112} fill={m.propDark} />
			<rect x={-10} y={-112} width={10} height={112} fill={m.propDark} />
			<path d="M20 -124 L90 -124 L104 -190 L34 -190 Z" fill={m.propLight} />
			<rect x={44} y={-182} width={52} height={50} fill={m.accent} opacity={0.4} transform="skewX(-12)" />
		</PS>
	);
};
const Barbell: React.FC<{s: S; y: number}> = ({s, y}) => {
	const m = pm(s);
	return (
		<g>
			<rect x={-150} y={y - 3} width={300} height={6} fill={m.propLight} />
			{[-150, 132].map((x, i) => <rect key={i} x={x} y={y - 26} width={18} height={52} rx={4} fill={m.accent} />)}
		</g>
	);
};
const Pitch: React.FC<{s: S}> = ({s}) => {
	const m = pm(s);
	return (
		<g>
			<rect x={-350} y={0} width={700} height={5} fill={m.propLight} opacity={0.6} />
			<ellipse cx={-70} cy={4} rx={60} ry={6} fill={m.propLight} opacity={0.15} />
		</g>
	);
};
const Goal: React.FC<{s: S; x: number; bulge: number}> = ({s, x, bulge}) => {
	const m = pm(s), b = bulge * 22;
	return (
		<g>
			<path d={`M${x} -150 L${x + 70 + b} -130 L${x + 70 + b} 0`} fill="none" stroke={m.propLight} strokeWidth={2} opacity={0.6} />
			{Array.from({length: 6}, (_, i) => <path key={i} d={`M${x + i * 12} ${-150 + i * 3.4} Q${x + i * 12 + b * (i / 5)} -60 ${x + i * 12} 0`} stroke={m.propLight} strokeWidth={1.5} fill="none" opacity={0.45} />)}
			{Array.from({length: 7}, (_, i) => <path key={i} d={`M${x} ${-140 + i * 22} Q${x + 40 + b} ${-140 + i * 22} ${x + 70 + b} ${-128 + i * 20}`} stroke={m.propLight} strokeWidth={1.5} fill="none" opacity={0.45} />)}
			<path d={`M${x} 0 L${x} -150 L${x + 70} -130`} fill="none" stroke={m.out ? m.line : m.propLight} strokeWidth={8} strokeLinecap="round" />
		</g>
	);
};
const Hoop: React.FC<{s: S; x: number; swish: number}> = ({s, x, swish}) => {
	const m = pm(s);
	return (
		<g>
			<rect x={x + 60} y={-330} width={10} height={330} fill={m.propDark} />
			<rect x={x + 30} y={-330} width={14} height={80} fill={m.propLight} />
			<ellipse cx={x} cy={-262} rx={30} ry={6} fill="none" stroke={m.accent} strokeWidth={5} />
			<path d={`M${x - 28} -262 L${x - 18} ${-222 + swish * 8} L${x + 18} ${-222 + swish * 8} L${x + 28} -262`} stroke={m.propLight} strokeWidth={2} fill="none" opacity={0.7} />
		</g>
	);
};
const Ball: React.FC<{s: S; x: number; y: number; spin: number; basket?: boolean}> = ({s, x, y, spin, basket}) => {
	const m = pm(s), r = basket ? 16 : 13;
	const fill = basket ? (s.id === 'grid' ? s.pal.acc : '#E8823A') : s.id === 'grid' ? s.pal.bg : '#FFFFFF';
	return (
		<g transform={`translate(${x} ${y}) rotate(${spin * 57})`}>
			<circle r={r} fill={fill} stroke={s.id === 'grid' || !m.out ? s.pal.ink : m.line} strokeWidth={2.5} />
			{basket ? <path d={`M${-r} 0 H${r} M0 ${-r} V${r}`} stroke={s.pal.ink} strokeWidth={2} /> : <polygon points="0,-6 5.7,-1.9 3.5,4.9 -3.5,4.9 -5.7,-1.9" fill={s.id === 'grid' ? s.pal.ink : '#222'} />}
		</g>
	);
};

// ── the stage: one action, centred in a box, figures + props in the style ──
export const stageOf = (action: string, s: S, t: number, words: Words = [], seed = 0): Out => (ACTIONS[action] || ACTIONS.talk).act({t: s.time(Math.max(0, t)), T: 0, words, at: 0, seed}, s);
export type Cam = {vb: [number, number, number, number]; z: number; sx: number; sy: number; tx: number; ty: number};
// shot → a viewBox around the hero (figure 0) + the matching set zoom. Figure units: feet on y=0, head ≈ y −205.
export const camFor = (out: Out, shot: string, aspect: number, t: number, wideAct: boolean): Cam => {
	const hero = out.figs[0] || base({});
	const headY = -205 + hero.y, push = 1 - 0.06 * Math.min(1, Math.max(0, t) / 6);
	const H0 = 640;                                            // the wide shot: a figure is ~38% of the frame height
	// two people in one action (chat, handshake…): a medium shot frames both, not just figure 0
	const xs = out.figs.map((f) => f.x), two = wideAct && xs.length > 1;
	const mid = two ? (Math.min(...xs) + Math.max(...xs)) / 2 : hero.x, span = two ? Math.max(...xs) - Math.min(...xs) + 150 : 0;
	let h = H0, cx = wideAct && aspect > 1 ? 0 : hero.x * (aspect > 1 ? 0.6 : 1), cy = -0.796 * H0 + H0 / 2, minW = wideAct ? out.w * 0.85 : 300;
	if (shot === 'medium') { h = 330; cx = mid; cy = -150 + hero.y; minW = Math.max(210, span); }
	if (shot === 'close') { h = 150; cx = hero.x; cy = headY + 14; minW = 140; }
	if (shot === 'xclose') { h = 86; cx = hero.x + 4 * hero.face; cy = headY + 2; minW = 92; }
	// portrait (9:16): a shot is as wide as it must be, not just as tall — else a close-up is a face filling the screen
	const h0 = h;
	h = Math.max(h, minW / aspect);
	if (shot !== 'wide') cy += (h - h0) * 0.3;               // the extra room goes below the face: the head stays in the upper third
	h *= push;
	const w = h * aspect;
	const vb: [number, number, number, number] = [cx - w / 2, cy - h / 2, w, h];
	// the set: zoom about the design-space point under the hero (wide mapping 1080/640 px per unit, ground at y 860)
	const k = 1080 / H0, z = Math.pow(H0 / h, 0.75);         // the background zooms less than the actor → depth
	return {vb, z, sx: 960 + cx * k, sy: 860 + cy * k, tx: 960, ty: 540};
};

export const Actor: React.FC<{s: S; t: number; action: string; figure?: Figure; figure2?: Figure; words?: Words; at?: number; w: number; h: number; seed?: number; mood?: string; vb?: [number, number, number, number]}> = ({s, t, action, figure = {}, figure2, words = [], at = 0, w, h, seed = 0, mood, vb}) => {
	const A = ACTIONS[action] || ACTIONS.talk;
	const tt = s.time(Math.max(0, t));
	const out = A.act({t: tt, T: 0, words, at, seed}, s);
	const sc = Math.min(w / out.w, h / out.h);
	const boil = s.id === 'paper' ? s.boil(tt, 300 + seed, 0.6) : '';
	return (
		<svg width={w} height={h} viewBox={vb ? vb.join(' ') : `${-out.w / 2} ${-out.ground} ${out.w} ${out.h}`} preserveAspectRatio={vb ? 'xMidYMid slice' : undefined} style={{overflow: vb ? 'hidden' : 'visible'}}>
			<g style={{transform: boil || undefined}}>
				{out.back}
				{out.figs.map((p, i) => <Person key={i} p={mood && !p.mood ? {...p, mood} : p} f={{...(i === 1 && figure2 ? figure2 : figure), ...(out.looks ? out.looks[i] : {})}} s={s} i={i + seed} t={tt} />)}
				{out.props}
			</g>
		</svg>
	);
};
export const ACTION_NAMES = Object.keys(ACTIONS);
