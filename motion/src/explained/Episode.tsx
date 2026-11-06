// MIR EXPLAINED episode renderer: plays a resolved episode JSON (explained_build.py) as one composition.
// Mode changes get the signature transitions: studio→HUD = blueprint dissolve, HUD→studio = blur-in. SFX are placed
// automatically on picture accents and kept ~12 dB under the narrator; music beds duck while anyone speaks.
import React from 'react';
import {AbsoluteFill, Audio, Img, Sequence, getStaticFiles, interpolate, random, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, F, clamp, ramp} from './theme';
import {Captions, Fit, VoLine} from './kit';
import {Figure, figFor} from './figures';
import * as B from './beats';
import {Diagram} from './Diagram';
import roadster from './episodes/roadster.json';

export const EPISODES: Record<string, any> = {roadster};
const FPS = 30;
export const episodeFrames = (slug: string) => Math.ceil((EPISODES[slug]?.total || 10) * FPS);

const STATIC = new Set(getStaticFiles().map((f) => f.name));
const VISUAL_MODES = ['studio', 'photo', 'end', 'brand', 'card'];

const BeatView: React.FC<{b: any; t: number; ep: any; asset: (n?: string) => string | null}> = ({b, t, ep, asset}) => {
	// hd = this beat's own chapter header; legacy = the hand-built Roadster episode, the only one allowed its baked-in art/labels
	const chap = (ep.chapters || []).find((c: any) => c.n === b.ch);
	const hd = {tag: chap ? `${String(b.ch).padStart(2, '0')} — ${String(chap.title || '').toUpperCase()}` : '', title: chap?.title || ''};
	const p = {t, dur: b.dur, b, asset, hd, legacy: ep.base === 'episodes/roadster/'};
	const title = ep.meta.title, series = ep.meta.series;
	switch (b.v.c) {
		case 'plate': return <B.Plate {...p} />;
		case 'bignum': return <B.BigNum {...p} />;
		case 'photo': return <B.Photo {...p} />;
		case 'brand': return <B.Brand {...p} title={title} series={series} />;
		case 'chapter': return <B.Chapter {...p} n={b.ch} of={ep.chapters.length - 1} title={ep.chapters.find((c: any) => c.n === b.ch)?.title || ''} />;
		case 'timeline': return <B.Timeline {...p} />;
		case 'compare': return <B.Compare {...p} />;
		case 'powertrain': return <B.Powertrain {...p} />;
		case 'spec': return <B.Spec {...p} />;
		case 'fans': return <B.Fans {...p} />;
		case 'gbars': return <B.GBars {...p} />;
		case 'wing': return <B.Wing {...p} />;
		case 'midroll': return <B.Midroll {...p} />;
		case 'thrusters': return <B.Thrusters {...p} />;
		case 'formula': return <B.Formula {...p} />;
		case 'trims': return <B.Trims {...p} />;
		case 'questions': return <B.ListBeat {...p} kind="questions" />;
		case 'recap': return <B.ListBeat {...p} kind="recap" />;
		case 'endcard': return <B.EndCard {...p} title={title} series={series} />;
		case 'diagram': return <Diagram {...p} />;
		default: return <AbsoluteFill style={{background: '#000'}} />;
	}
};

// still frame of the previous studio beat, used as the "before" layer of the blueprint dissolve
const prevStill = (prev: any, asset: (n?: string) => string | null) => {
	if (!prev) return null;
	if (prev.photo) return asset(prev.photo);
	const n = prev.plate;
	if (!n) return null;
	if (/\.png$/.test(n)) return asset(n);
	const assetKey = String(n).replace(/^pl_/, 'st_').replace(/\.mp4$/, '');
	return asset(assetKey + '.png') || asset(n.replace('.mp4', '') === 'launch' ? 'studio.png' : 'studio.png');
};

export type Vertical = {hook: string; label?: string};
export const Episode: React.FC<{slug?: string; ep?: any; vertical?: Vertical}> = ({slug, ep: given, vertical}) => {
	const ep = given || EPISODES[slug || 'roadster'];
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const T = f / fps;
	const asset = (n?: string) => (n && STATIC.has(ep.base + n) ? staticFile(ep.base + n) : null);
	const beats: any[] = ep.beats;

	const lines: VoLine[] = beats.filter((b) => b.cap && b.vo).map((b) => ({start: b.start + b.voAt, dur: b.dur - b.voAt - 0.55, text: b.cap}));
	const speaking = (x: number) => lines.some((l) => x >= l.start - 0.15 && x <= l.start + l.dur + 0.1);

	// automatic SFX cues: [file, time, volume, length, skip]. Oct 18 (user): a sound on EVERY scene change, and a
	// different one each time — each episode has its own pool (ep.sfxPool: whoosh/boom/tick takes made by
	// explained_build) dealt out in a seeded order (ep.sfxSeed; "Redo sound effects" changes it) so two cuts in a row
	// never sound the same. Episodes without a pool fall back to the v1 library file of that kind.
	const pool: Record<string, string[]> = ep.sfxPool || {};
	const dealt: Record<string, number> = {};
	const order: Record<string, number[]> = {};
	const deal = (kind: string): [string, number] => {
		const files = (pool[kind] || []).map((n) => n.replace(/\.mp3$/, ''));
		if (!files.length) return ['sfx_' + kind, kind === 'boom' ? 0.3 : 0];
		const k = (dealt[kind] = (dealt[kind] ?? -1) + 1);
		const cycle = Math.floor(k / files.length);
		if (k % files.length === 0) {           // a fresh shuffle per round, never starting with the last sound played
			const perm = files.map((_, i) => i).sort((a, z) => random(`sfx${ep.sfxSeed ?? 0}-${kind}-${cycle}-${a}`) - random(`sfx${ep.sfxSeed ?? 0}-${kind}-${cycle}-${z}`));
			const last = order[kind]?.[files.length - 1];
			if (files.length > 1 && perm[0] === last) perm.push(perm.shift()!);
			order[kind] = perm;
		}
		return [files[order[kind][k % files.length]], 0];
	};
	const sfx: [string, number, number, number, number][] = [];
	const cue = (kind: string, at: number, vol: number, len: number) => { const [f, skip] = deal(kind); sfx.push([f, at, vol, len, skip]); };
	beats.forEach((b, i) => {
		const prev = beats[i - 1];
		const pm = prev ? (VISUAL_MODES.includes(prev.mode) ? 'studio' : prev.mode) : null;
		const m = VISUAL_MODES.includes(b.mode) ? 'studio' : b.mode;
		if (b.mode === 'card') cue('boom', b.start + 0.05, 0.13, 1.3);
		else if (b.mode === 'brand') cue('boom', b.start + 0.1, 0.16, 1.6);
		else if (pm && prev.mode !== 'card' && b.id !== 'tail') cue('whoosh', b.start - 0.15, pm !== m ? 0.1 : 0.075, 0.9);
		if (b.v.c === 'thrusters' && b.v.stage === 'plume') sfx.push(['sfx_blast', b.start + b.dur * 0.25, 0.09, 0.6, 0]);
		if (b.v.c === 'thrusters' && b.v.stage === 'rocket') sfx.push(['sfx_blast', b.start + 1.4, 0.08, 0.6, 0]);
		if (b.v.stamp) cue('boom', b.start + b.dur - (b.v.c === 'gbars' ? 2.6 : 2.2), 0.12, 1.0);
		if (b.v.c === 'endcard') { cue('tick', b.start + 2.0, 0.08, 0.15); cue('tick', b.start + 3.2, 0.08, 0.15); }
		if (b.v.c === 'midroll') cue('tick', b.start + 2.0, 0.07, 0.15);
	});

	// music: each bed plays from its chapter to the next bed's chapter, 2 s crossfades, ducked under narration
	// (cuts/Shorts may hold only some chapters: a bed whose chapter isn't present starts at the cut's start only if it's
	//  the bed that covers the first beat; beds shorter than 4 s are dropped so the fade envelope stays valid)
	const firstCh = beats[0]?.ch ?? 0;
	const music: any[] = ep.music || [];
	const coverIdx = music.reduce((k: number, m: any, i: number) => (m.fromChapter <= firstCh ? i : k), 0);
	const chStart = (n: number) => beats.find((b) => b.ch >= n && b.id !== 'tail')?.start;
	const starts = music.map((m: any, i: number) => (i === coverIdx ? 0 : i < coverIdx ? undefined : chStart(m.fromChapter)));
	const beds = music.map((m: any, i: number) => {
		const from = starts[i];
		const nxt = starts.slice(i + 1).find((x: any) => x !== undefined);
		return {...m, from, to: nxt !== undefined ? nxt + 2 : ep.total};
	}).filter((m: any) => m.from !== undefined && m.to - m.from >= 4);

	const chips = factChips(beats);
	const visual = (
		<>
			{beats.map((b, i) => {
				const prev = beats[i - 1];
				const from = Math.round(b.start * fps);
				const dur = Math.round(b.dur * fps);
				const t = T - b.start;
				const intoHud = prev && VISUAL_MODES.includes(prev.mode) && !VISUAL_MODES.includes(b.mode);
				const intoStudio = prev && !VISUAL_MODES.includes(prev.mode) && VISUAL_MODES.includes(b.mode);
				const fadeIn = b.mode === 'card' || b.mode === 'brand' ? ramp(t, 0, 0.35) : 1;
				const ps = intoHud ? prevStill(prev, asset) : null;
				return (
					<Sequence key={b.id} from={from} durationInFrames={dur + (intoHud ? 0 : 0)}>
						<AbsoluteFill style={{opacity: fadeIn, filter: intoStudio ? `blur(${(1 - ramp(t, 0, 0.6)) * 14}px)` : undefined}}>
							<BeatView b={b} t={t} ep={ep} asset={asset} />
						</AbsoluteFill>
						{ps && t < 1.3 && (
							<AbsoluteFill style={{opacity: 1 - ramp(t, 0.15, 1.1)}}>
								<Img src={ps} style={{width: '100%', height: '100%', objectFit: 'cover', transform: 'translateX(150px) scale(1.05)', transformOrigin: '80% 60%', filter: `grayscale(1) brightness(${0.75 - 0.3 * ramp(t, 0, 1)}) contrast(1.25)`}} />
															</AbsoluteFill>
						)}
					</Sequence>
				);
			})}
			{chips.filter((c) => T >= c.at - 0.2 && T <= c.at + c.len + 0.5).map((c, i) => <FactChip key={i} c={c} T={T} />)}
		</>
	);
	const audio = (
		<>
			{beats.filter((b) => b.vo).map((b) => (
				<Sequence key={'vo' + b.id} from={Math.round((b.start + b.voAt) * fps)}><Audio src={asset(b.vo)!} /></Sequence>
			))}
			{sfx.map(([n, at, vol, len, skip], i) => {
				const s = asset(n + '.mp3') || asset(n + '.wav');
				const lenF = Math.round(len * fps);
				return s && <Sequence key={'sfx' + i} from={Math.max(0, Math.round(at * fps))} durationInFrames={lenF}>
					<Audio src={s} trimBefore={Math.round(skip * fps)} volume={(fr) => vol * interpolate(fr, [0, 2, lenF * 0.45, lenF], [0, 1, 1, 0], clamp)} />
				</Sequence>;
			})}
			{beds.map((m: any) => {
				const s = asset(m.name + '.mp3');
				const from = Math.round(m.from * fps), len = Math.round((m.to - m.from) * fps);
				return s && len > 0 && <Sequence key={m.name} from={from} durationInFrames={len}>
					<Audio src={s} loop volume={(fr) => {
						const x = fr / fps, g = m.from + x;
						const env = interpolate(x, [0, 2, m.to - m.from - 2, m.to - m.from], [0, 1, 1, 0], clamp);
						const tail = interpolate(g, [ep.total - 4, ep.total], [1, 0], clamp);
						return 0.22 * env * tail * (speaking(g) ? 0.35 : 1);
					}} />
				</Sequence>;
			})}
		</>
	);
	const fadeIn = <AbsoluteFill style={{background: '#000', opacity: 1 - ramp(T, 0, 0.6), pointerEvents: 'none'}} />;
	if (vertical) return <VerticalShort T={T} total={ep.total} visual={visual} lines={lines} audio={audio} fadeIn={fadeIn} v={vertical} ep={ep} />;
	return (
		<AbsoluteFill style={{background: '#000'}}>
			{visual}
			<Captions t={T} lines={lines} />
			{fadeIn}
			{audio}
		</AbsoluteFill>
	);
};

export const RoadsterEpisode: React.FC = () => <Episode slug="roadster" />;

// ── fact chips (Oct 18): a number spoken over a picture beat ("over 700 million regular players") pops up on the dark left
// side as a drawn card — figure + counting number + the words after it — timed to the word like the captions.
type Chip = {at: number; len: number; value: number; dec: number; pre: string; suf: string; label: string; fig: string | null};
const NUM = /(\$)?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(\s?(?:%|percent\b|million\b|billion\b|thousand\b|trillion\b))?((?:\s+[A-Za-z][\w'-]*){0,3})/g;
const factChips = (beats: any[]): Chip[] => {
	const out: Chip[] = [];
	beats.forEach((b) => {
		if (!b.cap || !b.vo || !['plate', 'photo'].includes(b.v?.c)) return;
		const text: string = b.cap, start = b.start + b.voAt, dur = b.dur - b.voAt - 0.55;
		const total = text.split(' ').reduce((n, w) => n + w.length + 1, 0);
		let m: RegExpExecArray | null;
		NUM.lastIndex = 0;
		while ((m = NUM.exec(text))) {
			const raw = m[2].replace(/,/g, ''), v = Number(raw), unit = (m[3] || '').trim();
			if (!Number.isFinite(v) || (!unit && !m[1] && v >= 1900 && v <= 2100) || (!unit && !m[1] && v < 10)) continue;   // years, small counts
			const at = start + (m.index / Math.max(1, total)) * dur * 0.94;
			const label = (m[4] || '').trim().replace(/[.,;:!?]+$/, '').split(/\s+/).filter((w) => !/^(and|or|but|the|a|an|of|in|on|to|with|for|its|it's|than|that)$/i.test(w)).slice(0, 3).join(' ');
			out.push({at, len: Math.min(3.6, b.start + b.dur - at - 0.4), value: v, dec: raw.includes('.') ? raw.split('.')[1].length : 0, pre: m[1] || '',
				suf: unit === 'percent' ? '%' : unit, label, fig: figFor(label, null) ?? figFor(unit, null) ?? figFor(text, 'chart')});
			break;                                       // one chip per beat
		}
	});
	return out.filter((c) => c.len > 1.2);
};
const FactChip: React.FC<{c: Chip; T: number}> = ({c, T}) => {
	const t = T - c.at;
	const o = interpolate(t, [0, 0.35, c.len, c.len + 0.4], [0, 1, 1, 0], clamp);
	const n = c.value * ramp(t, 0.1, 1.2, (x) => 1 - Math.pow(1 - x, 3));
	return (
		<div style={{position: 'absolute', left: 116, top: 300, opacity: o, transform: `translateX(${(1 - o) * -40}px)`, display: 'flex', alignItems: 'center', gap: 28,
			padding: '26px 38px 26px 28px', borderRadius: 20, background: 'rgba(8,8,10,.62)', border: '1px solid rgba(255,255,255,.14)', boxShadow: '0 20px 60px rgba(0,0,0,.5)'}}>
			<Figure id={c.fig} size={120} t={T} draw={ramp(t, 0.05, 1.1, (x) => x)} stroke={2.4} />
			<div>
				<Fit w={600} nowrap style={{fontFamily: F.num, fontWeight: 200, fontSize: 108, lineHeight: 1, color: '#fff', letterSpacing: -3}}>
					{c.pre}{n.toLocaleString('en-US', {minimumFractionDigits: c.dec, maximumFractionDigits: c.dec})}<span style={{fontSize: 52, color: C.quiet, marginLeft: 10, letterSpacing: 0}}>{c.suf}</span>
				</Fit>
				<div style={{height: 3, width: 110 * ramp(t, 0.3, 0.6), background: C.amber, margin: '14px 0 12px', boxShadow: `0 0 12px ${C.amber}`}} />
				<Fit w={600} nowrap style={{fontFamily: F.head, fontWeight: 600, fontSize: 28, letterSpacing: 6, color: C.amber, textTransform: 'uppercase'}}>{c.label}</Fit>
			</div>
		</div>
	);
};

// ── 9:16 Short (Signature vertical): blurred cover of the same frame behind, the 16:9 frame in the middle,
// series tag + hook on top, big karaoke captions under it, subscribe pill + "full video" line at the bottom.
const VerticalShort: React.FC<{T: number; total: number; visual: React.ReactNode; lines: VoLine[]; audio: React.ReactNode; fadeIn: React.ReactNode; v: Vertical; ep: any}> =
	({T, total, visual, lines, audio, fadeIn, v, ep}) => {
	const stage = (scale: number, extra: React.CSSProperties) => (
		<div style={{position: 'absolute', width: 1920, height: 1080, transform: `scale(${scale})`, transformOrigin: '0 0', overflow: 'hidden', ...extra}}>{visual}</div>
	);
	const head = ramp(T, 0.2, 0.6);
	const end = ramp(T, total - 3.2, 0.5);
	return (
		<AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
			<div style={{position: 'absolute', left: -(1920 * 1.78 - 1080) / 2, top: 0, filter: 'blur(38px) brightness(.38) saturate(1.1)'}}>{stage(1.78, {})}</div>
			<div style={{position: 'absolute', left: 0, top: 640, width: 1080, height: 608, boxShadow: '0 30px 90px rgba(0,0,0,.75)'}}>{stage(1080 / 1920, {})}</div>
			<div style={{position: 'absolute', left: 70, right: 70, top: 200, opacity: head, transform: `translateY(${(1 - head) * 20}px)`}}>
				<div style={{fontFamily: F.mono, fontSize: 34, letterSpacing: 9, color: C.amber}}>{v.label || ep.meta.series}</div>
				<div style={{height: 6, width: 200, background: C.amber, boxShadow: `0 0 20px ${C.amber}`, margin: '26px 0 28px'}} />
				<Fit w={940} h={330} style={{fontFamily: F.head, fontWeight: 700, fontSize: 92, lineHeight: 1.02, color: '#fff', textShadow: '0 6px 30px rgba(0,0,0,.8)'}}>{v.hook}</Fit>
			</div>
			<VCaptions T={T} lines={lines} />
			<div style={{position: 'absolute', left: 0, right: 0, bottom: 150, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22, transform: `scale(${1 + 0.12 * end})`}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 16, padding: '20px 44px', borderRadius: 60, background: '#E5322D', color: '#fff', fontFamily: F.head, fontWeight: 600, fontSize: 44, letterSpacing: 3}}>
					SUBSCRIBE <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 16V11C6 7.7 8.7 5 12 5C15.3 5 18 7.7 18 11V16L19.5 18H4.5Z M10 20.5C10.4 21.3 11.1 21.7 12 21.7C12.9 21.7 13.6 21.3 14 20.5" /></svg>
				</div>
				<div style={{fontFamily: F.head, fontSize: 38, color: '#d9dde3', opacity: 0.6 + 0.4 * end}}>Full breakdown on the channel</div>
			</div>
			{fadeIn}
			{audio}
		</AbsoluteFill>
	);
};

// vertical captions: ≤5-word chunks, wrapped inside the 9:16 frame, words light up as they're spoken
const VCaptions: React.FC<{T: number; lines: VoLine[]}> = ({T, lines}) => {
	const l = lines.find((x) => T >= x.start - 0.1 && T <= x.start + x.dur + 0.25);
	if (!l) return null;
	const words = l.text.split(' ');
	const total = words.reduce((n, w) => n + w.length + 1, 0);
	let acc = 0;
	const timed = words.map((w) => { const at = l.start + (acc / total) * l.dur * 0.94; acc += w.length + 1; return {w, at}; });
	const chunks: {w: string; at: number}[][] = [[]];
	timed.forEach((x) => { const c = chunks[chunks.length - 1]; c.push(x); if (c.length >= 5 || (c.length >= 2 && /[.,?!:]$/.test(x.w))) chunks.push([]); });
	const live = chunks.filter((c) => c.length);
	const chunk = [...live].reverse().find((c) => T >= c[0].at - 0.05) || live[0];
	const pop = ramp(T, chunk[0].at - 0.05, 0.15);
	return (
		<div style={{position: 'absolute', left: 60, right: 60, top: 1300, height: 300, display: 'flex', flexWrap: 'wrap', alignContent: 'center', justifyContent: 'center', columnGap: 20, rowGap: 6,
			fontFamily: F.head, fontWeight: 700, fontSize: 76, lineHeight: 1.1, textShadow: '0 4px 24px rgba(0,0,0,.9)', transform: `scale(${0.94 + 0.06 * pop})`}}>
			{chunk.map((x, i) => <span key={i} style={{color: T >= x.at ? (/[0-9]/.test(x.w) ? C.amber : '#fff') : 'rgba(255,255,255,.4)'}}>{x.w}</span>)}
		</div>
	);
};

// a Short = chosen beats re-timed back to back, plus a 3 s studio tail for the subscribe beat
export const makeCut = (slug: string, ids: string[], tailPlate = 'studio_rear.png') => makeCutFrom(EPISODES[slug], ids, tailPlate);
export const makeCutFrom = (src: any, ids: string[], tailPlate = 'studio_rear.png') => {
	let t = 0;
	const beats = ids.map((id) => src.beats.find((b: any) => b.id === id)).filter(Boolean).map((b: any) => {
		const nb = {...b, start: Math.round(t * 1000) / 1000};
		t += b.dur;
		return nb;
	});
	beats.push({id: 'tail', ch: beats[beats.length - 1]?.ch ?? 0, mode: 'studio', plate: tailPlate, v: {c: 'plate'}, cap: '', start: t, dur: 3.2, voAt: 0, vo: null});
	t += 3.2;
	return {...src, beats, total: Math.round(t * 1000) / 1000};
};

export const SHORTS: Record<string, {ids: string[]; hook: string}> = {
	'roadster-060': {ids: ['b02', 'b19', 'b20', 'b24', 'b25'], hook: '0–60 in 0.81 s. How?'},
	'roadster-fan': {ids: ['b13', 'b14', 'b15', 'b16'], hook: 'It sucks itself onto the road'},
	'roadster-fly': {ids: ['b01', 'b26', 'b27'], hook: 'Can the Tesla Roadster actually fly?'},
};
export const shortFrames = (key: string) => Math.ceil(makeCut('roadster', SHORTS[key].ids).total * FPS);
export const RoadsterShort: React.FC<{k: string}> = ({k}) => <Episode ep={makeCut('roadster', SHORTS[k].ids)} vertical={{hook: SHORTS[k].hook}} />;

// ── generic compositions (EXPLAINED Producer): the resolved episode JSON arrives as inputProps
export const ExplainedEpisode: React.FC<{ep: any}> = ({ep}) => <Episode ep={ep} />;
export const ExplainedShortGeneric: React.FC<{ep: any; cut: {ids: string[]; hook: string; tail?: string}}> = ({ep, cut}) =>
	<Episode ep={makeCutFrom(ep, cut.ids, cut.tail || ep.tailPlate || 'studio_rear.png')} vertical={{hook: cut.hook}} />;
export const shortTotal = (ep: any, cut: {ids: string[]}) => makeCutFrom(ep, cut.ids).total;
