// MIR MOTION GRAPHICS — style runtime. One JSON (mg_assets/styles.json) is the single source of truth for the four
// motion styles: the Python wizard, the asset builder and these scenes all read it, so tokens can't drift apart.
// Each style = visual tokens (palette, fonts, case) + motion tokens (easing, durations, stagger, stepped time, boil,
// camera push, transition kind). Every primitive in kit.tsx asks the style how to move instead of hard-coding it.
import {Easing} from 'remotion';
import RAW from '../../mg_assets/styles.json';

// style KEY (look, palette, assets) vs FAMILY (how it moves + lays out): a new look like 'dusk' reuses a family's motion code
export type StyleId = 'signature' | 'grid' | 'liquid' | 'paper';
export type StyleKey = StyleId | 'dusk';
export type Pal = {bg: string; bg2: string; ink: string; mute: string; acc: string; acc2: string; acc3: string; acc4?: string; line: string; dark: string};
type Motion = {ease: number[] | string; enter: number; stagger: number; overshoot: number; step: number; boil: number; push: number; float: number; transition: string; trans: number};
export type StyleDef = {family?: StyleId; name: string; tag: string; desc: string; palette: Pal; fonts: Record<string, [string, number]>; case: string; track: number; motion: Motion; icon: string; caption: string; sfx: Record<string, string>};

export const STYLES = RAW as unknown as Record<StyleKey, StyleDef>;
export const STYLE_IDS = Object.keys(STYLES) as StyleKey[];

export const c01 = (x: number) => Math.max(0, Math.min(1, x));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const backOut = (t: number, s = 1.70158) => (t <= 0 ? 0 : t >= 1 ? 1 : 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2));
export const expoOut = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));
export const inOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
// closed-form damped spring (seconds in, ~0→1 out with overshoot): deterministic, so preview == render
export const springT = (t: number, z = 0.42, w = 15) => (t <= 0 ? 0 : 1 - Math.exp(-z * w * t) * Math.cos(w * Math.sqrt(1 - z * z) * t));
// stable pseudo-random 0..1 per integer seed (line boil, particle layout)
export const rnd = (s: number) => {
	const x = Math.sin(s * 127.1 + 311.7) * 43758.5453;
	return x - Math.floor(x);
};

export type S = StyleDef & {
	/** behaviour family (every s.id branch) */
	id: StyleId;
	/** the real style: palette, sets, characters, asset folders */
	key: StyleKey;
	pal: Pal;
	/** style time: paper quantises to 12 fps ("on twos"), the rest are continuous */
	time: (t: number) => number;
	/** entrance progress 0→~1 (may overshoot) for something that starts at `at` seconds, optional duration scale */
	enter: (t: number, at: number, k?: number) => number;
	/** clamped 0→1 version (opacity, clip reveals) */
	in01: (t: number, at: number, k?: number) => number;
	/** subtle per-element jitter for the paper style ("line boil"), '' for the others */
	boil: (t: number, id: number, amt?: number) => string;
	font: (role: string) => {fontFamily: string; fontWeight: number};
	cased: (s: string) => string;
};

const FALLBACK: Record<string, string> = {
	'MG Archivo': '"Arial Black", "Segoe UI Black", sans-serif',
	'MG JB Mono': 'Consolas, monospace',
	'MG Outfit': '"Segoe UI", sans-serif',
	'MG Bricolage': '"Segoe UI Black", sans-serif',
	'MG Caveat': '"Segoe Print", cursive',
};

export const getStyle = (id?: string, accent?: string): S => {
	const key = (id && id in STYLES ? id : 'signature') as StyleKey;
	const d = STYLES[key];
	const sid = (d.family || key) as StyleId;
	const pal = {...d.palette, ...(accent ? {acc: accent} : {})};
	const m = d.motion;
	const bz = Array.isArray(m.ease) ? Easing.bezier(m.ease[0], m.ease[1], m.ease[2], m.ease[3]) : null;
	const time = (t: number) => (m.step ? Math.floor(t * m.step + 1e-6) / m.step : t);
	const curve = (p: number, dt: number) => {
		if (m.ease === 'spring') return springT(dt);
		if (m.ease === 'backOut') return backOut(c01(p), m.overshoot || 1.70158);
		return bz ? bz(c01(p)) : c01(p);
	};
	const enter = (t: number, at: number, k = 1) => {
		const tt = time(t) - at;
		if (tt <= 0) return 0;
		return curve(tt / (m.enter * k), tt / k);
	};
	return {
		...d,
		id: sid,
		key,
		pal,
		time,
		enter,
		in01: (t, at, k = 1) => c01(enter(t, at, k) * (m.ease === 'spring' ? 1.6 : 1.15)),
		boil: (t, id, amt = 1) => {
			if (!m.boil) return '';
			const st = Math.floor(t * (m.step || 12));
			const r = (rnd(st * 13 + id) - 0.5) * 1.4 * amt;
			const x = (rnd(st * 7 + id * 3) - 0.5) * 3.2 * amt;
			const y = (rnd(st * 5 + id * 9) - 0.5) * 3.2 * amt;
			return ` rotate(${r.toFixed(2)}deg) translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
		},
		font: (role) => {
			const [fam, w] = d.fonts[role] || d.fonts.body;
			return {fontFamily: `"${fam}", ${FALLBACK[fam] || '"Segoe UI", sans-serif'}`, fontWeight: w};
		},
		cased: (s) => {
			s = String(s ?? '');
			if (d.case === 'upper') return s.toUpperCase();
			if (d.case === 'lower') return s.toLowerCase();
			return s;
		},
	};
};
