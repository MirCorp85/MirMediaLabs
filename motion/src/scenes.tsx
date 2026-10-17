// MIR MOTION scene types. Each entry = component + inspector schema + defaults.
// The schema is exported to JSON (schema.json) and drives the Motion Studio inspector, the Python API and the AI prop writer.
import React from 'react';
import {AbsoluteFill, Audio, Img, OffthreadVideo, Video, getRemotionEnvironment, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {useAudioData, visualizeAudio} from '@remotion/media-utils';
import {AnimText} from './AnimText';
import {DEF_PAL, Project, TEXT_ANIMS, ease, fontFamily, pop, src} from './lib';

export type Field = {k: string; t: 'text' | 'long' | 'num' | 'color' | 'select' | 'bool' | 'media' | 'medias' | 'list' | 'json'; label: string; opts?: string[]; min?: number; max?: number; step?: number; accept?: string; d?: any};
type SP = {p: Record<string, any>; proj: Project; durF: number};
type Scene = {label: string; group: string; icon: string; dur: number; track: 'scene' | 'overlay' | 'audio' | 'captions'; fields: Field[]; C: React.FC<SP>};

const pal = (proj: Project, p: any) => ({...DEF_PAL, ...(proj.palette || {}), ...(p.bg ? {bg: p.bg} : {}), ...(p.fg ? {fg: p.fg} : {}), ...(p.acc ? {acc: p.acc} : {})});
const anim: Field = {k: 'anim', t: 'select', label: 'Text animation', opts: TEXT_ANIMS, d: 'rise'};
const colors: Field[] = [
	{k: 'bg', t: 'color', label: 'Background', d: ''},
	{k: 'fg', t: 'color', label: 'Text colour', d: ''},
	{k: 'acc', t: 'color', label: 'Accent', d: ''},
];
const fsz = (h: number, v: number) => (v * h) / 1080;
const isRender = () => getRemotionEnvironment().isRendering;
const Vid: React.FC<any> = (a) => (isRender() ? <OffthreadVideo {...a} /> : <Video {...a} />);

// ── backgrounds ──
const Background: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const g = p.style || 'solid';
	let bg: string = c.bg;
	if (g === 'gradient') bg = `linear-gradient(${p.angle ?? 135}deg, ${c.bg}, ${c.acc})`;
	if (g === 'radial') bg = `radial-gradient(circle at 50% 50%, ${c.acc}55, ${c.bg} 70%)`;
	if (g === 'animated') bg = `linear-gradient(${(f * 0.6) % 360}deg, ${c.bg}, ${c.acc}, ${c.acc2 || c.bg})`;
	if (g === 'grid')
		bg = `linear-gradient(${c.acc}22 1px, transparent 1px) 0 ${f % 40}px/40px 40px, linear-gradient(90deg, ${c.acc}22 1px, transparent 1px) 0 0/40px 40px, ${c.bg}`;
	return <AbsoluteFill style={{background: bg}} />;
};

const Title: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const {height} = useVideoConfig();
	const al = p.align || 'center';
	return (
		<AbsoluteFill style={{background: p.transparent ? 'transparent' : c.bg, justifyContent: p.valign || 'center', alignItems: al === 'left' ? 'flex-start' : al === 'right' ? 'flex-end' : 'center', padding: '6%', textAlign: al}}>
			<div style={{fontFamily: fontFamily(p.font || proj.font), fontSize: fsz(height, p.size || 120), fontWeight: 800, lineHeight: 1.05, color: c.fg}}>
				<AnimText text={p.text} anim={p.anim} acc={c.acc} speed={p.speed || 1} />
			</div>
			{p.sub ? (
				<div style={{marginTop: fsz(height, 24), fontFamily: fontFamily(proj.font), fontSize: fsz(height, (p.size || 120) * 0.32), color: c.acc, letterSpacing: '.18em', textTransform: 'uppercase'}}>
					<AnimText text={p.sub} anim="fade" delay={0.4} />
				</div>
			) : null}
		</AbsoluteFill>
	);
};

const LowerThird: React.FC<SP> = ({p, proj, durF}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {height, fps} = useVideoConfig();
	const inP = ease(f, 0, 14);
	const outP = ease(f, durF - 12, durF);
	const w = inP * (1 - outP);
	const left = p.side !== 'right';
	return (
		<AbsoluteFill style={{justifyContent: 'flex-end', alignItems: left ? 'flex-start' : 'flex-end', padding: '0 5% 7%'}}>
			<div style={{display: 'flex', alignItems: 'stretch', transform: `scaleX(${w})`, transformOrigin: left ? 'left' : 'right'}}>
				<div style={{width: fsz(height, 10), background: c.acc}} />
				<div style={{background: `${c.bg}e6`, padding: `${fsz(height, 14)}px ${fsz(height, 28)}px`, opacity: ease(f, 8, 18) * (1 - outP)}}>
					<div style={{fontFamily: fontFamily(p.font || proj.font), fontSize: fsz(height, 48), fontWeight: 800, color: c.fg}}>
						<AnimText text={p.name} anim={p.anim || 'mask-up'} delay={6 / fps} />
					</div>
					<div style={{fontFamily: fontFamily(p.font || proj.font), fontSize: fsz(height, 26), color: c.acc, letterSpacing: '.12em', textTransform: 'uppercase'}}>{p.role}</div>
				</div>
			</div>
		</AbsoluteFill>
	);
};

// words: [{w, s, e}] seconds relative to the clip; or plain text (auto-timed evenly)
const autoWords = (p: any, dur: number) => {
	if (Array.isArray(p.words) && p.words.length) return p.words as {w: string; s: number; e: number}[];
	const ws = String(p.text || '').split(/\s+/).filter(Boolean);
	const step = dur / Math.max(1, ws.length);
	return ws.map((w, i) => ({w, s: i * step, e: (i + 1) * step}));
};
const lineGroups = (ws: {w: string; s: number; e: number}[], n: number) => {
	const out: (typeof ws)[] = [];
	for (let i = 0; i < ws.length; i += n) out.push(ws.slice(i, i + n));
	return out;
};

const Captions: React.FC<SP> = ({p, proj, durF}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {fps, height} = useVideoConfig();
	const t = f / fps;
	const ws = autoWords(p, durF / fps);
	const lines = lineGroups(ws, p.perLine || 5);
	const line = lines.find((l) => t >= l[0].s - 0.05 && t <= l[l.length - 1].e + 0.25);
	if (!line) return null;
	const style = p.style || 'pop';
	const pos = p.pos || 'bottom';
	return (
		<AbsoluteFill style={{justifyContent: pos === 'top' ? 'flex-start' : pos === 'middle' ? 'center' : 'flex-end', alignItems: 'center', padding: '6% 8%'}}>
			<div style={{fontFamily: fontFamily(p.font || proj.font), fontSize: fsz(height, p.size || 64), fontWeight: 900, textAlign: 'center', lineHeight: 1.2, background: style === 'box' ? `${c.bg}cc` : undefined, padding: style === 'box' ? '0.2em 0.5em' : undefined, borderRadius: 12, textShadow: style !== 'box' ? '0 4px 16px #000c, 0 0 2px #000' : undefined}}>
				{line.map((w, i) => {
					const on = t >= w.s && t < w.e;
					const done = t >= w.e;
					const sc = style === 'pop' && on ? 1 + 0.15 * (1 - ease(f, w.s * fps, w.s * fps + 5)) + 0.05 : 1;
					return (
						<span key={i} style={{display: 'inline-block', marginRight: '0.28em', transform: `scale(${sc})`, color: on ? c.acc : style === 'karaoke' && !done ? `${c.fg}88` : c.fg, opacity: style === 'reveal' && t < w.s ? 0 : 1}}>
							{p.upper ? w.w.toUpperCase() : w.w}
						</span>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

const Lyrics: React.FC<SP> = (a) => {
	const {p, proj, durF} = a;
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {fps, height} = useVideoConfig();
	const t = f / fps;
	const ws = autoWords(p, durF / fps);
	const lines = Array.isArray(p.lines) && p.lines.length ? (p.lines as any[]) : lineGroups(ws, p.perLine || 6);
	const idx = Math.max(0, lines.findIndex((l: any) => t <= l[l.length - 1].e + 0.1));
	const show = [lines[idx], lines[idx + 1]].filter(Boolean);
	return (
		<AbsoluteFill style={{background: p.transparent ? 'transparent' : `radial-gradient(circle at 50% 60%, ${c.acc}33, ${c.bg} 70%)`, justifyContent: p.pos === 'bottom' ? 'flex-end' : 'center', alignItems: 'center', padding: '8%'}}>
			{show.map((l: any[], li: number) => (
				<div key={idx + li} style={{fontFamily: fontFamily(p.font || proj.font), fontSize: fsz(height, li === 0 ? p.size || 78 : (p.size || 78) * 0.7), fontWeight: 900, textAlign: 'center', marginBottom: '0.4em', opacity: li === 0 ? 1 : 0.45, textShadow: '0 4px 20px #000a'}}>
					{l.map((w: any, i: number) => {
						const k = interpolate(t, [w.s, w.e], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
						return (
							<span key={i} style={{marginRight: '0.3em', backgroundImage: `linear-gradient(90deg, ${c.acc} ${k}%, ${c.fg} ${k}%)`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent'}}>
								{w.w}
							</span>
						);
					})}
				</div>
			))}
		</AbsoluteFill>
	);
};

const Media: React.FC<SP> = ({p, proj, durF}) => {
	const f = useCurrentFrame();
	const {fps} = useVideoConfig();
	const u = src(proj, p.src);
	if (!u) return <AbsoluteFill style={{background: '#111'}} />;
	const kb = p.kenburns || 'none';
	const k = f / Math.max(1, durF);
	const z = p.zoom || 1.18;
	const tr: Record<string, string> = {
		none: '',
		'zoom-in': `scale(${1 + (z - 1) * k})`,
		'zoom-out': `scale(${z - (z - 1) * k})`,
		'pan-left': `scale(${z}) translateX(${(0.5 - k) * 8}%)`,
		'pan-right': `scale(${z}) translateX(${(k - 0.5) * 8}%)`,
		'pan-up': `scale(${z}) translateY(${(0.5 - k) * 8}%)`,
	};
	const st: React.CSSProperties = {width: '100%', height: '100%', objectFit: p.fit || 'cover', transform: tr[kb] || '', filter: p.filter || undefined};
	const isVid = p.kind === 'video' || /\.(mp4|webm|mov|mkv)$/i.test(p.src || '');
	return (
		<AbsoluteFill style={{background: '#000', overflow: 'hidden', borderRadius: p.radius || 0}}>
			{isVid ? <Vid src={u} style={st} volume={p.mute ? 0 : p.volume ?? 1} startFrom={Math.round((p.trimIn || 0) * fps)} playbackRate={p.speed || 1} /> : <Img src={u} style={st} />}
		</AbsoluteFill>
	);
};

const Slideshow: React.FC<SP> = ({p, proj, durF}) => {
	const f = useCurrentFrame();
	const imgs: string[] = (p.images || []).filter(Boolean);
	if (!imgs.length) return <AbsoluteFill style={{background: pal(proj, p).bg}} />;
	const per = durF / imgs.length;
	const i = Math.min(imgs.length - 1, Math.floor(f / per));
	const lf = f - i * per;
	const k = lf / per;
	const fade = Math.min(1, lf / Math.min(15, per / 3));
	const dirs = ['zoom-in', 'pan-left', 'zoom-out', 'pan-right'];
	const d = dirs[i % dirs.length];
	const tr = d === 'zoom-in' ? `scale(${1 + 0.15 * k})` : d === 'zoom-out' ? `scale(${1.15 - 0.15 * k})` : d === 'pan-left' ? `scale(1.15) translateX(${(0.5 - k) * 6}%)` : `scale(1.15) translateX(${(k - 0.5) * 6}%)`;
	return (
		<AbsoluteFill style={{background: '#000', overflow: 'hidden'}}>
			{i > 0 ? <Img src={src(proj, imgs[i - 1])} style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'cover'}} /> : null}
			<Img src={src(proj, imgs[i])} style={{position: 'absolute', width: '100%', height: '100%', objectFit: 'cover', transform: tr, opacity: fade}} />
		</AbsoluteFill>
	);
};

const Chart: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {height} = useVideoConfig();
	const data: {label: string; value: number}[] = Array.isArray(p.data) ? p.data : [];
	const mx = Math.max(1, ...data.map((d) => +d.value || 0));
	return (
		<AbsoluteFill style={{background: c.bg, padding: '7%', fontFamily: fontFamily(proj.font), color: c.fg}}>
			<div style={{fontSize: fsz(height, 64), fontWeight: 800, marginBottom: '3%'}}>
				<AnimText text={p.title || ''} anim="rise" />
			</div>
			<div style={{flex: 1, display: 'flex', alignItems: 'flex-end', gap: '3%'}}>
				{data.map((d, i) => {
					const g = ease(f, 10 + i * 5, 40 + i * 5);
					return (
						<div key={i} style={{flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end'}}>
							<div style={{fontSize: fsz(height, 32), fontWeight: 700, color: c.acc, opacity: g}}>{Math.round((+d.value || 0) * g * 10) / 10}{p.suffix || ''}</div>
							<div style={{width: '100%', height: `${((+d.value || 0) / mx) * 75 * g}%`, background: i % 2 ? c.acc2 || c.acc : c.acc, borderRadius: 8}} />
							<div style={{fontSize: fsz(height, 26), marginTop: 8, opacity: 0.8}}>{d.label}</div>
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

const Stat: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {height} = useVideoConfig();
	const v = (+p.value || 0) * ease(f, 0, 45);
	const dec = p.decimals ?? (Number.isInteger(+p.value) ? 0 : 1);
	return (
		<AbsoluteFill style={{background: p.transparent ? 'transparent' : c.bg, justifyContent: 'center', alignItems: 'center', fontFamily: fontFamily(proj.font)}}>
			<div style={{fontSize: fsz(height, 220), fontWeight: 900, color: c.acc}}>{(p.prefix || '') + v.toFixed(dec) + (p.suffix || '')}</div>
			<div style={{fontSize: fsz(height, 48), color: c.fg, letterSpacing: '.1em', textTransform: 'uppercase'}}>
				<AnimText text={p.label || ''} anim="fade" delay={0.5} />
			</div>
		</AbsoluteFill>
	);
};

const Credits: React.FC<SP> = ({p, proj, durF}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {height} = useVideoConfig();
	const lines: {role: string; name: string}[] = Array.isArray(p.lines) ? p.lines : [];
	const total = height * 0.6 + lines.length * fsz(height, 110) + height;
	const y = interpolate(f, [0, durF], [height, height - total], {extrapolateRight: 'clamp'});
	return (
		<AbsoluteFill style={{background: c.bg, fontFamily: fontFamily(proj.font), color: c.fg, overflow: 'hidden'}}>
			<div style={{position: 'absolute', top: y, width: '100%', textAlign: 'center'}}>
				<div style={{fontSize: fsz(height, 90), fontWeight: 900, color: c.acc, marginBottom: fsz(height, 80)}}>{p.title || ''}</div>
				{lines.map((l, i) => (
					<div key={i} style={{marginBottom: fsz(height, 40)}}>
						<div style={{fontSize: fsz(height, 26), opacity: 0.65, letterSpacing: '.15em', textTransform: 'uppercase'}}>{l.role}</div>
						<div style={{fontSize: fsz(height, 48), fontWeight: 700}}>{l.name}</div>
					</div>
				))}
			</div>
		</AbsoluteFill>
	);
};

const Chapter: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {height} = useVideoConfig();
	return (
		<AbsoluteFill style={{background: c.bg, justifyContent: 'center', padding: '8%', fontFamily: fontFamily(p.font || proj.font)}}>
			<div style={{fontSize: fsz(height, 40), color: c.acc, letterSpacing: '.3em', opacity: ease(f, 0, 12)}}>CHAPTER {p.num ?? ''}</div>
			<div style={{height: 6, background: c.acc, width: `${ease(f, 5, 30) * 30}%`, margin: '2% 0'}} />
			<div style={{fontSize: fsz(height, 110), fontWeight: 900, color: c.fg}}>
				<AnimText text={p.title || ''} anim={p.anim || 'mask-up'} delay={0.3} />
			</div>
		</AbsoluteFill>
	);
};

const Recap: React.FC<SP> = (a) => {
	const {p, proj} = a;
	const c = pal(proj, p);
	const {height} = useVideoConfig();
	return (
		<AbsoluteFill>
			<div style={{position: 'absolute', inset: 0, filter: 'saturate(0.6) contrast(1.1)'}}>
				<Slideshow {...a} />
			</div>
			<AbsoluteFill style={{background: `linear-gradient(transparent 55%, ${c.bg}ee)`, justifyContent: 'flex-end', padding: '5%'}}>
				<div style={{fontFamily: fontFamily(proj.font), fontSize: fsz(height, 64), fontWeight: 900, color: c.fg}}>
					<AnimText text={p.title || 'Previously on…'} anim="tracking" />
				</div>
			</AbsoluteFill>
		</AbsoluteFill>
	);
};

const Logo: React.FC<SP> = ({p, proj, durF}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {fps, height} = useVideoConfig();
	const s = pop(f, fps);
	const ring = ease(f, 0, 30);
	return (
		<AbsoluteFill style={{background: p.transparent ? 'transparent' : c.bg, justifyContent: 'center', alignItems: 'center'}}>
			<div style={{position: 'absolute', width: height * 0.5, height: height * 0.5, borderRadius: '50%', border: `${fsz(height, 6)}px solid ${c.acc}`, transform: `scale(${0.4 + ring})`, opacity: 1 - ring}} />
			{p.src ? <Img src={src(proj, p.src)} style={{height: height * 0.32, transform: `scale(${s})`}} /> : null}
			{p.text ? (
				<div style={{fontFamily: fontFamily(p.font || proj.font), fontSize: fsz(height, 96), fontWeight: 900, color: c.fg, marginTop: '2%'}}>
					<AnimText text={p.text} anim={p.anim || 'tracking'} delay={0.3} />
				</div>
			) : null}
			<div style={{position: 'absolute', inset: 0, background: c.fg, opacity: interpolate(f, [durF - 6, durF], [0, 0.0], {extrapolateLeft: 'clamp'})}} />
		</AbsoluteFill>
	);
};

const Visualizer: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {fps, height} = useVideoConfig();
	const u = src(proj, p.src);
	const data = useAudioData(u);
	const n = p.bars || 48;
	const vals = data ? visualizeAudio({fps, frame: f + Math.round((p.offset || 0) * fps), audioData: data, numberOfSamples: 64}).slice(0, n) : new Array(n).fill(0.05);
	return (
		<AbsoluteFill style={{background: p.transparent ? 'transparent' : c.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column'}}>
			{p.title ? <div style={{fontFamily: fontFamily(proj.font), fontSize: fsz(height, 64), fontWeight: 900, color: c.fg, marginBottom: '4%'}}>{p.title}</div> : null}
			<div style={{display: 'flex', alignItems: 'center', gap: 6, height: '40%', width: '80%'}}>
				{vals.map((v: number, i: number) => (
					<div key={i} style={{flex: 1, height: `${Math.min(100, 6 + v * 260)}%`, background: i % 2 ? c.acc : c.acc2 || c.acc, borderRadius: 6}} />
				))}
			</div>
		</AbsoluteFill>
	);
};

const Sound: React.FC<SP> = ({p, proj}) => {
	const {fps} = useVideoConfig();
	const f = useCurrentFrame();
	const u = src(proj, p.src);
	if (!u) return null;
	const fi = (p.fadeIn || 0) * fps;
	return <Audio src={u} startFrom={Math.round((p.trimIn || 0) * fps)} volume={(v) => (p.volume ?? 1) * (fi ? Math.min(1, v / fi) : 1)} playbackRate={p.speed || 1} />;
};

const Shape: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const s = ease(f, 0, 18);
	const sh = p.shape || 'circle';
	const st: React.CSSProperties = {position: 'absolute', left: `${p.x ?? 50}%`, top: `${p.y ?? 50}%`, width: `${p.size ?? 20}%`, aspectRatio: '1', transform: `translate(-50%,-50%) scale(${s}) rotate(${(p.spin || 0) * f}deg)`, background: sh === 'ring' ? 'transparent' : c.acc, border: sh === 'ring' ? `8px solid ${c.acc}` : undefined, borderRadius: sh === 'square' ? 12 : '50%', opacity: p.opacity ?? 1};
	return (
		<AbsoluteFill>
			<div style={st} />
		</AbsoluteFill>
	);
};

const Code: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const f = useCurrentFrame();
	const {height} = useVideoConfig();
	const txt = String(p.code || '');
	const n = Math.floor(Math.max(0, f) * (p.cps || 1.5));
	return (
		<AbsoluteFill style={{background: c.bg, justifyContent: 'center', alignItems: 'center'}}>
			<div style={{width: '82%', background: '#16161d', borderRadius: 16, boxShadow: '0 30px 80px #0008', overflow: 'hidden'}}>
				<div style={{padding: 14, display: 'flex', gap: 8}}>{['#ff5f57', '#febc2e', '#28c840'].map((x) => <div key={x} style={{width: 14, height: 14, borderRadius: 7, background: x}} />)}</div>
				<pre style={{margin: 0, padding: '0 28px 28px', fontFamily: 'Consolas, monospace', fontSize: fsz(height, 30), color: '#e8e6e3', whiteSpace: 'pre-wrap'}}>
					{txt.slice(0, n)}
					<span style={{color: c.acc}}>▌</span>
				</pre>
			</div>
		</AbsoluteFill>
	);
};

const Quote: React.FC<SP> = ({p, proj}) => {
	const c = pal(proj, p);
	const {height} = useVideoConfig();
	return (
		<AbsoluteFill style={{background: c.bg, justifyContent: 'center', padding: '10%', fontFamily: fontFamily(p.font || proj.font)}}>
			<div style={{fontSize: fsz(height, 200), color: c.acc, lineHeight: 0.6}}>“</div>
			<div style={{fontSize: fsz(height, 68), fontWeight: 700, color: c.fg, lineHeight: 1.25}}>
				<AnimText text={p.text || ''} anim={p.anim || 'rise'} />
			</div>
			{p.by ? <div style={{marginTop: '3%', fontSize: fsz(height, 32), color: c.acc}}>— {p.by}</div> : null}
		</AbsoluteFill>
	);
};

const Split: React.FC<SP> = (a) => {
	const {p, proj} = a;
	const c = pal(proj, p);
	const {height} = useVideoConfig();
	return (
		<AbsoluteFill style={{flexDirection: p.flip ? 'row-reverse' : 'row', background: c.bg}}>
			<div style={{flex: 1, position: 'relative'}}>
				<Media {...a} />
			</div>
			<div style={{flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '5%', fontFamily: fontFamily(proj.font)}}>
				<div style={{fontSize: fsz(height, 72), fontWeight: 900, color: c.fg}}>
					<AnimText text={p.title || ''} anim={p.anim || 'rise'} />
				</div>
				<div style={{fontSize: fsz(height, 34), color: c.fg, opacity: 0.8, marginTop: '3%'}}>
					<AnimText text={p.body || ''} anim="fade" delay={0.5} />
				</div>
			</div>
		</AbsoluteFill>
	);
};

export const SCENES: Record<string, Scene> = {
	background: {label: 'Background', group: 'Basics', icon: 'layers', dur: 5, track: 'scene', C: Background, fields: [{k: 'style', t: 'select', label: 'Style', opts: ['solid', 'gradient', 'radial', 'animated', 'grid'], d: 'gradient'}, {k: 'angle', t: 'num', label: 'Angle', min: 0, max: 360, d: 135}, ...colors]},
	title: {label: 'Title card', group: 'Text', icon: 'type', dur: 4, track: 'scene', C: Title, fields: [{k: 'text', t: 'text', label: 'Title', d: 'Your title'}, {k: 'sub', t: 'text', label: 'Subtitle', d: ''}, anim, {k: 'size', t: 'num', label: 'Size', min: 30, max: 300, d: 120}, {k: 'align', t: 'select', label: 'Align', opts: ['center', 'left', 'right'], d: 'center'}, {k: 'valign', t: 'select', label: 'Vertical', opts: ['center', 'flex-start', 'flex-end'], d: 'center'}, {k: 'speed', t: 'num', label: 'Speed', min: 0.25, max: 4, step: 0.25, d: 1}, {k: 'transparent', t: 'bool', label: 'Transparent (overlay)', d: false}, ...colors]},
	lowerthird: {label: 'Lower third', group: 'Text', icon: 'user', dur: 5, track: 'overlay', C: LowerThird, fields: [{k: 'name', t: 'text', label: 'Name', d: 'Name'}, {k: 'role', t: 'text', label: 'Role / line 2', d: 'Role'}, {k: 'side', t: 'select', label: 'Side', opts: ['left', 'right'], d: 'left'}, anim, ...colors]},
	captions: {label: 'Captions', group: 'Text', icon: 'message', dur: 8, track: 'captions', C: Captions, fields: [{k: 'text', t: 'long', label: 'Text (auto-timed) — or use Auto-caption', d: ''}, {k: 'words', t: 'json', label: 'Word timings [{w,s,e}]', d: []}, {k: 'style', t: 'select', label: 'Style', opts: ['pop', 'karaoke', 'reveal', 'box', 'plain'], d: 'pop'}, {k: 'pos', t: 'select', label: 'Position', opts: ['bottom', 'middle', 'top'], d: 'bottom'}, {k: 'perLine', t: 'num', label: 'Words per line', min: 1, max: 12, d: 5}, {k: 'size', t: 'num', label: 'Size', min: 24, max: 160, d: 64}, {k: 'upper', t: 'bool', label: 'UPPERCASE', d: false}, ...colors]},
	lyrics: {label: 'Lyric video', group: 'Text', icon: 'music', dur: 30, track: 'scene', C: Lyrics, fields: [{k: 'text', t: 'long', label: 'Lyrics (auto-timed) — or Sync to song', d: ''}, {k: 'words', t: 'json', label: 'Word timings [{w,s,e}]', d: []}, {k: 'perLine', t: 'num', label: 'Words per line', min: 2, max: 14, d: 6}, {k: 'size', t: 'num', label: 'Size', min: 30, max: 160, d: 78}, {k: 'pos', t: 'select', label: 'Position', opts: ['center', 'bottom'], d: 'center'}, {k: 'transparent', t: 'bool', label: 'Transparent (overlay)', d: false}, ...colors]},
	quote: {label: 'Quote', group: 'Text', icon: 'message', dur: 6, track: 'scene', C: Quote, fields: [{k: 'text', t: 'long', label: 'Quote', d: 'Make it simple, but significant.'}, {k: 'by', t: 'text', label: 'By', d: ''}, anim, ...colors]},
	chapter: {label: 'Chapter card', group: 'Structure', icon: 'bookmark', dur: 3, track: 'scene', C: Chapter, fields: [{k: 'num', t: 'text', label: 'Number', d: '1'}, {k: 'title', t: 'text', label: 'Title', d: 'The beginning'}, anim, ...colors]},
	recap: {label: 'Recap — previously on', group: 'Structure', icon: 'rewind', dur: 8, track: 'scene', C: Recap, fields: [{k: 'title', t: 'text', label: 'Title', d: 'Previously on…'}, {k: 'images', t: 'medias', label: 'Stills', accept: 'image', d: []}, ...colors]},
	credits: {label: 'Credits roll', group: 'Structure', icon: 'list', dur: 12, track: 'scene', C: Credits, fields: [{k: 'title', t: 'text', label: 'Title', d: 'Credits'}, {k: 'lines', t: 'list', label: 'Lines (role | name)', d: [{role: 'Created by', name: 'MirCorp'}]}, ...colors]},
	logo: {label: 'Logo sting', group: 'Structure', icon: 'star', dur: 3, track: 'scene', C: Logo, fields: [{k: 'src', t: 'media', label: 'Logo image', accept: 'image', d: ''}, {k: 'text', t: 'text', label: 'Text', d: 'MIR MEDIA'}, anim, {k: 'transparent', t: 'bool', label: 'Transparent', d: false}, ...colors]},
	media: {label: 'Video / image', group: 'Media', icon: 'film', dur: 5, track: 'scene', C: Media, fields: [{k: 'src', t: 'media', label: 'File', accept: 'video,image', d: ''}, {k: 'fit', t: 'select', label: 'Fit', opts: ['cover', 'contain'], d: 'cover'}, {k: 'kenburns', t: 'select', label: 'Camera move', opts: ['none', 'zoom-in', 'zoom-out', 'pan-left', 'pan-right', 'pan-up'], d: 'none'}, {k: 'zoom', t: 'num', label: 'Move amount', min: 1, max: 2, step: 0.02, d: 1.18}, {k: 'trimIn', t: 'num', label: 'Start at (s)', min: 0, d: 0}, {k: 'speed', t: 'num', label: 'Speed', min: 0.25, max: 4, step: 0.25, d: 1}, {k: 'volume', t: 'num', label: 'Volume', min: 0, max: 2, step: 0.05, d: 1}, {k: 'mute', t: 'bool', label: 'Mute', d: false}, {k: 'filter', t: 'select', label: 'Look', opts: ['', 'grayscale(1)', 'sepia(0.7)', 'saturate(1.6)', 'contrast(1.3)', 'blur(6px)', 'brightness(0.6)', 'hue-rotate(180deg)'], d: ''}, {k: 'radius', t: 'num', label: 'Corner radius', min: 0, max: 200, d: 0}]},
	slideshow: {label: 'Slideshow (Ken Burns)', group: 'Media', icon: 'grid', dur: 15, track: 'scene', C: Slideshow, fields: [{k: 'images', t: 'medias', label: 'Images', accept: 'image', d: []}, ...colors]},
	split: {label: 'Split — media + text', group: 'Media', icon: 'layers', dur: 6, track: 'scene', C: Split, fields: [{k: 'src', t: 'media', label: 'Media', accept: 'video,image', d: ''}, {k: 'title', t: 'text', label: 'Title', d: 'Headline'}, {k: 'body', t: 'long', label: 'Body', d: ''}, {k: 'flip', t: 'bool', label: 'Media on right', d: false}, {k: 'kenburns', t: 'select', label: 'Camera move', opts: ['none', 'zoom-in', 'zoom-out'], d: 'zoom-in'}, anim, ...colors]},
	chart: {label: 'Bar chart', group: 'Data', icon: 'chart', dur: 6, track: 'scene', C: Chart, fields: [{k: 'title', t: 'text', label: 'Title', d: 'Results'}, {k: 'data', t: 'json', label: 'Data [{label,value}]', d: [{label: 'A', value: 3}, {label: 'B', value: 7}, {label: 'C', value: 5}]}, {k: 'suffix', t: 'text', label: 'Suffix', d: ''}, ...colors]},
	stat: {label: 'Big number', group: 'Data', icon: 'trending-up', dur: 4, track: 'scene', C: Stat, fields: [{k: 'value', t: 'num', label: 'Value', d: 100}, {k: 'prefix', t: 'text', label: 'Prefix', d: ''}, {k: 'suffix', t: 'text', label: 'Suffix', d: '%'}, {k: 'label', t: 'text', label: 'Label', d: 'growth'}, {k: 'transparent', t: 'bool', label: 'Transparent', d: false}, ...colors]},
	code: {label: 'Code window', group: 'Data', icon: 'code', dur: 8, track: 'scene', C: Code, fields: [{k: 'code', t: 'long', label: 'Code', d: 'print("hello MIR MEDIA LABS")'}, {k: 'cps', t: 'num', label: 'Chars per frame', min: 0.2, max: 10, step: 0.1, d: 1.5}, ...colors]},
	shape: {label: 'Shape', group: 'Basics', icon: 'circle', dur: 4, track: 'overlay', C: Shape, fields: [{k: 'shape', t: 'select', label: 'Shape', opts: ['circle', 'ring', 'square'], d: 'circle'}, {k: 'x', t: 'num', label: 'X %', min: 0, max: 100, d: 50}, {k: 'y', t: 'num', label: 'Y %', min: 0, max: 100, d: 50}, {k: 'size', t: 'num', label: 'Size %', min: 1, max: 150, d: 20}, {k: 'spin', t: 'num', label: 'Spin °/frame', min: -20, max: 20, d: 0}, {k: 'opacity', t: 'num', label: 'Opacity', min: 0, max: 1, step: 0.05, d: 1}, {k: 'acc', t: 'color', label: 'Colour', d: ''}]},
	visualizer: {label: 'Audio visualizer', group: 'Audio', icon: 'activity', dur: 20, track: 'scene', C: Visualizer, fields: [{k: 'src', t: 'media', label: 'Audio', accept: 'audio', d: ''}, {k: 'offset', t: 'num', label: 'Audio offset (s)', d: 0}, {k: 'title', t: 'text', label: 'Title', d: ''}, {k: 'bars', t: 'num', label: 'Bars', min: 8, max: 64, d: 48}, {k: 'transparent', t: 'bool', label: 'Transparent', d: false}, ...colors]},
	audio: {label: 'Audio (music / voice / SFX)', group: 'Audio', icon: 'volume', dur: 30, track: 'audio', C: Sound, fields: [{k: 'src', t: 'media', label: 'Audio', accept: 'audio,video', d: ''}, {k: 'volume', t: 'num', label: 'Volume', min: 0, max: 2, step: 0.05, d: 1}, {k: 'fadeIn', t: 'num', label: 'Fade in (s)', min: 0, max: 10, d: 0}, {k: 'trimIn', t: 'num', label: 'Start at (s)', min: 0, d: 0}, {k: 'speed', t: 'num', label: 'Speed', min: 0.5, max: 2, step: 0.05, d: 1}]},
};

export const schema = () =>
	Object.fromEntries(Object.entries(SCENES).map(([k, s]) => [k, {label: s.label, group: s.group, icon: s.icon, dur: s.dur, track: s.track, fields: s.fields}]));
