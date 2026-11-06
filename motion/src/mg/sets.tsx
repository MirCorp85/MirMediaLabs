// MIR MOTION GRAPHICS — SETS: real places for story beats (user reference, Oct 28 2026: a "what if" story film — characters
// living through scenes in a café street at dusk, a lab, a bedroom, a pitch, a stadium…). Every set is built from parallax
// LAYERS in a 1920×1080 design space (sky → far → mid → floor → near) drawn with the style's materials, so the same set reads
// as a dusk silhouette street (dusk), a silver line-art studio set (signature), a Swiss poster (grid), a glossy toy town
// (liquid) or layered paper (paper). The camera (zoom + parallax) and depth of field come from the action beat's shot.
import React from 'react';
import {S, rnd} from './style';

export const SET_NAMES = ['street', 'cafe', 'room', 'lab', 'field', 'stadium', 'track', 'city', 'nature', 'space', 'stage'];
export const GROUND = 860;                  // floor line in design space — the puppet's feet stand here

type Mat = {sky: [string, string, string]; sun: string; far: string; mid: string; near: string; win: string; floor: string; line: string; out: number; beam: string;
	grain: number; flat: boolean; shadow?: string};
const mats = (s: S): Mat => {
	const p = s.pal;
	// Ember & Teal (style key 'dusk'): deep teal night, ember-orange lights, cream highlights (the user's own palette, Oct 28 2026)
	if (s.key === 'dusk') return {sky: ['#04161A', '#0C3439', '#1F5A5B'], sun: '#FF8A4C', far: '#0E3036', mid: '#09232A', near: '#03100F', win: '#FF8A4C', floor: '#071D21', line: '#FFE0C2', out: 0, beam: '#FFB079', grain: 0.1, flat: false};
	if (s.id === 'signature') return {sky: ['#08080A', '#25252B', '#3A3A40'], sun: p.acc, far: '#232328', mid: '#1A1A1E', near: '#0E0E10', win: p.acc, floor: '#121215', line: p.line, out: 1.6, beam: '#FFFFFF', grain: 0.08, flat: false};
	if (s.id === 'grid') return {sky: [p.bg, p.bg, p.bg], sun: p.acc, far: '#D8D1C3', mid: p.ink, near: p.ink, win: p.acc, floor: p.bg2, line: p.ink, out: 0, beam: p.acc, grain: 0, flat: true};
	if (s.id === 'liquid') return {sky: ['#0E0B22', '#2A1F5C', '#6B3FA0'], sun: p.acc3, far: '#2E2660', mid: '#231D4C', near: '#16122F', win: p.acc3, floor: '#1E1A42', line: '#FFFFFF', out: 0, beam: p.acc, grain: 0, flat: false};
	return {sky: ['#E8D6B9', '#E2CBA6', '#D9BE93'], sun: p.acc3, far: '#C9AE84', mid: p.acc2, near: p.dark, win: p.acc3, floor: '#CDB48C', line: p.dark, out: 0, beam: '#FFF4D8', grain: 0.12, flat: true,
		shadow: 'drop-shadow(6px 8px 0 rgba(59,42,23,.3))'};
};

// ── building blocks ──
const Sky: React.FC<{m: Mat; id: string; sun?: boolean; night?: boolean}> = ({m, id, sun = true, night}) => (
	<g>
		<defs>
			<linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={m.sky[0]} /><stop offset="0.62" stopColor={night ? m.sky[0] : m.sky[1]} /><stop offset="1" stopColor={night ? m.sky[1] : m.sky[2]} /></linearGradient>
			<radialGradient id={id + 's'}><stop offset="0" stopColor={m.sun} stopOpacity="0.95" /><stop offset="0.25" stopColor={m.sun} stopOpacity="0.45" /><stop offset="1" stopColor={m.sun} stopOpacity="0" /></radialGradient>
		</defs>
		<rect x={-400} y={-200} width={2720} height={1500} fill={`url(#${id})`} />
		{sun && !m.flat ? <circle cx={1180} cy={700} r={520} fill={`url(#${id}s)`} opacity={m.sun === '#FF8A4C' ? 0.45 : 1} /> : null}
		{sun && m.flat ? <circle cx={1180} cy={640} r={150} fill={m.sun} style={{filter: m.shadow}} /> : null}
		{sun && !m.flat ? <circle cx={1180} cy={700} r={70} fill={m.sun === '#FF8A4C' ? '#FFE6C8' : m.sun} opacity={m.sun === '#FF8A4C' ? 0.75 : 0.9} /> : null}
	</g>
);
const Skyline: React.FC<{m: Mat; y: number; seed: number; color: string; h: number; lit?: number}> = ({m, y, seed, color, h, lit = 0}) => {
	const out: React.ReactNode[] = [];
	let x = -300;
	let i = 0;
	while (x < 2300) {
		const w = 60 + rnd(seed + i) * 130, bh = h * (0.35 + rnd(seed + i * 3) * 0.65);
		out.push(<rect key={'b' + i} x={x} y={y - bh} width={w} height={bh + 400} fill={color} stroke={m.out ? m.line : 'none'} strokeOpacity={0.25} strokeWidth={m.out} />);
		if (lit) for (let r = 0; r < Math.floor(bh / 34); r++) for (let c = 0; c < Math.floor(w / 26); c++) {
			if (rnd(seed * 7 + i * 31 + r * 5 + c) < lit) out.push(<rect key={`w${i}-${r}-${c}`} x={x + 8 + c * 26} y={y - bh + 12 + r * 34} width={12} height={16} fill={m.win} opacity={0.75} />);
		}
		x += w + 6;
		i++;
	}
	return <g>{out}</g>;
};
const Houses: React.FC<{m: Mat; y: number; seed: number}> = ({m, y, seed}) => {
	const out: React.ReactNode[] = [];
	let x = -200;
	let i = 0;
	while (x < 2200) {
		const w = 260 + rnd(seed + i) * 140, h = 360 + rnd(seed + i * 5) * 200;
		out.push(<rect key={'h' + i} x={x} y={y - h} width={w} height={h} fill={m.mid} stroke={m.out ? m.line : 'none'} strokeOpacity={0.35} strokeWidth={m.out} style={{filter: m.shadow}} />);
		out.push(<polygon key={'r' + i} points={`${x - 10},${y - h} ${x + w / 2},${y - h - 70} ${x + w + 10},${y - h}`} fill={m.near} />);
		for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) {
			const on = rnd(seed * 3 + i * 17 + r * 7 + c) < 0.55;
			out.push(<rect key={`w${i}${r}${c}`} x={x + 30 + c * (w - 60) / 3} y={y - h + 50 + r * 100} width={(w - 60) / 3 - 22} height={64} fill={on ? m.win : m.near} opacity={on ? 0.85 : 0.6}
				stroke={m.out ? m.line : 'none'} strokeOpacity={0.3} strokeWidth={m.out} />);
		}
		x += w + 40;
		i++;
	}
	return <g>{out}</g>;
};
const Lamp: React.FC<{m: Mat; x: number; t: number}> = ({m, x, t}) => (
	<g>
		<rect x={x - 5} y={GROUND - 420} width={10} height={420} fill={m.near} />
		<rect x={x - 26} y={GROUND - 440} width={52} height={22} rx={6} fill={m.near} />
		{!m.flat ? <polygon points={`${x - 24},${GROUND - 420} ${x + 24},${GROUND - 420} ${x + 150},${GROUND} ${x - 150},${GROUND}`} fill={m.beam} opacity={0.06 + 0.01 * Math.sin(t * 3)} /> : null}
		<circle cx={x} cy={GROUND - 418} r={9} fill={m.win} />
	</g>
);
const Floor: React.FC<{m: Mat; color?: string; lines?: boolean}> = ({m, color, lines}) => (
	<g>
		<rect x={-400} y={GROUND} width={2720} height={500} fill={color || m.floor} />
		<rect x={-400} y={GROUND} width={2720} height={4} fill={m.line} opacity={m.flat ? 0.9 : 0.25} />
		{lines ? Array.from({length: 7}, (_, i) => <line key={i} x1={960} y1={GROUND} x2={-1200 + i * 700} y2={1300} stroke={m.line} strokeOpacity={0.12} strokeWidth={3} />) : null}
	</g>
);
const Window: React.FC<{m: Mat; x: number; y: number; w: number; h: number; id: string}> = ({m, x, y, w, h, id}) => (
	<g>
		<clipPath id={id}><rect x={x} y={y} width={w} height={h} /></clipPath>
		<g clipPath={`url(#${id})`}>
			<Sky m={m} id={id + 'k'} />
			<Skyline m={m} y={y + h} seed={9} color={m.far} h={h * 0.55} lit={0.2} />
		</g>
		<rect x={x} y={y} width={w} height={h} fill="none" stroke={m.near} strokeWidth={18} />
		<line x1={x + w / 2} y1={y} x2={x + w / 2} y2={y + h} stroke={m.near} strokeWidth={10} />
		<line x1={x} y1={y + h * 0.45} x2={x + w} y2={y + h * 0.45} stroke={m.near} strokeWidth={10} />
		{!m.flat ? <polygon points={`${x},${y + h} ${x + w},${y + h} ${x + w + 380},${GROUND + 160} ${x - 60},${GROUND + 160}`} fill={m.beam} opacity={0.07} /> : null}
	</g>
);
const Crowd: React.FC<{m: Mat; y: number; rows: number; t: number}> = ({m, y, rows, t}) => {
	const out: React.ReactNode[] = [];
	for (let r = 0; r < rows; r++) for (let i = 0; i < 70; i++) {
		const x = -300 + i * 36 + (r % 2) * 18, b = Math.max(0, Math.sin(t * 5 + i * 1.3 + r)) * 4;
		out.push(<circle key={`${r}-${i}`} cx={x} cy={y - r * 34 - b} r={11} fill={r % 2 ? m.far : m.mid} opacity={0.9} />);
	}
	return <g>{out}</g>;
};
const Floodlight: React.FC<{m: Mat; x: number; flip?: boolean}> = ({m, x, flip}) => (
	<g>
		<rect x={x - 6} y={180} width={12} height={420} fill={m.near} />
		<rect x={x - 60} y={150} width={120} height={50} fill={m.near} />
		{Array.from({length: 8}, (_, i) => <circle key={i} cx={x - 48 + (i % 4) * 32} cy={162 + Math.floor(i / 4) * 24} r={8} fill={m.sun} />)}
		{!m.flat ? <polygon points={`${x - 60},${200} ${x + 60},${200} ${x + (flip ? -700 : 700)},${GROUND} ${x + (flip ? -200 : 200)},${GROUND}`} fill={m.beam} opacity={0.07} /> : null}
	</g>
);
const Trees: React.FC<{m: Mat; y: number; seed: number; color: string; scale?: number}> = ({m, y, seed, color, scale = 1}) => (
	<g>
		{Array.from({length: 16}, (_, i) => {
			const x = -200 + i * 150 + rnd(seed + i) * 60, h = (120 + rnd(seed + i * 3) * 120) * scale;
			return <g key={i}><rect x={x - 6} y={y - h * 0.4} width={12} height={h * 0.4} fill={color} /><ellipse cx={x} cy={y - h * 0.6} rx={h * 0.35} ry={h * 0.42} fill={color} /></g>;
		})}
	</g>
);

// ── the sets ──
type Layers = {sky: React.ReactNode; far?: React.ReactNode; mid?: React.ReactNode; floor?: React.ReactNode; near?: React.ReactNode};
const BUILD: Record<string, (m: Mat, t: number, id: string) => Layers> = {
	street: (m, t, id) => ({sky: <Sky m={m} id={id} />, far: <Skyline m={m} y={620} seed={3} color={m.far} h={260} lit={0.08} />, mid: <g><Houses m={m} y={GROUND} seed={5} /><Lamp m={m} x={340} t={t} /><Lamp m={m} x={1560} t={t} /></g>,
		floor: <Floor m={m} />, near: <g><rect x={-300} y={GROUND + 120} width={2600} height={300} fill={m.near} /><Trees m={m} y={GROUND + 140} seed={11} color={m.near} scale={1.6} /></g>}),
	cafe: (m, t, id) => ({sky: <Sky m={m} id={id} />, far: <Skyline m={m} y={600} seed={4} color={m.far} h={240} lit={0.1} />,
		mid: <g><rect x={260} y={300} width={1400} height={GROUND - 300} fill={m.mid} style={{filter: m.shadow}} />
			{Array.from({length: 12}, (_, i) => <rect key={i} x={240 + i * 120} y={300} width={60} height={90} fill={i % 2 ? m.win : m.near} opacity={0.85} />)}
			<rect x={360} y={440} width={1200} height={300} fill={m.win} opacity={0.75} />
			{Array.from({length: 5}, (_, i) => <rect key={'f' + i} x={360 + i * 300} y={440} width={12} height={300} fill={m.near} />)}
			<Lamp m={m} x={140} t={t} /></g>,
		floor: <Floor m={m} />, near: <g>{[[520, 'l'], [1400, 'r']].map(([x], i) => <g key={i}><ellipse cx={+x} cy={GROUND - 120} rx={110} ry={20} fill={m.near} /><rect x={+x - 6} y={GROUND - 120} width={12} height={120} fill={m.near} /></g>)}</g>}),
	room: (m, t, id) => ({sky: <rect x={-400} y={-200} width={2720} height={1500} fill={m.mid} />,
		mid: <g><Window m={m} x={620} y={180} w={680} h={460} id={id + 'w'} />
			<rect x={140} y={300} width={180} height={240} fill={m.far} stroke={m.out ? m.line : 'none'} strokeWidth={m.out} strokeOpacity={0.4} style={{filter: m.shadow}} />
			<circle cx={230} cy={420} r={50} fill="none" stroke={m.win} strokeWidth={6} opacity={0.6} />
			<rect x={1420} y={560} width={420} height={18} fill={m.near} /><rect x={1500} y={430} width={240} height={130} fill={m.near} />
			<rect x={1510} y={440} width={220} height={110} fill={m.win} opacity={0.5} /><rect x={1440} y={578} width={14} height={282} fill={m.near} /><rect x={1806} y={578} width={14} height={282} fill={m.near} /></g>,
		floor: <Floor m={m} lines />}),
	lab: (m, t, id) => ({sky: <rect x={-400} y={-200} width={2720} height={1500} fill={m.mid} />,
		mid: <g><Window m={m} x={560} y={160} w={800} h={420} id={id + 'w'} />
			{[120, 1480].map((x, k) => <g key={k}><rect x={x} y={220} width={300} height={180} rx={10} fill={m.near} /><polyline points={`${x + 20},${360} ${x + 80},${300} ${x + 140},${330} ${x + 200},${260} ${x + 280},${280}`} fill="none" stroke={m.win} strokeWidth={5} opacity={0.8} /></g>)}
			<rect x={200} y={640} width={1520} height={40} fill={m.near} /><rect x={240} y={680} width={1440} height={180} fill={m.far} />
			{[420, 520, 1300, 1420].map((x, k) => <g key={'f' + k}><rect x={x} y={560} width={26} height={80} fill="none" stroke={m.line} strokeOpacity={0.5} strokeWidth={4} /><rect x={x + 3} y={600} width={20} height={38} fill={k % 2 ? m.win : m.sun} opacity={0.7} /></g>)}</g>,
		floor: <Floor m={m} lines />}),
	field: (m, t, id) => ({sky: <Sky m={m} id={id} />, far: <g><Trees m={m} y={640} seed={7} color={m.far} /><rect x={-300} y={600} width={2600} height={50} fill={m.far} opacity={0.6} /></g>,
		mid: <g>{Array.from({length: 30}, (_, i) => <rect key={i} x={-300 + i * 90} y={560} width={4} height={80} fill={m.near} opacity={0.5} />)}<rect x={-300} y={575} width={2600} height={4} fill={m.near} opacity={0.5} /></g>,
		floor: <g><rect x={-400} y={640} width={2720} height={800} fill={m.floor} />
			<rect x={-400} y={640} width={2720} height={800} fill={m.flat ? 'transparent' : m.sun === '#FF8A4C' ? '#1D5A4E' : '#3E6B45'} opacity={0.55} />
			{[700, 800, 960].map((y, i) => <rect key={i} x={-400} y={y} width={2720} height={4} fill={m.line} opacity={0.35} />)}
			<line x1={960} y1={640} x2={960} y2={1300} stroke={m.line} strokeOpacity={0.35} strokeWidth={4} /></g>}),
	stadium: (m, t, id) => ({sky: <Sky m={m} id={id} night />, far: <g><rect x={-300} y={250} width={2600} height={400} fill={m.far} /><Crowd m={m} y={600} rows={9} t={t} /></g>,
		mid: <g><Floodlight m={m} x={260} /><Floodlight m={m} x={1660} flip /></g>,
		floor: <g><rect x={-400} y={650} width={2720} height={800} fill={m.flat ? m.floor : m.sun === '#FF8A4C' ? '#17493F' : '#2F5E3B'} opacity={m.flat ? 1 : 0.85} />{[760, 900].map((y, i) => <rect key={i} x={-400} y={y} width={2720} height={4} fill={m.line} opacity={0.4} />)}
			<ellipse cx={960} cy={900} rx={260} ry={60} fill="none" stroke={m.line} strokeOpacity={0.4} strokeWidth={4} /></g>}),
	track: (m, t, id) => ({sky: <Sky m={m} id={id} />, far: <g><rect x={-300} y={420} width={2600} height={240} fill={m.far} /><Crowd m={m} y={630} rows={5} t={t} /></g>,
		floor: <g><rect x={-400} y={680} width={2720} height={800} fill={m.flat ? m.floor : m.sun === '#FF8A4C' ? '#7A3426' : '#8A3B2E'} opacity={m.flat ? 1 : 0.85} />{Array.from({length: 6}, (_, i) => <rect key={i} x={-400} y={700 + i * (40 + i * 12)} width={2720} height={4} fill={m.line} opacity={0.5} />)}</g>}),
	city: (m, t, id) => ({sky: <Sky m={m} id={id} night />, far: <Skyline m={m} y={700} seed={13} color={m.far} h={420} lit={0.25} />, mid: <Skyline m={m} y={GROUND} seed={17} color={m.mid} h={520} lit={0.35} />, floor: <Floor m={m} />}),
	nature: (m, t, id) => ({sky: <Sky m={m} id={id} />, far: <path d="M-400 700 Q200 480 700 640 T1700 560 T2400 660 V1100 H-400Z" fill={m.far} />,
		mid: <g><path d="M-400 800 Q300 640 900 760 T2400 740 V1100 H-400Z" fill={m.mid} /><Trees m={m} y={800} seed={21} color={m.near} /></g>, floor: <Floor m={m} />}),
	space: (m, t, id) => ({sky: <g><rect x={-400} y={-200} width={2720} height={1500} fill={m.flat ? m.sky[0] : '#07060F'} />{Array.from({length: 140}, (_, i) => <circle key={i} cx={-300 + rnd(i) * 2500} cy={rnd(i * 3) * 1080} r={1 + rnd(i * 7) * 2.4} fill={m.flat ? m.line : '#FFFFFF'} opacity={0.3 + 0.6 * Math.abs(Math.sin(t * 2 + i))} />)}</g>,
		far: <g><circle cx={1500} cy={300} r={170} fill={m.sun} opacity={0.9} style={{filter: m.shadow}} /><ellipse cx={1500} cy={300} rx={280} ry={46} fill="none" stroke={m.win} strokeWidth={10} opacity={0.6} /></g>,
		floor: <path d={`M-400 ${GROUND} Q960 ${GROUND - 80} 2320 ${GROUND} V1300 H-400Z`} fill={m.flat ? m.floor : '#3A3A48'} />}),
	stage: (m, t, id) => ({sky: <rect x={-400} y={-200} width={2720} height={1500} fill={m.flat ? m.sky[0] : '#0C0A12'} />,
		mid: <g>{!m.flat ? <polygon points={`${860},0 ${1060},0 ${1360},${GROUND} ${560},${GROUND}`} fill={m.beam} opacity={0.12} /> : null}
			<rect x={-300} y={0} width={420} height={GROUND} fill={m.flat ? m.mid : '#5A1E2A'} /><rect x={1800} y={0} width={420} height={GROUND} fill={m.flat ? m.mid : '#5A1E2A'} />
			{Array.from({length: 3}, (_, i) => <line key={i} x1={300} y1={GROUND - 200 - i * 60} x2={1620} y2={GROUND - 200 - i * 60} stroke={m.line} strokeOpacity={0.4} strokeWidth={5} />)}</g>,
		floor: <g><Floor m={m} /><ellipse cx={960} cy={GROUND + 30} rx={420} ry={40} fill={m.beam} opacity={m.flat ? 0 : 0.18} /></g>}),
};

// the set behind an action beat: zoom (shot) + parallax drift + depth of field on the far layers
export const SetView: React.FC<{s: S; t: number; name: string; cam: {z: number; sx: number; sy: number; tx: number; ty: number}; dof: number; drift: number; W: number; H: number; id: string}> = ({s, t, name, cam, dof, drift, W, H, id}) => {
	const m = mats(s);
	const L = (BUILD[name] || BUILD.street)(m, t, id);
	const layer = (k: number, node: React.ReactNode, blur: number) =>
		node ? <g transform={`translate(${-drift * k} 0)`} style={{filter: blur > 0.2 ? `blur(${blur}px)` : undefined}}>{node}</g> : null;
	return (
		<svg viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMax slice" style={{position: 'absolute', inset: 0, width: W, height: H, overflow: 'hidden'}}>
			<g transform={`translate(${cam.tx} ${cam.ty}) scale(${cam.z}) translate(${-cam.sx} ${-cam.sy})`}>
				{layer(0.1, L.sky, dof * 0.6)}
				{layer(0.25, L.far, dof)}
				{layer(0.5, L.mid, dof * 0.7)}
				{layer(0.8, L.floor, dof * 0.3)}
				{layer(1.3, L.near, Math.max(2, dof * 0.4))}
			</g>
			{m.grain ? (
				<g>
					<filter id={id + 'g'}><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={Math.floor(t * 24) % 97} /><feColorMatrix type="saturate" values="0" /></filter>
					<rect width="1920" height="1080" filter={`url(#${id}g)`} opacity={m.grain} style={{mixBlendMode: 'overlay'}} />
				</g>
			) : null}
		</svg>
	);
};
