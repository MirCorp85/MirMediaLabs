// Cinematic cold open: the MML flask logo draws itself on in gold, ring spins in, bloom + flare, title in letterbox.
import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {AMBER, CREAM, Dust, Flare, FONT, GOLD, Grain, Letterbox, Vignette, clamp, ease} from './fx';

/** The flask logo as strokes (1024 space, traced from MirMediaLabs-icon-1024.png). */
export const FlaskLogo: React.FC<{draw: number; ring: number; bubbles: number; glow: number; spin?: number}> = ({draw, ring, bubbles, glow, spin = 0}) => {
	const dash = (p: number) => ({strokeDasharray: 1, strokeDashoffset: 1 - Math.max(0, Math.min(1, p))});
	const seg = (a: number, b: number) => interpolate(draw, [a, b], [0, 1], clamp);
	const sq = (x: number, y: number) => <rect x={x - 18} y={y - 18} width={36} height={36} fill={CREAM} />;
	const ang = spin * Math.PI * 2;
	const node = (t: number) => {
		const a = ang + t;
		return [512 + Math.cos(a) * 310, 540 + Math.sin(a) * 92];
	};
	return (
		<svg viewBox="0 0 1024 1024" width="100%" height="100%" style={{overflow: 'visible'}}>
			<defs>
				<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
					<feGaussianBlur stdDeviation={8 + glow * 18} result="b" />
					<feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
				</filter>
			</defs>
			<g filter="url(#glow)" fill="none" stroke={GOLD} strokeWidth={30} strokeLinecap="butt" strokeLinejoin="round">
				{/* lip */}
				<path pathLength={1} d="M421 240 H603" style={dash(seg(0, 0.15))} />
				{/* flask outline: neck → shoulders → body → base */}
				<path pathLength={1} d="M452 255 V420 L290 700 L305 760 Q312 785 335 785 H690 Q713 785 720 760 L735 700 L572 420 V255"
					style={dash(seg(0.1, 0.65))} />
				{/* liquid line */}
				<path pathLength={1} d="M362 602 H662" style={dash(seg(0.5, 0.7))} />
				{/* M */}
				<path pathLength={1} d="M397 752 V655 L512 728 L627 655 V752" stroke={CREAM} strokeWidth={34} style={dash(seg(0.6, 0.95))} />
			</g>
			{/* bubbles */}
			<g fill={GOLD} filter="url(#glow)">
				{[[490, 530, 17], [540, 487, 13], [518, 560, 11]].map(([x, y, r], i) => {
					const t = interpolate(bubbles, [i * 0.2, i * 0.2 + 0.5], [0, 1], clamp);
					return <circle key={i} cx={x} cy={y + (1 - t) * 50} r={r * t} opacity={t} />;
				})}
			</g>
			{/* orbit ring */}
			<g opacity={ring} filter="url(#glow)" transform={`rotate(-3 512 540)`}>
				<ellipse cx={512} cy={540} rx={310 * (0.6 + 0.4 * ring)} ry={92 * (0.6 + 0.4 * ring)} fill="none" stroke={AMBER} strokeWidth={10}
					pathLength={1} style={dash(ring)} />
				{ring > 0.6 && [0, 2.25, 4.1].map((t, i) => { const [x, y] = node(t); return <g key={i} opacity={(ring - 0.6) / 0.4}>{sq(x, y)}</g>; })}
			</g>
		</svg>
	);
};

export const LogoOpen: React.FC = () => {
	const f = useCurrentFrame();
	const draw = interpolate(f, [12, 95], [0, 1], {...clamp, easing: ease});
	const ring = interpolate(f, [70, 110], [0, 1], {...clamp, easing: ease});
	const bubbles = interpolate(f, [85, 125], [0, 1], clamp);
	const flash = interpolate(f, [108, 114, 140], [0, 1, 0], clamp);
	const push = interpolate(f, [0, 180], [1.18, 0.92], {...clamp, easing: ease});
	const title = interpolate(f, [118, 140], [0, 1], {...clamp, easing: ease});
	const bars = interpolate(f, [150, 178], [0, 1], {...clamp, easing: ease});
	const out = interpolate(f, [168, 180], [1, 0], clamp);
	const bloomIn = interpolate(f, [0, 20], [0, 1], clamp);
	return (
		<AbsoluteFill style={{background: '#000'}}>
			<AbsoluteFill style={{opacity: bloomIn * out,
				background: `radial-gradient(ellipse at 50% 48%, rgba(120,80,20,${0.35 + flash * 0.4}) 0%, #140e05 45%, #000 80%)`}} />
			<Dust count={90} seed="open" />
			<AbsoluteFill style={{opacity: out, transform: `scale(${push}) translateY(${-title * 70}px)`}}>
				<div style={{position: 'absolute', left: 960 - 330, top: 540 - 360, width: 660, height: 660}}>
					<FlaskLogo draw={draw} ring={ring} bubbles={bubbles} glow={flash + ring * 0.3} spin={f / 300} />
				</div>
			</AbsoluteFill>
			<div style={{position: 'absolute', left: 0, right: 0, top: 760, textAlign: 'center', fontFamily: FONT, opacity: title * out}}>
				<div style={{fontSize: 96, fontWeight: 900, letterSpacing: interpolate(title, [0, 1], [60, 22]), color: CREAM,
					textShadow: `0 0 40px ${AMBER}, 0 0 90px rgba(255,170,60,.5)`}}>MIR MEDIA LABS</div>
				<div style={{fontSize: 28, letterSpacing: 14, color: GOLD, marginTop: 6, opacity: interpolate(f, [135, 155], [0, 1], clamp)}}>
					YOUR AI FILM STUDIO
				</div>
			</div>
			<Flare p={interpolate(f, [100, 150], [0, 1], clamp)} y={560} opacity={out} />
			<AbsoluteFill style={{background: '#fff3d6', opacity: flash * 0.55, mixBlendMode: 'screen'}} />
			<Letterbox open={bars} />
			<Vignette />
			<Grain opacity={0.12} />
		</AbsoluteFill>
	);
};

export const EndCard: React.FC = () => {
	const f = useCurrentFrame();
	const t = interpolate(f, [0, 25], [0, 1], {...clamp, easing: ease});
	return (
		<AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 40%, #2a1c08 0%, #0d0904 55%, #000 100%)', fontFamily: FONT}}>
			<Dust count={60} seed="end" />
			<Img src={staticFile('promo/logo.png')} style={{position: 'absolute', left: 960 - 260, top: 40, width: 520, height: 520,
				opacity: t, transform: `scale(${0.85 + 0.15 * t})`, mixBlendMode: 'screen'}} />
			<div style={{position: 'absolute', top: 570, left: 0, right: 0, textAlign: 'center', opacity: t}}>
				<div style={{fontSize: 92, fontWeight: 900, letterSpacing: 20, color: CREAM, textShadow: `0 0 40px ${AMBER}`}}>MIR MEDIA LABS</div>
				<div style={{fontSize: 34, letterSpacing: 8, color: GOLD, marginTop: 16, opacity: interpolate(f, [15, 35], [0, 1], clamp)}}>
					IMAGES · VIDEO · MUSIC · SERIES — ALL ON YOUR PC
				</div>
				<div style={{display: 'inline-block', marginTop: 46, padding: '18px 44px', borderRadius: 60, border: `2px solid ${GOLD}`,
					fontSize: 30, letterSpacing: 4, color: '#fff', opacity: interpolate(f, [30, 50], [0, 1], clamp),
					boxShadow: `0 0 40px rgba(255,190,90,${0.3 + 0.2 * Math.sin(f / 8)})`}}>github.com/MirCorp85/MirMediaLabs</div>
			</div>
			<Flare p={interpolate(f, [5, 70], [0, 1], clamp)} y={300} opacity={0.7} />
			<Letterbox open={interpolate(f, [120, 150], [1, 0], clamp)} />
			<AbsoluteFill style={{background: '#000', opacity: interpolate(f, [135, 150], [0, 1], clamp)}} />
			<Vignette />
			<Grain />
		</AbsoluteFill>
	);
};
