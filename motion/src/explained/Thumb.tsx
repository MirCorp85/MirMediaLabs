// MIR EXPLAINED YouTube thumbnail (1280×720) in the Signature style: hero plate right, giant thin numeral left,
// amber rule, two-word hook, series tag. Variants pick the plate + hook so we can A/B the click-through.
import React from 'react';
import {AbsoluteFill, Img, getStaticFiles, staticFile} from 'remotion';
import {C, F} from './theme';
import {Grain, Vignette} from '../promo/fx';

const STATIC = new Set(getStaticFiles().map((f) => f.name));
const asset = (base: string, n: string) => (STATIC.has(base + n) ? staticFile(base + n) : null);

export type ThumbProps = {base: string; plate: string; number: string; unit: string; hook: string; tag: string; shift?: number; zoom?: number};

export const ExplainedThumb: React.FC<ThumbProps> = ({base, plate, number, unit, hook, tag, shift = 220, zoom = 1.08}) => {
	const src = asset(base, plate);
	return (
		<AbsoluteFill style={{background: C.studio0}}>
			{src && <Img src={src} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', transform: `translateX(${shift}px) scale(${zoom})`, transformOrigin: '70% 55%', filter: 'contrast(1.12) saturate(1.05)'}} />}
			<AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(4,4,6,.96) 0%, rgba(4,4,6,.82) 30%, rgba(4,4,6,.25) 55%, transparent 70%)'}} />
			<Vignette strength={0.6} />
			<div style={{position: 'absolute', left: 62, top: 70, fontFamily: F.mono, fontSize: 26, letterSpacing: 8, color: C.amber}}>{tag}</div>
			<div style={{position: 'absolute', left: 50, top: 108, fontFamily: F.num, fontWeight: 200, fontSize: 250, lineHeight: 1, letterSpacing: -10, color: '#fff', textShadow: '0 6px 40px rgba(0,0,0,.7)'}}>
				{number}<span style={{fontSize: 110, color: '#c9cdd3', marginLeft: 10, letterSpacing: 0}}>{unit}</span>
			</div>
			<div style={{position: 'absolute', left: 62, top: 390, height: 8, width: 230, background: C.amber, boxShadow: `0 0 24px ${C.amber}`}} />
			<div style={{position: 'absolute', left: 58, top: 420, width: 640, fontFamily: F.head, fontWeight: 700, fontSize: 92, lineHeight: 1.0, color: '#fff', textTransform: 'uppercase', textShadow: '0 6px 30px rgba(0,0,0,.8)'}}>{hook}</div>
			<Grain opacity={0.05} />
		</AbsoluteFill>
	);
};
