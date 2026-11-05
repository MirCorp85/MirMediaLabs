// MIR MOTION GRAPHICS — beats. A motion-graphics video is a list of BEATS (one per script line); each beat renders its
// own styled background, an entrance transition, the visuals the wizard cued to the spoken words (props.visuals[].at =
// seconds into the beat, from the Whisper word timings) and the spoken captions (props.words). Every beat works in all
// four styles (style.ts) and in 16:9 / 9:16 / 1:1 — layout is computed from the canvas, never hard-coded.
import React from 'react';
import {AbsoluteFill, Loop, OffthreadVideo, Sequence, Video, getRemotionEnvironment, useCurrentFrame, useVideoConfig} from 'remotion';
import {Project} from '../lib';
import {Connector, Counter, Rule, Tag as TagK, Txt, Visual, VisualT, mediaUrl, setMediaBase, useMgFonts} from './kit';
import {S, STYLE_IDS, c01, expoOut, getStyle, inOut, rnd} from './style';
import {Actor, ACTION_NAMES, camFor, stageOf, ACTIONS} from './puppet';
import {Diorama} from './diorama';
import {SetView, SET_NAMES} from './sets';
import {Fx, FX_TYPES, Overlay, fxShake, fxTime} from './overlay';
import {Btn, Cursor, Flask, GITHUB, Ic} from './brand';

type SP = {p: Record<string, any>; proj: Project; durF: number};
type Ctx = {s: S; t: number; T: number; W: number; H: number; u: number; mg: string; port: boolean; p: Record<string, any>};

const useCtx = (p: Record<string, any>, proj: Project, durF: number): Ctx => {
	const f = useCurrentFrame();
	const {fps, width: W, height: H} = useVideoConfig();
	const s = getStyle(p.style || (proj as any).style, p.accent || (proj as any).accent);
	const mg = (proj as any).mgBase || 'mg/';
	useMgFonts(proj.fontBase || 'fonts/');
	setMediaBase(proj.mediaBase);
	return {s, t: f / fps - (+p.shift || 0), T: durF / fps, W, H, u: Math.min(W, H) / 1080 * (W > H ? 1 : 1.15), mg, port: H > W, p};
};

// ── backgrounds ──
const Grain: React.FC<{t: number; amt: number; id: string}> = ({t, amt, id}) => (
	<svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: amt, mixBlendMode: 'overlay'}}>
		<filter id={id}>
			<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={Math.floor(t * 24) % 97} stitchTiles="stitch" />
			<feColorMatrix type="saturate" values="0" />
		</filter>
		<rect width="100%" height="100%" filter={`url(#${id})`} />
	</svg>
);

const Bg: React.FC<{c: Ctx; n: number}> = ({c, n}) => {
	const {s, t, W, H, u} = c;
	const pal = s.pal;
	if (s.key === 'dusk')
		return (
			<AbsoluteFill style={{background: 'linear-gradient(180deg, #04161A 0%, #0C3439 55%, #1F5A5B 82%, #3E5A4E 100%)'}}>
				<div style={{position: 'absolute', left: W * 0.62, top: H * 0.78, width: 900 * u, height: 900 * u, transform: 'translate(-50%,-50%)', borderRadius: '50%', background: 'radial-gradient(closest-side, rgba(255,138,76,.32), transparent)'}} />
				<svg style={{position: 'absolute', left: 0, bottom: 0, width: W, height: H * 0.22, opacity: 0.85}} viewBox="0 0 1920 240" preserveAspectRatio="none">
					<path d={'M0 240 ' + Array.from({length: 33}, (_, i) => `L${i * 60} ${120 + rnd(i * 3 + n) * 110} L${i * 60 + 60} ${120 + rnd(i * 3 + n) * 110}`).join(' ') + ' L1920 240 Z'} fill="#03100F" />
				</svg>
				<Grain t={t} amt={0.1} id="g-dusk" />
				<AbsoluteFill style={{background: 'radial-gradient(75% 75% at 50% 50%, transparent 55%, rgba(0,0,0,.5))'}} />
			</AbsoluteFill>
		);
	if (s.id === 'signature')
		return (
			<AbsoluteFill style={{background: `radial-gradient(75% 75% at 50% 42%, ${pal.bg2}, ${pal.bg})`}}>
				<div style={{position: 'absolute', left: '50%', top: H * 0.86, width: W, height: H * 0.13, transform: 'translateX(-50%)', borderRadius: '50%', background: '#fff', opacity: 0.03}} />
				<div style={{position: 'absolute', top: -H * 0.3, left: ((t * 0.06 + n * 0.37) % 1.4) * W * 1.4 - W * 0.45, width: 240 * u, height: H * 1.6, transform: 'rotate(18deg)',
					background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent)'}} />
				<Grain t={t} amt={0.09} id="g-sig" />
				<AbsoluteFill style={{background: 'radial-gradient(72% 72% at 50% 50%, transparent 55%, rgba(0,0,0,.55))'}} />
			</AbsoluteFill>
		);
	if (s.id === 'grid')
		return (
			<AbsoluteFill style={{background: pal.bg}}>
				<svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.08}}>
					{Array.from({length: 12}, (_, i) => <line key={i} x1={(W / 12) * (i + 1)} y1={0} x2={(W / 12) * (i + 1)} y2={H} stroke={pal.ink} strokeWidth={2 * u} />)}
					<line x1={0} y1={H * 0.13} x2={W} y2={H * 0.13} stroke={pal.ink} strokeWidth={2 * u} />
					<line x1={0} y1={H * 0.87} x2={W} y2={H * 0.87} stroke={pal.ink} strokeWidth={2 * u} />
				</svg>
				<div style={{position: 'absolute', left: W * 0.052, top: H * 0.07, ...s.font('label'), fontSize: 26 * u, color: pal.ink}}>{String(n + 1).padStart(2, '0')}</div>
				<div style={{position: 'absolute', right: W * 0.052, top: H * 0.07, ...s.font('label'), fontSize: 26 * u, color: pal.ink}}>{s.cased(c.p.brand || 'MIR')}</div>
				<div style={{position: 'absolute', left: W * 0.052, bottom: H * 0.065, height: 10 * u, width: (W * 0.896) * c01(t / c.T), background: pal.ink}} />
			</AbsoluteFill>
		);
	if (s.id === 'liquid') {
		const w = (2 * Math.PI * t) / 12;
		const blobs = [[pal.acc, W * 0.26 + Math.sin(w) * W * 0.14, H * 0.28 + Math.cos(w * 2) * H * 0.11], [pal.acc2, W * 0.76 + Math.cos(w) * W * 0.12, H * 0.7 + Math.sin(w) * H * 0.13], [pal.acc3, W * 0.5 + Math.sin(w * 2) * W * 0.16, H * 0.84 + Math.cos(w) * H * 0.08]];
		return (
			<AbsoluteFill style={{background: pal.bg}}>
				{blobs.map(([col, x, y], i) => (
					<div key={i} style={{position: 'absolute', left: x, top: y, width: 1240 * u, height: 1240 * u, transform: 'translate(-50%,-50%)', borderRadius: '50%', background: `radial-gradient(closest-side, ${col}66, transparent)`}} />
				))}
			</AbsoluteFill>
		);
	}
	return (
		<AbsoluteFill style={{background: pal.bg}}>
			<Grain t={0} amt={0.16} id="g-paper" />
		</AbsoluteFill>
	);
};

// ── entrance transition (drawn on top at the start of the beat; the previous beat's last frame is behind us anyway) ──
const Trans: React.FC<{c: Ctx; n: number}> = ({c, n}) => {
	const {s, t, W, H} = c;
	const d = s.motion.trans;
	if (n === 0 || t > d) return null;
	const p = t / d, pal = s.pal;
	if (s.id === 'signature') return <AbsoluteFill style={{background: '#000', opacity: 1 - inOut(p)}} />;
	if (s.id === 'grid') return <div style={{position: 'absolute', top: 0, bottom: 0, width: W, left: W * inOut(p), background: pal.acc}} />;
	if (s.id === 'liquid') return <div style={{position: 'absolute', left: W / 2, top: H / 2, width: 1, height: 1, borderRadius: '50%', background: pal.acc2, transform: `translate(-50%,-50%) scale(${Math.hypot(W, H) * 1.3 * (1 - inOut(p))})`}} />;
	return <div style={{position: 'absolute', top: -H * 0.2, height: H * 1.4, width: W * 1.3, left: W * 1.1 - W * 2.5 * s.time(p), background: pal.acc, transform: 'rotate(-3deg)', boxShadow: '0 0 60px rgba(59,42,23,.4)'}} />;
};

// ── spoken captions (words with timings → the current word is lit) ──
// ── safe areas (16:9 + 9:16 + 1:1) ──
// Every beat lays itself out inside ZONE: below the headline row (+ the who-tag row) and ABOVE the captions band, so a
// picture, list row or character can never sit on the spoken subtitles, whatever the aspect ratio. Captions get their own
// band at the bottom (taller in portrait: 4 words a line, up to 2 lines).
const capsOn = (c: Ctx) => Array.isArray(c.p.words) && c.p.words.length > 0 && c.p.captions !== false;
const bands = (c: Ctx) => {
	const {H, port} = c;
	return port ? {hd: 0.12 * H, cap: 0.86 * H, capTop: 0.79 * H, end: 0.93 * H} : {hd: 0.12 * H, cap: 0.88 * H, capTop: 0.81 * H, end: 0.93 * H};
};
type Zone = {y0: number; y1: number; h: number; mid: number};
const zone = (c: Ctx, head: boolean, extra = 0): Zone => {
	const b = bands(c), H = c.H;
	const y0 = (head ? (c.port ? 0.22 : 0.23) * H : 0.08 * H) + extra;
	const y1 = (capsOn(c) ? b.capTop - 0.015 * H : b.end);
	return {y0, y1, h: y1 - y0, mid: (y0 + y1) / 2};
};
const LABEL = (u: number) => 74 * u;          // height a picture's label adds under it (Visual: gap + label)

const Captions: React.FC<{c: Ctx; y?: number}> = ({c, y}) => {
	const {s, t, W, u, p} = c;
	const words: {w: string; s: number; e: number}[] = Array.isArray(p.words) ? p.words : [];
	if (!words.length || p.captions === false) return null;
	const pal = s.pal;
	// a window of words around the current one, so long lines never spill out of the captions band
	let cur = words.findIndex((w) => t < w.e);
	if (cur < 0) cur = words.length - 1;
	const per = c.port ? 4 : 6, start = Math.floor(cur / per) * per;
	const win = words.slice(start, start + per);
	const fz = {signature: 38, grid: 44, liquid: 42, paper: 46}[s.id] * u * (c.port ? 1.05 : 1);
	const role = 'head';
	const wrap: React.CSSProperties = {position: 'absolute', left: '50%', top: y ?? bands(c).cap, transform: 'translate(-50%,-50%)', display: 'flex', gap: 0.32 * fz, rowGap: 0.18 * fz, flexWrap: 'wrap', justifyContent: 'center', maxWidth: W * (c.port ? 0.9 : 0.86)};
	return (
		<div style={wrap}>
			{win.map((w, i) => {
				const on = start + i === cur && t >= w.s, past = t >= w.e;
				const base: React.CSSProperties = {...s.font(role), fontSize: fz, lineHeight: 1.2, whiteSpace: 'nowrap', transition: 'none'};
				if (s.id === 'signature') return <span key={i} style={{...base, color: on ? pal.acc : pal.ink, opacity: past || on ? 1 : 0.4}}>{s.cased(w.w)}</span>;
				if (s.id === 'grid') return <span key={i} style={{...base, padding: `${2 * u}px ${10 * u}px`, background: on ? pal.acc : past ? pal.ink : 'transparent', color: on || past ? pal.bg : pal.ink, outline: `${3 * u}px solid ${pal.ink}`}}>{s.cased(w.w)}</span>;
				if (s.id === 'liquid') {
					const sp = on ? 1 + 0.12 * Math.sin(c01((t - w.s) / 0.25) * Math.PI) : 1;
					return <span key={i} style={{...base, padding: `${4 * u}px ${18 * u}px`, borderRadius: 999, background: on ? pal.acc : 'rgba(255,255,255,.1)', color: '#fff', transform: `scale(${sp})`, display: 'inline-block'}}>{s.cased(w.w)}</span>;
				}
				return <span key={i} style={{...base, color: on ? pal.acc : pal.ink, transform: `rotate(${(rnd(i + start) - 0.5) * 4}deg)${s.boil(t, 200 + i, 0.5)}`, display: 'inline-block', textDecoration: on ? `underline ${pal.acc3}` : 'none'}}>{s.cased(w.w)}</span>;
			})}
		</div>
	);
};

const Frame: React.FC<{c: Ctx; n: number; children: React.ReactNode; captions?: boolean}> = ({c, n, children, captions = true}) => {
	const {s, t, T} = c;
	const push = s.motion.push ? 1 + s.motion.push * c01(t / T) : 1;
	if (c.p.inShot) return <AbsoluteFill style={{transform: `scale(${push})`}}>{children}</AbsoluteFill>;
	return (
		<AbsoluteFill>
			<Bg c={c} n={n} />
			<AbsoluteFill style={{transform: `scale(${push})`}}>{children}</AbsoluteFill>
			{captions ? <Captions c={c} /> : null}
			<Trans c={c} n={n} />
		</AbsoluteFill>
	);
};

const vis = (p: Record<string, any>): VisualT[] => (Array.isArray(p.visuals) ? p.visuals : []).filter((v: any) => v && v.kind);

const Head: React.FC<{c: Ctx; text?: string; id: number; size?: number; align?: 'left' | 'center'; left?: number}> = ({c, text, id, size = 66, align = 'center', left}) =>
	text ? (
		<div style={{position: 'absolute', left: left ?? c.W / 2, top: bands(c).hd, transform: left != null ? 'translateY(-50%)' : 'translate(-50%,-50%)'}}>
			<Txt s={c.s} t={c.t} at={0.1} role="head" size={size * c.u * (c.port ? 0.92 : 1)} text={text} width={c.W * (c.port ? 0.88 : 0.84)} align={align} lines={2} id={id} />
		</div>
	) : null;

// n pictures (with labels) packed into a zone: one row in landscape; 1 column (n≤2) or 2 columns in portrait.
// Returns centres + the picture size that keeps every picture AND its label inside the zone.
const pack = (c: Ctx, z: Zone, n: number, base: number, labels = true): {pts: [number, number][]; sz: number} => {
	const {W, u, port} = c;
	if (n <= 0) return {pts: [], sz: 0};
	const lab = labels ? LABEL(u) : 0;
	const cols = port ? (n <= 2 ? 1 : 2) : n, rows = Math.ceil(n / cols);
	const cellH = z.h / rows, cellW = (W * 0.9) / cols;
	const sz = Math.max(60 * u, Math.min(base * u, cellH - lab - 24 * u, cellW * 0.82));
	const pts: [number, number][] = [];
	for (let i = 0; i < n; i++) {
		const r = Math.floor(i / cols), inRow = Math.min(cols, n - r * cols), k = i - r * cols;
		const span = port ? W * 0.5 : Math.min(W * 0.76, (sz + 120 * u) * (inRow - 1));
		const x = inRow === 1 ? W / 2 : W / 2 - span / 2 + (span * k) / (inRow - 1);
		const y = z.y0 + cellH * (r + 0.5) - lab / 2;
		pts.push([x, y]);
	}
	return {pts, sz};
};

// ── beats ──
const Title: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, u, port} = c;
	const vs = vis(p);
	const z = zone(c, false);
	const vsz = vs.length ? Math.min(200 * u, z.h * 0.22) : 0;
	const left = s.id === 'grid' && !port;
	const kick = p.kicker ? <Txt s={s} t={t} at={0.15} role="label" size={30 * u} text={p.kicker} width={W * 0.8} color={s.pal.acc} lines={1} style={{letterSpacing: s.id === 'signature' ? '0.4em' : undefined}} /> : null;
	return (
		<Frame c={c} n={+p.n || 0}>
			<div style={{position: 'absolute', left: W / 2, top: vs.length ? z.y0 + (z.h - vsz - 30 * u) / 2 : z.mid, transform: 'translate(-50%,-50%)', display: 'flex', flexDirection: 'column', alignItems: left ? 'flex-start' : 'center', gap: 24 * u, width: W * 0.86}}>
				{kick}
				<Txt s={s} t={t} at={0.3} role="display" size={(port ? 112 : 150) * u} text={p.title || ''} width={W * 0.86} align={left ? 'left' : 'center'} lines={port ? 4 : 2} id={1} />
				<Rule s={s} t={t} at={0.75} w={W * (s.id === 'grid' ? 0.86 : 0.4)} u={u} />
				{p.sub ? <Txt s={s} t={t} at={1.1} role="body" size={(port ? 40 : 44) * u} text={p.sub} width={W * 0.76} color={s.pal.mute} align={left ? 'left' : 'center'} id={2} noCase /> : null}
			</div>
			{vs.map((v, i) => {
				const span = Math.min(W * 0.6, (vsz + 80 * u) * (vs.length - 1));
				const x = vs.length === 1 ? W / 2 : W / 2 - span / 2 + (span * i) / (vs.length - 1);
				return <Visual key={i} s={s} t={t} v={v} x={x} y={z.y1 - vsz / 2} sz={vsz} u={u} mg={c.mg} i={i} showLabel={false} />;
			})}
		</Frame>
	);
};

const Stat: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, u, port} = c;
	const vs = vis(p);
	const side = vs.length && !port;
	const z = zone(c, false);
	const vsz = vs.length ? (side ? Math.min(420 * u, z.h * 0.7) : Math.min(300 * u, z.h * 0.3)) : 0;
	const cx = side ? W * 0.36 : W / 2;
	const cy = side || !vs.length ? z.mid : z.y0 + (z.h - vsz - 30 * u) / 2;
	return (
		<Frame c={c} n={+p.n || 0}>
			<div style={{position: 'absolute', left: cx, top: cy, transform: 'translate(-50%,-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22 * u}}>
				{p.kicker ? <Txt s={s} t={t} at={0.15} role="label" size={30 * u} text={p.kicker} width={W * 0.6} color={s.pal.acc} lines={1} style={{letterSpacing: s.id === 'signature' ? '0.35em' : undefined}} /> : null}
				<Counter s={s} t={t} at={0.25} value={+p.value || 0} prefix={p.prefix} suffix={p.suffix} size={(port ? 200 : side ? 230 : 280) * u} u={u} width={W * (side ? 0.6 : 0.86)} />
				<Rule s={s} t={t} at={0.5} w={W * (side ? 0.4 : 0.34)} u={u} />
				{p.label ? <Txt s={s} t={t} at={0.9} role="label" size={34 * u} text={p.label} width={W * (port ? 0.8 : 0.6)} color={s.pal.mute} lines={2} id={3} style={{letterSpacing: s.id === 'signature' ? '0.3em' : undefined}} /> : null}
			</div>
			{vs.length ? (side ? <Visual s={s} t={t} v={vs[0]} x={W * 0.76} y={z.mid - LABEL(u) / 2} sz={vsz} u={u} mg={c.mg} i={0} />
				: <Visual s={s} t={t} v={vs[0]} x={W / 2} y={z.y1 - vsz / 2} sz={vsz} u={u} mg={c.mg} i={0} showLabel={false} />) : null}
		</Frame>
	);
};

// 1–4 visuals cued to words — the workhorse "every phrase gets a picture" beat
const Visuals: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, u} = c;
	const vs = vis(p).slice(0, 4);
	const n = vs.length;
	const z = zone(c, !!p.headline);
	const {pts, sz} = pack(c, z, n, n <= 1 ? 460 : n === 2 ? 380 : n === 3 ? 320 : 270);
	return (
		<Frame c={c} n={+p.n || 0}>
			<Head c={c} text={p.headline} id={4} size={70} />
			{pts.map(([x, y], i) => <Visual key={i} s={s} t={t} v={vs[i]} x={x} y={y} sz={sz} u={u} mg={c.mg} i={i} />)}
		</Frame>
	);
};

// A → B with a labelled connector (cause/effect, distance, flow)
const Relation: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, u, port} = c;
	const vs = vis(p);
	const a = vs[0], b = vs[1];
	const z = zone(c, !!p.headline);
	const lab = LABEL(u);
	const sz = port ? Math.min(270 * u, z.h / 2 - lab - 120 * u) : Math.min(360 * u, z.h - lab - 30 * u);   // portrait leaves room for the link tag between A and B
	const A: [number, number] = port ? [W / 2, z.y0 + sz / 2 + 10 * u] : [W * 0.24, z.mid - lab / 2];
	const B: [number, number] = port ? [W / 2, z.y1 - lab - sz / 2] : [W * 0.76, z.mid - lab / 2];
	const at = (v?: VisualT) => +(v?.at || 0);
	return (
		<Frame c={c} n={+p.n || 0}>
			<Head c={c} text={p.headline} id={5} size={64} />
			{a && b ? <Connector s={s} t={t} at={Math.max(at(a), at(b)) + 0.4} a={port ? [A[0], A[1] + sz * 0.5 + lab] : [A[0] + sz * 0.55, A[1]]} b={port ? [B[0], B[1] - sz * 0.55] : [B[0] - sz * 0.55, B[1]]} u={u} label={p.link} /> : null}
			{a ? <Visual s={s} t={t} v={a} x={A[0]} y={A[1]} sz={sz} u={u} mg={c.mg} i={0} /> : null}
			{b ? <Visual s={s} t={t} v={b} x={B[0]} y={B[1]} sz={sz} u={u} mg={c.mg} i={1} /> : null}
		</Frame>
	);
};

// bullet list; each item is cued (props.items[].at) and may carry a small visual
const List: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, u, port} = c;
	const items: {text: string; at?: number; visual?: VisualT}[] = Array.isArray(p.items) ? p.items.slice(0, 6) : [];
	const left = port ? W * 0.08 : W * 0.14;
	const z = zone(c, !!p.headline);
	const gap = z.h / Math.max(1, items.length);
	const rowW = W * (port ? 0.84 : 0.78);
	return (
		<Frame c={c} n={+p.n || 0}>
			<Head c={c} text={p.headline} id={6} size={64} align="left" left={left} />
			{items.map((it, i) => {
				const at = +(it.at ?? 0.3 + i * 0.5);
				const vsz = Math.min(gap * 0.78, (port ? 130 : 150) * u);
				return (
					<div key={i} style={{position: 'absolute', left, top: z.y0 + gap * i, height: gap, display: 'flex', alignItems: 'center', gap: 28 * u, width: rowW}}>
						<div style={{position: 'relative', width: vsz, height: vsz, flex: 'none'}}>
							{it.visual ? <Visual s={s} t={t} v={{...it.visual, at}} x={vsz / 2} y={vsz / 2} sz={vsz} u={u} mg={c.mg} i={i} showLabel={false} /> : (
								<div style={{position: 'absolute', left: vsz / 2, top: vsz / 2, transform: 'translate(-50%,-50%)'}}>
									<Counter s={s} t={t} at={at} value={i + 1} size={vsz * 0.55} u={u} width={vsz} color={s.pal.acc} />
								</div>
							)}
						</div>
						<Txt s={s} t={t} at={at + 0.1} role="head" size={Math.min((port ? 50 : 54) * u, gap * 0.36)} text={it.text} width={rowW - vsz - 28 * u} align="left" lines={2} id={10 + i} noCase={s.id !== 'grid'} />
					</div>
				);
			})}
		</Frame>
	);
};

const Compare: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, u, port} = c;
	const vs = vis(p);
	const pal = s.pal;
	const z = zone(c, !!p.headline);
	// portrait: two stacked cards (title / picture / value) each half the zone; landscape: two columns
	const cellH = port ? z.h / 2 : z.h;
	const tH = 50 * u, vH = 90 * u;
	const vsz = Math.max(60 * u, Math.min((port ? 240 : 300) * u, cellH - tH - vH - 30 * u));
	const cols = [0, 1].map((i) => {
		const top = port ? z.y0 + cellH * i : z.y0;
		const blockH = tH + vsz + vH;
		const y0 = top + (cellH - blockH) / 2;
		return {v: vs[i], title: i ? p.b : p.a, val: i ? p.bval : p.aval, x: port ? W / 2 : W * (i ? 0.73 : 0.27), yT: y0 + tH / 2, yV: y0 + tH + vsz / 2, yN: y0 + tH + vsz + vH / 2};
	});
	return (
		<Frame c={c} n={+p.n || 0}>
			<Head c={c} text={p.headline} id={7} size={60} />
			{port ? <div style={{position: 'absolute', top: z.y0 + cellH, left: W * 0.2, width: W * 0.6 * c01(s.enter(t, 0.3)), height: 3 * u, background: pal.line, opacity: s.id === 'liquid' ? 0.3 : 0.5}} />
				: <div style={{position: 'absolute', left: W / 2, top: z.y0, height: z.h * c01(s.enter(t, 0.3)), width: 3 * u, background: pal.line, opacity: s.id === 'liquid' ? 0.3 : 0.5}} />}
			{cols.map((col, i) => (
				<React.Fragment key={i}>
					<div style={{position: 'absolute', left: col.x, top: col.yT, transform: 'translate(-50%,-50%)'}}>
						<Txt s={s} t={t} at={0.2 + i * 0.25} role="label" size={34 * u} text={col.title || ''} width={W * (port ? 0.8 : 0.4)} color={i ? pal.acc : pal.mute} lines={1} id={20 + i} />
					</div>
					{col.v ? <Visual s={s} t={t} v={col.v} x={col.x} y={col.yV} sz={vsz} u={u} mg={c.mg} i={i} showLabel={false} /> : null}
					{col.val != null ? (
						<div style={{position: 'absolute', left: col.x, top: col.yN, transform: 'translate(-50%,-50%)'}}>
							<Txt s={s} t={t} at={0.8 + i * 0.25} role="num" size={(port ? 64 : 76) * u} text={String(col.val)} width={W * (port ? 0.8 : 0.4)} color={i ? pal.acc : pal.ink} lines={1} id={24 + i} noCase />
						</div>
					) : null}
				</React.Fragment>
			))}
		</Frame>
	);
};

const Quote: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, u, port} = c;
	const vs = vis(p);
	const z = zone(c, false);
	const vsz = vs.length ? Math.min(200 * u, z.h * 0.2) : 0;
	return (
		<Frame c={c} n={+p.n || 0}>
			<div style={{position: 'absolute', left: W / 2, top: vs.length ? z.y0 + (z.h - vsz - 30 * u) / 2 : z.mid, transform: 'translate(-50%,-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26 * u}}>
				<div style={{...s.font('display'), fontSize: (port ? 170 : 200) * u, lineHeight: 0.6, color: s.pal.acc, opacity: s.in01(t, 0.1)}}>“</div>
				<Txt s={s} t={t} at={0.25} role={s.id === 'paper' ? 'hand' : 'head'} size={(port ? 64 : 72) * u} text={p.text || ''} width={W * (port ? 0.86 : 0.76)} lines={port ? 6 : 4} id={8} noCase={s.id !== 'grid'} />
				{p.by ? <Txt s={s} t={t} at={1.2} role="label" size={32 * u} text={'— ' + p.by} width={W * 0.7} color={s.pal.mute} lines={1} id={9} noCase /> : null}
			</div>
			{vs[0] ? <Visual s={s} t={t} v={vs[0]} x={W / 2} y={z.y1 - vsz / 2} sz={vsz} u={u} mg={c.mg} i={0} showLabel={false} /> : null}
		</Frame>
	);
};

// MIR MEDIA LABS end card (every video, user rule): thanks + LIKE and SUBSCRIBE pressed by a cursor + the GitHub download line
const EndCard: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, H, u, port} = c;
	const pal = s.pal;
	const ly = H * (port ? 0.5 : 0.56);
	const likeX = port ? W / 2 : W * 0.36, subX = port ? W / 2 : W * 0.64, likeY = port ? H * 0.46 : ly, subY = port ? H * 0.56 : ly;
	const ghOn = s.in01(t, 1.6);
	return (
		<Frame c={c} n={+p.n || 0} captions={false}>
			<div style={{position: 'absolute', left: W / 2, top: H * (port ? 0.24 : 0.22), transform: 'translate(-50%,-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22 * u}}>
				<Txt s={s} t={t} at={0.15} role="display" size={(port ? 96 : 110) * u} text={p.title || 'Thanks for watching'} width={W * 0.84} lines={2} id={30} />
				<Rule s={s} t={t} at={0.5} w={W * 0.26} u={u} />
			</div>
			<div style={{position: 'absolute', left: likeX, top: likeY, transform: 'translate(-50%,-50%)'}}>
				<Btn s={s} t={t} at={0.6} press={1.9} icon="like" label={p.line1 && /like/i.test(p.line1) ? 'Like' : 'Like'} done="Liked" u={u} t0={0} />
			</div>
			<div style={{position: 'absolute', left: subX, top: subY, transform: 'translate(-50%,-50%)'}}>
				<Btn s={s} t={t} at={0.85} press={2.9} icon="bell" label="Subscribe" done="Subscribed" u={u} t0={0} />
			</div>
			<Cursor s={s} t={t} u={u} pts={[[likeX + 20 * u, likeY + 10 * u, 1.9], [subX + 30 * u, subY + 10 * u, 2.9]]} />
			<div style={{position: 'absolute', left: W / 2, top: H * (port ? 0.76 : 0.82), transform: `translate(-50%,-50%) translateY(${(1 - ghOn) * 20 * u}px)`, opacity: ghOn,
				display: 'flex', alignItems: 'center', gap: 22 * u}}>
				<Flask s={s} draw={c01((t - 1.6) / 1.2)} ring={c01((t - 2.2) / 0.8)} bubbles={c01((t - 2.6) / 0.8)} spin={t * 0.05} size={110 * u} />
				<div style={{display: 'flex', flexDirection: 'column', gap: 6 * u}}>
					<div style={{...s.font('head'), fontSize: 40 * u, color: pal.ink, lineHeight: 1.1}}>{s.cased(p.line2 || 'Download the MIR MEDIA LABS app')}</div>
					<div style={{display: 'flex', alignItems: 'center', gap: 10 * u, ...s.font('label'), fontSize: 30 * u, color: pal.acc, letterSpacing: s.id === 'signature' ? '0.08em' : 0}}>
						<Ic n="github" size={34 * u} color={pal.acc} /> {GITHUB}
					</div>
				</div>
			</div>
		</Frame>
	);
};

// MIR MEDIA LABS intro sting (every video, user rule): the flask draws itself in the style, the wordmark lands, the title follows
const Intro: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, H, u, port} = c;
	const pal = s.pal;
	const d = s.time(t);
	const pop = s.id === 'liquid' ? Math.max(0, s.enter(t, 0.05)) : s.id === 'grid' ? s.enter(t, 0.05) : 1;
	return (
		<Frame c={c} n={0} captions={false}>
			<div style={{position: 'absolute', left: W / 2, top: H * (port ? 0.4 : 0.38), transform: `translate(-50%,-50%) scale(${pop})`}}>
				<Flask s={s} draw={c01(d / 1.3)} ring={c01((d - 0.7) / 0.9)} bubbles={c01((d - 1.1) / 0.8)} spin={d * 0.08} size={(port ? 380 : 330) * u} />
			</div>
			<div style={{position: 'absolute', left: W / 2, top: H * (port ? 0.62 : 0.7), transform: 'translate(-50%,-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 * u}}>
				<Txt s={s} t={t} at={0.9} role="display" size={(port ? 92 : 100) * u} text="MIR MEDIA LABS" width={W * 0.86} lines={1} id={60} noCase={false}
					style={{letterSpacing: s.id === 'signature' ? '0.14em' : s.id === 'grid' ? '0' : '0.02em'}} />
				<Rule s={s} t={t} at={1.25} w={W * 0.22} u={u} />
				{p.title ? <Txt s={s} t={t} at={1.5} role="label" size={32 * u} text={p.title} width={W * 0.7} color={pal.mute} lines={1} id={61}
					style={{letterSpacing: s.id === 'signature' ? '0.3em' : undefined}} /> : null}
			</div>
		</Frame>
	);
};

// an animated character performing an action (speech, run, score…) with the mouth on the spoken words
const ActionBeat: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, H, u, port} = c;
	const vs = vis(p);
	const side = vs.length && !port;
	// the stage fills the safe zone: below the headline + who tag, above the captions band (any aspect ratio)
	const z = zone(c, !!p.headline, p.who ? (p.headline ? 0.035 : 0.06) * H : 0);
	const aw = side ? W * 0.62 : W * 0.9, ah = z.h;
	const ax = side ? W * 0.4 : W / 2, ay = z.mid;
	const at = +p.at || 0;
	const e = s.in01(t, at);
	const words = (Array.isArray(p.words) ? p.words : []).map((w: any) => ({w: w.w, s: w.s - 0.35, e: w.e - 0.35}));   // the voice starts 0.35 s into the beat
	if (p.set || p.plate) return <StoryShot c={c} words={words} />;
	return (
		<Frame c={c} n={+p.n || 0}>
			<Head c={c} text={p.headline} id={70} size={62} />
			<div style={{position: 'absolute', left: ax, top: ay, transform: `translate(-50%,-50%) translateY(${(1 - e) * 30 * u}px)`, opacity: e}}>
				<Actor s={s} t={t - at} action={p.action || 'talk'} figure={p.figure || {}} figure2={p.figure2} words={words} w={aw} h={ah} seed={+p.n || 0} />
			</div>
			{p.who ? (
				<div style={{position: 'absolute', left: W / 2, top: p.headline ? zone(c, true).y0 - 0.005 * H : 0.09 * H, transform: 'translate(-50%,-50%)'}}>
					<Tag2 s={s} t={t} at={at + 0.6} text={p.who} u={u} />
				</div>
			) : null}
			{side ? <Visual s={s} t={t} v={vs[0]} x={W * 0.82} y={z.mid - LABEL(u) / 2} sz={Math.min(300 * u, z.h - LABEL(u))} u={u} mg={c.mg} i={0} /> : null}
		</Frame>
	);
};
const Tag2: React.FC<{s: S; t: number; at: number; text: string; u: number}> = ({s, t, at, text, u}) => <TagK s={s} t={t} at={at} text={text} u={u} />;

const PlateVid: React.FC<any> = (a) => (getRemotionEnvironment().isRendering ? <OffthreadVideo {...a} /> : <Video {...a} />);
// STORY SHOT: the character inside a real place (a set), framed by a camera shot (wide / medium / close / xclose) with depth of
// field, the scene's data overlay (timer, distance, score, gauge, chain, label) and an FX moment (slowmo, impact, freeze, flash).
const StoryShot: React.FC<{c: Ctx; words: {w: string; s: number; e: number}[]}> = ({c, words}) => {
	const {s, t, W, H, u, p} = c;
	const {fps} = useVideoConfig();
	const at = +p.at || 0;
	const fxAt = +(p.fxAt ?? 0.9);
	const ta = fxTime(p.fx, t - at, fxAt);
	// a podium speech only makes sense on the stage set; anywhere else a spoken line is natural talking
	const action = p.action === 'speech' && p.set !== 'stage' ? 'talk' : p.action || 'talk';
	const out = stageOf(action, s, ta, words, +p.n || 0);
	const shot = ['wide', 'medium', 'close', 'xclose'].includes(p.shot) ? p.shot : 'wide';
	const cam = camFor(out, shot, W / H, t, !!(ACTIONS[action] || {}).wide);
	const dof = {wide: s.key === 'dusk' ? 1.2 : 0, medium: 3, close: 7, xclose: 10}[shot];
	const e = s.in01(t, at);
	const vs = vis(p);
	return (
		<Frame c={c} n={+p.n || 0}>
			<AbsoluteFill style={{transform: fxShake(p.fx, t - at, fxAt, u) || undefined}}>
				{p.plate ? (
					// HYBRID: this key moment is an AI-animated shot (motion_scenes.py: cast sheet → keyframe → H3 → smoothed)
					<AbsoluteFill style={{transform: `scale(${1 + 0.05 * Math.min(1, t / Math.max(1, c.T))})`}}>
						{/* the clip runs on THIS beat's clock (inside a continuous shot a station's clock is shifted) and loops within its
						    length — a neighbouring station still on screen never asks the decoder for a frame past the clip's end */}
						<Sequence from={Math.round((+p.shift || 0) * fps)} layout="none">
							<Loop durationInFrames={Math.max(30, Math.floor((+p.plate_dur || +p.dur || c.T || 6) * fps) - 2)} layout="none">
								<PlateVid src={mediaUrl(p.plate)} style={{width: '100%', height: '100%', objectFit: 'cover'}} muted />
							</Loop>
						</Sequence>
					</AbsoluteFill>
				) : (
					<>
						<SetView s={s} t={t} name={p.set || 'street'} cam={cam} dof={dof} drift={t * 6} W={W} H={H} id={'set' + (+p.n || 0)} />
						<AbsoluteFill style={{opacity: e}}>
							<Actor s={s} t={ta} action={action} figure={p.figure || {}} figure2={p.figure2} words={words} w={W} h={H} seed={+p.n || 0} mood={p.mood} vb={cam.vb} />
						</AbsoluteFill>
					</>
				)}
				{vs.length ? <Visual s={s} t={t} v={vs[0]} x={W * (c.port ? 0.5 : 0.8)} y={H * (c.port ? 0.3 : 0.36)} sz={Math.min(260 * u, H * 0.24)} u={u} mg={c.mg} i={0} /> : null}
			</AbsoluteFill>
			{p.overlay && p.overlay.type ? <Overlay s={s} t={t} o={p.overlay} W={W} H={H} u={u} /> : null}
			<Fx s={s} t={t - at} fx={p.fx} at={fxAt} W={W} H={H} u={u} />
			{p.headline ? <Head c={c} text={p.headline} id={70} size={58} /> : null}
			{p.who ? (
				<div style={{position: 'absolute', left: W * 0.06, top: H * (p.headline ? 0.2 : 0.08), transform: 'translateY(-50%)'}}>
					<Tag2 s={s} t={t} at={at + 0.6} text={p.who} u={u} />
				</div>
			) : null}
		</Frame>
	);
};

// style preview card (the wizard's style picker thumbnails + the lab) — a tiny 3-beat demo
const Demo: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {t, T} = c;
	const b = t < T / 3 ? 0 : t < (2 * T) / 3 ? 1 : 2;
	const local = t - (b * T) / 3;
	const fake = (q: Record<string, any>) => <SubBeat c={c} local={local} q={q} />;
	(c as any).proj = proj;
	if (b === 0) return fake({kind: 'title', kicker: 'Chapter one', title: 'The speed of light', sub: 'A tiny trip at 300,000 km every second'});
	if (b === 1) return fake({kind: 'stat', kicker: 'In a vacuum', value: 299792, label: 'kilometres per second', visuals: [{kind: 'icon', id: 'zap', at: 0.3, nodes: p.zap}]});
	return fake({kind: 'relation', visuals: [{kind: 'art', id: 'sun', label: 'Sun', at: 0.1}, {kind: 'art', id: 'earth', label: 'Earth', at: 0.4}], link: '8 min 20 s'});
};
const SubBeat: React.FC<{c: Ctx; local: number; q: Record<string, any>}> = ({c, q}) => {
	const C = {title: Title, stat: Stat, relation: Relation}[q.kind as string] as React.FC<SP>;
	const n = q.kind === 'title' ? 0 : q.kind === 'stat' ? 1 : 2;
	return <C p={{...q, n, style: c.s.id, accent: c.p.accent, shift: (n * c.T) / 3}} proj={(c as any).proj} durF={Math.round((c.T / 3) * 30)} />;
};

// ── CONTINUOUS SHOT (user, Oct 28 2026: "long continuous shots, evolving animations, only switch shots when necessary") ──
// Several beats share ONE camera move across a world: each beat is a STATION, and instead of cutting, the camera glides to the
// next station (pan sideways · crane up · push through the frame) while the previous graphics stay on screen and slide away.
// One background, one captions track, a timeline ribbon of station marks and the style's motion VFX tie it together.
const TRAVEL = 1.1;                         // seconds of camera move at the end of each station
const BEATS_C: Record<string, React.FC<SP>> = {};    // filled below (title, stat, visuals, relation, action, list, compare, quote)

const Ribbon: React.FC<{c: Ctx; marks: string[]; q: number}> = ({c, marks, q}) => {
	const {s, W, H, u, t} = c;
	if (!marks.some(Boolean)) return null;
	const pal = s.pal, gap = W * (c.port ? 0.42 : 0.28), y = H * 0.045;
	const x0 = W / 2 - q * gap;
	const line = {signature: pal.line, grid: pal.ink, liquid: '#FFFFFF', paper: pal.acc2}[s.id];
	const dot = {signature: pal.acc, grid: pal.acc, liquid: pal.acc, paper: pal.acc}[s.id];
	return (
		<div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
			<svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible'}}>
				<line x1={x0 - gap} y1={y} x2={x0 + gap * marks.length} y2={y} stroke={line} strokeOpacity={s.id === 'liquid' ? 0.35 : 0.45} strokeWidth={(s.id === 'grid' ? 5 : 2.5) * u}
					strokeDasharray={s.id === 'paper' ? `${14 * u} ${10 * u}` : undefined} />
				<line x1={x0 - gap} y1={y} x2={x0 + q * gap} y2={y} stroke={dot} strokeWidth={(s.id === 'grid' ? 5 : 3) * u} />
				{marks.map((m, k) => {
					const x = x0 + k * gap, on = k <= Math.round(q);
					return <circle key={k} cx={x} cy={y} r={(on ? 9 : 6) * u} fill={on ? dot : 'none'} stroke={on ? dot : line} strokeWidth={2 * u} style={{filter: s.id === 'liquid' && on ? `drop-shadow(0 0 ${10 * u}px ${dot})` : undefined}} />;
				})}
			</svg>
			{marks.map((m, k) => {
				const x = x0 + k * gap, d = Math.abs(k - q);
				return m ? (
					<div key={k} style={{position: 'absolute', left: x, top: y + 16 * u, transform: `translateX(-50%) ${s.boil(t, 700 + k, 0.4)}`, opacity: Math.max(0.25, 1 - d * 0.45),
						...s.font(s.id === 'paper' ? 'hand' : 'label'), fontSize: (s.id === 'paper' ? 34 : 22) * u, color: k === Math.round(q) ? pal.acc : pal.mute, whiteSpace: 'nowrap',
						letterSpacing: s.id === 'signature' ? '0.25em' : 0}}>{s.cased(m)}</div>
				) : null;
			})}
		</div>
	);
};

// style VFX living in the world (parallax) + speed streaks while the camera travels
const Vfx: React.FC<{c: Ctx; q: number; speed: number; move: string}> = ({c, q, speed, move}) => {
	const {s, W, H, u, t} = c;
	const pal = s.pal;
	const N = 26, par = 0.55;
	const shiftX = move === 'pan' ? -q * W * par : 0, shiftY = move === 'crane' ? q * H * par : 0;
	const parts = Array.from({length: N}, (_, i) => {
		const bx = rnd(i * 3 + 1) * W * 1.4, by = rnd(i * 7 + 2) * H;
		let x = ((bx + shiftX + Math.sin(t * 0.4 + i) * 30 * u) % (W * 1.4) + W * 1.4) % (W * 1.4) - W * 0.2;
		let y = ((by + shiftY - t * (8 + rnd(i) * 22) * u) % H + H) % H;
		const r = (2 + rnd(i * 5) * 6) * u;
		if (s.id === 'signature') return <circle key={i} cx={x} cy={y} r={r * 0.6} fill={i % 5 ? '#FFFFFF' : pal.acc} opacity={0.08 + rnd(i * 11) * 0.12} />;
		if (s.id === 'grid') return i % 3 ? null : <rect key={i} x={x} y={y} width={r * 3} height={r * 3} fill={i % 2 ? pal.acc : pal.ink} opacity={0.07} />;
		if (s.id === 'liquid') return <circle key={i} cx={x} cy={y} r={r * 1.6} fill={[pal.acc, pal.acc2, pal.acc3, pal.acc4 || '#fff'][i % 4]} opacity={0.12 + rnd(i * 13) * 0.12} style={{filter: `blur(${r * 0.6}px)`}} />;
		return <rect key={i} x={x} y={y} width={r * 1.6} height={r * 2.4} fill={[pal.acc, pal.acc2, pal.acc3][i % 3]} opacity={0.18} transform={`rotate(${(Math.floor(t * 12) * 9 + i * 40) % 360} ${x} ${y})`} />;
	});
	const streaks = speed > 0.05 ? Array.from({length: s.id === 'paper' ? 7 : 14}, (_, i) => {
		const len = (120 + rnd(i * 9) * 260) * u * speed, a = (0.18 + rnd(i) * 0.25) * Math.min(1, speed) * (s.id === 'paper' || s.id === 'grid' ? 0.45 : 1);
		const col = {signature: '#FFFFFF', grid: pal.acc, liquid: pal.acc, paper: pal.acc2}[s.id];
		if (move === 'crane') {
			const x = rnd(i * 5 + 3) * W, y = ((rnd(i * 3) * H + t * 1400 * u) % (H * 1.2)) - H * 0.1;
			return <rect key={'s' + i} x={x} y={y} width={3 * u} height={len} fill={col} opacity={a} />;
		}
		if (move === 'push') {
			const ang = rnd(i * 4) * Math.PI * 2, r0 = (0.15 + rnd(i * 6) * 0.35) * Math.min(W, H);
			return <line key={'s' + i} x1={W / 2 + Math.cos(ang) * r0} y1={H / 2 + Math.sin(ang) * r0} x2={W / 2 + Math.cos(ang) * (r0 + len)} y2={H / 2 + Math.sin(ang) * (r0 + len)} stroke={col} strokeWidth={3 * u} opacity={a} />;
		}
		const y = rnd(i * 5 + 3) * H, x = W - ((rnd(i * 3) * W + t * 1600 * u) % (W * 1.3));
		return <rect key={'s' + i} x={x} y={y} width={len} height={3 * u} fill={col} opacity={a} />;
	}) : null;
	return (
		<svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}>
			{parts}
			{streaks}
		</svg>
	);
};

const Shot: React.FC<SP> = ({p, proj, durF}) => {
	const c = useCtx(p, proj, durF);
	const {s, t, W, H} = c;
	const beats: Record<string, any>[] = Array.isArray(p.beats) ? p.beats.filter((b: any) => b && BEATS_C[b.kind]) : [];
	const n = beats.length;
	if (!n) return <Frame c={c} n={+p.n || 0}>{null}</Frame>;
	const starts: number[] = [];
	let acc = 0;
	for (const b of beats) {
		starts.push(acc);
		acc += Math.max(1, +b.dur || 4);
	}
	let i = n - 1;
	for (let k = 0; k < n; k++) if (t < starts[k] + Math.max(1, +beats[k].dur || 4)) { i = k; break; }
	const end = starts[i] + Math.max(1, +beats[i].dur || 4);
	let q = i, speed = 0;
	if (i < n - 1 && t > end - TRAVEL) {
		const x = c01((t - (end - TRAVEL)) / TRAVEL);
		q = i + inOut(x);
		speed = 6 * x * (1 - x) * 1.0;                     // d(inOut)/dx peaks mid-move
	}
	const move = ['pan', 'crane', 'push'].includes(p.move) ? p.move : 'pan';
	const drift = s.motion.push ? 0 : 0.006;               // a slow continuous dolly so a long station never freezes
	const station = (k: number): React.CSSProperties => {
		const d = k - q;
		if (move === 'crane') return {transform: `translateY(${-d * H * 1.06}px)`};
		if (move === 'push') {
			const sc = d >= 0 ? 1 / (1 + d * 1.8) : 1 + -d * 2.4;
			return {transform: `scale(${sc})`, opacity: d < 0 ? Math.max(0, 1 + d * 1.6) : d > 1 ? 0 : 1 - Math.max(0, d - 0.35) * 1.4};
		}
		return {transform: `translateX(${(d * 1.06 - (t - starts[Math.max(0, Math.min(n - 1, k))]) * drift) * W}px)`};
	};
	const blur = move !== 'push' && speed > 0.15 ? Math.min(3, speed * 2.6) : 0;
	const cur = beats[i];
	const capCtx: Ctx = {...c, t: t - starts[i], p: {...cur, captions: p.captions, style: p.style}};
	const show = [i - 1, i, i + 1].filter((k) => k >= 0 && k < n);
	return (
		<AbsoluteFill>
			<Bg c={{...c, p: {...p}}} n={(+p.n || 0) + i} />
			<Vfx c={c} q={q} speed={speed} move={move} />
			<AbsoluteFill style={{filter: blur ? `blur(${blur}px)` : undefined}}>
				{show.map((k) => {
					// lead-in: a station's clock starts as the camera sets off toward it, so its headline/tags build DURING the move;
					// word-cued pictures, list rows, the character and its mouth are shifted by the same lead → still on their word
					const lead = k > 0 ? TRAVEL : 0;
					const sh = (v: any) => (v && v.at != null ? {...v, at: +v.at + lead} : v);
					const b0 = beats[k];
					const b = lead ? {...b0, visuals: (b0.visuals || []).map(sh), items: (b0.items || []).map((it: any) => ({...sh(it), visual: sh(it.visual)})),
						words: (b0.words || []).map((w: any) => ({...w, s: w.s + lead, e: w.e + lead})), at: (+b0.at || 0.1) + lead} : b0;
					const C = BEATS_C[b.kind];
					return (
						<AbsoluteFill key={k} style={station(k)}>
							<C p={{...b, style: p.style, accent: p.accent, brand: p.brand, n: (+p.n || 0) + k, inShot: true, shift: starts[k] - lead}} proj={proj} durF={Math.round((Math.max(1, +b.dur || 4) + lead) * 30)} />
						</AbsoluteFill>
					);
				})}
			</AbsoluteFill>
			<Ribbon c={c} marks={beats.map((b) => b.mark || '')} q={q} />
			<Captions c={capCtx} />
			<Trans c={c} n={+p.n || 0} />
		</AbsoluteFill>
	);
};

Object.assign(BEATS_C, {title: Title, stat: Stat, visuals: Visuals, relation: Relation, action: ActionBeat, list: List, compare: Compare, quote: Quote});

const F = (role: 'scene', dur: number, C: React.FC<SP>, label: string, icon: string, fields: any[]) => ({label, group: 'Motion Graphics', icon, dur, track: role, C, fields});
const styleF = {k: 'style', t: 'select' as const, label: 'Style', opts: STYLE_IDS as string[], d: 'signature'};
const common = [styleF, {k: 'accent', t: 'color' as const, label: 'Accent override', d: ''}, {k: 'n', t: 'num' as const, label: 'Beat #', min: 0, max: 999, d: 1},
	{k: 'visuals', t: 'json' as const, label: 'Visuals [{kind:art|icon|stat|text, id, label, at}]', d: []}, {k: 'words', t: 'json' as const, label: 'Spoken words [{w,s,e}] (captions)', d: []},
	{k: 'captions', t: 'bool' as const, label: 'Show captions', d: true}];

export const MG_SCENES = {
	'mg-title': F('scene', 5, Title, 'MG · Title', 'type', [{k: 'kicker', t: 'text', label: 'Kicker', d: 'Chapter one'}, {k: 'title', t: 'text', label: 'Title', d: 'The speed of light'}, {k: 'sub', t: 'text', label: 'Subtitle', d: ''}, ...common]),
	'mg-stat': F('scene', 5, Stat, 'MG · Big number', 'trending-up', [{k: 'kicker', t: 'text', label: 'Kicker', d: ''}, {k: 'value', t: 'num', label: 'Value', d: 299792}, {k: 'prefix', t: 'text', label: 'Prefix', d: ''}, {k: 'suffix', t: 'text', label: 'Suffix', d: ''}, {k: 'label', t: 'text', label: 'Label', d: 'kilometres per second'}, ...common]),
	'mg-visuals': F('scene', 5, Visuals, 'MG · Visuals (1–4)', 'grid', [{k: 'headline', t: 'text', label: 'Headline', d: ''}, ...common]),
	'mg-relation': F('scene', 6, Relation, 'MG · A → B', 'chain', [{k: 'headline', t: 'text', label: 'Headline', d: ''}, {k: 'link', t: 'text', label: 'Link label', d: ''}, ...common]),
	'mg-list': F('scene', 7, List, 'MG · List', 'layers', [{k: 'headline', t: 'text', label: 'Headline', d: ''}, {k: 'items', t: 'json', label: 'Items [{text, at, visual}]', d: [{text: 'First point'}, {text: 'Second point'}]}, ...common]),
	'mg-compare': F('scene', 6, Compare, 'MG · Compare', 'layers', [{k: 'headline', t: 'text', label: 'Headline', d: ''}, {k: 'a', t: 'text', label: 'Left title', d: 'Before'}, {k: 'aval', t: 'text', label: 'Left value', d: ''}, {k: 'b', t: 'text', label: 'Right title', d: 'After'}, {k: 'bval', t: 'text', label: 'Right value', d: ''}, ...common]),
	'mg-quote': F('scene', 6, Quote, 'MG · Quote', 'message', [{k: 'text', t: 'long', label: 'Quote', d: ''}, {k: 'by', t: 'text', label: 'By', d: ''}, ...common]),
	'mg-intro': F('scene', 3.4, Intro, 'MG · MIR MEDIA LABS intro', 'sparkle', [{k: 'title', t: 'text', label: 'Video title (under the logo)', d: ''}, styleF, common[1]]),
	'mg-action': F('scene', 6, ActionBeat, 'MG · Animated character', 'user', [{k: 'action', t: 'select', label: 'Action', opts: ACTION_NAMES, d: 'speech'}, {k: 'who', t: 'text', label: 'Who (tag)', d: ''},
		{k: 'headline', t: 'text', label: 'Headline', d: ''}, {k: 'figure', t: 'json', label: 'Figure {skin, hair, hairColor, outfit: suit|jersey|casual|dress|lab, color, number, accessory: tie|glasses|cap|crown|tophat|helmet, beard}', d: {outfit: 'suit', hair: 'side'}},
		{k: 'figure2', t: 'json', label: 'Second figure (handshake / chat)', d: null}, {k: 'at', t: 'num', label: 'Enters at (s)', min: 0, max: 30, step: 0.1, d: 0.1},
		{k: 'set', t: 'select', label: 'Set (place) — empty = plain stage', opts: ['', ...SET_NAMES], d: ''}, {k: 'shot', t: 'select', label: 'Camera shot', opts: ['wide', 'medium', 'close', 'xclose'], d: 'wide'},
		{k: 'mood', t: 'select', label: 'Mood', opts: ['', 'happy', 'surprised', 'angry', 'determined', 'sad', 'scared'], d: ''},
		{k: 'overlay', t: 'json', label: 'Overlay {type: timer|distance|score|gauge|chain|label, value, unit, label, a, b, av, bv, ratio, items, text, at}', d: null},
		{k: 'plate', t: 'media', label: 'AI-animated shot (replaces set + character)', accept: 'video', d: ''}, {k: 'fx', t: 'select', label: 'FX', opts: ['', ...FX_TYPES], d: ''}, {k: 'fxAt', t: 'num', label: 'FX at (s)', min: 0, max: 30, step: 0.1, d: 0.9}, ...common]),
	'mg-shot': F('scene', 15, Shot, 'MG · Continuous shot (beats as stations)', 'film', [{k: 'move', t: 'select', label: 'Camera move', opts: ['pan', 'crane', 'push'], d: 'pan'},
		{k: 'beats', t: 'json', label: 'Beats [{kind, dur, mark, …the beat props}]', d: []}, styleF, common[1], {k: 'n', t: 'num', label: 'First beat #', min: 0, max: 999, d: 1}, {k: 'captions', t: 'bool', label: 'Show captions', d: true}]),
	'mg-endcard': F('scene', 6, EndCard, 'MG · End card', 'star', [{k: 'title', t: 'text', label: 'Title', d: 'Thanks for watching'}, {k: 'line1', t: 'text', label: 'Line 1', d: 'Like · Subscribe'}, {k: 'line2', t: 'text', label: 'Line 2', d: 'Download the MIR MEDIA LABS app'}, styleF, common[1], common[2]]),
	'mg-diorama': F('scene', 20, Diorama, 'MG · Diorama (whole story)', 'film', [{k: 'beats', t: 'json', label: 'Beats [{t0, t1, line, station, pose, mood, camera, panel, sfx, fx, rings, cue}]', d: []},
		{k: 'words', t: 'json', label: 'Words [{w, s, e}] (absolute seconds)', d: []}, {k: 'offset', t: 'num', label: 'Clock offset (s)', min: -30, max: 30, step: .1, d: 0}, {k: 'captions', t: 'bool', label: 'Captions', d: true}]),
	'mg-demo': F('scene', 9, Demo, 'MG · Style demo', 'sparkle', [styleF, common[1], {k: 'zap', t: 'json', label: 'zap icon nodes', d: []}]),
};
