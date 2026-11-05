// RANK REEL — the viral "ranking" Short (MIR RANK SHORTS, Oct 26 2026). One scene = the whole 9:16 video:
// 2-line title with colour-keyed keywords, a rank ladder (#1 at the top) whose labels reveal as each clip plays,
// clips in SHUFFLED order with #1 always last (retention trick), and per-clip VO verdict + caption (the
// "transformation" layer that keeps the channel monetisable). Timing lives in props.items[].dur; the Python
// builder (server/rankreel.py) sets the scene's dur = intro + sum(items.dur).
import React from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, Sequence, Video, getRemotionEnvironment, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {AnimText} from '../AnimText';
import {Project, ease, fontFamily, pop, src} from '../lib';

type Item = {src?: string; label?: string; rank?: number; trimIn?: number; dur?: number; verdict?: string; vo?: string; voDur?: number; play?: number; aspect?: number; focusX?: number; focusY?: number};
type SP = {p: Record<string, any>; proj: Project; durF: number};

const isRender = () => getRemotionEnvironment().isRendering;
const Vid: React.FC<any> = (a) => (isRender() ? <OffthreadVideo {...a} /> : <Video {...a} />);
const fsz = (h: number, v: number) => (v * h) / 1920;

// mulberry32 — same seed → same order in preview, render and the Python mirror (rankreel.play_order)
const rng = (seed: number) => {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
};

// items (any order) → play order. shuffle = random with #1 last and never opening on the last rank;
// countdown = N…1; custom = items[].play ascending.
export const playOrder = (items: Item[], mode: string, seed: number): Item[] => {
	const xs = items.map((it, i) => ({...it, rank: +it.rank! || i + 1}));
	if (mode === 'custom') return [...xs].sort((a, b) => (+a.play! || 0) - (+b.play! || 0));
	const byRank = [...xs].sort((a, b) => a.rank! - b.rank!);
	if (mode === 'countdown') return byRank.reverse();
	const top = byRank[0];
	const rest = byRank.slice(1);
	const r = rng(seed || 1);
	for (let i = rest.length - 1; i > 0; i--) {
		const j = Math.floor(r() * (i + 1));
		[rest[i], rest[j]] = [rest[j], rest[i]];
	}
	if (rest.length > 2 && rest[0].rank === byRank[byRank.length - 1].rank) [rest[0], rest[1]] = [rest[1], rest[0]];
	return top ? [...rest, top] : rest;
};

// "Ranking the best\nfootball moments" + "football moments" → coloured keyword spans, max 2 lines
const TitleText: React.FC<{text: string; keys: string[]; kw: string; fg: string}> = ({text, keys, kw, fg}) => {
	const lines = String(text || '').split('\n').slice(0, 2);
	const k = keys.map((s) => s.trim().toLowerCase()).filter(Boolean);
	const paint = (line: string) => {
		if (!k.length) return [line];
		const re = new RegExp('(' + k.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'ig');
		return line.split(re).map((s, i) => (k.includes(s.toLowerCase()) ? <span key={i} style={{color: kw}}>{s}</span> : <span key={i} style={{color: fg}}>{s}</span>));
	};
	return (
		<>
			{lines.map((l, i) => (
				<div key={i}>{paint(l)}</div>
			))}
		</>
	);
};

const RankReel: React.FC<SP> = ({p, proj}) => {
	const f = useCurrentFrame();
	const {fps, height, width} = useVideoConfig();
	const kw = p.kwColor || '#2dd4bf';
	const fg = p.fg || '#ffffff';
	const font = fontFamily(p.font || proj.font || 'Bahnschrift');
	const items: Item[] = Array.isArray(p.items) ? p.items.slice(0, 10) : [];
	const order = playOrder(items, p.order || 'shuffle', +p.seed || 7);
	const ranks = [...order].sort((a, b) => a.rank! - b.rank!);
	const intro = Math.max(0, +p.intro || 0);
	const titleH = height * (+p.titleBand || 0.15);
	const stroke = `${fsz(height, 7)}px #000`;
	const ladderSz = +p.ladderSize || 70;
	const ladderGap = fsz(height, 18);

	// slot timeline (frames)
	let t = Math.round(intro * fps);
	const slots = order.map((it) => {
		const d = Math.max(1, Math.round(Math.max(0.5, +it.dur! || 5) * fps));
		const s = {it, from: t, d};
		t += d;
		return s;
	});
	const curI = slots.findIndex((s) => f >= s.from && f < s.from + s.d);
	const cur = curI >= 0 ? slots[curI] : null;

	// fit: vertical sources (Shorts/Reels — the priority) fill the frame; a 16:9 fallback is shown WHOLE at full width
	// over a blurred copy of itself, under the ladder and ABOVE the bottom ~25% where Shorts/Reels/TikTok draw the
	// title, description and buttons (it used to sink there and get covered).
	const safeH = height * 0.75 - titleH;
	const ladderPx = fsz(height, ladderSz);
	const ladderH = height * 0.035 * 2 + ranks.length * (ladderPx * 1.18 + ladderGap);
	const fitOf = (it: Item) => (p.fit && p.fit !== 'auto' ? p.fit : (+it.aspect! || 0.5625) > 1.05 ? 'blur' : 'cover');
	const boxOf = (it: Item) => {
		const vh = Math.min(width / Math.max(0.3, +it.aspect! || 1.778), safeH);
		return {top: Math.max(0, Math.min(ladderH, safeH - vh)), h: vh};
	};

	return (
		<AbsoluteFill style={{background: '#000', overflow: 'hidden', fontFamily: font}}>
			{/* clips — each in its own Sequence so trimIn/startFrom are relative to its slot */}
			<AbsoluteFill style={{top: titleH}}>
				{slots.map((s, i) => {
					const u = src(proj, s.it.src);
					const under = s.it.vo && s.it.voDur ? Math.round((+s.it.voDur + 0.15) * fps) : 0;
					const base = p.clipVolume ?? 0.8;
					const duck = p.duckVolume ?? 0.25;
					return (
						<Sequence key={i} from={s.from} durationInFrames={s.d} layout="none">
							{(() => {
								const fit = fitOf(s.it);
								const pos = `${s.it.focusX ?? 50}% ${s.it.focusY ?? 50}%`;
								const sf = Math.round((+s.it.trimIn! || 0) * fps);
								const vol = (fr: number) => (under && fr < under ? duck : base);
								if (!u) return <AbsoluteFill style={{background: '#111'}} />;
								if (/\.(png|jpe?g|webp|gif)$/i.test(s.it.src || ''))
									return <AbsoluteFill><img src={u} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: pos}} /></AbsoluteFill>;
								if (fit !== 'blur')
									return <AbsoluteFill><Vid src={u} style={{width: '100%', height: '100%', objectFit: fit, objectPosition: pos}} startFrom={sf} volume={vol} /></AbsoluteFill>;
								const b = boxOf(s.it);
								return (
									<AbsoluteFill>
										<AbsoluteFill style={{filter: 'blur(28px) brightness(0.45)', transform: 'scale(1.15)'}}>
											<Vid src={u} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} startFrom={sf} />
										</AbsoluteFill>
										<div style={{position: 'absolute', left: 0, width: '100%', top: b.top, height: b.h, boxShadow: '0 0 40px rgba(0,0,0,.6)'}}>
											<Vid src={u} style={{width: '100%', height: '100%', objectFit: 'contain'}} startFrom={sf} volume={vol} />
										</div>
									</AbsoluteFill>
								);
							})()}
							{s.it.vo ? <Audio src={src(proj, s.it.vo)} volume={p.voVolume ?? 1.6} /> : null}
							{p.sting ? <Audio src={src(proj, p.sting)} volume={p.stingVolume ?? 0.6} /> : null}
						</Sequence>
					);
				})}
				{/* soft top/bottom shade so the ladder + captions read on any clip */}
				<AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 45%)'}} />
			</AbsoluteFill>

			{/* title band */}
			<AbsoluteFill style={{height: titleH, background: p.bandColor || '#000', justifyContent: 'center', alignItems: 'center', textAlign: 'center', padding: `0 ${width * 0.05}px`}}>
				<div style={{fontSize: fsz(height, +p.titleSize || 68), fontWeight: 900, lineHeight: 1.08, textTransform: p.upper === false ? 'none' : 'uppercase', transform: `scale(${0.85 + 0.15 * pop(f, fps)})`}}>
					<TitleText text={p.title} keys={String(p.keywords || '').split(',')} kw={kw} fg={fg} />
				</div>
			</AbsoluteFill>

			{/* rank ladder */}
			<div style={{position: 'absolute', left: width * 0.04, top: titleH + height * 0.035, display: 'flex', flexDirection: 'column', gap: ladderGap}}>
				{ranks.map((it) => {
					const on = cur && cur.it.rank === it.rank;
					// only the playing clip shows its label; past ones collapse back to the number (user, Oct 30 2026)
					const shown = !!on;
					const sl = slots.find((s) => s.it.rank === it.rank);
					const rp = sl ? ease(f, sl.from, sl.from + 10) : 0;
					return (
						<div key={it.rank} style={{display: 'flex', alignItems: 'baseline', gap: fsz(height, 14), fontSize: ladderPx, fontWeight: 900,
							color: on ? kw : fg, WebkitTextStroke: stroke, paintOrder: 'stroke fill', textShadow: on ? `0 0 ${fsz(height, 24)}px ${kw}aa` : 'none',
							transform: on ? `scale(${1 + 0.08 * pop(f - (sl?.from || 0), fps)})` : 'none', transformOrigin: 'left center'}}>
							<span>{it.rank}.</span>
							<span style={{opacity: shown ? rp : 0, transform: `translateX(${(1 - rp) * -30}px)`, display: 'inline-block', maxWidth: width * 0.78, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
								{shown ? it.label || '' : ''}
							</span>
						</div>
					);
				})}
			</div>

			{/* verdict caption (VO line) */}
			{/* off by default (user, Oct 30 2026: on-screen subtitles crowd the clip) — the VO still speaks the verdict */}
			{cur && cur.it.verdict && p.captions === true ? (
				<Sequence from={cur.from} durationInFrames={cur.d} layout="none">
					<AbsoluteFill style={fitOf(cur.it) === 'blur'
						? {justifyContent: 'flex-start', alignItems: 'center', paddingTop: titleH + boxOf(cur.it).top + boxOf(cur.it).h + fsz(height, 36), textAlign: 'center'}
						: {justifyContent: 'flex-end', alignItems: 'center', paddingBottom: height * 0.14, textAlign: 'center'}}>
						<div style={{maxWidth: width * 0.86, fontSize: fsz(height, +p.verdictSize || 74), fontWeight: 900, color: fg, WebkitTextStroke: stroke, paintOrder: 'stroke fill', lineHeight: 1.15}}>
							<AnimText text={cur.it.verdict} anim="word-pop" acc={kw} speed={1.4} />
						</div>
					</AbsoluteFill>
				</Sequence>
			) : null}

			{/* intro hook (optional): title-only beat */}
			{intro > 0 && f < intro * fps ? (
				<AbsoluteFill style={{top: titleH, justifyContent: 'center', alignItems: 'center', opacity: 1 - ease(f, intro * fps - 8, intro * fps)}}>
					<div style={{fontSize: fsz(height, 120), fontWeight: 900, color: kw, WebkitTextStroke: stroke, paintOrder: 'stroke fill',
						transform: `scale(${interpolate(f, [0, intro * fps], [0.9, 1.1], {extrapolateRight: 'clamp'})})`}}>{p.hook || 'WAIT FOR #1'}</div>
				</AbsoluteFill>
			) : null}
		</AbsoluteFill>
	);
};

const DEMO_ITEMS: Item[] = [
	{rank: 1, label: 'Instant Karma', dur: 5, verdict: 'Number one. Nobody saw that coming.'},
	{rank: 2, label: 'Red Card', dur: 5, verdict: 'The ref had seen enough.'},
	{rank: 3, label: 'Keeper Panic', dur: 5, verdict: ''},
	{rank: 4, label: 'Own Goal', dur: 5, verdict: ''},
	{rank: 5, label: 'Bicycle Kick', dur: 5, verdict: ''},
];

export const RANK_SCENES = {
	rankreel: {
		label: 'Rank Reel (ranking Short)', group: 'Social', icon: 'list', dur: 25, track: 'scene' as const, C: RankReel,
		fields: [
			{k: 'title', t: 'long' as const, label: 'Title (2 lines — Enter splits)', d: 'Ranking the best\nfootball moments'},
			{k: 'keywords', t: 'text' as const, label: 'Highlight words (comma)', d: 'football moments'},
			{k: 'kwColor', t: 'color' as const, label: 'Keyword colour', d: '#2dd4bf'},
			{k: 'items', t: 'json' as const, label: 'Clips [{src,label,rank,trimIn,dur,verdict,vo,voDur}]', d: DEMO_ITEMS},
			{k: 'order', t: 'select' as const, label: 'Play order', opts: ['shuffle', 'countdown', 'custom'], d: 'shuffle'},
			{k: 'seed', t: 'num' as const, label: 'Shuffle seed', min: 1, max: 9999, d: 7},
			{k: 'intro', t: 'num' as const, label: 'Hook intro (s)', min: 0, max: 3, step: 0.1, d: 0},
			{k: 'hook', t: 'text' as const, label: 'Hook text', d: 'WAIT FOR #1'},
			{k: 'captions', t: 'bool' as const, label: 'Verdict captions', d: false},
			{k: 'clipVolume', t: 'num' as const, label: 'Clip volume', min: 0, max: 2, step: 0.05, d: 0.8},
			{k: 'duckVolume', t: 'num' as const, label: 'Clip volume under VO', min: 0, max: 1, step: 0.05, d: 0.25},
			{k: 'voVolume', t: 'num' as const, label: 'VO volume', min: 0, max: 3, step: 0.05, d: 1.6},
			{k: 'sting', t: 'media' as const, label: 'Rank sting sound', accept: 'audio', d: ''},
			{k: 'titleSize', t: 'num' as const, label: 'Title size', min: 40, max: 140, d: 68},
			{k: 'ladderSize', t: 'num' as const, label: 'Ladder size', min: 30, max: 100, d: 70},
			{k: 'verdictSize', t: 'num' as const, label: 'Verdict caption size', min: 40, max: 110, d: 74},
			{k: 'titleBand', t: 'num' as const, label: 'Title band height', min: 0.12, max: 0.32, step: 0.01, d: 0.15},
			{k: 'fit', t: 'select' as const, label: 'Clip fit (auto: vertical fills, 16:9 shown whole on blur)', opts: ['auto', 'cover', 'blur', 'contain'], d: 'auto'},
		],
	},
};
