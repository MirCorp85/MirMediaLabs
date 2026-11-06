// MIR MOTION GRAPHICS — primitives. Every piece of a motion-graphics video is built from these, and every one of
// them asks the style (style.ts) how to look and move, so one storyboard renders in any of the four styles:
//   Txt       text with the style's entrance (tracking-in / mask-rise / letter springs / stepped paper drop)
//   Visual    one cued asset: AI art cut-out, a library icon, a number or a word — styled + animated per style
//   Connector a relation between two visuals (thin light path / ruled bar / sine wave / stitched paper arc)
//   Counter   count-ups (thin numerals + flare / rolling digits / ring / stepped badge)
//   Rule      the accent rule under titles
import React, {useEffect, useState} from 'react';
import {Img, continueRender, delayRender} from 'remotion';
import {S, backOut, c01, expoOut, inOut, lerp, rnd} from './style';
import {DioItem} from './dio_item';

// ── fonts: local woff2 files (server/static/fonts/mir, served as fonts/ by the daemon and /motion/fonts/ by the lab) ──
const FILES: [string, string, number][] = [
	['MG Archivo', 'mgarchivo', 400], ['MG JB Mono', 'mgjbmono', 500], ['MG JB Mono', 'mgjbmonob', 700],
	['MG Outfit', 'mgoutfitl', 300], ['MG Outfit', 'mgoutfitb', 700], ['MG Outfit', 'mgoutfitx', 800],
	['MG Bricolage', 'mgbricolage', 800], ['MG Caveat', 'mgcaveat', 400], ['Mir Orbit', 'orbit', 400],
];
const LOADED: Record<string, Promise<void>> = {};
// every MIR font face for canvas scenes (canvas text never triggers a webfont load — wait for all of them first)
export const mgFontsReady = (base: string) =>
	Promise.all(FILES.map(([fam, file, w]) => {const k = base + file;
		if (!LOADED[k]) LOADED[k] = new FontFace(fam, `url(${base}${file}.woff2)`, {weight: String(w)}).load().then((f) => void (document.fonts as any).add(f)).catch(() => undefined);
		return LOADED[k];}));
export const useMgFonts = (base: string) => {
	const [h] = useState(() => delayRender('mg fonts', {timeoutInMilliseconds: 20000}));
	useEffect(() => {
		const ps = FILES.map(([fam, file, w]) => {
			const k = base + file;
			if (!LOADED[k])
				LOADED[k] = new FontFace(fam, `url(${base}${file}.woff2)`, {weight: String(w)})
					.load()
					.then((f) => void (document.fonts as any).add(f))
					.catch(() => undefined);
			return LOADED[k];
		});
		Promise.all(ps).then(() => continueRender(h));
	}, [base, h]);
};

// width heuristic (no DOM measuring → identical in preview, render and still): shrink until the text fits the box
const CW: Record<string, number> = {display: 0.56, head: 0.58, body: 0.52, label: 0.6, num: 0.58, hand: 0.45};
export const fit = (s: S, role: string, text: string, size: number, width: number, lines = 2) => {
	const k = (s.id === 'grid' && (role === 'display' || role === 'head' || role === 'num') ? 0.72 : CW[role] || 0.56) * (s.case === 'upper' ? 1.08 : 1);
	const t = String(text || '');
	const longest = Math.max(1, ...t.split(/\s+/).map((w) => w.length));
	return Math.max(10, Math.min(size, (width * lines * 0.92) / Math.max(1, t.length * k), (width * 0.98) / (longest * k)));
};

type TxtP = {s: S; t: number; at: number; role: string; size: number; color?: string; text: string; width: number; align?: 'center' | 'left' | 'right'; lines?: number; id?: number; style?: React.CSSProperties; noCase?: boolean};
export const Txt: React.FC<TxtP> = ({s, t, at, role, size, color, text, width, align = 'center', lines = 2, id = 0, style, noCase}) => {
	const str = noCase ? text : s.cased(text);
	const fz = fit(s, role, str, size, width, lines);
	const base: React.CSSProperties = {...s.font(role), fontSize: fz, lineHeight: role === 'hand' ? 1.05 : 1.08, color: color || s.pal.ink, width, textAlign: align,
		letterSpacing: `${s.track}em`, textWrap: 'balance' as any, ...style};
	const p = s.enter(t, at);
	const o = s.in01(t, at);
	if (t < at) return <div style={{...base, opacity: 0}}>{str}</div>;
	if (s.id === 'signature') {
		return <div style={{...base, opacity: o, letterSpacing: `${s.track + 0.32 * (1 - c01(p))}em`, filter: `blur(${(1 - c01(p)) * 7}px)`}}>{str}</div>;
	}
	if (s.id === 'grid') {
		return (
			<div style={{...base, overflow: 'hidden', paddingBottom: fz * 0.06}}>
				<div style={{transform: `translateY(${(1 - p) * 108}%)`}}>{str}</div>
			</div>
		);
	}
	if (s.id === 'liquid') {
		let i = 0;
		return (
			<div style={base}>
				{str.split(/(\s+)/).map((w, wi) =>
					/^\s+$/.test(w) ? (
						<span key={wi}> </span>
					) : (
						<span key={wi} style={{display: 'inline-block', whiteSpace: 'nowrap'}}>
							{[...w].map((ch, ci) => {
								const a = at + i++ * s.motion.stagger;
								const sp = s.enter(t, a);
								return (
									<span key={ci} style={{display: 'inline-block', opacity: c01((t - a) * 9), transform: `translateY(${(1 - sp) * 0.45}em) scale(${0.25 + 0.75 * Math.max(0, sp)})`}}>
										{ch}
									</span>
								);
							})}
						</span>
					),
				)}
			</div>
		);
	}
	// paper: stepped drop + slight tilt + boil
	const tilt = (rnd(id * 3 + 1) - 0.5) * 3;
	return <div style={{...base, opacity: o > 0 ? 1 : 0, transform: `translateY(${(1 - p) * -70}px) rotate(${tilt}deg)${s.boil(t, id + 40)}`}}>{str}</div>;
};

// ── accent rule ──
export const Rule: React.FC<{s: S; t: number; at: number; w: number; u: number; id?: number}> = ({s, t, at, w, u, id = 0}) => {
	const p = c01(s.enter(t, at, 1.2));
	if (s.id === 'signature') {
		const x = w * inOut(c01((s.time(t) - at) / 1.1));
		const fl = x > 0 ? 1 - c01((t - at - 1.2) / 0.6) : 0;
		return (
			<div style={{position: 'relative', width: w, height: 3 * u}}>
				<div style={{position: 'absolute', left: 0, top: 0, height: 3 * u, width: x, background: s.pal.acc}} />
				<div style={{position: 'absolute', left: x - 120 * u, top: -14 * u, width: 240 * u, height: 31 * u, opacity: fl,
					background: `radial-gradient(closest-side, ${s.pal.acc3}, ${s.pal.acc}cc 30%, transparent)`}} />
			</div>
		);
	}
	if (s.id === 'grid') return <div style={{width: w * expoOut(c01((t - at) / 0.5)), height: 16 * u, background: s.pal.acc}} />;
	if (s.id === 'liquid')
		return <div style={{width: w * Math.max(0, s.enter(t, at)), height: 14 * u, borderRadius: 14 * u, background: `linear-gradient(90deg, ${s.pal.acc}, ${s.pal.acc2})`, boxShadow: `0 0 ${24 * u}px ${s.pal.acc}88`}} />;
	return <div style={{width: w, height: 26 * u, background: s.pal.acc3, opacity: p > 0 ? 1 : 0, transform: `scaleX(${p}) rotate(-1.2deg)${s.boil(t, id + 70)}`, transformOrigin: 'left', boxShadow: `${5 * u}px ${6 * u}px 0 rgba(59,42,23,.3)`}} />;
};

// ── icons (Lucide geometry, ISC — restyled per style) ──
type Node = [string, Record<string, string>];
const IconSvg: React.FC<{nodes: Node[]; stroke: string; sw: number; draw: number; size: number}> = ({nodes, stroke, sw, draw, size}) => (
	<svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" style={{overflow: 'visible'}}>
		{(nodes || []).map(([tag, a], i) =>
			React.createElement(tag, {key: i, ...a, pathLength: 1, strokeDasharray: 1, strokeDashoffset: 1 - c01(draw)}),
		)}
	</svg>
);

// lib = a picture from the person's own Media Lab library (resolved against the project's mediaBase)
let MEDIA = 'media/';
export const mediaUrl = (ref: string) => MEDIA + encodeURIComponent(String(ref || '').replace(/^lib:/, ''));
export const setMediaBase = (b?: string) => {
	if (b) MEDIA = b;
};
export type VisualT = {kind: 'art' | 'vec' | 'lib' | 'dio' | 'icon' | 'stat' | 'text'; item?: any; id?: string; nodes?: Node[]; label?: string; at?: number; value?: number; prefix?: string; suffix?: string; text?: string; tone?: number; motion?: string};
type VisP = {s: S; t: number; v: VisualT; x: number; y: number; sz: number; u: number; mg: string; i: number; showLabel?: boolean; dim?: number};

// what a picture DOES once it has landed (fly, spin, pulse…): the wizard picks it from the concept (motion_wizard.MOTIONS)
export const MOTIONS = ['none', 'float', 'fly', 'spin', 'pulse', 'swing', 'bounce', 'drive', 'sway', 'flicker', 'grow', 'shake', 'orbit', 'wobble'];
export const idle = (m: string | undefined, t: number, sz: number) => {
	if (!m || m === 'none' || t <= 0) return 'none';
	const k = Math.min(1, t / 0.6), q = sz / 100;          // ease the action in after the entrance
	switch (m) {
		case 'fly': return `translate(${Math.sin(t * 1.3) * 6 * q * k}px, ${(-Math.abs(Math.sin(t * 0.9)) * 22 - t * 4) * q * k}px) rotate(${Math.sin(t * 2.6) * 4 * k}deg)`;
		case 'spin': return `rotate(${t * 40 * k}deg)`;
		case 'pulse': return `scale(${1 + 0.07 * Math.max(0, Math.sin(t * 7.5)) * Math.max(0, Math.sin(t * 3.75)) * 2 * k})`;
		case 'swing': return `rotate(${Math.sin(t * 3.2) * 12 * k}deg)`;
		case 'bounce': return `translateY(${-Math.abs(Math.sin(t * 4.4)) * 26 * q * k}px) scale(${1 + 0.05 * (1 - Math.abs(Math.sin(t * 4.4))) * k}, ${1 - 0.05 * (1 - Math.abs(Math.sin(t * 4.4))) * k})`;
		case 'drive': return `translate(${Math.sin(t * 0.9) * 26 * q * k}px, ${Math.abs(Math.sin(t * 14)) * -2.5 * q * k}px)`;
		case 'sway': return `rotate(${Math.sin(t * 1.8) * 5 * k}deg)`;
		case 'flicker': return `scale(${1 + 0.04 * Math.sin(t * 23) * Math.sin(t * 7) * k}) skewX(${Math.sin(t * 11) * 2 * k}deg)`;
		case 'grow': return `scale(${1 + 0.12 * Math.min(1, t / 2.5)})`;
		case 'shake': return `translateX(${Math.sin(t * 40) * 4 * q * k * (Math.sin(t * 2) > 0.3 ? 1 : 0.15)}px)`;
		case 'orbit': return `translate(${Math.cos(t * 1.6) * 16 * q * k}px, ${Math.sin(t * 1.6) * 8 * q * k}px)`;
		case 'wobble': return `rotate(${Math.sin(t * 5) * 6 * k}deg) scale(${1 + Math.sin(t * 2.5) * 0.03 * k})`;
		default: return `translateY(${Math.sin(t * 2.1) * 8 * q * k}px)`;
	}
};

// one cued visual, centred on (x, y), `sz` px tall
export const Visual: React.FC<VisP> = ({s, t, v, x, y, sz, u, mg, i, showLabel = true, dim = 1}) => {
	const at = +v.at! || 0;
	if (t < at - 0.02) return null;
	const p = s.enter(t, at);
	const o = s.in01(t, at);
	const dt = s.time(t) - at;
	let body: React.ReactNode = null;
	let tf = '';
	let op = o;
	const pal = s.pal;
	const flt = s.motion.float ? Math.sin((t + i * 0.7) * 2.2) * s.motion.float * sz : 0;
	if (s.id === 'signature') tf = `scale(${0.93 + 0.07 * c01(p)})`;
	else if (s.id === 'grid') tf = `scale(${0.6 + 0.4 * p})`;
	else if (s.id === 'liquid') tf = `translateY(${flt}px) scale(${Math.max(0, p)})`;
	else {
		tf = `translateY(${(1 - p) * -90 * u}px) rotate(${(rnd(i * 5 + 2) - 0.5) * 7}deg)${s.boil(t, i + 10)}`;
		op = o > 0 ? 1 : 0;
	}
	if (v.kind === 'dio') {
		// a character / animal / object / place from the shared motion library, drawn live by the Diorama engine (it moves)
		body = <div style={{filter: `drop-shadow(0 ${14 * u}px ${24 * u}px rgba(0,0,0,.45))`}}><DioItem id={v.id} item={v.item} size={sz} t={Math.max(0, dt)} /></div>;
	} else if (v.kind === 'art' || v.kind === 'vec' || v.kind === 'lib') {
		// art = AI cut-out (build_art.py); vec = code-drawn styled glyph (build_vectors.mjs) — same treatment, different file
		const src = v.kind === 'art' ? `${mg}art/${s.key}/${v.id}.png` : v.kind === 'lib' ? MEDIA + encodeURIComponent(v.id || '') : `${mg}vec/${s.key}/${v.id}.svg`;
		const img = <Img src={src} onError={() => undefined} style={{width: sz, height: sz, objectFit: 'contain', display: 'block'}} />; // a missing cut-out must never abort a render
		if (s.id === 'signature')
			body = (
				<div style={{position: 'relative', filter: `blur(${(1 - c01(p)) * 10}px) drop-shadow(0 ${18 * u}px ${30 * u}px rgba(0,0,0,.6))`}}>
					{img}
					<div style={{position: 'absolute', left: 0, top: sz * 0.98, width: sz, height: sz * 0.35, overflow: 'hidden', opacity: 0.16, transform: 'scaleY(-1)',
						WebkitMaskImage: 'linear-gradient(to top, black, transparent 70%)'}}>
						<Img src={src} onError={() => undefined} style={{width: sz, height: sz, objectFit: 'contain', marginTop: -sz * 0.65}} />
					</div>
				</div>
			);
		else if (s.id === 'grid') {
			const rv = c01(dt / 0.45);
			body = (
				<div style={{position: 'relative'}}>
					<div style={{clipPath: `inset(${(1 - expoOut(rv)) * 100}% 0 0 0)`}}>{img}</div>
					{rv < 1 ? <div style={{position: 'absolute', left: 0, width: sz, top: (1 - expoOut(rv)) * sz - 10 * u, height: 20 * u, background: pal.acc}} /> : null}
				</div>
			);
		} else if (s.id === 'liquid')
			body = (
				<div style={{position: 'relative'}}>
					<div style={{position: 'absolute', inset: -sz * 0.18, borderRadius: '50%', background: `radial-gradient(closest-side, ${[pal.acc, pal.acc2, pal.acc3, pal.acc4][i % 4]}55, transparent)`}} />
					<div style={{position: 'relative', filter: `drop-shadow(0 ${14 * u}px ${24 * u}px rgba(0,0,0,.35))`}}>{img}</div>
				</div>
			);
		else body = <div style={{filter: `drop-shadow(${8 * u}px ${10 * u}px 0 rgba(59,42,23,.32))`}}>{img}</div>;
	} else if (v.kind === 'icon') {
		const draw = c01(dt / 0.9);
		if (s.id === 'signature') {
			const r = sz * 0.5;
			body = (
				<div style={{position: 'relative', width: sz, height: sz, display: 'grid', placeItems: 'center'}}>
					<svg width={sz} height={sz} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
						<circle cx={r} cy={r} r={r * 0.96} fill="none" stroke={pal.line} strokeOpacity={0.35} strokeWidth={1.5 * u} strokeDasharray={`${4 * u} ${10 * u}`}
							transform={`rotate(${t * 9} ${r} ${r})`} />
						<circle cx={r} cy={r} r={r * 0.96} fill="none" stroke={pal.acc} strokeWidth={2.5 * u} pathLength={1} strokeDasharray="0.18 0.82"
							strokeDashoffset={-draw * 0.6 - t * 0.04} opacity={c01(dt * 2)} />
					</svg>
					<div style={{filter: `drop-shadow(0 0 ${10 * u}px ${pal.acc}55)`}}>
						<IconSvg nodes={v.nodes!} stroke={pal.line} sw={1.15} draw={draw} size={sz * 0.52} />
					</div>
				</div>
			);
		} else if (s.id === 'grid') {
			const red = (v.tone ?? i) % 2 === 0;
			body = (
				<div style={{width: sz, height: sz, background: red ? pal.acc : pal.ink, display: 'grid', placeItems: 'center', overflow: 'hidden'}}>
					<div style={{transform: `translateY(${(1 - c01(dt / 0.35)) * 110}%)`}}>
						<IconSvg nodes={v.nodes!} stroke={pal.bg} sw={2.3} draw={1} size={sz * 0.58} />
					</div>
				</div>
			);
		} else if (s.id === 'liquid') {
			const c = [pal.acc, pal.acc2, pal.acc3, pal.acc4][(v.tone ?? i) % 4];
			body = (
				<div style={{width: sz, height: sz, borderRadius: '50%', display: 'grid', placeItems: 'center',
					background: `radial-gradient(circle at 32% 28%, #ffffffaa, ${c} 38%, ${pal.acc2} 100%)`, boxShadow: `0 ${16 * u}px ${40 * u}px ${c}66, inset 0 ${-10 * u}px ${24 * u}px #0003`}}>
					<IconSvg nodes={v.nodes!} stroke="#fff" sw={2} draw={draw * 1.4} size={sz * 0.5} />
				</div>
			);
		} else {
			const ring = [pal.acc, pal.acc2, pal.acc3][(v.tone ?? i) % 3];
			body = (
				<div style={{width: sz, height: sz, borderRadius: '50%', background: pal.acc4, border: `${8 * u}px solid ${ring}`, display: 'grid', placeItems: 'center',
					boxShadow: `${8 * u}px ${10 * u}px 0 rgba(59,42,23,.32)`}}>
					<IconSvg nodes={v.nodes!} stroke={pal.acc2} sw={2.2} draw={1} size={sz * 0.5} />
				</div>
			);
		}
	} else if (v.kind === 'stat') {
		body = <Counter s={s} t={t} at={at} value={+v.value! || 0} prefix={v.prefix} suffix={v.suffix} size={sz * 0.62} u={u} width={sz * 2.6} />;
	} else {
		body = (
			<div style={{width: sz * 2.4, display: 'grid', placeItems: 'center', height: sz}}>
				<Txt s={s} t={t} at={at} role="display" size={sz * 0.42} text={v.text || v.label || ''} width={sz * 2.4} color={i % 2 ? pal.acc : pal.ink} id={i} lines={2} />
			</div>
		);
	}
	const lab = showLabel && v.label && v.kind !== 'text' ? <Label s={s} t={t} at={at + 0.25} text={v.label} u={u} w={Math.max(sz * 1.15, 200 * u)} i={i} /> : null;
	return (
		<div style={{position: 'absolute', left: x, top: y, transform: 'translate(-50%, -50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 * u, opacity: dim}}>
			<div style={{opacity: op, transform: tf}}>
				<div style={{transform: idle(v.motion, s.time(t) - at - 0.4, sz), transformOrigin: v.motion === 'swing' ? '50% 8%' : '50% 50%'}}>{body}</div>
			</div>
			{lab}
		</div>
	);
};

export const Label: React.FC<{s: S; t: number; at: number; text: string; u: number; w: number; i?: number}> = ({s, t, at, text, u, w, i = 0}) => {
	const pal = s.pal;
	if (s.id === 'signature')
		return <Txt s={s} t={t} at={at} role="label" size={26 * u} text={text} width={w} color={pal.mute} style={{letterSpacing: '0.3em'}} lines={1} />;
	if (s.id === 'grid')
		return (
			<div style={{background: pal.ink, padding: `${6 * u}px ${14 * u}px`, opacity: t > at ? 1 : 0}}>
				<Txt s={s} t={t} at={at} role="label" size={28 * u} text={text} width={w * 0.9} color={pal.bg} lines={1} />
			</div>
		);
	if (s.id === 'liquid') {
		const sp = s.enter(t, at);
		return (
			<div style={{background: [pal.acc, pal.acc2, pal.acc3, pal.acc4][i % 4], borderRadius: 999, padding: `${8 * u}px ${24 * u}px`, transform: `scale(${Math.max(0, sp)})`}}>
				<Txt s={s} t={t} at={at} role="label" size={30 * u} text={text} width={w * 0.8} color={i % 4 >= 2 ? pal.dark : '#fff'} lines={1} />
			</div>
		);
	}
	return <Txt s={s} t={t} at={at} role="hand" size={48 * u} text={text} width={w} color={pal.ink} id={i + 30} lines={1} />;
};

// ── relation between two points ──
export const Connector: React.FC<{s: S; t: number; at: number; a: [number, number]; b: [number, number]; u: number; label?: string}> = ({s, t, at, a, b, u, label}) => {
	if (t < at) return null;
	const pal = s.pal;
	const dt = s.time(t) - at;
	const pr = inOut(c01(dt / 0.9));
	const [x1, y1] = a, [x2, y2] = b;
	const len = Math.hypot(x2 - x1, y2 - y1);
	const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
	let path = `M${x1} ${y1} L${x2} ${y2}`;
	let el: React.ReactNode;
	const dotU = ((dt - 0.9) / 1.4) % 1;
	const pt = (q: number) => [lerp(x1, x2, q), lerp(y1, y2, q)];
	if (s.id === 'liquid') {
		const n = 48, amp = 34 * u, waves = Math.max(1, Math.round(len / (360 * u)));
		const nx = -(y2 - y1) / (len || 1), ny = (x2 - x1) / (len || 1);
		path = Array.from({length: n + 1}, (_, k) => {
			const q = k / n, w = Math.sin(q * Math.PI * 2 * waves) * amp;
			return `${k ? 'L' : 'M'}${(lerp(x1, x2, q) + nx * w).toFixed(1)} ${(lerp(y1, y2, q) + ny * w).toFixed(1)}`;
		}).join(' ');
	}
	if (s.id === 'paper') path = `M${x1} ${y1} Q${mx} ${my - len * 0.22} ${x2} ${y2}`;
	if (s.id === 'signature')
		el = (
			<>
				<path d={path} stroke={pal.line} strokeWidth={2 * u} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - pr} opacity={0.8} />
				{dt > 0.9 ? <circle cx={pt(inOut(dotU))[0]} cy={pt(inOut(dotU))[1]} r={8 * u} fill={pal.acc3} style={{filter: `drop-shadow(0 0 ${12 * u}px ${pal.acc})`}} /> : null}
			</>
		);
	else if (s.id === 'grid') {
		const ticks = Math.max(2, Math.floor(len / (100 * u)));
		el = (
			<>
				<path d={path} stroke={pal.ink} strokeWidth={14 * u} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - expoOut(c01(dt / 0.6))} />
				{Array.from({length: ticks - 1}, (_, k) => {
					const q = (k + 1) / ticks, e = backOut(c01((dt - 0.25 - k * 0.04) / 0.3));
					const [px, py] = pt(q);
					return <rect key={k} x={px - 3 * u} y={py - 25 * u * e} width={6 * u} height={50 * u * e} fill={pal.ink} />;
				})}
			</>
		);
	} else if (s.id === 'liquid') {
		el = <path d={path} stroke="#fff" strokeOpacity={0.6} strokeWidth={6 * u} strokeLinecap="round" fill="none" strokeDasharray={`${2 * u} ${16 * u}`} style={{clipPath: `inset(0 ${(1 - pr) * 100}% 0 0)`}} />;
	} else {
		el = <path d={path} stroke={pal.acc4} strokeWidth={9 * u} strokeLinecap="round" fill="none" strokeDasharray={`${22 * u} ${15 * u}`} style={{clipPath: `inset(0 ${(1 - pr) * 100}% 0 0)`, filter: `drop-shadow(${4 * u}px ${5 * u}px 0 rgba(59,42,23,.3))`}} />;
	}
	return (
		<>
			<svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible'}}>{el}</svg>
			{label ? (
				<div style={{position: 'absolute', left: mx, top: my - (s.id === 'paper' ? len * 0.11 : 0) - 70 * u, transform: 'translate(-50%,-50%)'}}>
					<Tag s={s} t={t} at={at + 0.7} text={label} u={u} />
				</div>
			) : null}
		</>
	);
};

// small emphasis tag (signature amber plate, grid black box, liquid pill, paper mustard note)
export const Tag: React.FC<{s: S; t: number; at: number; text: string; u: number}> = ({s, t, at, text, u}) => {
	if (t < at) return null;
	const pal = s.pal;
	const p = s.enter(t, at);
	const box: Record<string, React.CSSProperties> = {
		signature: {background: pal.acc, padding: `${10 * u}px ${22 * u}px`, borderRadius: 4 * u, opacity: s.in01(t, at), transform: `translateY(${(1 - c01(p)) * 14 * u}px)`},
		grid: {background: pal.ink, padding: `${12 * u}px ${24 * u}px`, transform: `scale(${p})`},
		liquid: {background: pal.acc, padding: `${10 * u}px ${28 * u}px`, borderRadius: 999, transform: `scale(${Math.max(0, p)})`, boxShadow: `0 ${10 * u}px ${30 * u}px ${pal.acc}77`},
		paper: {background: pal.acc3, padding: `${8 * u}px ${24 * u}px`, transform: `scale(${p}) rotate(4deg)${s.boil(t, 91)}`, boxShadow: `${6 * u}px ${7 * u}px 0 rgba(59,42,23,.32)`},
	};
	const col = {signature: pal.dark, grid: pal.bg, liquid: '#fff', paper: pal.dark}[s.id];
	const role = {signature: 'label', grid: 'head', liquid: 'label', paper: 'hand'}[s.id];
	const fz = {signature: 28, grid: 46, liquid: 34, paper: 56}[s.id] * u;
	return (
		<div style={box[s.id]}>
			<div style={{...s.font(role), fontSize: fz, color: col, whiteSpace: 'nowrap', letterSpacing: s.id === 'signature' ? '0.12em' : 0, lineHeight: 1.1}}>{s.cased(text)}</div>
		</div>
	);
};

// ── numbers ──
const fmt = (n: number, dec: number) => n.toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec});
export const Counter: React.FC<{s: S; t: number; at: number; value: number; prefix?: string; suffix?: string; size: number; u: number; width: number; color?: string}> = ({s, t, at, value, prefix = '', suffix = '', size, u, width, color}) => {
	if (suffix && /^[A-Za-z]{2,}/.test(suffix)) suffix = ' ' + suffix;      // 8 billion, not 8billion
	if (prefix && /[A-Za-z]{2,}$/.test(prefix)) prefix = prefix + ' ';
	const pal = s.pal;
	const dec = Math.abs(value) < 100 && !Number.isInteger(value) ? 1 : 0;
	const final = prefix + fmt(value, dec) + suffix;
	const fz = fit(s, 'num', final, size, width, 1);
	const dt = s.time(t) - at;
	if (dt < 0) return <div style={{height: fz}} />;
	const font = {...s.font('num'), fontSize: fz, lineHeight: 1, color: color || pal.ink, whiteSpace: 'nowrap' as const};
	if (s.id === 'grid') {
		// rolling digits: each column spins down to its digit, staggered
		const chars = [...final];
		let di = 0;
		return (
			<div style={{...font, display: 'flex', alignItems: 'flex-end'}}>
				{chars.map((ch, k) => {
					if (!/\d/.test(ch)) return <span key={k} style={{opacity: c01(dt * 4)}}>{ch}</span>;
					const d = +ch, e = backOut(c01((dt - di++ * 0.07) / 0.9), 1.2);
					return (
						<span key={k} style={{display: 'inline-block', height: fz * 1.02, overflow: 'hidden'}}>
							<span style={{display: 'flex', flexDirection: 'column', transform: `translateY(${-(10 + d) * e * fz * 1.02}px)`}}>
								{Array.from({length: 20}, (_, j) => (
									<span key={j} style={{height: fz * 1.02, display: 'block'}}>{j % 10}</span>
								))}
							</span>
						</span>
					);
				})}
			</div>
		);
	}
	const prog = s.id === 'liquid' ? inOut(c01(dt / 1.6)) : expoOut(c01(dt / 1.7));
	const txt = prefix + fmt(value * prog, dec) + suffix;
	if (s.id === 'signature') return <div style={{...font, opacity: c01(dt * 3)}}>{txt}</div>;
	if (s.id === 'liquid') return <div style={{...font, transform: `scale(${Math.max(0, s.enter(t, at))})`}}>{txt}</div>;
	return <div style={{...font, color: color || pal.acc, transform: `${s.boil(t, 77)}`}}>{txt}</div>;
};
