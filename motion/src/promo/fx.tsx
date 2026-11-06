// Shared cinematic helpers for the MML promo: palette, film grain, vignette, letterbox, flare, cursor.
import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, useCurrentFrame} from 'remotion';

export const GOLD = '#FFD27A';
export const AMBER = '#E8A040';
export const CREAM = '#FFE6A8';
export const INK = '#120d06';
export const FONT = '"Segoe UI", "Inter", system-ui, sans-serif';

export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const ease = Easing.bezier(0.22, 1, 0.36, 1);

export const Grain: React.FC<{opacity?: number}> = ({opacity = 0.09}) => {
	const f = useCurrentFrame();
	const seed = Math.floor(f / 2);
	return (
		<AbsoluteFill style={{pointerEvents: 'none', mixBlendMode: 'overlay', opacity}}>
			<svg width="100%" height="100%">
				<filter id={'g' + seed}>
					<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={seed} />
					<feColorMatrix type="saturate" values="0" />
				</filter>
				<rect width="100%" height="100%" filter={`url(#g${seed})`} />
			</svg>
		</AbsoluteFill>
	);
};

export const Vignette: React.FC<{strength?: number}> = ({strength = 0.75}) => (
	<AbsoluteFill style={{pointerEvents: 'none', background: `radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,${strength}) 100%)`}} />
);

/** 2.39:1 bars; open = 0 → full letterbox, 1 → no bars. */
export const Letterbox: React.FC<{open: number}> = ({open}) => {
	const bar = (1080 - 1920 / 2.39) / 2 * (1 - open);
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div style={{position: 'absolute', top: 0, left: 0, right: 0, height: bar, background: '#000'}} />
			<div style={{position: 'absolute', bottom: 0, left: 0, right: 0, height: bar, background: '#000'}} />
		</AbsoluteFill>
	);
};

/** Horizontal anamorphic streak sweeping across at progress p (0..1). */
export const Flare: React.FC<{p: number; y?: number; opacity?: number}> = ({p, y = 540, opacity = 1}) => {
	const x = interpolate(p, [0, 1], [-400, 2320]);
	return (
		<AbsoluteFill style={{pointerEvents: 'none', mixBlendMode: 'screen', opacity}}>
			<div style={{position: 'absolute', left: 0, right: 0, top: y - 3, height: 6,
				background: `linear-gradient(90deg, transparent, rgba(255,190,90,0.0) ${x / 19.2 - 30}%, rgba(255,220,150,0.95) ${x / 19.2}%, rgba(255,190,90,0) ${x / 19.2 + 30}%, transparent)`,
				filter: 'blur(2px)'}} />
			<div style={{position: 'absolute', left: x - 260, top: y - 260, width: 520, height: 520, borderRadius: '50%',
				background: 'radial-gradient(circle, rgba(255,230,170,0.85) 0%, rgba(255,170,60,0.25) 30%, transparent 65%)'}} />
		</AbsoluteFill>
	);
};

export const Dust: React.FC<{count?: number; seed?: string}> = ({count = 70, seed = 'd'}) => {
	const f = useCurrentFrame();
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			{new Array(count).fill(0).map((_, i) => {
				const x = random(seed + 'x' + i) * 1920 + Math.sin((f + i * 20) / 60) * 30;
				const y = ((random(seed + 'y' + i) * 1080 - f * (0.3 + random(seed + 's' + i) * 0.8)) % 1080 + 1080) % 1080;
				const s = 1 + random(seed + 'r' + i) * 3;
				return <div key={i} style={{position: 'absolute', left: x, top: y, width: s, height: s, borderRadius: s,
					background: CREAM, opacity: 0.25 + random(seed + 'o' + i) * 0.5, boxShadow: `0 0 ${s * 3}px ${GOLD}`}} />;
			})}
		</AbsoluteFill>
	);
};

export type CursorKey = {f: number; x: number; y: number; click?: boolean};

export const cursorAt = (keys: CursorKey[], f: number) => {
	if (f <= keys[0].f) return keys[0];
	for (let i = 0; i < keys.length - 1; i++) {
		const a = keys[i], b = keys[i + 1];
		if (f <= b.f) {
			const t = ease((f - a.f) / Math.max(1, b.f - a.f));
			// slight arc so motion feels hand-driven
			const arc = Math.sin(t * Math.PI) * Math.min(60, Math.hypot(b.x - a.x, b.y - a.y) * 0.08);
			return {f, x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t - arc};
		}
	}
	return keys[keys.length - 1];
};

/** Fake mouse pointer in the coordinate space of its parent. */
export const FakeCursor: React.FC<{keys: CursorKey[]; offset?: number}> = ({keys, offset = 0}) => {
	const f = useCurrentFrame() - offset;
	const p = cursorAt(keys, f);
	const click = keys.filter((k) => k.click).map((k) => f - k.f).find((d) => d >= 0 && d < 18);
	const press = click !== undefined && click < 6 ? 0.82 : 1;
	return (
		<>
			{click !== undefined && (
				<div style={{position: 'absolute', left: p.x - 40, top: p.y - 40, width: 80, height: 80, borderRadius: '50%',
					border: `4px solid ${GOLD}`, opacity: 1 - click / 18, transform: `scale(${0.3 + click / 12})`,
					boxShadow: `0 0 30px ${GOLD}`}} />
			)}
			<svg width="46" height="46" viewBox="0 0 24 24" style={{position: 'absolute', left: p.x - 4, top: p.y - 2,
				transform: `scale(${press})`, transformOrigin: '4px 2px', filter: 'drop-shadow(0 4px 8px rgba(0,0,0,.6))'}}>
				<path d="M4 2 L4 20 L9 15.5 L12.5 22 L15.5 20.6 L12.2 14.2 L19 14 Z" fill="#fff" stroke="#111" strokeWidth="1.3" strokeLinejoin="round" />
			</svg>
		</>
	);
};

/** Modern kinetic caption: masked word rise with motion blur, gold-gradient key word + highlight bar, glass sub pill, kinetic exit. */
export const Caption: React.FC<{text: string; sub?: string; at: number; dur: number; y?: number; size?: number; accent?: number}> = ({text, sub, at, dur, y = 860, size = 74, accent}) => {
	const f = useCurrentFrame() - at;
	if (f < 0 || f > dur) return null;
	const words = text.split(' ');
	const key = accent ?? words.length - 1;
	const exit = interpolate(f, [dur - 12, dur], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
	return (
		<div style={{position: 'absolute', left: 0, right: 0, top: y, textAlign: 'center', fontFamily: FONT,
			transform: `translateY(${-exit * 40}px)`, opacity: 1 - exit, filter: `blur(${exit * 12}px)`}}>
			<div style={{display: 'inline-flex', gap: size * 0.3, fontSize: size, fontWeight: 900, letterSpacing: -1, lineHeight: 1.1,
				textTransform: 'uppercase', fontStyle: 'italic'}}>
				{words.map((w, i) => {
					const t = interpolate(f, [i * 3, i * 3 + 14], [0, 1], {...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1)});
					const isKey = i === key;
					const bar = interpolate(f, [words.length * 3 + 4, words.length * 3 + 16], [0, 1], {...clamp, easing: ease});
					const shine = interpolate(f, [8, 40], [-40, 140], clamp);
					return (
						<span key={i} style={{position: 'relative', display: 'inline-block', overflow: 'hidden', padding: `0 ${size * 0.06}px ${size * 0.08}px`}}>
							{isKey && <span style={{position: 'absolute', left: 0, bottom: size * 0.1, height: size * 0.32, width: `${bar * 100}%`,
								background: `linear-gradient(90deg, ${AMBER}, ${GOLD})`, opacity: 0.35, borderRadius: 4}} />}
							<span style={{position: 'relative', display: 'inline-block', transform: `translateY(${(1 - t) * 110}%) skewY(${(1 - t) * 8}deg)`,
								filter: `blur(${(1 - t) * 6}px)`,
								...(isKey ? {backgroundImage: `linear-gradient(100deg, ${AMBER} ${shine - 30}%, #fff ${shine}%, ${GOLD} ${shine + 30}%)`,
									WebkitBackgroundClip: 'text', color: 'transparent', filter: `blur(${(1 - t) * 6}px) drop-shadow(0 0 18px rgba(255,180,80,.55))`}
									: {color: '#fff', textShadow: '0 4px 24px rgba(0,0,0,.75)'})}}>{w}</span>
						</span>
					);
				})}
			</div>
			{sub && (() => {
				const st = interpolate(f, [10, 24], [0, 1], {...clamp, easing: ease});
				return <div style={{display: 'flex', justifyContent: 'center', marginTop: 14}}>
					<div style={{padding: `${size * 0.1}px ${size * 0.34}px`, borderRadius: 999, fontSize: size * 0.3, letterSpacing: 4, fontWeight: 600,
						color: CREAM, textTransform: 'uppercase', background: 'rgba(20,14,6,.45)', backdropFilter: 'blur(14px)',
						border: '1px solid rgba(255,210,122,.45)', boxShadow: '0 8px 30px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.12)',
						opacity: st, transform: `translateY(${(1 - st) * 16}px) scale(${0.92 + 0.08 * st})`,
						clipPath: `inset(0 ${(1 - st) * 50}% 0 ${(1 - st) * 50}% round 999px)`}}>
						<span style={{display: 'inline-block', width: 8, height: 8, borderRadius: 8, background: GOLD, marginRight: 12, verticalAlign: 'middle',
							boxShadow: `0 0 10px ${GOLD}`, opacity: 0.5 + 0.5 * Math.sin(f / 4)}} />{sub}
					</div>
				</div>;
			})()}
		</div>
	);
};
