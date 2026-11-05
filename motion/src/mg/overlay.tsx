// MIR MOTION GRAPHICS — in-scene data overlays + cinematic FX for story beats (user reference, Oct 28 2026: numbers live INSIDE
// the scene — a "0.20 s" timer over a smash, an "11 m" arrow on the pitch, a flip scoreboard "21 : 0", a "Normal 30 cm / You
// 3 mm" gauge, an "Eyes → Brain → Muscles" chain — and big moments get slow motion, an impact flash or a time-freeze).
import React from 'react';
import {S, backOut, c01, expoOut, inOut} from './style';

export type OverlayT = {type: string; value?: number; unit?: string; label?: string; a?: string; b?: string; av?: string; bv?: string; ratio?: number; items?: string[]; text?: string; at?: number};
export const OVERLAY_TYPES = ['timer', 'distance', 'score', 'gauge', 'chain', 'label'];
export const FX_TYPES = ['slowmo', 'impact', 'freeze', 'flash'];

const panel = (s: S, u: number): React.CSSProperties => {
	const p = s.pal;
	if (s.key === 'dusk' || s.id === 'signature') return {background: 'rgba(10,8,16,.55)', border: `${1.5 * u}px solid ${p.line}55`, borderRadius: 10 * u, backdropFilter: 'blur(6px)'};
	if (s.id === 'grid') return {background: p.ink, color: p.bg};
	if (s.id === 'liquid') return {background: 'rgba(255,255,255,.12)', borderRadius: 22 * u, boxShadow: `0 ${10 * u}px ${30 * u}px ${p.acc}55`};
	return {background: p.acc4 || '#FBF4E6', boxShadow: `${6 * u}px ${7 * u}px 0 rgba(59,42,23,.3)`};
};
const ink = (s: S) => (s.id === 'grid' ? s.pal.bg : s.id === 'paper' ? s.pal.dark : s.pal.ink);

export const Overlay: React.FC<{s: S; t: number; o: OverlayT; W: number; H: number; u: number}> = ({s, t, o, W, H, u}) => {
	const at = +(o.at ?? 0.6);
	if (!o || !o.type || t < at) return null;
	const p = s.pal, d = t - at, e = c01(d / 0.5), pop = s.enter(t, at);
	const font = (role: string, sz: number): React.CSSProperties => ({...s.font(role), fontSize: sz * u, lineHeight: 1, whiteSpace: 'nowrap'});
	if (o.type === 'timer') {
		const v = (+(o.value ?? 0)) * expoOut(c01(d / 1.2));
		const dec = Math.abs(+(o.value || 0)) < 10 ? 2 : 0;
		return (
			<div style={{position: 'absolute', right: W * 0.05, top: H * 0.1, padding: `${12 * u}px ${22 * u}px`, ...panel(s, u), opacity: e, transform: `translateY(${(1 - e) * -16 * u}px)`}}>
				{o.label ? <div style={{...font('label', 22), color: s.id === 'grid' ? p.bg : p.mute, marginBottom: 6 * u, letterSpacing: '0.12em'}}>{s.cased(o.label)}</div> : null}
				<div style={{...font('num', 64), color: s.id === 'grid' ? p.bg : p.acc}}>{v.toFixed(dec)}{o.unit ? ' ' + o.unit : ''}</div>
			</div>
		);
	}
	if (o.type === 'distance') {
		const x0 = W * 0.28, x1 = W * 0.72, y = H * 0.72, k = inOut(c01(d / 0.8));
		const col = s.id === 'grid' ? p.ink : p.line;
		return (
			<div style={{position: 'absolute', inset: 0}}>
				<svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
					<line x1={x0} y1={y} x2={x0 + (x1 - x0) * k} y2={y} stroke={col} strokeWidth={3 * u} strokeDasharray={`${10 * u} ${7 * u}`} />
					<line x1={x0} y1={y - 16 * u} x2={x0} y2={y + 16 * u} stroke={col} strokeWidth={3 * u} />
					{k > 0.98 ? <line x1={x1} y1={y - 16 * u} x2={x1} y2={y + 16 * u} stroke={col} strokeWidth={3 * u} /> : null}
				</svg>
				<div style={{position: 'absolute', left: (x0 + x1) / 2, top: y - 46 * u, transform: 'translateX(-50%)', opacity: c01((d - 0.5) * 3), ...font('head', 40), color: s.id === 'grid' ? p.ink : p.ink}}>{s.cased(o.label || '')}</div>
			</div>
		);
	}
	if (o.type === 'score') {
		const card = (txt: string, k: number) => {
			const f = c01((d - k * 0.25) / 0.45), flip = Math.cos(Math.min(1, f) * Math.PI);
			return (
				<div style={{minWidth: 150 * u, padding: `0 ${18 * u}px`, height: 190 * u, display: 'grid', placeItems: 'center', ...panel(s, u), background: s.id === 'grid' ? p.ink : '#F4EEE2', color: s.id === 'grid' ? p.bg : '#16121C',
					transform: `perspective(${600 * u}px) rotateX(${f < 0.5 ? 0 : 0}deg) scaleY(${Math.abs(flip) < 0.02 ? 0.02 : Math.abs(flip)})`, ...font('num', 130)}}>{f < 0.5 ? '0' : txt}</div>
			);
		};
		return (
			<div style={{position: 'absolute', left: W / 2, top: H * 0.2, transform: `translate(-50%,-50%) scale(${Math.max(0, pop) * 0.8})`, display: 'flex', alignItems: 'center', gap: 22 * u}}>
				{card(String(o.a ?? ''), 0)}
				<div style={{...font('num', 90), color: s.id === 'grid' ? p.ink : p.ink}}>:</div>
				{card(String(o.b ?? ''), 1)}
			</div>
		);
	}
	if (o.type === 'gauge') {
		const r = Math.max(0.02, Math.min(1, +(o.ratio ?? 0.1))), g = expoOut(c01(d / 1.0)), g2 = expoOut(c01((d - 0.6) / 1.0));
		const bar = (lab: string, val: string, frac: number, k: number, hi: boolean) => (
			<div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 * u}}>
				<div style={{width: 46 * u, height: 300 * u, background: 'rgba(255,255,255,.08)', borderRadius: s.id === 'liquid' ? 23 * u : 4 * u, display: 'flex', alignItems: 'flex-end', overflow: 'hidden', outline: s.id === 'grid' ? `${3 * u}px solid ${p.ink}` : undefined}}>
					<div style={{width: '100%', height: `${frac * k * 100}%`, background: hi ? p.acc : (s.id === 'grid' ? p.ink : p.mute)}} />
				</div>
				<div style={{...font('label', 22), color: s.id === 'grid' ? p.ink : p.mute}}>{s.cased(lab)}</div>
				<div style={{...font('num', 40), color: hi ? p.acc : (s.id === 'grid' ? p.ink : p.ink)}}>{val}</div>
			</div>
		);
		return (
			<div style={{position: 'absolute', right: W * 0.06, top: H * 0.16, padding: `${18 * u}px ${26 * u}px`, ...panel(s, u), background: s.id === 'grid' ? p.bg : (panel(s, u).background as string), display: 'flex', gap: 30 * u, opacity: e}}>
				{bar(o.a || 'Normal', o.av || '', 1, g, false)}
				{bar(o.b || 'You', o.bv || '', r, g2, true)}
			</div>
		);
	}
	if (o.type === 'chain') {
		const items = (o.items || []).slice(0, 5);
		return (
			<div style={{position: 'absolute', left: W / 2, top: H * 0.1, transform: 'translateX(-50%)', display: 'flex', alignItems: 'center', gap: 18 * u, opacity: e}}>
				{items.map((it, i) => {
					const on = d > 0.3 + i * 0.6;
					return (
						<React.Fragment key={i}>
							{i ? <div style={{...font('head', 34), color: on ? p.acc : p.mute, opacity: on ? 1 : 0.5}}>→</div> : null}
							<div style={{...font('head', 34), padding: `${8 * u}px ${16 * u}px`, ...(on ? panel(s, u) : {}), color: on ? (s.id === 'grid' ? p.bg : p.acc) : (s.id === 'grid' ? p.ink : p.mute),
								transform: `scale(${on ? 1 + 0.08 * Math.max(0, 1 - (d - 0.3 - i * 0.6) * 3) : 1})`}}>{s.cased(it)}</div>
						</React.Fragment>
					);
				})}
			</div>
		);
	}
	// label: a callout near the hero's head
	return (
		<div style={{position: 'absolute', left: W * 0.62, top: H * 0.24, transform: `scale(${Math.max(0, pop)}) rotate(${s.id === 'paper' ? -4 : 0}deg)`, padding: `${10 * u}px ${20 * u}px`, ...panel(s, u), ...font('head', 46), color: s.id === 'grid' ? p.bg : p.acc}}>
			{s.cased(o.text || o.label || '')}
		</div>
	);
};

// cinematic FX layered over the scene
export const Fx: React.FC<{s: S; t: number; fx?: string; at?: number; W: number; H: number; u: number}> = ({s, t, fx, at = 0.8, W, H, u}) => {
	if (!fx) return null;
	const p = s.pal, d = t - at;
	if (fx === 'slowmo') {
		return (
			<div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
				<div style={{position: 'absolute', inset: 0, background: 'radial-gradient(circle at 50% 48%, transparent 40%, rgba(20,30,60,.35))', mixBlendMode: 'multiply'}} />
				<svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
					{[0, 1, 2].map((k) => {
						const ph = ((t * 0.5 + k / 3) % 1);
						return <circle key={k} cx={W / 2} cy={H * 0.48} r={(0.15 + ph * 0.6) * Math.min(W, H)} fill="none" stroke={s.id === 'grid' ? p.ink : '#FFFFFF'} strokeWidth={2 * u} opacity={(1 - ph) * 0.25} />;
					})}
				</svg>
			</div>
		);
	}
	if (fx === 'freeze') {
		const k = c01(d * 4);
		return <div style={{position: 'absolute', inset: 0, pointerEvents: 'none', background: `rgba(120,170,255,${0.16 * k})`, mixBlendMode: 'screen',
			boxShadow: `inset 0 0 ${180 * u}px rgba(160,200,255,${0.35 * k})`}} />;
	}
	if (d < 0 || d > 1.2) return null;
	if (fx === 'flash') return <div style={{position: 'absolute', inset: 0, background: '#FFFFFF', opacity: Math.max(0, 0.85 - d * 2.4), pointerEvents: 'none'}} />;
	// impact: flash + shockwave ring + short shake handled by the caller
	const r = expoOut(c01(d / 0.6)) * Math.max(W, H) * 0.7;
	return (
		<div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
			<div style={{position: 'absolute', inset: 0, background: '#FFFFFF', opacity: Math.max(0, 0.6 - d * 3)}} />
			<svg style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
				<circle cx={W / 2} cy={H * 0.5} r={r} fill="none" stroke={s.id === 'grid' ? p.acc : p.acc3 || p.acc} strokeWidth={10 * u * (1 - c01(d / 0.8))} opacity={1 - c01(d / 0.8)} />
			</svg>
		</div>
	);
};
// time warp for the actor under an FX (slow motion plays at a quarter speed after the moment, freeze stops it)
export const fxTime = (fx: string | undefined, t: number, at = 0.8) => (fx === 'slowmo' && t > at ? at + (t - at) * 0.28 : fx === 'freeze' && t > at ? at : t);
export const fxShake = (fx: string | undefined, t: number, at = 0.8, u = 1) => (fx === 'impact' && t > at && t < at + 0.45 ? `translate(${Math.sin(t * 90) * 8 * u * (1 - (t - at) / 0.45)}px, ${Math.cos(t * 70) * 5 * u * (1 - (t - at) / 0.45)}px)` : '');
export {backOut};
