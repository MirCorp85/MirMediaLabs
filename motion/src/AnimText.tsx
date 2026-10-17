// Animated text with 24 presets. Splits into words/letters as the preset needs.
import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {ease, pop} from './lib';

type P = {text: string; anim?: string; style?: React.CSSProperties; speed?: number; delay?: number; color?: string; acc?: string};

export const AnimText: React.FC<P> = ({text, anim = 'rise', style, speed = 1, delay = 0, color, acc}) => {
	const f0 = useCurrentFrame();
	const {fps} = useVideoConfig();
	const f = (f0 - delay * fps) * speed;
	const s = String(text ?? '');
	const words = s.split(/(\s+)/);
	const letters = Array.from(s);
	const base: React.CSSProperties = {display: 'inline-block', whiteSpace: 'pre', color, ...style};

	const per = (units: string[], step: number, fn: (p: number, i: number) => React.CSSProperties) => (
		<span style={{...style, color}}>
			{units.map((u, i) => {
				const p = ease(f, i * step, i * step + 10);
				return (
					<span key={i} style={{display: 'inline-block', whiteSpace: 'pre', ...fn(p, i)}}>
						{u}
					</span>
				);
			})}
		</span>
	);

	switch (anim) {
		case 'none':
			return <span style={base}>{s}</span>;
		case 'fade':
			return <span style={{...base, opacity: ease(f, 0, 15)}}>{s}</span>;
		case 'drop':
			return <span style={{...base, opacity: ease(f, 0, 12), transform: `translateY(${(1 - pop(f, fps)) * -80}px)`}}>{s}</span>;
		case 'typewriter': {
			const n = Math.floor(Math.max(0, f) / 2);
			return (
				<span style={base}>
					{letters.slice(0, n).join('')}
					<span style={{opacity: Math.floor(f / 8) % 2 ? 0 : 1, color: acc}}>{n < letters.length ? '▌' : ''}</span>
				</span>
			);
		}
		case 'word-pop':
			return per(words, 4, (_p, i) => ({transform: `scale(${pop(f, fps, i * 4)})`}));
		case 'letter-pop':
			return per(letters, 1.5, (_p, i) => ({transform: `scale(${pop(f, fps, i * 1.5)})`}));
		case 'kinetic':
			return per(words, 5, (p, i) => ({transform: `translateY(${(1 - p) * 60}px) rotate(${(1 - p) * (i % 2 ? 8 : -8)}deg)`, opacity: p}));
		case 'glitch': {
			const j = f < 18 ? Math.sin(f * 7) * 12 : 0;
			return (
				<span style={{...base, position: 'relative', transform: `translateX(${j}px)`, textShadow: f < 18 ? `${-j / 2}px 0 #f0f, ${j / 2}px 0 #0ff` : undefined}}>
					{s}
				</span>
			);
		}
		case 'blur-in':
			return <span style={{...base, filter: `blur(${(1 - ease(f, 0, 18)) * 20}px)`, opacity: ease(f, 0, 18)}}>{s}</span>;
		case 'scale-in':
			return <span style={{...base, transform: `scale(${pop(f, fps)})`}}>{s}</span>;
		case 'slide-left':
			return <span style={{...base, transform: `translateX(${(1 - ease(f, 0, 18)) * 200}px)`, opacity: ease(f, 0, 12)}}>{s}</span>;
		case 'slide-right':
			return <span style={{...base, transform: `translateX(${(1 - ease(f, 0, 18)) * -200}px)`, opacity: ease(f, 0, 12)}}>{s}</span>;
		case 'wave':
			return per(letters, 1, (p, i) => ({transform: `translateY(${Math.sin(f / 6 + i / 2) * 8 + (1 - p) * 40}px)`, opacity: p}));
		case 'tracking':
			return <span style={{...base, letterSpacing: `${interpolate(ease(f, 0, 30), [0, 1], [0.6, 0.02])}em`, opacity: ease(f, 0, 15)}}>{s}</span>;
		case 'flip':
			return per(letters, 1.5, (p) => ({transform: `perspective(400px) rotateX(${(1 - p) * 90}deg)`, opacity: p}));
		case 'neon': {
			const fl = f < 20 ? (Math.floor(f / 3) % 2 ? 0.3 : 1) : 1;
			return <span style={{...base, opacity: fl, textShadow: `0 0 8px ${acc}, 0 0 24px ${acc}, 0 0 48px ${acc}`}}>{s}</span>;
		}
		case 'bounce':
			return per(words, 4, (_p, i) => ({transform: `translateY(${(1 - pop(f, fps, i * 4)) * -120}px)`}));
		case 'mask-up':
			return (
				<span style={{display: 'inline-block', overflow: 'hidden', verticalAlign: 'bottom'}}>
					<span style={{...base, transform: `translateY(${(1 - ease(f, 0, 16)) * 110}%)`}}>{s}</span>
				</span>
			);
		case 'split': {
			const p = ease(f, 0, 20);
			return (
				<span style={{...base, position: 'relative'}}>
					<span style={{clipPath: 'inset(0 0 50% 0)', display: 'inline-block', transform: `translateX(${(1 - p) * -120}px)`}}>{s}</span>
					<span style={{clipPath: 'inset(50% 0 0 0)', position: 'absolute', left: 0, top: 0, transform: `translateX(${(1 - p) * 120}px)`}}>{s}</span>
				</span>
			);
		}
		case 'shake':
			return <span style={{...base, transform: `translate(${f < 20 ? Math.sin(f * 3) * (20 - f) : 0}px, 0)`}}>{s}</span>;
		case 'rainbow':
			return per(letters, 1, (p, i) => ({color: `hsl(${(i * 25 + f * 4) % 360} 90% 65%)`, opacity: p}));
		case 'stamp': {
			const p = ease(f, 0, 8);
			return <span style={{...base, transform: `scale(${interpolate(p, [0, 1], [3, 1])}) rotate(${(1 - p) * -12}deg)`, opacity: p}}>{s}</span>;
		}
		case 'cascade':
			return per(letters, 2, (p) => ({transform: `translateY(${(1 - p) * -50}px)`, opacity: p, filter: `blur(${(1 - p) * 6}px)`}));
		case 'rise':
		default:
			return per(words, 3, (p) => ({transform: `translateY(${(1 - p) * 40}px)`, opacity: p}));
	}
};
