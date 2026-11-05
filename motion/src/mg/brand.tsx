// MIR MOTION GRAPHICS — the MIR MEDIA LABS brand pieces every motion video carries (user rule, Oct 28 2026):
//   Flask   the MML flask + orbit mark (geometry from promo/LogoOpen.tsx) drawn in each style's materials
//   Btn     the like / subscribe buttons of the end card, pressed by an animated cursor
// The intro + end card SCENES that use them live in scenes.tsx (mg-intro / mg-endcard).
import React from 'react';
import {S, backOut, c01, lerp, springT} from './style';

const dash = (p: number) => ({strokeDasharray: 1, strokeDashoffset: 1 - c01(p)});
const seg = (d: number, a: number, b: number) => c01((d - a) / (b - a));

export const Flask: React.FC<{s: S; draw: number; ring: number; bubbles: number; spin?: number; size: number}> = ({s, draw, ring, bubbles, spin = 0, size}) => {
	const p = s.pal;
	const st = {
		signature: {line: p.line, m: p.acc, ring: p.acc, bub: p.acc, w: 22, glow: `drop-shadow(0 0 18px ${p.acc}66)`, fill: 'none'},
		grid: {line: p.ink, m: p.acc, ring: p.acc, bub: p.acc, w: 40, glow: 'none', fill: 'none'},
		liquid: {line: '#FFFFFF', m: p.acc3, ring: p.acc, bub: p.acc4 || p.acc, w: 34, glow: `drop-shadow(0 0 26px ${p.acc2})`, fill: 'none'},
		paper: {line: p.acc2, m: p.acc, ring: p.acc3, bub: p.acc, w: 36, glow: 'drop-shadow(10px 12px 0 rgba(59,42,23,.32))', fill: p.acc4 || '#FBF4E6'},
	}[s.id];
	const ang = spin * Math.PI * 2;
	const node = (t: number) => [512 + Math.cos(ang + t) * 310, 540 + Math.sin(ang + t) * 92];
	const body = 'M452 255 V420 L290 700 L305 760 Q312 785 335 785 H690 Q713 785 720 760 L735 700 L572 420 V255';
	return (
		<svg viewBox="0 0 1024 1024" width={size} height={size} style={{overflow: 'visible', filter: st.glow}}>
			{s.id === 'paper' ? <path d={body + ' Z'} fill={st.fill} opacity={c01(draw * 3)} /> : null}
			{s.id === 'liquid' ? <circle cx={512} cy={540} r={380 * springT(draw * 0.9)} fill={`url(#mgfl)`} opacity={0.9} /> : null}
			<defs>
				<radialGradient id="mgfl" cx=".35" cy=".3" r=".8"><stop offset="0" stopColor="#fff" stopOpacity=".5" /><stop offset=".3" stopColor={p.acc2} /><stop offset="1" stopColor={p.acc} /></radialGradient>
			</defs>
			<g fill="none" stroke={st.line} strokeWidth={st.w} strokeLinecap={s.id === 'grid' ? 'square' : 'round'} strokeLinejoin="round">
				<path pathLength={1} d="M421 240 H603" style={dash(seg(draw, 0, 0.15))} />
				<path pathLength={1} d={body} style={dash(seg(draw, 0.1, 0.65))} />
				<path pathLength={1} d="M362 602 H662" style={dash(seg(draw, 0.5, 0.7))} />
				<path pathLength={1} d="M397 752 V655 L512 728 L627 655 V752" stroke={st.m} strokeWidth={st.w * 1.15} style={dash(seg(draw, 0.6, 0.95))} />
			</g>
			<g fill={st.bub}>
				{[[490, 530, 17], [540, 487, 13], [518, 560, 11]].map(([x, y, r], i) => {
					const t = c01((bubbles - i * 0.2) / 0.5);
					return <circle key={i} cx={x} cy={y + (1 - t) * 50} r={r * t * (s.id === 'grid' ? 1.3 : 1)} opacity={t} />;
				})}
			</g>
			<g opacity={c01(ring * 1.5)} transform="rotate(-3 512 540)">
				<ellipse cx={512} cy={540} rx={310 * (0.6 + 0.4 * ring)} ry={92 * (0.6 + 0.4 * ring)} fill="none" stroke={st.ring} strokeWidth={s.id === 'grid' ? 16 : 10} pathLength={1} style={dash(ring)} />
				{ring > 0.6 ? [0, 2.25, 4.1].map((t, i) => {
					const [x, y] = node(t);
					return <rect key={i} x={x - 18} y={y - 18} width={36} height={36} rx={s.id === 'liquid' ? 18 : 0} fill={st.m} opacity={(ring - 0.6) / 0.4} />;
				}) : null}
			</g>
		</svg>
	);
};

const ICON: Record<string, string[]> = {
	like: ['M7 10v12', 'M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z'],
	bell: ['M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9', 'M10.3 21a1.94 1.94 0 0 0 3.4 0'],
	github: ['M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4', 'M9 18c-4.51 2-5-2-7-2'],
	cursor: ['M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z'],
};
export const Ic: React.FC<{n: string; size: number; color: string; fill?: string; sw?: number; rot?: number}> = ({n, size, color, fill = 'none', sw = 2.2, rot = 0}) => (
	<svg viewBox="0 0 24 24" width={size} height={size} style={{overflow: 'visible', transform: rot ? `rotate(${rot}deg)` : undefined, transformOrigin: '50% 10%'}}>
		{(ICON[n] || []).map((d, i) => <path key={i} d={d} stroke={color} strokeWidth={sw} fill={i === (n === 'like' ? 1 : 0) ? fill : 'none'} strokeLinecap="round" strokeLinejoin="round" />)}
	</svg>
);

// one end-card button: pops in at `at`, gets pressed at `press` (cursor click) and switches to its "done" look
export const Btn: React.FC<{s: S; t: number; at: number; press: number; icon: string; label: string; done: string; u: number; t0: number}> = ({s, t, at, press, icon, label, done, u}) => {
	if (t < at) return null;
	const p = s.pal;
	const e = s.enter(t, at);
	const on = t >= press;
	const squash = on ? 1 - 0.12 * Math.sin(c01((t - press) / 0.25) * Math.PI) : 1;
	const ring = icon === 'bell' && on ? Math.sin((t - press) * 22) * 18 * Math.max(0, 1 - (t - press) / 1.2) : 0;
	const fz = 44 * u;
	const look: Record<string, React.CSSProperties> = {
		signature: {border: `${2 * u}px solid ${on ? p.acc : p.line}`, background: on ? p.acc : 'rgba(255,255,255,.04)', color: on ? p.dark : p.ink, borderRadius: 999,
			boxShadow: on ? `0 0 ${40 * u}px ${p.acc}88` : 'none', opacity: s.in01(t, at), transform: `scale(${(0.94 + 0.06 * c01(e)) * squash})`},
		grid: {background: on ? p.acc : p.ink, color: p.bg, transform: `scale(${e * squash})`},
		liquid: {background: on ? `linear-gradient(90deg, ${p.acc}, ${p.acc2})` : 'rgba(255,255,255,.12)', color: '#fff', borderRadius: 999, transform: `scale(${Math.max(0, e) * squash})`,
			boxShadow: on ? `0 ${12 * u}px ${36 * u}px ${p.acc}88` : 'none'},
		paper: {background: on ? p.acc : p.acc4, color: on ? '#fff' : p.dark, transform: `scale(${e * squash}) rotate(${icon === 'like' ? -2 : 2}deg)${s.boil(t, icon === 'like' ? 501 : 502)}`,
			boxShadow: `${7 * u}px ${8 * u}px 0 rgba(59,42,23,.32)`},
	};
	const col = (look[s.id].color as string) || p.ink;
	return (
		<div style={{display: 'flex', alignItems: 'center', gap: 18 * u, padding: `${20 * u}px ${44 * u}px`, ...look[s.id]}}>
			<Ic n={icon} size={fz * 1.1} color={col} fill={on && icon === 'like' ? col : 'none'} rot={ring} />
			<span style={{...s.font(s.id === 'paper' ? 'head' : 'head'), fontSize: fz, lineHeight: 1, whiteSpace: 'nowrap', letterSpacing: s.id === 'signature' ? '0.12em' : 0}}>{s.cased(on ? done : label)}</span>
		</div>
	);
};

// the cursor that clicks the buttons: glides between targets with the style's ease
export const Cursor: React.FC<{s: S; t: number; pts: [number, number, number][]; u: number}> = ({s, t, pts, u}) => {
	if (!pts.length || t < pts[0][2] - 0.6) return null;
	let x = pts[0][0], y = pts[0][1] + 140 * u, click = 0;
	for (let i = 0; i < pts.length; i++) {
		const [px, py, at] = pts[i];
		const from = i ? pts[i - 1] : [pts[0][0] + 220 * u, pts[0][1] + 200 * u, at - 0.6];
		const k = c01((t - (at - 0.55)) / 0.5);
		if (t >= at - 0.55) {
			x = lerp(from[0], px, backOut(k, 1.2));
			y = lerp(from[1], py, backOut(k, 1.2));
		}
		if (t >= at && t < at + 0.18) click = 1;
	}
	const col = s.id === 'grid' ? s.pal.ink : '#FFFFFF';
	return (
		<div style={{position: 'absolute', left: x, top: y, transform: `scale(${1 - 0.15 * click})`, transformOrigin: '0 0', filter: 'drop-shadow(0 4px 8px rgba(0,0,0,.45))'}}>
			<Ic n="cursor" size={58 * u} color={s.id === 'grid' ? s.pal.bg : '#111'} fill={col} sw={1.6} />
		</div>
	);
};

export const GITHUB = 'github.com/MirCorp85/MirMediaLabs';
