// Generic schematic for ANY subject (Signature): a Media Lab line-art pass of the hero still (silver lines on
// black, screen-blended onto the charcoal stage) revealed left→right, with callouts pinned at fractional image coords.
// Replaces the Roadster-only CarLines for episodes the EXPLAINED Producer writes.
import React from 'react';
import {Img} from 'remotion';
import {C, F, ramp} from './theme';
import {Callout, Fit, HudStage} from './kit';
import type {BeatProps} from './beats';

type Pin = {x: number; y: number; title: string; sub?: string; color?: string};
type Box = {x: number; y: number; w: number; h: number};

// image box in the 1600×900 schematic space (16:9 art, contained)
const BOX = {x: 120, y: 200, w: 1360, h: 650};
const ART_H = BOX.h, ART_W = (BOX.h * 16) / 9;
const AX = BOX.x + (BOX.w - ART_W) / 2, AY = BOX.y;
const px = (fx: number) => AX + fx * ART_W;
const py = (fy: number) => AY + fy * ART_H;

const COL: Record<string, string> = {amber: C.amber, silver: C.ink, cyan: C.ink, ink: C.ink, red: C.red, green: '#7BD88F'};

const layout = (pins: Pin[]) => {
	// left/right columns, labels stacked top→bottom with a minimum gap so they never overlap
	const out: (Pin & {side: 'l' | 'r'; ly: number; i: number})[] = [];
	(['l', 'r'] as const).forEach((side) => {
		const col = pins.map((p, i) => ({...p, i})).filter((p) => (p.x < 0.5) === (side === 'l')).sort((a, z) => a.y - z.y);
		let last = 200;
		col.forEach((p) => {
			const want = Math.max(270, Math.min(800, py(p.y)));
			const ly = Math.max(want, last + 100);
			last = ly;
			out.push({...p, side, ly});
		});
	});
	return out.sort((a, z) => a.i - z.i);
};

export const Diagram: React.FC<BeatProps> = ({t, dur, b, asset, hd}) => {
	const v = b.v || {};
	const art = asset(v.art) || (v.art && !String(v.art).includes('.') ? asset(v.art + '.png') : null);
	const reveal = ramp(t, 0.1, 1.8, (x) => x);
	const pins = layout((v.callouts || []) as Pin[]);
	const span = Math.max(1, dur * 0.6);
	return (
		<HudStage t={t}>
			{art && (
				<div style={{position: 'absolute', left: (AX / 1600) * 1920, top: (AY / 900) * 1080, width: (ART_W / 1600) * 1920, height: (ART_H / 900) * 1080,
					clipPath: `inset(0 ${(1 - reveal) * 100}% 0 0)`, mixBlendMode: 'screen', filter: 'grayscale(1) contrast(1.8) brightness(1.7) drop-shadow(0 0 2px rgba(255,255,255,.9)) drop-shadow(0 0 8px rgba(230,235,240,.45))'}}>
					<Img src={art} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
				</div>
			)}
			{art && reveal < 1 && <div style={{position: 'absolute', top: (AY / 900) * 1080, height: (ART_H / 900) * 1080, width: 3, left: ((AX + ART_W * reveal) / 1600) * 1920, background: C.ink, boxShadow: `0 0 22px ${C.ink}`}} />}
			<svg width="100%" height="100%" viewBox="0 0 1600 900" style={{position: 'absolute'}}>
				{(v.highlights || []).map((h: Box & {at?: number}, i: number) => {
					const p = ramp(t, h.at ?? 1.2 + i * 0.6, 0.5);
					const pulse = (t * 0.8 + i * 0.3) % 1;
					return (
						<g key={i} opacity={p}>
							<rect x={px(h.x)} y={py(h.y)} width={h.w * ART_W} height={h.h * ART_H} rx="12" fill={C.amber} fillOpacity=".14" stroke={C.amber} strokeWidth="2.5" />
							<rect x={px(h.x) - pulse * 10} y={py(h.y) - pulse * 10} width={h.w * ART_W + pulse * 20} height={h.h * ART_H + pulse * 20} rx="16" fill="none" stroke={C.amber} strokeWidth="1.5" opacity={1 - pulse} />
						</g>
					);
				})}
			</svg>
			{pins.map((p, k) => {
				const at = 1.4 + (k / Math.max(1, pins.length)) * span;
				const right = p.side === 'r';
				return (
					<Callout key={k} p={ramp(t, at, 0.9)} from={[px(p.x), py(p.y)]} elbow={[right ? 1130 : 470, p.ly]} end={[right ? 1560 : 40, p.ly]}
						title={p.title} sub={p.sub || ''} color={COL[p.color || 'silver'] || C.ink} align={right ? 'end' : 'start'} />
				);
			})}
			<div style={{position: 'absolute', left: 116, top: 96, opacity: ramp(t, 0.2, 0.6)}}>
				<Fit w={1690} nowrap style={{fontFamily: F.mono, fontSize: 28, letterSpacing: 6, color: C.amber}}>{v.tag || hd?.tag || ''}</Fit>
				<div style={{marginTop: 4}}><Fit w={1690} h={176} style={{fontFamily: F.head, fontWeight: 600, fontSize: 80, lineHeight: 1.05, color: C.ink}}>{v.title || ''}</Fit></div>
			</div>
		</HudStage>
	);
};
