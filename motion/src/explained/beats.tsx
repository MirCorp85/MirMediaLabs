// Signature beat visuals. Each takes local time t (s since the beat started) + the beat's duration.
// Data comes from the episode JSON; geometry for the car comes from CAR (traced from the unveil photo).
import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile} from 'remotion';
import {FlaskLogo} from '../promo/LogoOpen';
import {Vignette} from '../promo/fx';
import {Figure, SvgFigure, figFor} from './figures';
import {C, F, T, clamp, ramp} from './theme';
import {BigNumber, CAR, Callout, CarLines, Fit, HudStage, ICON, Icon, SpecPanel, StudioStage, svgFit} from './kit';

// hd = the beat's chapter header ("03 — CHAPTER TITLE" + title); legacy = the hand-built Roadster episode. Generated
// episodes never fall back to Roadster art/labels — only legacy does.
export type BeatProps = {t: number; dur: number; b: any; asset: (n?: string) => string | null; hd?: {tag: string; title: string}; legacy?: boolean};
const S = (s: string) => s;   // keeps literal strings greppable

// ── studio plate: H3 video if present, else Qwen still with a slow push
export const PlateMedia: React.FC<{t: number; dur: number; src: string | null; push?: number; shift?: number}> = ({t, dur, src, push = 0.05, shift = 150}) => {
	if (!src) return null;
	if (/(^|\/)pl_[^/]*$/.test(src)) { push = 0; shift = 0; }   // Nov 4 2026: screen recordings fill the frame exactly (no Ken Burns offset/crop)
	const scale = 1 + push * Math.min(1, t / Math.max(1, dur));
	const isVid = /\.(mp4|webm|mov)$/i.test(src);
	const smooth = /\.s\d+p?\.mp4$/i.test(src);           // explained_build smooth_plate(): 30 fps, as long as the beat
	return (
		<AbsoluteFill style={{transform: `translateX(${shift}px) scale(${scale})`, transformOrigin: '80% 60%'}}>
			{isVid
				? <OffthreadVideo src={src} muted playbackRate={smooth ? 1 : Math.max(0.45, Math.min(1, 6 / Math.max(1, dur)))} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
				: <Img src={src} style={{width: '100%', height: '100%', objectFit: 'cover'}} />}
		</AbsoluteFill>
	);
};

// a plate that never got made (H3 failed) shows the still it was made from — never the empty studio (Oct 24, 1:22 blank)
const plateSrc = (asset: BeatProps['asset'], name?: string) =>
	asset(name) || (name && !name.includes('.') ? asset(name + '.mp4') || asset(name + '.png') : null) ||
	(name && /^pl_/.test(name) ? asset(name.replace(/^pl_/, 'st_').replace(/(\.s\d+p?)?\.mp4$/, '') + '.png') : null) || asset('studio.png');

// Nov 4 2026: recorded screen demos (pl_*) are UI, not cinematic plates — keep them bright and readable:
// no left darkening, a light vignette, only a soft bottom fade so captions stay legible.
export const isScreenPlate = (name?: string) => !!name && /^pl_/.test(name);
export const ScreenStage: React.FC<{children?: React.ReactNode}> = ({children}) => (
	<AbsoluteFill style={{background: '#0b0b0e'}}>
		{children}
		<AbsoluteFill style={{background: 'linear-gradient(180deg, transparent 72%, rgba(5,5,7,.55) 100%)'}} />
		<Vignette strength={0.18} />
	</AbsoluteFill>
);
export const Plate: React.FC<BeatProps> = ({t, dur, b, asset}) => isScreenPlate(b.plate)
	? <ScreenStage><PlateMedia t={t} dur={dur} src={plateSrc(asset, b.plate)} /></ScreenStage>
	: <StudioStage t={t}><PlateMedia t={t} dur={dur} src={plateSrc(asset, b.plate)} /></StudioStage>;

export const BigNum: React.FC<BeatProps> = (p) => (
	<>
		<StudioStage t={p.t}><PlateMedia t={p.t} dur={p.dur} src={plateSrc(p.asset, p.b.plate)} /></StudioStage>
		<BigNumber t={p.t} at={0.3} value={p.b.v.value} decimals={p.b.v.decimals} unit={p.b.v.unit} label={p.b.v.label} sub={p.b.v.sub} subAt={1.6} plain={p.b.v.plain}
				fig={p.b.v.fig ?? figFor(`${p.b.v.unit} ${p.b.v.label} ${p.b.v.sub || ''}`, 'chart')} />
	</>
);

// ── real photo with an on-screen credit (editorial use)
export const Photo: React.FC<BeatProps> = ({t, dur, b, asset}) => {
	const src = asset(b.photo);
	const o = ramp(t, 0.6, 0.5);
	return (
		<AbsoluteFill style={{background: '#000'}}>
			{src && <Img src={src} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${1.02 + 0.06 * t / dur})`}} />}
			<AbsoluteFill style={{background: 'linear-gradient(180deg, transparent 55%, rgba(0,0,0,.75) 100%)'}} />
			<div style={{position: 'absolute', left: 116, top: 96, opacity: o}}><Fit w={1500} nowrap style={{fontFamily: F.mono, fontSize: 22, letterSpacing: 3, color: C.ink, background: 'rgba(0,0,0,.45)', padding: '8px 14px', borderRadius: 6}}>{b.v.credit}</Fit></div>
		</AbsoluteFill>
	);
};

// ── brand sting: flask + series + episode title
export const Brand: React.FC<BeatProps & {title: string; series: string}> = ({t, title, series}) => {
	const a = ramp(t, 0.1, 1.2, (x) => x);
	const txt = ramp(t, 0.7, 0.6);
	const out = 1 - ramp(t, 2.7, 0.5);
	return (
		<AbsoluteFill style={{background: `radial-gradient(ellipse 60% 60% at 50% 45%, #1b1b20 0%, ${C.studio0} 100%)`, opacity: out}}>
			<div style={{position: 'absolute', left: 110, right: 110, top: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 40}}>
				<div style={{width: 300, height: 300, flex: 'none'}}><FlaskLogo draw={a} ring={ramp(t, 0.6, 0.8)} bubbles={ramp(t, 0.9, 0.6)} glow={0.5 * txt} spin={t * 0.05} /></div>
				<div style={{opacity: txt, transform: `translateX(${(1 - txt) * -24}px)`, flex: 'none'}}>
					<Fit w={1300} nowrap style={{fontFamily: F.mono, fontSize: 30, letterSpacing: 10, color: C.cyan}}>{series}</Fit>
					<div style={{height: 4, width: 420 * txt, background: C.amber, margin: '20px 0'}} />
					<Fit w={1300} h={210} style={{fontFamily: F.head, fontWeight: 600, fontSize: 92, lineHeight: 1.08, color: C.ink, width: 'fit-content'}}>{title}</Fit>
				</div>
			</div>
		</AbsoluteFill>
	);
};

// ── chapter card (B, studio): dimmed hero plate, giant thin numeral, amber rule, title
export const Chapter: React.FC<BeatProps & {n: number; title: string; of?: number}> = ({t, dur, b, asset, n, title, of = 0}) => {
	const num = ramp(t, 0.05, 0.7);
	const rule = ramp(t, 0.35, 0.6);
	const txt = ramp(t, 0.5, 0.6);
	const out = 1 - ramp(t, dur - 0.45, 0.4);
	return (
		<>
			<StudioStage t={t}>
				<AbsoluteFill style={{filter: `brightness(${0.62 - 0.12 * ramp(t, 0, dur)}) blur(${2 * (1 - num)}px)`}}><PlateMedia t={t} dur={dur} src={plateSrc(asset, b.plate)} push={0.04} /></AbsoluteFill>
			</StudioStage>
			<AbsoluteFill style={{opacity: out}}>
				<div style={{position: 'absolute', left: 110, top: 230, fontFamily: F.num, fontWeight: 200, fontSize: 340, lineHeight: 1, color: '#fff', letterSpacing: -12, opacity: num, transform: `translateY(${(1 - num) * 30}px)`}}>{String(n).padStart(2, '0')}</div>
				<div style={{position: 'absolute', left: 540, top: 236, opacity: 0.95, filter: 'drop-shadow(0 0 14px rgba(255,181,71,.25))'}}>
					<Figure id={b.v.fig ?? figFor(title, null) ?? figFor(b.cap || '', 'chart')} size={360} t={t} draw={ramp(t, 0.25, 1.5, (x) => x)} stroke={1.5} />
				</div>
				<div style={{position: 'absolute', left: 124, top: 600, height: 5, width: 180 * rule, background: C.amber, boxShadow: `0 0 18px ${C.amber}`}} />
				<div style={{position: 'absolute', left: 124, top: 640, opacity: txt, transform: `translateX(${(1 - txt) * -20}px)`}}>
											<div style={{fontFamily: F.mono, fontSize: 28, letterSpacing: 8, color: C.amber}}>CHAPTER {n}{of ? ` OF ${of}` : ''}</div>
						<div style={{marginTop: 8}}><Fit w={1680} h={225} style={{fontFamily: F.head, fontWeight: 600, fontSize: 96, lineHeight: 1.05, color: C.ink}}>{title}</Fit></div>
				</div>
			</AbsoluteFill>
		</>
	);
};

// hero drawing (Oct 18): every chart/table/list scene gets a big line drawing of its subject, drawing itself on in the
// empty top-right corner and then idling (fans spin, globe turns…). Subject = the scene's own title/words.
export const Hero: React.FC<{t: number; title: string; text: string; fallback?: string; fig?: string}> = ({t, title, text, fallback = 'chart', fig}) => {
	const f = fig || (figFor(title, null) ?? figFor(text, fallback));   // v.fig = the editor's Drawing pick           // the scene's title names its subject best
	return f ? <div style={{position: 'absolute', right: 120, top: 70, filter: 'drop-shadow(0 0 18px rgba(255,181,71,.18))', opacity: 0.92}}>
		<Figure id={f} size={250} t={t} draw={ramp(t, 0.3, 1.6, (x) => x)} stroke={1.6} />
	</div> : null;
};

const Head: React.FC<{t: number; tag: string; title: string; hero?: string; fig?: string}> = ({t, tag, title, hero, fig}) => {
	const a = ramp(t, 0.2, 0.6);
	return (
		<>{hero !== undefined && <Hero t={t} title={title} text={hero} fig={fig} />}
		<div style={{position: 'absolute', left: 116, top: 96, opacity: a, transform: `translateY(${(1 - a) * 16}px)`}}>
			<Fit w={hero !== undefined ? 1380 : 1690} nowrap style={{fontFamily: F.mono, fontSize: 28, letterSpacing: 6, color: C.amber}}>{tag}</Fit>
			<div style={{marginTop: 4}}><Fit w={hero !== undefined ? 1380 : 1690} h={176} style={{fontFamily: F.head, fontWeight: 600, fontSize: 80, lineHeight: 1.05, color: C.ink}}>{title}</Fit></div>
		</div></>
	);
};

const SVG: React.FC<{children: React.ReactNode}> = ({children}) => (
	<svg width="100%" height="100%" viewBox="0 0 1600 900" style={{position: 'absolute'}}>{children}</svg>
);

// ── the delivery date that kept sliding right
const SLIPS: [number, string][] = [[2020, 'PROMISED 2020'], [2022, '2022'], [2023, '2023'], [2024, '2024'], [2025, '2025'], [2026.25, 'APR 2026'], [2026.75, 'OCT 1 · RAIN'], [2026.79, 'OCT 15 UNVEIL'], [2028, 'PRODUCTION 2028']];
export const Timeline: React.FC<BeatProps> = (props) => (props.b?.v?.events || !props.legacy ? <EventsTimeline {...props} /> : <RoadsterTimeline {...props} />);

// generic: events [{at: number, label, kind: past|miss|now|future}] revealed left→right on an even-spaced axis
const KIND_COL: Record<string, string> = {past: C.cyan, miss: C.red, now: C.amber, future: C.cyanSoft, claim: C.hudLabel};
export const EventsTimeline: React.FC<BeatProps> = ({t, dur, b, hd}) => {
	// 'at' may be a year (2022) or text ("Dec 2024", "Day 3"): numeric → true-scale axis, otherwise even spacing in script order
	const raw: {at: any; label: string; kind?: string; sub?: string}[] = b.v.events || [];
	const numeric = raw.length > 0 && raw.every((e) => e.at !== '' && Number.isFinite(Number(e.at)));
	const ev: any[] = numeric ? raw.map((e) => ({...e, at: Number(e.at)})).sort((a, z) => a.at - z.at) : raw.map((e, i) => ({...e, at: i, tick: String(e.at ?? '')}));
	if (!ev.length) return <HudStage t={t} />;
	const lo = Math.floor(ev[0].at), hi = numeric ? Math.ceil(ev[ev.length - 1].at + 0.01) : ev.length - 1;
	const span = Math.max(1, hi - lo);
	const X = (v: number) => 170 + ((v - lo) / span) * 1260;
	const step = span <= 14 ? 1 : Math.ceil(span / 12);
	const ticks: [number, string][] = numeric ? Array.from({length: Math.floor(span / step) + 1}, (_, i) => [lo + i * step, String(lo + i * step)] as [number, string]) : ev.map((e) => [e.at, e.tick] as [number, string]);
	const shown = Math.min(ev.length, 1 + Math.floor(ramp(t, 0.6, dur * 0.8, (x) => x) * (ev.length - 1) + 0.0001));
	return (
		<HudStage t={t}>
			<Head t={t} tag={b.v.tag || hd?.tag || ''} title={b.v.title || hd?.title || ''} hero={(b.v.events || []).map((e: any) => e.label).join(' ') + ' ' + (b.cap || '')} fig={(b as any)?.v?.fig} />
			<SVG>
				<path d={`M${X(lo)} 560H${X(hi)}`} stroke={C.cyan} strokeOpacity=".7" strokeWidth="2" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ramp(t, 0, 0.8)} />
				{ticks.map(([y, lbl], i) => (
					<g key={i} opacity={ramp(t, 0.2 + i * 0.04, 0.3)}>
						<path d={`M${X(y)} 552V568`} stroke={C.cyan} strokeOpacity=".7" />
													<text x={X(y)} y="600" textAnchor="middle" fontFamily={F.mono} fontSize={svgFit(lbl, X(y), 22, Math.max(60, 1260 / Math.max(1, ticks.length - 1) - 8), 40, 1560, 0.62).fontSize} fill={C.hudLabel}>{lbl}</text>
						</g>
					))}
					{shown > 1 && <path d={`M${X(ev[0].at)} 560H${X(ev[shown - 1].at)}`} stroke={C.amber} strokeWidth="3" strokeOpacity=".75" />}
					{shown > 1 && <circle cx={X(ev[0].at) + (X(ev[shown - 1].at) - X(ev[0].at)) * ((t * 0.45) % 1)} cy="560" r="5" fill={C.amber} opacity={0.9} />}
					{ev.slice(0, shown).map((e, i) => {
						const last = i === shown - 1;
						const side = ev.map((z, j) => j).filter((j) => j !== i && j % 2 === i % 2).map((j) => Math.abs(X(ev[j].at) - X(e.at)));
						const room = side.length ? Math.min(...side) - 16 : 1520;
						const base = last ? 30 : 24;
						const fid = figFor(`${e.label} ${e.sub || ''}`);
						// crowded: wrap onto two balanced lines before shrinking, so labels stay readable
						let lines: string[] = [String(e.label || '')];
						if (svgFit(lines[0], 0, base, room).fontSize < base * 0.75 && lines[0].includes(' ')) {
							const w = lines[0].split(' ');
							let k = 1, best = 1e9;
							for (let j = 1; j < w.length; j++) { const d = Math.abs(w.slice(0, j).join(' ').length - w.slice(j).join(' ').length); if (d < best) { best = d; k = j; } }
							lines = [w.slice(0, k).join(' '), w.slice(k).join(' ')];
						}
						const longest = lines.reduce((m, l) => (l.length > m.length ? l : m), '');
						const lab = svgFit(longest, X(e.at), base, room);
						const sb = e.sub ? svgFit(e.sub, X(e.at), 20, room, 40, 1560, 0.62) : null;
					const col = KIND_COL[e.kind || 'past'] || C.cyan;
					const up = i % 2 === 0;
					return (
						<g key={i} opacity={last ? ramp(t, 0.6 + (i / Math.max(1, ev.length - 1)) * dur * 0.8, 0.35) : 0.85}>
															{fid ? <>
									<circle cx={X(e.at)} cy="560" r={last ? 30 : 24} fill={C.hudBg0} stroke={last ? C.amber : col} strokeWidth={last ? 2.5 : 1.5} />
									<SvgFigure id={fid} x={X(e.at)} y={560} size={last ? 40 : 32} t={t} draw={last ? ramp(t, 0.6 + (i / Math.max(1, ev.length - 1)) * dur * 0.8, 0.9, (x) => x) : 1} />
								</> : <circle cx={X(e.at)} cy="560" r={last ? 11 : 7} fill={col} />}
							{e.kind === 'miss' && <path d={`M${X(e.at) - 8} 552L${X(e.at) + 8} 568M${X(e.at) + 8} 552L${X(e.at) - 8} 568`} stroke={C.red} strokeWidth="2" />}
															<path d={`M${X(e.at)} ${up ? (fid ? 530 : 550) : (fid ? 590 : 570)}V${up ? 470 : 650}`} stroke={col} strokeOpacity=".5" />
															<text x={lab.x} y={up ? 455 - (lines.length - 1) * lab.fontSize * 1.1 : 685} textAnchor="middle" fontFamily={F.head} fontWeight={700} fontSize={lab.fontSize} fill={last ? C.amber : C.ink}>{lines.map((l, j) => <tspan key={j} x={lab.x} dy={j ? lab.fontSize * 1.1 : 0}>{l}</tspan>)}</text>
								{sb && <text x={sb.x} y={up ? 425 - (lines.length - 1) * lab.fontSize * 1.1 : 715 + (lines.length - 1) * lab.fontSize * 1.1} textAnchor="middle" fontFamily={F.mono} fontSize={sb.fontSize} fill={C.cyanSoft}>{e.sub}</text>}
						</g>
					);
				})}
			</SVG>
		</HudStage>
	);
};

const RoadsterTimeline: React.FC<BeatProps> = ({t, dur, b}) => {
	const X = (y: number) => 160 + (y - 2017) * 116;
	const n = b.v.upto;
	const shown = n <= 1 ? 1 : Math.min(SLIPS.length, 1 + Math.floor(ramp(t, 0.6, dur * 0.8, (x) => x) * (SLIPS.length - 1) + 0.0001));
	const cur = SLIPS[shown - 1];
	return (
		<HudStage t={t}>
			<Head t={t} tag="01 — THE NINE-YEAR WAIT" title={n <= 1 ? 'The 2017 promise' : 'The date kept moving'} />
			<SVG>
				<path d={`M${X(2017)} 560H${X(2028.6)}`} stroke={C.cyan} strokeOpacity=".7" strokeWidth="2" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ramp(t, 0, 0.8)} />
				{Array.from({length: 12}, (_, i) => 2017 + i).map((y) => (
					<g key={y} opacity={ramp(t, 0.2 + (y - 2017) * 0.04, 0.3)}>
						<path d={`M${X(y)} 552V568`} stroke={C.cyan} strokeOpacity=".7" />
						<text x={X(y)} y="600" textAnchor="middle" fontFamily={F.mono} fontSize="22" fill={C.hudLabel}>{y}</text>
					</g>
				))}
				<g opacity={ramp(t, 0.3, 0.5)}>
					<circle cx={X(2017.87)} cy="560" r="9" fill={C.cyan} />
					<path d={`M${X(2017.87)} 550V430`} stroke={C.cyan} strokeOpacity=".6" />
					<text x={X(2017.87)} y="410" fontFamily={F.head} fontWeight={700} fontSize="34" fill={C.ink} textAnchor="middle">NOV 2017 REVEAL</text>
					<text x={X(2017.87)} y="378" fontFamily={F.mono} fontSize="22" fill={C.cyanSoft} textAnchor="middle">1.9 s · 620 mi · $200k</text>
				</g>
				{SLIPS.slice(0, shown).map(([y, label], i) => {
					const last = i === shown - 1;
					const final = y === 2028;
					return (
						<g key={label}>
							<circle cx={X(y)} cy="560" r={last ? 12 : 7} fill={last ? (final ? C.cyan : C.amber) : 'none'} stroke={last ? 'none' : C.red} strokeWidth="2" opacity={last ? 1 : 0.8} />
							{!last && <path d={`M${X(y) - 8} 552L${X(y) + 8} 568M${X(y) + 8} 552L${X(y) - 8} 568`} stroke={C.red} strokeWidth="2" />}
							{(last || y < 2026) && <text x={X(y)} y={last ? 650 : (i % 2 ? 690 : 650)} textAnchor="middle" fontFamily={F.mono} fontSize={last ? 26 : 20} fill={last ? C.amber : C.red} opacity={last ? 1 : 0.7}>{label}</text>}
						</g>
					);
				})}
				<text x={X(cur[0])} y="520" textAnchor="middle" fontFamily={F.head} fontWeight={700} fontSize="30" fill={C.amber}>DELIVERY ▼</text>
			</SVG>
		</HudStage>
	);
};

// ── 2017 promise vs 2026 reality
const CMP: [string, string, string][] = [['Seats', '4 (2+2)', '2'], ['Drive', '3-motor AWD', '2-motor RWD'], ['Range', '620 mi', '≈300 mi'], ['0–60 mph', '1.9 s', '0.81 s (Thrust)'], ['Battery', '200 kWh', '100+ kWh'], ['Delivery', '2020', '2028 (production)']];
export const Compare: React.FC<BeatProps> = ({t, dur, b, hd, legacy}) => {
	const rows: [string, string, string][] = b?.v?.rows || (legacy ? CMP : []);
	const cols: [string, string] = b?.v?.cols || (legacy ? ['2017 PROMISE', '2026 UNVEIL'] : [String(b?.v?.left || '').toUpperCase(), String(b?.v?.right || '').toUpperCase()]);
	const hiRow: string = b?.v?.hi ?? (b?.v?.rows ? '' : '0–60 mph');
	const strikeOn = legacy || !!b?.v?.strike;
	return (
	<HudStage t={t}>
		<Head t={t} tag={b?.v?.tag ?? (legacy ? '01 — THE NINE-YEAR WAIT' : hd?.tag || '')} title={b?.v?.title ?? (legacy ? 'Promise vs reality' : hd?.title || '')} hero={legacy ? undefined : `${cols.join(' ')} ${b?.cap || ''}`} fig={(b as any)?.v?.fig} />
					<div style={{position: 'absolute', left: 240, top: 330}}><Fit w={1440} h={600} style={{fontFamily: F.mono, fontSize: 34}}>
			<div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', color: C.hudLabel, fontSize: 24, letterSpacing: 4, paddingBottom: 14, borderBottom: '1px solid rgba(255,255,255,.2)'}}>
									<span /> {[0, 1].map((k) => <span key={k} style={{display: 'flex', alignItems: 'center', gap: 14}}><Figure id={figFor(cols[k] + ' ' + (b?.v?.title || hd?.title || ''), k ? 'chart' : 'gpu')} size={54} t={t + k} draw={ramp(t, 0.3 + k * 0.3, 1.0, (x) => x)} stroke={3} />{cols[k]}</span>)}
			</div>
			{rows.map(([k, a, z], i) => {
				const at = 0.5 + i * (dur * 0.75 / rows.length);
				const p = ramp(t, at, 0.4);
				const strike = ramp(t, at + 0.35, 0.3);
				return (
											<div key={i} style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', padding: '16px 0', borderBottom: '1px solid rgba(255,255,255,.07)', opacity: p, transform: `translateX(${(1 - p) * -16}px)`}}>
						<span style={{color: C.hudLabel}}>{k}</span>
													<span style={{color: strikeOn ? C.red : C.ink, position: 'relative', width: 'fit-content', paddingRight: 16}}>{a}{strikeOn && <span style={{position: 'absolute', left: 0, top: '52%', height: 3, width: `${strike * 100}%`, background: C.red}} />}</span>
							<span style={{color: k === hiRow ? C.amber : C.ink, opacity: strikeOn ? strike : p}}>{z}</span>
						</div>
					);
				})}
			</Fit></div>
	</HudStage>
	);
};

// shared HUD car (drawn in over the first ~1.6 s of any HUD beat)
const Car: React.FC<{t: number; tank?: number; plume?: number; dims?: number; dim?: number}> = ({t, tank = 0, plume = 0, dims = 0, dim = 1}) => (
	<AbsoluteFill style={{opacity: dim}}><CarLines t={t} draw={ramp(t, 0, 1.6, (x) => x)} tank={tank} plume={plume} dims={dims} /></AbsoluteFill>
);

// ── powertrain: battery → two rear motors, no differential
export const Powertrain: React.FC<BeatProps> = ({t, dur}) => {
	const flow = ramp(t, 1.4, 1.0);
	const dash = (t * 60) % 40;
	const m = ramp(t, 2.0, 0.5);
	return (
		<HudStage t={t}>
			<Car t={t} />
			<SVG>
				<rect x="620" y="650" width="400" height="18" rx="4" fill={C.cyan} fillOpacity={0.25 * flow} />
				<path d="M1020 659H1110" stroke={C.amber} strokeWidth="3" strokeDasharray="10 10" strokeDashoffset={-dash} opacity={flow} />
				<g opacity={m}>
					<circle cx="1110" cy="640" r="30" fill={C.amber} fillOpacity=".2" stroke={C.amber} strokeWidth="3" />
					<circle cx="1110" cy="640" r="12" fill={C.amber} />
				</g>
			</SVG>
			<Callout p={ramp(t, 2.3, 0.9)} from={[1110, 610]} elbow={[1200, 400]} end={[1560, 400]} title="2 motors · 1 MW+" sub="8.4:1 planetary · own inverter" color={C.amber} align="end" />
			<Callout p={ramp(t, dur * 0.55, 0.9)} from={[820, 650]} elbow={[700, 420]} end={[640, 420]} title="No differential" sub="software torque vectoring" align="end" />
			<Head t={t} tag="02 — THE POWER" title="Two motors, one per wheel" />
		</HudStage>
	);
};

// ── spec panel beat (battery)
export const Spec: React.FC<BeatProps> = (p) => (p.legacy ? <RoadsterSpec {...p} /> : <SpecTable {...p} />);

// generic spec: rows typed in as a big two-column table under the chapter header (no baked-in art)
const SpecTable: React.FC<BeatProps> = ({t, dur, b, hd}) => {
	const rows: any[] = b.v.rows || [];
	return (
		<HudStage t={t}>
			<Head t={t} tag={b.v.tag || hd?.tag || ''} title={b.v.title || hd?.title || ''} hero={rows.map((r: any) => r.join(' ')).join(' ') + ' ' + (b.cap || '')} fig={(b as any)?.v?.fig} />
				<div style={{position: 'absolute', left: 160, top: 340}}><Fit w={1600} h={600} style={{fontFamily: F.mono, fontSize: 40}}>
				{rows.map(([k, v, hi]: [string, string, boolean], i: number) => {
					const at = 0.7 + i * (dur * 0.6 / Math.max(1, rows.length));
					const p = ramp(t, at, 0.4);
					const val = String(v ?? '');
					return (
						<div key={i} style={{display: 'flex', justifyContent: 'space-between', gap: 40, padding: '20px 0', borderBottom: '1px solid rgba(255,255,255,.09)', opacity: p, transform: `translateX(${(1 - p) * -16}px)`}}>
															<span style={{color: C.hudLabel, flex: 'none', maxWidth: '45%', display: 'flex', alignItems: 'center', gap: 16}}>{(() => { const f = figFor(`${k} ${val}`); return f ? <Figure id={f} size={46} t={t + i} draw={ramp(t, at, 0.9, (x) => x)} stroke={3} /> : null; })()}{k}</span>
								<span style={{color: hi ? C.amber : C.ink, textAlign: 'right', minWidth: 0}}>{val.slice(0, Math.ceil(val.length * ramp(t, at + 0.1, 0.5)))}</span>
							</div>
						);
					})}
				</Fit></div>
		</HudStage>
	);
};

const RoadsterSpec: React.FC<BeatProps> = ({t, dur, b}) => (
	<HudStage t={t}>
		<Car t={t} dims={ramp(t, 1.2, 0.5)} />
		<SVG><rect x="620" y="650" width="400" height="18" rx="4" fill={C.cyan} fillOpacity={0.3 + 0.15 * Math.sin(t * 4)} /></SVG>
		<Callout p={ramp(t, 1.0, 0.9)} from={[820, 668]} elbow={[700, 735]} end={[560, 735]} title="4680 pack" sub="under the floor" align="end" />
		<SpecPanel t={t} at={0.8} rows={b.v.rows.map(([k, v, hi]: [string, string, boolean], i: number) => ({k, v, hi, at: 1.4 + i * (dur * 0.55 / b.v.rows.length)}))} />
		<Head t={t} tag="02 — THE POWER" title={b.v.title} />
	</HudStage>
);

// ── fan car: rear fans + drop-down skirts pull a vacuum under the floor
export const Fans: React.FC<BeatProps> = ({t, dur}) => {
	const sk = ramp(t, 1.8, 0.7);
	const fan = ramp(t, 1.2, 0.5);
	const suck = ramp(t, dur * 0.45, 0.8);
	const spin = t * 900;
	return (
		<HudStage t={t}>
			<Car t={t} />
			<SVG>
				{[1196, 1218, 1240].map((x, i) => (
					<g key={x} opacity={fan} transform={`translate(${x} ${632 - i * 2})`}>
						<circle r="10" fill="none" stroke={C.amber} strokeWidth="2.5" />
						{[0, 120, 240].map((a) => <path key={a} d="M0 0L0 -8" stroke={C.amber} strokeWidth="3" transform={`rotate(${a + spin})`} />)}
					</g>
				))}
				<g stroke={C.amber} strokeWidth="3" opacity={sk}>
					<path d={`M612 682V${682 + 30 * sk}`} /><path d={`M1028 682V${682 + 30 * sk}`} /><path d={`M612 ${682 + 30 * sk}H1028`} strokeDasharray="6 8" strokeOpacity=".6" />
				</g>
				{[680, 760, 840, 920, 1000].map((x, i) => (
					<path key={x} d={`M${x} 470V${430 - 10 * Math.sin(t * 3 + i)}`} stroke={C.cyan} strokeWidth="3" markerEnd="url(#dn)" opacity={suck} transform={`rotate(180 ${x} 450)`} />
				))}
				<defs><marker id="dn" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill={C.cyan} /></marker></defs>
				{[0, 1, 2].map((i) => {
					const x = 640 + ((t * 260 + i * 140) % 560);
					return <circle key={i} cx={x} cy={700} r="4" fill={C.cyanSoft} opacity={sk * 0.8} />;
				})}
			</SVG>
			<Callout p={ramp(t, 1.4, 0.9)} from={[1218, 622]} elbow={[1150, 420]} end={[1560, 420]} title="4 fans · ~20 kW each" sub="pull air from under the car" color={C.amber} align="end" />
			<Callout p={ramp(t, 2.2, 0.9)} from={[760, 712]} elbow={[700, 735]} end={[560, 735]} title="Skirts drop" sub="seal the floor" align="end" />
			<Head t={t} tag="03 — THE FAN CAR" title="Suction grip" />
		</HudStage>
	);
};

// ── horizontal g bars (+ optional verdict stamp)
const BAR_COLOR: Record<string, string> = {amber: C.amber, cyan: C.cyan, ink: C.ink, none: C.hudLabel, red: C.red, green: '#7BD88F', silver: C.cyan};
export const GBars: React.FC<BeatProps> = ({t, dur, b, hd, legacy}) => {
	const W = 900;
	return (
		<HudStage t={t}>
			<Head t={t} tag={b.v.tag ?? (legacy ? (b.ch === 3 ? '03 — THE FAN CAR' : '05 — PHYSICS CHECK') : hd?.tag || '')} title={b.v.title ?? hd?.title ?? ''} hero={legacy ? undefined : b.v.bars.map((x: any) => x[0]).join(' ') + ' ' + (b.v.unit || '') + ' ' + (b.cap || '')} fig={(b as any)?.v?.fig} />
							<div style={{position: 'absolute', left: 160, top: 340}}><Fit w={1600} h={600}>
					{b.v.bars.map(([label, g, col]: [string, number, string], i: number) => {
					const p = ramp(t, 0.6 + i * (dur * 0.5 / b.v.bars.length), 1.0);
					return (
													<div key={i} style={{marginBottom: 46}}>
															<div style={{fontFamily: F.head, fontSize: 34, color: C.ink, marginBottom: 12, opacity: ramp(t, 0.4 + i * 0.3, 0.4), display: 'flex', alignItems: 'center', gap: 16}}>
									<Figure id={figFor(label + ' ' + (b.v.title || ''), 'monitor')} size={48} t={t + i} draw={ramp(t, 0.4 + i * 0.3, 0.9, (x) => x)} stroke={3} accent={BAR_COLOR[col] || C.amber} />{label}</div>
							<div style={{display: 'flex', alignItems: 'center', gap: 24}}>
								<div style={{width: W, height: 34, background: 'rgba(255,255,255,.07)', borderRadius: 6, overflow: 'hidden'}}>
																			<div style={{position: 'relative', width: `${(g / (b.v.max || Math.max(...b.v.bars.map((x: any) => Number(x[1]) || 0), 1))) * 100 * p}%`, height: '100%', background: BAR_COLOR[col], opacity: col === 'ink' ? 0.85 : 1, borderRadius: 6}}>
											<div style={{position: 'absolute', right: -6, top: -6, bottom: -6, width: 14, borderRadius: 8, background: '#fff', filter: 'blur(5px)', opacity: p > 0 && p < 1 ? 0.9 : 0.25 + 0.15 * Math.sin(t * 4 + i)}} />
										</div>
								</div>
								<span style={{fontFamily: F.mono, fontSize: 36, color: BAR_COLOR[col], minWidth: 160}}>{g === 0 ? '≈ 0 g' : `${(g * p).toFixed(g % 1 ? 2 : 1)} ${b.v.unit}`}</span>
							</div>
						</div>
					);
									})}
				</Fit></div>
				{b.v.stamp && <Stamp t={t} at={dur - 2.6} text={b.v.stamp} />}
		</HudStage>
	);
};

// ── verdict stamp
export const Stamp: React.FC<{t: number; at: number; text: string; color?: string}> = ({t, at, text, color = C.amber}) => {
	const p = ramp(t, at, 0.25);
	if (p <= 0) return null;
	return (
		<div style={{position: 'absolute', right: 150, top: 790, transform: `rotate(-6deg) scale(${1.6 - 0.6 * p})`, opacity: p, border: `6px solid ${color}`, color, borderRadius: 14,
							padding: '14px 34px', fontFamily: F.head, fontWeight: 700, fontSize: Math.min(64, 64 * 16 / Math.max(16, String(text).length)), letterSpacing: 6, background: 'rgba(8,8,10,.6)', maxWidth: 900}}>{text}</div>
	);
};

// ── active wing tilting into an air brake
export const Wing: React.FC<BeatProps> = ({t, dur}) => {
	const tilt = interpolate(t, [dur * 0.5, dur * 0.5 + 1.2], [0, 80], {...clamp, easing: (x) => 1 - Math.pow(1 - x, 3)});
	return (
		<HudStage t={t}>
			<AbsoluteFill style={{opacity: 0.9}}><CarLines t={t} draw={ramp(t, 0, 1.6, (x) => x)} noWing /></AbsoluteFill>
			<SVG>
				<path d="M1150 478L1162 514M1222 469L1230 520" stroke={C.cyan} strokeWidth="2" />
				<g transform={`rotate(${-tilt} 1183 471)`}>
					<path d="M1100 470L1262 461L1266 473L1104 482Z" fill={C.amber} fillOpacity=".25" stroke={C.amber} strokeWidth="3" />
				</g>
				{[0, 1, 2].map((i) => {
					const x = 1500 - ((t * 420 + i * 160) % 480);
					return <path key={i} d={`M${x} ${430 + i * 22}h-60`} stroke={C.cyanSoft} strokeWidth="2.5" opacity={0.6} />;
				})}
			</SVG>
			<Callout p={ramp(t, 1.0, 0.9)} from={[760, 690]} elbow={[700, 735]} end={[560, 735]} title="200+ mph: skirts open" sub="fans → up to 2 g downforce" align="end" />
			<Callout p={ramp(t, dur * 0.5 + 0.4, 0.9)} from={[1183, 420]} elbow={[1260, 330]} end={[1560, 330]} title="Wing tilts ~90°" sub="becomes an air brake" color={C.amber} align="end" />
			<Head t={t} tag="03 — THE FAN CAR" title="Shape-shifting aero" />
		</HudStage>
	);
};

// ── mid-roll like + subscribe reminder over a studio plate
export const Midroll: React.FC<BeatProps> = (p) => {
	const {t, dur} = p;
	const o = interpolate(t, [0.5, 0.9, dur - 0.6, dur - 0.2], [0, 1, 1, 0], clamp);
	const liked = t > 2.0;
	return (
		<>
			<Plate {...p} />
			<div style={{position: 'absolute', left: 116, bottom: 190, display: 'flex', gap: 18, opacity: o, transform: `translateY(${(1 - o) * 20}px)`}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 12, padding: '14px 26px', borderRadius: 40, border: `2px solid ${liked ? C.amber : 'rgba(255,255,255,.4)'}`, background: liked ? 'rgba(255,181,71,.15)' : 'rgba(0,0,0,.4)', color: liked ? C.amber : C.ink, fontFamily: F.head, fontWeight: 600, fontSize: 32}}>
					<Icon d={ICON.heart} size={32} color={liked ? C.amber : C.ink} fill={liked ? C.amber : 'none'} /> LIKE
				</div>
				<div style={{display: 'flex', alignItems: 'center', gap: 12, padding: '14px 26px', borderRadius: 40, background: '#E5322D', color: '#fff', fontFamily: F.head, fontWeight: 600, fontSize: 32}}>
					SUBSCRIBE <Icon d={ICON.bell} size={30} color="#fff" />
				</div>
			</div>
		</>
	);
};

// ── cold-gas thruster stages
export const Thrusters: React.FC<BeatProps> = ({t, dur, b}) => {
	const st = b.v.stage as 'tank' | 'plume' | 'thrust' | 'rocket';
	const plume = st === 'tank' ? 0 : ramp(t, st === 'plume' ? dur * 0.25 : 0.6, 0.3);
	const extra = st === 'rocket' ? ramp(t, 1.4, 0.4) : 0;
	const flick = 0.85 + 0.3 * Math.abs(Math.sin(t * 37));
	return (
		<HudStage t={t}>
			<Car t={t} tank={st === 'tank' || st === 'thrust' ? ramp(t, 0.9, 0.5) : 0.6} plume={plume} />
			{st === 'tank' && <Callout p={ramp(t, 1.2, 0.9)} from={[955, 590]} elbow={[1100, 330]} end={[1560, 330]} title="N₂ COPV" sub="10,000 psi · carbon-wrapped" color={C.amber} align="end" />}
			{st === 'plume' && <SpecPanel t={t} at={dur * 0.35} rows={[{k: 'COMBUSTION', v: 'none', at: dur * 0.42}, {k: 'PEAK THRUST', v: '80+ kN', at: dur * 0.55, hi: true}, {k: 'VS TIRE GRIP', v: '4–5×', at: dur * 0.72}]} />}
			{st === 'thrust' && <SpecPanel t={t} at={0.6} rows={[{k: 'NOZZLES', v: '4 rear', at: 1.0}, {k: 'TANK', v: '200 L', at: dur * 0.4, hi: true}, {k: 'PER FILL', v: '≈5 s', at: dur * 0.65}]} />}
			{(st === 'plume' || st === 'thrust') && <Callout p={ramp(t, dur * 0.3, 0.9)} from={[1252, 612]} elbow={[1330, 720]} end={[1560, 720]} title="4 rear nozzles" sub="cold gas · no flame" align="end" />}
			{st === 'rocket' && (
				<>
					<SVG>
						<defs><linearGradient id="dplume" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#FFE3A3" /><stop offset="1" stopColor={C.amber} stopOpacity="0" /></linearGradient>
							<linearGradient id="fplume" x1="1" x2="0"><stop offset="0" stopColor="#FFE3A3" /><stop offset="1" stopColor={C.amber} stopOpacity="0" /></linearGradient></defs>
						{[612, 1204].map((x) => <polygon key={x} points={`${x - 8},700 ${x + 8},700 ${x + 12},${700 + 70 * extra * flick} ${x - 12},${700 + 70 * extra * flick}`} fill="url(#dplume)" opacity={extra} />)}
						{[628, 642].map((y) => <polygon key={y} points={`346,${y - 5} 346,${y + 5} ${346 - 150 * extra * flick},${y + (y - 635) * 2}`} fill="url(#fplume)" opacity={extra} />)}
						<rect x="770" y="590" width="100" height="44" rx="12" fill={C.amber} fillOpacity=".16" stroke={C.amber} strokeWidth="2.5" opacity={ramp(t, 2.2, 0.5)} />
					</SVG>
					<SpecPanel t={t} at={0.6} rows={[{k: 'THRUSTERS', v: '10', at: 1.2, hi: true}, {k: 'TANKS', v: '600 L total', at: dur * 0.35}, {k: 'SEATS', v: '1', at: dur * 0.55}]} />
					<Callout p={ramp(t, 1.8, 0.9)} from={[612, 712]} elbow={[590, 735]} end={[560, 735]} title="Down + nose thrusters" sub="+6 over the Thrust trim" align="end" color={C.amber} />
				</>
			)}
			<Head t={t} tag="04 — THE SPACEX PACKAGE" title={{tank: 'Cold-gas thrusters', plume: 'No flame, just pressure', thrust: 'Thrust trim', rocket: 'Rocket trim'}[st]} />
		</HudStage>
	);
};

// ── formula lines typed in one by one (+ note, + stamp)
export const Formula: React.FC<BeatProps> = ({t, dur, b, hd, legacy}) => {
	const lines: string[] = b.v.lines;
	return (
		<HudStage t={t}>
			<Head t={t} tag={b.v.tag ?? (legacy ? '05 — PHYSICS CHECK' : hd?.tag || '')} title={b.v.title ?? (legacy ? (b.id === 'b24' ? 'Average acceleration' : b.id === 'b26' ? 'The gas budget' : 'Could it fly?') : 'The math')} hero={legacy ? undefined : lines.join(' ') + ' ' + (b.cap || '')} fig={(b as any)?.v?.fig} />
			<div style={{position: 'absolute', left: 200, top: 340}}><Fit w={1520} h={600}>
				{lines.map((l, i) => {
					const at = 0.6 + i * (dur * 0.6 / lines.length);
					const p = ramp(t, at, 0.6, (x) => x);
					const last = i === lines.length - 1;
					return (
						<div key={i} style={{fontFamily: F.mono, fontSize: last ? 66 : 54, color: last ? C.amber : C.ink, marginBottom: 34, whiteSpace: 'pre', opacity: p > 0 ? 1 : 0}}>
							{l.slice(0, Math.ceil(l.length * p))}<span style={{opacity: p < 1 && p > 0 ? 1 : 0, color: C.cyan}}>▍</span>
						</div>
					);
				})}
				{b.v.note && <div style={{fontFamily: F.mono, fontSize: 22, letterSpacing: 3, color: C.hudLabel, marginTop: 10, opacity: ramp(t, dur * 0.7, 0.5)}}>{b.v.note}</div>}
			</Fit></div>
			{b.v.stamp && <Stamp t={t} at={dur - 2.2} text={b.v.stamp} color={b.v.stamp.includes('NOT') ? C.red : C.amber} />}
		</HudStage>
	);
};

// ── trims: three cards, revealed as the narrator names them
const TRIMS = [
	{name: 'Performance', tag: 'ROAD READY', seats: '2 seats', hw: '1 MW · fan suction · active aero', res: '$50,000', road: 'Road car', col: C.cyan},
	{name: 'Thrust', tag: 'RACE READY', seats: '2 seats', hw: '+ 4 rear thrusters · 200 L tank', res: '$250,000', road: 'Road car', col: C.amber},
	{name: 'Rocket', tag: 'AIR READY', seats: '1 seat', hw: '10 thrusters · 600 L total', res: 'Invite only', road: 'Off-road only', col: C.red},
];
const CARD_COL: Record<string, string> = {silver: C.cyan, cyan: C.cyan, ink: C.ink, amber: C.amber, red: C.red, green: '#7BD88F'};
export const Trims: React.FC<BeatProps> = ({t, dur, b, hd, legacy}) => {
	const cards = b?.v?.cards ? b.v.cards.map((x: any) => ({name: x.name, tag: x.tag || '', seats: x.line1 || '', hw: x.line2 || '', res: x.value || '', road: x.foot || '', col: CARD_COL[x.color] || C.cyan, label: x.label})) : legacy ? TRIMS : [];
	return (
	<HudStage t={t}>
		<Head t={t} tag={b?.v?.tag ?? (legacy ? '06 — TRIMS, PRICE, ROAD-LEGAL' : hd?.tag || '')} title={b?.v?.title ?? (legacy ? 'Three trims' : hd?.title || '')} hero={legacy ? undefined : cards.map((x: any) => x.name).join(' ') + ' ' + (b?.cap || '')} fig={(b as any)?.v?.fig} />
					<div style={{position: 'absolute', left: 116, top: 320}}><Fit w={1688} h={640} style={{display: 'flex', gap: 36}}>
				{cards.map((x: any, i: number) => {
				const p = ramp(t, 0.5 + i * dur * (0.8 / cards.length), 0.6);
				return (
					<div key={x.name} style={{flex: 1, padding: '34px 36px', borderRadius: 16, border: `2px solid ${x.col}`, background: 'rgba(14,14,16,.72)', opacity: p, transform: `translateY(${(1 - p) * 30}px)`}}>
						<div style={{fontFamily: F.mono, fontSize: 22, letterSpacing: 5, color: x.col}}>{x.tag}</div>
						<div style={{fontFamily: F.head, fontWeight: 600, fontSize: 64, color: C.ink, margin: '8px 0 20px'}}>{x.name}</div>
						<div style={{fontFamily: F.head, fontSize: 30, color: C.cyanSoft, lineHeight: 1.5}}>{x.seats}<br />{x.hw}</div>
						<div style={{height: 1, background: 'rgba(255,255,255,.14)', margin: '24px 0'}} />
						<div style={{fontFamily: F.mono, fontSize: 22, color: C.hudLabel, letterSpacing: 3}}>{x.label ?? 'RESERVATION'}</div>
						<div style={{fontFamily: F.head, fontWeight: 600, fontSize: 48, color: x.col, marginTop: 4}}>{x.res}</div>
						<div style={{fontFamily: F.mono, fontSize: 24, color: x.road.startsWith('Off') ? C.red : C.ink, marginTop: 18}}>{x.road}</div>
					</div>
									);
				})}
			</Fit></div>
		</HudStage>
		);
	};

// ── list beats: open questions (warn) / recap (check)
export const ListBeat: React.FC<BeatProps & {kind: 'questions' | 'recap'}> = ({t, dur, b, kind, hd, legacy}) => {
	const items: string[] = b.v.items;
	const q = kind === 'questions';
	return (
		<HudStage t={t}>
			<Head t={t} tag={b.v.tag ?? (legacy ? (q ? '06 — TRIMS, PRICE, ROAD-LEGAL' : '07 — THE VERDICT') : hd?.tag || '')} title={b.v.title ?? (q ? 'Open questions' : legacy ? 'The Roadster, in four lines' : 'In short')} hero={legacy ? undefined : items.join(' ') + ' ' + (b.cap || '')} fig={(b as any)?.v?.fig} />
			<div style={{position: 'absolute', left: 160, top: 340}}><Fit w={1600} h={560}>
				{items.map((it, i) => {
					const p = ramp(t, 0.8 + i * (dur * 0.65 / items.length), 0.5);
					return (
						<div key={i} style={{display: 'flex', alignItems: 'center', gap: 28, marginBottom: 40, opacity: p, transform: `translateX(${(1 - p) * -20}px)`}}>
															{figFor(it) ? <div style={{flex: 'none', width: 72, height: 72, borderRadius: 36, border: `1.5px solid ${q ? C.amber : 'rgba(230,235,240,.4)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
									<Figure id={figFor(it)} size={50} t={t + i} draw={ramp(t, 0.8 + i * (dur * 0.65 / items.length), 0.9, (x) => x)} stroke={3} /></div> :
								<svg width="54" height="54" style={{flex: 'none'}} viewBox="0 0 24 24" fill="none" stroke={q ? C.amber : C.cyan} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
								{q ? <><path d="M12 3.5L21.5 20H2.5Z" /><path d="M12 10V14" /><circle cx="12" cy="17" r="1" fill={C.amber} /></> : <><circle cx="12" cy="12" r="9" /><path d="M8 12.5L11 15.5L16.5 9.5" /></>}
								</svg>}
							<span style={{fontFamily: F.head, fontSize: 50, lineHeight: 1.15, color: C.ink, minWidth: 0}}>{it}</span>
						</div>
					);
				})}
			</Fit></div>
		</HudStage>
	);
};

// ── end card: like + subscribe + download the MIR MEDIA LABS app
export const EndCard: React.FC<BeatProps & {title: string; series: string}> = (p) => {
	const {t, title, series} = p;
	const inA = ramp(t, 0.3, 0.6);
	const likeAt = 2.0, subAt = 3.2;
	const liked = t >= likeAt, subbed = t >= subAt;
	const pop = (at: number) => 1 + 0.18 * Math.sin(Math.min(1, Math.max(0, (t - at) / 0.3)) * Math.PI);
	const ring = t >= subAt + 0.1 && t < subAt + 1.1 ? Math.sin((t - subAt) * 28) * 16 * (1 - (t - subAt - 0.1)) : 0;
	const ez = (x: number) => 1 - Math.pow(1 - x, 3);
	const cx = interpolate(t, [0.9, likeAt - 0.1, likeAt + 0.3, subAt - 0.1], [1700, 760, 760, 1150], {...clamp, easing: ez});
	const cy = interpolate(t, [0.9, likeAt - 0.1, likeAt + 0.3, subAt - 0.1], [1000, 560, 560, 560], {...clamp, easing: ez});
	const press = (t > likeAt - 0.08 && t < likeAt + 0.1) || (t > subAt - 0.08 && t < subAt + 0.1) ? 0.85 : 1;
	const app = ramp(t, subAt + 0.8, 0.6);
	const btn: React.CSSProperties = {display: 'flex', alignItems: 'center', gap: 18, padding: '22px 40px', borderRadius: 60, fontFamily: F.head, fontWeight: 600, fontSize: 40, letterSpacing: 3};
	return (
		<>
			<StudioStage><AbsoluteFill style={{filter: 'brightness(.5)'}}><PlateMedia t={t} dur={p.dur} src={plateSrc(p.asset, p.b.plate)} /></AbsoluteFill></StudioStage>
			<AbsoluteFill style={{opacity: inA * (1 - ramp(t, p.dur - 0.8, 0.8))}}>
				<div style={{position: 'absolute', left: 0, right: 0, top: 480, display: 'flex', justifyContent: 'center', gap: 40}}>
					<div style={{...btn, transform: `scale(${liked ? pop(likeAt) : 1})`, background: liked ? 'rgba(255,181,71,.16)' : 'rgba(255,255,255,.08)', border: `2px solid ${liked ? C.amber : 'rgba(255,255,255,.35)'}`, color: liked ? C.amber : C.ink}}>
						<Icon d={ICON.heart} size={46} color={liked ? C.amber : C.ink} fill={liked ? C.amber : 'none'} /> LIKE
					</div>
					<div style={{...btn, transform: `scale(${subbed ? pop(subAt) : 1})`, background: subbed ? 'rgba(255,255,255,.12)' : '#E5322D', border: '2px solid transparent', color: '#fff'}}>
						{subbed ? 'SUBSCRIBED' : 'SUBSCRIBE'}
						<span style={{display: 'inline-flex', transform: `rotate(${ring}deg)`, transformOrigin: '50% 10%'}}><Icon d={ICON.bell} size={42} color="#fff" /></span>
					</div>
				</div>
				<div style={{position: 'absolute', left: 0, right: 0, top: 690, textAlign: 'center', opacity: app, transform: `translateY(${(1 - app) * 16}px)`}}>
					<div style={{display: 'inline-flex', alignItems: 'center', gap: 16, fontFamily: F.head, fontSize: 44, color: C.ink}}>
						<Icon d={ICON.download} size={48} color={C.amber} /> Download the <b style={{color: C.amber, fontWeight: 600}}>MIR MEDIA LABS</b> app
					</div>
					<div style={{fontFamily: F.mono, fontSize: 28, color: C.quiet, marginTop: 14, letterSpacing: 1}}>github.com/MirCorp85/MirMediaLabs</div>
				</div>
				<svg width="46" height="46" viewBox="0 0 24 24" style={{position: 'absolute', left: cx, top: cy, transform: `scale(${press})`, transformOrigin: '0 0', opacity: t < subAt + 1.2 ? 1 : 1 - ramp(t, subAt + 1.2, 0.4)}}>
					<path d="M4 2L4 19L8.5 14.8L11.5 21.5L14.2 20.3L11.3 13.8L17.5 13.6Z" fill="#fff" stroke="#111" strokeWidth="1.2" strokeLinejoin="round" />
				</svg>
				<div style={{position: 'absolute', left: 116, top: 96}}><Fit w={1690} nowrap style={{fontFamily: F.mono, fontSize: 28, letterSpacing: 6, color: C.cyan}}>{series}</Fit></div>
				<div style={{position: 'absolute', left: 116, top: 140}}><Fit w={1690} h={150} style={{fontFamily: F.head, fontWeight: 600, fontSize: 64, lineHeight: 1.08, color: C.ink}}>{title}</Fit></div>
			</AbsoluteFill>
		</>
	);
};

export {S};
