// MIR EXPLAINED component kit — shared primitives (stages, line-art car, callouts, panels, captions). All styling comes from theme.ts.
import React, {useLayoutEffect, useRef} from 'react';
import {AbsoluteFill, interpolate, random} from 'remotion';
import {Grain, Vignette} from '../promo/fx';
import {C, F, T, clamp, ramp} from './theme';
import {Figure} from './figures';

// ── the 2027 Roadster side profile in a 1600×900 space, traced from the Oct 15 2026 unveil side photo (ref/side.jpg).
// Mapping: photo wheel centres (305,330)/(615,328) → (520,640)/(1110,640), i.e. 590 units = 2,825 mm wheelbase.
export const CAR = {
	body: 'M350 668L344 626L368 584C440 562 505 542 568 526L853 469L1034 476C1120 490 1200 508 1258 522L1257 583L1234 617L1200 617A92 92 0 1 0 1030 682L602 682A92 92 0 1 0 432 668Z',
	glass: 'M882 480L1034 482L920 520Z',
	crease: 'M600 578L1252 548',
	door: 'M640 682L620 600L853 469',
	wing: 'M1100 470L1262 461L1266 473L1104 482ZM1150 478L1162 514M1222 469L1230 520',
	lightbar: 'M1258 526L1257 560',
	wheels: [520, 1110],
	wheelY: 640,
	tireR: 72,
	rimR: 48,
	tank: {x: 900, y: 590, w: 110, h: 44},
	nozzleX: 1252,
	nozzles: [588, 596, 604, 612],
};

// MIR ICONS (24×24 line icons, from MirIcons/icons.py)
export const ICON = {
	heart: 'M12 20C12 20 3.5 14.8 3.5 9.2C3.5 6.6 5.5 4.5 8 4.5C9.7 4.5 11.2 5.4 12 6.8C12.8 5.4 14.3 4.5 16 4.5C18.5 4.5 20.5 6.6 20.5 9.2C20.5 14.8 12 20 12 20Z',
	bell: 'M6 16V11C6 7.7 8.7 5 12 5C15.3 5 18 7.7 18 11V16L19.5 18H4.5Z M10 20.5C10.4 21.3 11.1 21.7 12 21.7C12.9 21.7 13.6 21.3 14 20.5',
	download: 'M12 4V15 M7 10L12 15L17 10 M5 20H19',
	play: 'M8 5L19 12L8 19Z',
};
export const Icon: React.FC<{d: string; size: number; color: string; fill?: string}> = ({d, size, color, fill = 'none'}) => (
	<svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

// ── frame guard (Oct 18: generated titles/labels ran off-frame, e.g. the brand title at x=900 in one 92 px line).
// Fit = a box of w×h px: text wraps inside w, and if it still overflows (a long word, too many lines/rows) the content
// is scaled down until it fits. Measured every frame before paint, so a render can never show clipped text.
// nowrap=true keeps one line and only scales. Every piece of generated text in a scene goes through Fit.
export const Fit: React.FC<{w: number; h?: number; nowrap?: boolean; align?: 'left' | 'center' | 'right'; style?: React.CSSProperties; children?: React.ReactNode}> =
	({w, h, nowrap = false, align = 'left', style, children}) => {
	const ref = useRef<HTMLDivElement>(null);
	useLayoutEffect(() => {
		const el = ref.current;
		if (!el) return;
		el.style.transform = '';
		const s = Math.min(1, w / Math.max(1, el.scrollWidth), h ? h / Math.max(1, el.scrollHeight) : 1);
		if (s < 0.999) el.style.transform = `scale(${s})`;
	});
	const origin = align === 'center' ? '50% 0' : align === 'right' ? '100% 0' : '0 0';
	return (
		<div style={{width: w, textAlign: align}}>
			<div ref={ref} style={{...style, width: nowrap ? 'max-content' : w, maxWidth: nowrap ? undefined : w, whiteSpace: nowrap ? 'nowrap' : 'normal',
				overflowWrap: 'break-word', transformOrigin: origin, marginLeft: nowrap && align === 'center' ? 'auto' : undefined, marginRight: nowrap && align === 'center' ? 'auto' : undefined,
				...(nowrap && align === 'right' ? {marginLeft: 'auto'} : {})}}>{children}</div>
		</div>
	);
};

// SVG text can't be measured before paint the same way: estimate its width and shrink/clamp it into [x0, x1].
export const svgFit = (text: string, x: number, size: number, room: number, x0 = 40, x1 = 1560, em = 0.56) => {
	const est = Math.max(1, String(text || '').length * size * em);
	const fs = Math.min(size, size * Math.min(room, x1 - x0) / est);
	const half = (String(text || '').length * fs * em) / 2;
	return {x: Math.min(x1 - half, Math.max(x0 + half, x)), fontSize: fs};
};

// ── STUDIO mode: charcoal showroom with spotlight, vignette, grain
export const StudioStage: React.FC<{children?: React.ReactNode; t?: number}> = ({children, t}) => (
	<AbsoluteFill style={{background: `radial-gradient(ellipse 70% 60% at 62% 18%, ${C.studio1} 0%, #141417 55%, ${C.studio0} 100%)`}}>
		{children}
		<AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(5,5,7,.92) 0%, rgba(5,5,7,.55) 34%, transparent 62%)'}} />
		{t !== undefined && <Streaks t={t} />}
		<Vignette strength={0.7} />
		<Grain opacity={0.07} />
	</AbsoluteFill>
);

// B signature: faint light streaks drifting across the showroom (speed without motion blur on the car)
export const Streaks: React.FC<{t: number}> = ({t}) => (
	<svg width="100%" height="100%" viewBox="0 0 1920 1080" style={{position: 'absolute', mixBlendMode: 'screen'}}>
		<defs><linearGradient id="stk" x1="0" x2="1"><stop offset="0" stopColor="#fff" stopOpacity="0" /><stop offset=".5" stopColor="#fff" stopOpacity=".55" /><stop offset="1" stopColor="#fff" stopOpacity="0" /></linearGradient></defs>
		{[[300, 0.0, 520], [470, 0.37, 380], [610, 0.71, 640], [180, 0.53, 300]].map(([y, ph, w], i) => {
			const x = 2100 - (((t * 0.32 + ph) % 1) * 2900);
			return <rect key={i} x={x} y={y} width={w} height={i === 2 ? 2 : 1.5} fill="url(#stk)" opacity={0.18} />;
		})}
	</svg>
);

// ── schematic stage (B language): charcoal showroom, faint drafting grid, light streaks, vignette + grain
export const HudStage: React.FC<{t: number; children?: React.ReactNode}> = ({t, children}) => (
	<AbsoluteFill style={{background: `radial-gradient(ellipse 70% 60% at 58% 22%, ${C.hudBg1} 0%, #141417 55%, ${C.hudBg0} 100%)`}}>
		<svg width="100%" height="100%" viewBox="0 0 1600 900" style={{position: 'absolute'}}>
			<defs>
				<pattern id="hg2" width="200" height="200" patternUnits="userSpaceOnUse"><path d="M200 0H0V200" fill="none" stroke="#fff" strokeOpacity=".035" /></pattern>
				<linearGradient id="hfloor" x1="0" x2="1"><stop offset="0" stopColor="#fff" stopOpacity="0" /><stop offset=".5" stopColor="#fff" stopOpacity=".16" /><stop offset="1" stopColor="#fff" stopOpacity="0" /></linearGradient>
			</defs>
			<rect width="1600" height="900" fill="url(#hg2)" />
			<rect x="0" y="719" width="1600" height="1.5" fill="url(#hfloor)" />
		</svg>
		<Streaks t={t} />
		{children}
		<Vignette strength={0.7} />
		<Grain opacity={0.07} />
	</AbsoluteFill>
);

// ── glowing line-art car that draws on (draw 0→1), with tank highlight + thruster plumes
export const CarLines: React.FC<{t: number; draw: number; tank?: number; plume?: number; dims?: number; noWing?: boolean}> = ({t, draw, tank = 0, plume = 0, dims = 0, noWing = false}) => {
	const dash = (p: number) => ({pathLength: 1, strokeDasharray: 1, strokeDashoffset: 1 - p});
	const flick = 0.85 + random(`pl${Math.floor(t * 30)}`) * 0.3;
	const pulse = (t * 0.8) % 1;
	return (
		<svg width="100%" height="100%" viewBox="0 0 1600 900" style={{position: 'absolute'}}>
			<defs>
				<filter id="cglow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
				<linearGradient id="cplume" x1="0" x2="1"><stop offset="0" stopColor="#FFE3A3" /><stop offset=".35" stopColor={C.amber} stopOpacity=".7" /><stop offset="1" stopColor={C.amber} stopOpacity="0" /></linearGradient>
			</defs>
			<g filter="url(#cglow)" fill="none" stroke={C.cyan} strokeWidth={3} strokeLinejoin="round">
				<path d={CAR.body} fill={C.cyan} fillOpacity={0.05 * draw} {...dash(draw)} />
				<path d={CAR.glass} strokeWidth={2} {...dash(ramp(draw, 0.3, 0.5))} />
				<path d={CAR.crease} strokeWidth={1.5} strokeOpacity={0.7} {...dash(ramp(draw, 0.35, 0.5))} />
				<path d={CAR.door} strokeWidth={1.5} strokeOpacity={0.7} {...dash(ramp(draw, 0.4, 0.5))} />
				{!noWing && <path d={CAR.wing} strokeWidth={2} {...dash(ramp(draw, 0.45, 0.5))} />}
				{CAR.wheels.map((x) => <circle key={x} cx={x} cy={CAR.wheelY} r={CAR.tireR} {...dash(ramp(draw, 0.3, 0.6))} />)}
				{CAR.wheels.map((x) => <circle key={'r' + x} cx={x} cy={CAR.wheelY} r={CAR.rimR} strokeWidth={1.5} {...dash(ramp(draw, 0.5, 0.5))} />)}
			</g>
			<path d={CAR.lightbar} stroke={C.red} strokeWidth={4} strokeLinecap="round" opacity={ramp(draw, 0.8, 0.2)} />
			<rect x="620" y="650" width="400" height="18" rx="4" fill="none" stroke={C.cyan} strokeOpacity={0.6 * ramp(draw, 0.7, 0.3)} strokeDasharray="8 6" />
			{tank > 0 && (
				<g opacity={tank}>
					<rect x={CAR.tank.x} y={CAR.tank.y} width={CAR.tank.w} height={CAR.tank.h} rx="12" fill={C.amber} fillOpacity=".16" stroke={C.amber} strokeWidth="2.5" />
					<circle cx={CAR.tank.x + CAR.tank.w / 2} cy={CAR.tank.y + CAR.tank.h / 2} r={10 + pulse * 26} fill="none" stroke={C.amber} strokeWidth="2" opacity={1 - pulse} />
				</g>
			)}
			{plume > 0 && CAR.nozzles.map((y, i) => (
				<polygon key={y} points={`${CAR.nozzleX},${y - 5} ${CAR.nozzleX},${y + 5} ${CAR.nozzleX + (230 + i * 14) * plume * flick},${y + (i - 1.5) * 9}`} fill="url(#cplume)" opacity={plume} />
			))}
			{plume > 0 && CAR.nozzles.map((y) => <circle key={'n' + y} cx={CAR.nozzleX} cy={y} r={3.5} fill={C.amber} opacity={plume} />)}
			{dims > 0 && (
				<g opacity={dims}>
					<path d="M520 772H1110M520 758V786M1110 758V786" stroke={C.cyan} strokeOpacity=".6" strokeWidth="1.5" />
					<rect x="745" y="756" width="140" height="32" fill={C.hudBg0} />
					<text x="815" y="780" textAnchor="middle" fontFamily={F.mono} fontSize={T.mono} fill={C.cyan}>2,825 mm</text>
				</g>
			)}
		</svg>
	);
};

// ── leader-line callout in the 1600×900 space; p = 0→1 reveal
export const Callout: React.FC<{p: number; from: [number, number]; elbow: [number, number]; end: [number, number]; title: string; sub: string; color?: string; align?: 'start' | 'end'}> = ({p, from, elbow, end, title, sub, color = C.ink, align = 'start'}) => {
	const line = Math.min(1, p * 1.6);
	const text = ramp(p, 0.55, 0.45);
	const dx = align === 'start' ? 12 : -12;
	const room = align === 'start' ? 1580 - end[0] : end[0] - 20;            // never past the frame edge it points at
	const ft = svgFit(title, 0, 36, room), fsub = svgFit(sub, 0, T.mono, room, 40, 1560, 0.62);
	return (
		<svg width="100%" height="100%" viewBox="0 0 1600 900" style={{position: 'absolute'}}>
			<path d={`M${from[0]} ${from[1]}L${elbow[0]} ${elbow[1]}L${end[0]} ${end[1]}`} fill="none" stroke="#E8F4FF" strokeOpacity=".8" strokeWidth="1.5" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - line} />
			<circle cx={from[0]} cy={from[1]} r={5 * Math.min(1, p * 4)} fill={color} />
			<g opacity={text} transform={`translate(${(1 - text) * (align === 'start' ? -10 : 10)} 0)`}>
				<text x={end[0] + dx} y={end[1] - 8} textAnchor={align} fontFamily={F.head} fontWeight={700} fontSize={ft.fontSize} fill={color}>{title}</text>
				<text x={end[0] + dx} y={end[1] + 28} textAnchor={align} fontFamily={F.mono} fontSize={fsub.fontSize} fill={C.cyanSoft}>{sub}</text>
			</g>
		</svg>
	);
};

// ── HUD spec panel: rows type on at their own times
export const SpecPanel: React.FC<{t: number; at: number; rows: {k: string; v: string; at: number; hi?: boolean}[]}> = ({t, at, rows}) => {
	const o = ramp(t, at, 0.5);
	return (
		<div style={{position: 'absolute', right: 116, top: 96, width: 390, padding: '18px 28px', borderRadius: 12, opacity: o,
			transform: `translateY(${(1 - o) * 16}px)`, background: 'rgba(12,12,14,.72)', border: `1px solid rgba(255,255,255,.18)`, fontFamily: F.mono, fontSize: 28}}>
			{rows.map((r) => {
				const p = ramp(t, r.at, 0.35);
				const chars = Math.round(r.v.length * p);
				return (
					<div key={r.k} style={{display: 'flex', justifyContent: 'space-between', padding: '9px 0', opacity: 0.35 + 0.65 * Math.min(1, p * 3)}}>
						<span style={{color: C.hudLabel}}>{r.k}</span>
						<span style={{color: r.hi ? C.amber : C.ink}}>{r.v.slice(0, chars) || ' '}</span>
					</div>
				);
			})}
		</div>
	);
};

// ── chapter tag + headline (both modes)
export const Headline: React.FC<{t: number; at: number; tag: string; title: string}> = ({t, at, tag, title}) => {
	const a = ramp(t, at, 0.6);
	const b = ramp(t, at + 0.15, 0.7);
	return (
		<div style={{position: 'absolute', left: 116, top: 96}}>
			<div style={{fontFamily: F.mono, fontSize: 30, letterSpacing: 5, color: C.amber, opacity: a, transform: `translateX(${(1 - a) * -20}px)`}}>{tag}</div>
			<div style={{fontFamily: F.head, fontWeight: 600, fontSize: 96, color: C.ink, marginTop: 6, opacity: b, transform: `translateY(${(1 - b) * 24}px)`}}>{title}</div>
		</div>
	);
};

// ── giant thin count-up numeral with amber rule + label
export const BigNumber: React.FC<{t: number; at: number; value: number; decimals: number; unit: string; label: string; sub?: string; subAt?: number; plain?: boolean; fig?: string | null}> = ({t, at, value, decimals, unit, label, sub, subAt = 0, plain = false, fig = null}) => {
	const p = ramp(t, at, 2.2, (x) => 1 - Math.pow(1 - x, 3));
	const o = ramp(t, at, 0.4);
	const s = sub ? ramp(t, subAt, 0.6) : 0;
	return (
		<div style={{position: 'absolute', left: 110, top: 120, opacity: o}}>
			<Fit w={1690} nowrap style={{fontFamily: F.num, fontWeight: 200, fontSize: 250, lineHeight: 1, letterSpacing: -8, color: '#fff'}}>
				{plain ? Math.round(value - 11 * (1 - p)) : (value * p).toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals})}<span style={{fontSize: 130, color: C.quiet, marginLeft: 18, letterSpacing: 0}}>{unit}</span>
			</Fit>
			<div style={{position: 'relative', height: 5, width: 150 * ramp(t, at + 0.3, 0.8), background: C.amber, margin: '34px 0 30px 10px', boxShadow: `0 0 18px ${C.amber}`}}>
				<div style={{position: 'absolute', top: -2, left: -400 + 950 * ramp(t, at + 0.4, 1.2), width: 260, height: 9, borderRadius: 9, background: 'radial-gradient(ellipse at center, rgba(255,226,170,.95) 0%, rgba(255,181,71,.35) 40%, transparent 70%)', opacity: 1 - ramp(t, at + 1.3, 0.5)}} />
			</div>
			<div style={{marginLeft: 10}}><Fit w={1680} h={96} style={{fontFamily: F.head, fontWeight: 600, fontSize: 38, letterSpacing: 9, color: C.amber}}>{label}</Fit></div>
			{sub && <div style={{marginLeft: 10, marginTop: 16, opacity: s, transform: `translateY(${(1 - s) * 12}px)`}}><Fit w={1680} h={104} style={{fontFamily: F.head, fontWeight: 300, fontSize: 40, color: '#d4d8de'}}>{sub}</Fit></div>}
			{fig && <div style={{display: 'flex', gap: 18, marginLeft: 6, marginTop: 34}}>{Array.from({length: 8}, (_, i) => {
				const lit = p * 8 - i;                 // the row fills up with the count-up
				return <Figure key={i} id={fig} size={96} t={t + i * 0.37} draw={Math.max(0, Math.min(1, ramp(t, at + 0.2 + i * 0.09, 0.7, (x) => x)))}
					color={lit > 0.5 ? C.ink : 'rgba(230,235,240,.32)'} accent={lit > 0.5 ? C.amber : 'rgba(255,181,71,.3)'} stroke={3} />;
			})}</div>}
		</div>
	);
};

// ── karaoke captions: words light up across each narration line (length-weighted timing)
export type VoLine = {start: number; dur: number; text: string};
export const Captions: React.FC<{t: number; lines: VoLine[]}> = ({t, lines}) => {
	const l = lines.find((x) => t >= x.start - 0.1 && t <= x.start + x.dur + 0.25);
	if (!l) return null;
	const words = l.text.split(' ');
	const total = words.reduce((n, w) => n + w.length + 1, 0);
	let acc = 0;
	const timed = words.map((w) => {
		const at = l.start + (acc / total) * l.dur * 0.94;
		acc += w.length + 1;
		return {w, at};
	});
	// show short chunks (≤ 7 words, broken after punctuation when possible) so a caption never runs past one line
	const chunks: {w: string; at: number}[][] = [[]];
	timed.forEach((x) => {
		const cur = chunks[chunks.length - 1];
		cur.push(x);
		if (cur.length >= 7 || (cur.length >= 3 && /[.,?!]$/.test(x.w))) chunks.push([]);
	});
	const live = chunks.filter((c) => c.length);
	const chunk = [...live].reverse().find((c) => t >= c[0].at - 0.05) || live[0];
	const o = interpolate(t, [l.start - 0.1, l.start + 0.1, l.start + l.dur, l.start + l.dur + 0.25], [0, 1, 1, 0], clamp);
	return (
		<div style={{position: 'absolute', left: 110, right: 110, bottom: 74, opacity: o}}>
			<Fit w={1700} nowrap align="center" style={{display: 'flex', gap: 14, fontFamily: F.head, fontSize: T.caption + 6, textShadow: '0 2px 18px rgba(0,0,0,.85)'}}>
				{chunk.map((x, i) => (
					<span key={i} style={{color: t >= x.at ? C.ink : 'rgba(242,246,250,.38)'}}>{x.w}</span>
				))}
			</Fit>
		</div>
	);
};

// ── source credit lower third
export const Credit: React.FC<{t: number; at: number; dur: number; text: string}> = ({t, at, dur, text}) => {
	const o = interpolate(t, [at, at + 0.4, at + dur - 0.4, at + dur], [0, 1, 1, 0], clamp);
	return <div style={{position: 'absolute', left: 116, bottom: 168, opacity: o, fontFamily: F.mono, fontSize: 22, letterSpacing: 2, color: C.hudLabel}}>{text}</div>;
};
