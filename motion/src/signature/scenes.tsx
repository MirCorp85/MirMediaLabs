// SIGNATURE — the house video style, as MIR MOTION scenes.
// Same components as MIR EXPLAINED episodes (src/explained), wrapped for the Motion Studio catalog so Motion Studio,
// the AI writer, MUSE, Series and Producer all build with it. Authored on a 1920×1080 stage and scaled to the project.
import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Field} from '../scenes';
import {Project, src} from '../lib';
import * as B from '../explained/beats';
import {Captions, Headline, HudStage, SpecPanel, VoLine} from '../explained/kit';
import {C} from '../explained/theme';

type SP = {p: Record<string, any>; proj: Project; durF: number};

const Fit: React.FC<{children: React.ReactNode; clear?: boolean}> = ({children, clear}) => {
	const {width, height} = useVideoConfig();
	const s = Math.min(width / 1920, height / 1080);
	return (
		<AbsoluteFill style={{background: clear ? 'transparent' : C.studio0, overflow: 'hidden'}}>
			<div style={{position: 'absolute', left: (width - 1920 * s) / 2, top: (height - 1080 * s) / 2, width: 1920, height: 1080, transform: `scale(${s})`, transformOrigin: '0 0'}}>{children}</div>
		</AbsoluteFill>
	);
};

const useLocal = (proj: Project, durF: number) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const asset = (n?: string) => (n && /^(lib:|ref:|https?:|data:|blob:)/.test(n) ? src(proj, n) : null);
	return {t: f / fps, dur: durF / fps, asset};
};

const wrap = (render: (x: {t: number; dur: number; asset: (n?: string) => string | null; p: any}) => React.ReactNode, clear = false): React.FC<SP> =>
	({p, proj, durF}) => {
		const L = useLocal(proj, durF);
		return <Fit clear={clear}>{render({...L, p})}</Fit>;
	};

const asList = (v: any): string[] => (Array.isArray(v) ? v.map((x) => (typeof x === 'string' ? x : x?.text || x?.name || '')).filter(Boolean) : String(v || '').split('\n').map((x) => x.trim()).filter(Boolean));

// generic schematic slide: headline + optional dimmed media on the right + spec panel rows
const SpecSlide: React.FC<{t: number; dur: number; p: any; asset: (n?: string) => string | null}> = ({t, dur, p, asset}) => {
	const rows = (Array.isArray(p.rows) ? p.rows : []).map((r: any, i: number, a: any[]) => ({k: String(r.k ?? r[0] ?? ''), v: String(r.v ?? r[1] ?? ''), hi: !!(r.hi ?? r[2]), at: 1.2 + i * (dur * 0.55 / Math.max(1, a.length))}));
	const m = asset(p.src);
	return (
		<HudStage t={t}>
			{m && <div style={{position: 'absolute', right: 0, top: 220, width: 1100, height: 700, opacity: 0.55, filter: 'grayscale(1) contrast(1.2) brightness(.8)', WebkitMaskImage: 'linear-gradient(90deg, transparent, #000 35%)'}}>
				<B.PlateMedia t={t} dur={dur} src={m} shift={0} push={0.04} />
			</div>}
			<Headline t={t} at={0.2} tag={p.tag || ''} title={p.title || ''} />
			{rows.length > 0 && <SpecPanel t={t} at={0.8} rows={rows} />}
			{p.note && <div style={{position: 'absolute', left: 116, bottom: 190, fontFamily: '"Consolas", monospace', fontSize: 24, letterSpacing: 3, color: C.hudLabel}}>{p.note}</div>}
		</HudStage>
	);
};

const SigCaptions: React.FC<SP> = ({p, proj, durF}) => {
	const {t, dur} = useLocal(proj, durF);
	let lines: VoLine[] = [];
	const ws = Array.isArray(p.words) ? p.words.filter((w: any) => w && w.w) : [];
	if (ws.length) {
		for (let i = 0; i < ws.length; i += 7) {
			const g = ws.slice(i, i + 7);
			lines.push({start: +g[0].s, dur: Math.max(0.3, +g[g.length - 1].e - +g[0].s), text: g.map((w: any) => w.w).join(' ')});
		}
	} else if (p.text) lines = [{start: 0.1, dur: Math.max(0.5, dur - 0.4), text: String(p.text)}];
	return <Fit clear><Captions t={t} lines={lines} /></Fit>;
};

const media = (label = 'Hero plate (studio shot)'): Field => ({k: 'src', t: 'media', label, accept: 'video,image', d: ''});
const tag: Field = {k: 'tag', t: 'text', label: 'Chapter tag (amber)', d: '01 — THE BIG IDEA'};

export const SIG_SCENES: Record<string, any> = {
	'sig-plate': {label: 'Signature · studio plate', group: 'Signature', icon: 'film', dur: 6, track: 'scene', fields: [media()],
		C: wrap(({t, dur, p, asset}) => <B.Plate t={t} dur={dur} b={{plate: p.src}} asset={asset} />)},
	'sig-number': {label: 'Signature · big number', group: 'Signature', icon: 'trending-up', dur: 6, track: 'scene',
		fields: [media(), {k: 'value', t: 'num', label: 'Value', d: 0.81}, {k: 'decimals', t: 'num', label: 'Decimals', min: 0, max: 3, d: 2}, {k: 'unit', t: 'text', label: 'Unit', d: 's'},
			{k: 'label', t: 'text', label: 'Label (amber caps)', d: 'ZERO TO 60 MPH'}, {k: 'sub', t: 'text', label: 'Sub line', d: ''}, {k: 'plain', t: 'bool', label: 'Year (no comma, counts up 11)', d: false}],
		C: wrap(({t, dur, p, asset}) => <B.BigNum t={t} dur={dur} b={{plate: p.src, v: {value: +p.value || 0, decimals: +p.decimals || 0, unit: p.unit || '', label: p.label || '', sub: p.sub || '', plain: !!p.plain}}} asset={asset} />)},
	'sig-chapter': {label: 'Signature · chapter card', group: 'Signature', icon: 'bookmark', dur: 2.6, track: 'scene',
		fields: [media(), {k: 'num', t: 'num', label: 'Chapter', min: 0, max: 99, d: 1}, {k: 'of', t: 'num', label: 'Of (0 = hide)', min: 0, max: 99, d: 0}, {k: 'title', t: 'text', label: 'Title', d: 'The big idea'}],
		C: wrap(({t, dur, p, asset}) => <B.Chapter t={t} dur={dur} b={{plate: p.src}} asset={asset} n={+p.num || 1} of={+p.of || 0} title={p.title || ''} />)},
	'sig-spec': {label: 'Signature · schematic spec', group: 'Signature', icon: 'sliders', dur: 8, track: 'scene',
		fields: [tag, {k: 'title', t: 'text', label: 'Headline', d: 'How it works'}, {k: 'rows', t: 'json', label: 'Spec rows [{k,v,hi}]', d: [{k: 'POWER', v: '1 MW'}, {k: 'VOLTAGE', v: '800 V'}, {k: 'CHARGE', v: '500 kW', hi: true}]},
			media('Optional subject (shown dimmed, right)'), {k: 'note', t: 'text', label: 'Footnote', d: ''}],
		C: wrap(({t, dur, p, asset}) => <SpecSlide t={t} dur={dur} p={p} asset={asset} />)},
	'sig-bars': {label: 'Signature · bars + verdict', group: 'Signature', icon: 'chart', dur: 8, track: 'scene',
		fields: [tag, {k: 'title', t: 'text', label: 'Headline', d: 'Where it comes from'}, {k: 'bars', t: 'json', label: 'Bars [{label,value,color: silver|amber|ink}]', d: [{label: 'Tires', value: 1.75, color: 'silver'}, {label: 'Thrusters', value: 1.65, color: 'amber'}]},
			{k: 'unit', t: 'text', label: 'Unit', d: 'g'}, {k: 'max', t: 'num', label: 'Scale max', d: 4}, {k: 'stamp', t: 'text', label: 'Verdict stamp (blank = none)', d: ''}],
		C: wrap(({t, dur, p, asset}) => <B.GBars t={t} dur={dur} asset={asset} b={{ch: -1, v: {tag: p.tag || '', title: p.title || '', unit: p.unit || '', max: +p.max || 1, stamp: p.stamp || '',
			bars: (Array.isArray(p.bars) ? p.bars : []).map((x: any) => [x.label ?? x[0], +(x.value ?? x[1]) || 0, ({silver: 'cyan', amber: 'amber', ink: 'ink'} as any)[x.color ?? x[2]] || 'cyan'])}}} />)},
	'sig-cards': {label: 'Signature · comparison cards', group: 'Signature', icon: 'grid', dur: 10, track: 'scene',
		fields: [tag, {k: 'title', t: 'text', label: 'Headline', d: 'Three options'},
			{k: 'cards', t: 'json', label: 'Cards [{tag,name,line1,line2,label,value,foot,color: silver|amber|red}]', d: [{tag: 'ROAD READY', name: 'Base', line1: '2 seats', line2: '', label: 'PRICE', value: '$50,000', foot: '', color: 'silver'}]}],
		C: wrap(({t, dur, p, asset}) => <B.Trims t={t} dur={dur} asset={asset} b={{v: {tag: p.tag || '', title: p.title || '', cards: Array.isArray(p.cards) ? p.cards : []}}} />)},
	'sig-list': {label: 'Signature · list (recap / questions)', group: 'Signature', icon: 'list', dur: 8, track: 'scene',
		fields: [tag, {k: 'title', t: 'text', label: 'Headline', d: 'In four lines'}, {k: 'items', t: 'list', label: 'Items', d: ['First point', 'Second point']}, {k: 'kind', t: 'select', label: 'Icons', opts: ['recap', 'questions'], d: 'recap'}],
		C: wrap(({t, dur, p, asset}) => <B.ListBeat t={t} dur={dur} asset={asset} kind={p.kind === 'questions' ? 'questions' : 'recap'} b={{v: {tag: p.tag || '', title: p.title || '', items: asList(p.items)}}} />)},
	'sig-formula': {label: 'Signature · formula / calculation', group: 'Signature', icon: 'code', dur: 8, track: 'scene',
		fields: [tag, {k: 'title', t: 'text', label: 'Headline', d: 'Check the math'}, {k: 'lines', t: 'list', label: 'Lines (last = result, amber)', d: ['a = Δv / t', 'a ≈ 3.4 g']}, {k: 'note', t: 'text', label: 'Note', d: ''}, {k: 'stamp', t: 'text', label: 'Verdict stamp', d: ''}],
		C: wrap(({t, dur, p, asset}) => <B.Formula t={t} dur={dur} asset={asset} b={{id: 'sig', v: {tag: p.tag || '', title: p.title || '', lines: asList(p.lines), note: p.note || '', stamp: p.stamp || ''}}} />)},
	'sig-photo': {label: 'Signature · real photo + credit', group: 'Signature', icon: 'image', dur: 6, track: 'scene',
		fields: [{k: 'src', t: 'media', label: 'Photo', accept: 'image', d: ''}, {k: 'credit', t: 'text', label: 'Credit (required for real photos)', d: 'IMAGE: SOURCE'}],
		C: wrap(({t, dur, p, asset}) => <B.Photo t={t} dur={dur} asset={(n) => asset(n)} b={{photo: p.src, v: {credit: p.credit || ''}}} />)},
	'sig-brand': {label: 'Signature · brand sting', group: 'Signature', icon: 'star', dur: 3.2, track: 'scene',
		fields: [{k: 'series', t: 'text', label: 'Series', d: 'MIR EXPLAINED'}, {k: 'title', t: 'text', label: 'Episode title', d: 'The big idea'}],
		C: wrap(({t, dur, p, asset}) => <B.Brand t={t} dur={dur} asset={asset} b={{}} series={p.series || 'MIR EXPLAINED'} title={p.title || ''} />)},
	'sig-endcard': {label: 'Signature · end card (like + subscribe + app)', group: 'Signature', icon: 'heart', dur: 8, track: 'scene',
		fields: [media(), {k: 'series', t: 'text', label: 'Series', d: 'MIR EXPLAINED'}, {k: 'title', t: 'text', label: 'Episode title', d: ''}],
		C: wrap(({t, dur, p, asset}) => <B.EndCard t={t} dur={dur} asset={asset} b={{plate: p.src}} series={p.series || 'MIR EXPLAINED'} title={p.title || ''} />)},
	'sig-captions': {label: 'Signature · captions (karaoke chunks)', group: 'Signature', icon: 'message', dur: 8, track: 'captions',
		fields: [{k: 'text', t: 'long', label: 'Text (auto-timed) — or use Auto-caption', d: ''}, {k: 'words', t: 'json', label: 'Word timings [{w,s,e}]', d: []}],
		C: SigCaptions},
};
