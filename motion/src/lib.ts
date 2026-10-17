// Shared helpers for MIR MOTION scenes: project model, media/font URL resolution, keyframes, text presets.
import type React from 'react';
import {Easing, interpolate, spring} from 'remotion';

export type KF = [number, number][]; // [seconds-from-clip-start, value]
export type Clip = {
	id: string;
	type: string;
	start: number; // seconds on the timeline
	dur: number; // seconds
	props: Record<string, any>;
	trans?: {type: string; dur: number}; // entrance transition
	out?: {type: string; dur: number}; // exit transition
	kf?: Record<string, KF>; // x,y,scale,rotate,opacity,blur
};
export type Track = {kind: 'scene' | 'overlay' | 'audio' | 'captions'; name?: string; mute?: boolean; hide?: boolean; clips: Clip[]};
export type Project = {
	w: number;
	h: number;
	fps: number;
	bg?: string;
	palette?: {bg: string; fg: string; acc: string; acc2?: string};
	font?: string; // MIR font id (bastion, orbit…) or CSS family
	mediaBase?: string; // "lib:x" → mediaBase + x
	refBase?: string; // "ref:x" → refBase + x (defaults to mediaBase + 'ref/')
	fontBase?: string;
	tracks: Track[];
};

export const DEF_PAL = {bg: '#0b0b10', fg: '#f4f1ea', acc: '#ffcc33', acc2: '#ff5a8a'};
export const MIR_FONTS = ['bastion', 'hollow', 'horizon', 'matrix', 'orbit', 'pixel', 'quill', 'stencil', 'vector', 'velocity'];

export const projectDuration = (p: Project) => {
	let end = 1;
	for (const t of p.tracks || []) for (const c of t.clips || []) end = Math.max(end, (+c.start || 0) + (+c.dur || 0));
	return end;
};

export const src = (p: Project, s?: string) => {
	if (!s) return '';
	if (/^(https?:|data:|blob:)/.test(s)) return s;
	const [kind, ...rest] = s.split(':');
	const name = rest.join(':');
	if (kind === 'ref') return (p.refBase || (p.mediaBase || 'media/') + 'ref/') + encodeURIComponent(name);
	if (kind === 'lib') return (p.mediaBase || 'media/') + encodeURIComponent(name);
	return (p.mediaBase || 'media/') + encodeURIComponent(s);
};

export const fontFamily = (f?: string) => (f && MIR_FONTS.includes(f) ? `MIR-${f}, system-ui, sans-serif` : f || 'system-ui, sans-serif');

// keyframe track → value at time t (seconds from clip start); linear w/ ease-in-out
export const kfAt = (k: KF | undefined, t: number, d: number) => {
	if (!k || !k.length) return d;
	if (k.length === 1) return k[0][1];
	const xs = k.map((x) => x[0]);
	const ys = k.map((x) => x[1]);
	return interpolate(t, xs, ys, {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
};

export const ease = (f: number, a: number, b: number, from = 0, to = 1) =>
	interpolate(f, [a, b], [from, to], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});

export const pop = (frame: number, fps: number, delay = 0) => spring({frame: frame - delay, fps, config: {damping: 14, stiffness: 160, mass: 0.6}});

// Transition styles (entrance when dir=1 is progress 0→1; exit uses 1→0)
export const TRANSITIONS = ['cut', 'fade', 'slide-left', 'slide-right', 'slide-up', 'wipe', 'iris', 'zoom', 'blur', 'glitch', 'flash', 'spin'];
export const transStyle = (type: string, p: number, w: number): React.CSSProperties => {
	const q = 1 - p;
	switch (type) {
		case 'fade':
			return {opacity: p};
		case 'slide-left':
			return {transform: `translateX(${q * w}px)`};
		case 'slide-right':
			return {transform: `translateX(${-q * w}px)`};
		case 'slide-up':
			return {transform: `translateY(${q * 100}%)`};
		case 'wipe':
			return {clipPath: `inset(0 ${q * 100}% 0 0)`};
		case 'iris':
			return {clipPath: `circle(${p * 75}% at 50% 50%)`};
		case 'zoom':
			return {transform: `scale(${0.6 + 0.4 * p})`, opacity: p};
		case 'blur':
			return {filter: `blur(${q * 30}px)`, opacity: p};
		case 'glitch':
			return {transform: `translateX(${Math.sin(p * 60) * q * 40}px)`, filter: `hue-rotate(${q * 180}deg)`, opacity: p > 0.15 ? 1 : p * 6};
		case 'flash':
			return {filter: `brightness(${1 + q * 4})`, opacity: Math.min(1, p * 3)};
		case 'spin':
			return {transform: `rotate(${q * -90}deg) scale(${p})`, opacity: p};
		default:
			return {};
	}
};

// Text animation presets (per-unit progress); used by Title/Text/LowerThird/Chapter
export const TEXT_ANIMS = [
	'fade', 'rise', 'drop', 'typewriter', 'word-pop', 'letter-pop', 'kinetic', 'glitch', 'blur-in', 'scale-in',
	'slide-left', 'slide-right', 'wave', 'tracking', 'flip', 'neon', 'bounce', 'mask-up', 'split', 'shake',
	'rainbow', 'stamp', 'cascade', 'none',
];
