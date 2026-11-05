// MIR EXPLAINED figure library (Oct 18, user: "more drawings and more animations with figure models and objects").
// Hand-drawn line-art figures in the B house style (silver line, one amber accent). Every figure draws itself on
// (draw 0→1, strokes staggered) and then keeps a small idle motion driven by t (fans spin, globe turns, smoke rises,
// flag waves, crowd breathes). figFor(text) picks a figure from a scene's own words, so generated episodes get
// drawings with no script changes. All deterministic (pure functions of t) — safe for Remotion renders.
import React from 'react';
import {C, ramp} from './theme';
import {DioItem, isLib} from '../mg/dio_item';      // the shared motion library (lib:<id> figures)

type Dash = {pathLength: number; strokeDasharray: number; strokeDashoffset: number};
type P = {t: number; dr: (o?: number) => Dash; a: string; c: string};
const pts = (n: number, f: (i: number) => string) => Array.from({length: n}, (_, i) => f(i)).join('');

const person = (x: number, y: number, s: number) =>
	`M${x - 24 * s} ${y + 44 * s}V${y + 30 * s}C${x - 24 * s} ${y + 15 * s} ${x - 13 * s} ${y + 8 * s} ${x} ${y + 8 * s}C${x + 13 * s} ${y + 8 * s} ${x + 24 * s} ${y + 15 * s} ${x + 24 * s} ${y + 30 * s}V${y + 44 * s}`;

const FIG: Record<string, (p: P) => React.ReactNode> = {
	person: ({t, dr}) => {
		const bob = Math.sin(t * 2) * 1.2;
		return <g transform={`translate(0 ${bob})`}><circle cx="50" cy="26" r="13" {...dr(0)} /><path d={person(50, 40, 1.15)} {...dr(0.15)} /></g>;
	},
	crowd: ({t, dr, a}) => (
		<>
			{[[24, 46, 0.7, 1.1], [76, 46, 0.7, 2.3], [50, 38, 0.9, 0]].map(([x, y, s, ph], i) => {
				const bob = Math.sin(t * 2 + ph) * 1.2;
				return <g key={i} transform={`translate(0 ${bob})`}>
					<circle cx={x} cy={y - 14 * s} r={11 * s} {...dr(i * 0.1)} stroke={i === 2 ? a : undefined} />
					<path d={person(x, y - 2 * s, s)} {...dr(0.1 + i * 0.1)} stroke={i === 2 ? a : undefined} />
				</g>;
			})}
		</>
	),
	controller: ({t, dr, a}) => {
		const glow = 0.5 + 0.5 * Math.sin(t * 5);
		return (
			<>
				<path d="M28 34H72C82 34 89 42 88 53L86 66C85 74 77 77 71 71L63 63H37L29 71C23 77 15 74 14 66L12 53C11 42 18 34 28 34Z" {...dr(0)} />
				<path d="M30 46V58M24 52H36" {...dr(0.25)} />
				<circle cx="66" cy="47" r="3" {...dr(0.35)} stroke={a} opacity={0.5 + 0.5 * glow} />
				<circle cx="74" cy="54" r="3" {...dr(0.4)} stroke={a} opacity={1 - 0.5 * glow} />
				<path d="M44 28C44 22 48 18 52 18" {...dr(0.45)} strokeOpacity=".6" />
			</>
		);
	},
	gpu: ({t, dr, a}) => (
		<>
			<path d="M8 32H92V68H8Z" {...dr(0)} />
			<path d="M8 26V76" {...dr(0.1)} />
			<path d="M22 68V75H60V68" {...dr(0.2)} stroke={a} />
			{[31, 67].map((cx, k) => (
				<g key={cx}>
					<circle cx={cx} cy="50" r="13" {...dr(0.2 + k * 0.1)} />
					<g transform={`rotate(${t * 420 + k * 40} ${cx} 50)`} opacity={ramp(t, 0.5, 0.4)}>
						{[0, 120, 240].map((r) => <path key={r} d={`M${cx} 50L${cx} 39`} transform={`rotate(${r} ${cx} 50)`} strokeWidth="2.6" />)}
					</g>
				</g>
			))}
			<path d="M84 38V62" stroke={a} {...dr(0.4)} />
		</>
	),
	chip: ({t, dr, a}) => {
		const pulse = (t * 0.9) % 1;
		return (
			<>
				<path d="M30 30H70V70H30Z" {...dr(0)} />
				<path d="M40 40H60V60H40Z" stroke={a} {...dr(0.2)} />
				<path d={pts(4, (i) => { const v = 36 + i * 9.3; return `M${v} 30V20M${v} 70V80M30 ${v}H20M70 ${v}H80`; })} {...dr(0.3)} />
				<path d="M40 40H60V60H40Z" stroke={a} opacity={1 - pulse} transform={`translate(${50 - 50 * (1 + pulse * 0.6)} ${50 - 50 * (1 + pulse * 0.6)}) scale(${1 + pulse * 0.6})`} strokeWidth="1.2" />
			</>
		);
	},
	monitor: ({t, dr, a}) => (
		<>
			<path d="M10 16H90V68H10Z" {...dr(0)} />
			<path d="M42 68L38 82H62L58 68M30 84H70" {...dr(0.15)} />
			<path d="M18 58L32 46L44 52L58 34L82 26" stroke={a} {...dr(0.3)} />
			<circle cx="82" cy="26" r={2.5 + Math.abs(Math.sin(t * 3))} fill={a} stroke="none" opacity={ramp(t, 1, 0.3)} />
		</>
	),
	chart: ({t, dr, a}) => (
		<>
			<path d="M14 14V86H88" {...dr(0)} />
			<path d="M24 78V62M40 78V52M56 78V58M72 78V36" strokeWidth="5" strokeOpacity=".35" {...dr(0.15)} />
			<path d="M20 70L38 52L54 58L80 26" stroke={a} {...dr(0.3)} />
			<path d="M70 24L82 24L82 36" stroke={a} {...dr(0.5)} />
			<circle cx="80" cy="26" r={3 + Math.abs(Math.sin(t * 3))} fill={a} stroke="none" opacity={ramp(t, 1, 0.3)} />
		</>
	),
	globe: ({t, dr, a}) => (
		<>
			<circle cx="50" cy="50" r="34" {...dr(0)} />
			<path d="M16 50H84M22 32H78M22 68H78" strokeOpacity=".6" {...dr(0.2)} />
			{[0, 1.05, 2.1].map((k, i) => <ellipse key={i} cx="50" cy="50" ry="34" rx={Math.abs(34 * Math.cos(t * 0.7 + k))} strokeOpacity=".7" stroke={i === 0 ? a : undefined} opacity={ramp(t, 0.4, 0.4)} />)}
		</>
	),
	ban: ({dr, t}) => (
		<g transform={`translate(50 50) scale(${1 + 0.04 * Math.sin(t * 4)}) translate(-50 -50)`}>
			<circle cx="50" cy="50" r="34" stroke={C.red} {...dr(0)} strokeWidth="4" />
			<path d="M26 74L74 26" stroke={C.red} {...dr(0.3)} strokeWidth="4" />
		</g>
	),
	license: ({t, dr, a}) => {
		const s = ramp(t, 1.0, 0.25);
		return (
			<>
				<path d="M26 12H60L74 26V88H26Z" {...dr(0)} />
				<path d="M60 12V26H74" {...dr(0.15)} />
				<path d="M34 38H66M34 48H66M34 58H54" strokeOpacity=".7" {...dr(0.25)} />
				<g opacity={s} transform={`translate(64 74) scale(${1.8 - 0.8 * s}) rotate(-14)`}>
					<circle r="12" stroke={a} strokeWidth="2.5" />
					<path d="M-6 0L-2 4L6 -5" stroke={a} strokeWidth="2.5" />
				</g>
			</>
		);
	},
	law: ({t, dr, a}) => {
		const tilt = Math.sin(t * 1.4) * 6;
		return (
			<>
				<path d="M50 14V84M32 86H68" {...dr(0)} />
				<g transform={`rotate(${tilt} 50 26)`}>
					<path d="M18 26H82" {...dr(0.15)} />
					<g transform={`rotate(${-tilt} 18 26)`}><path d="M18 26L8 48H28Z" {...dr(0.3)} /></g>
					<g transform={`rotate(${-tilt} 82 26)`}><path d="M82 26L72 48H92Z" stroke={a} {...dr(0.35)} /></g>
				</g>
				<circle cx="50" cy="14" r="3" fill={a} stroke="none" />
			</>
		);
	},
	coins: ({t, dr, a}) => (
		<>
			{[0, 1, 2, 3].map((i) => {
				const y = 76 - i * 12, o = ramp(t, 0.3 + i * 0.22, 0.3);
				return <g key={i} opacity={o} transform={`translate(0 ${(1 - o) * -18})`}>
					<ellipse cx="44" cy={y} rx="22" ry="7" stroke={i === 3 ? a : undefined} />
					<path d={`M22 ${y}V${y + 7}M66 ${y}V${y + 7}`} />
				</g>;
			})}
			<circle cx="76" cy="40" r="12" {...dr(0.2)} stroke={a} />
			<path d="M72 34L76 40L80 34M76 40V48M72 42H80" stroke={a} {...dr(0.4)} />
		</>
	),
	box: ({t, dr, a}) => {
		const lift = Math.sin(t * 2) * 1.5;
		return (
			<g transform={`translate(0 ${lift})`}>
				<path d="M50 18L82 34V68L50 84L18 68V34Z" {...dr(0)} />
				<path d="M18 34L50 50L82 34M50 50V84" {...dr(0.2)} />
				<path d="M34 26L66 42V54" stroke={a} {...dr(0.35)} />
			</g>
		);
	},
	trophy: ({t, dr, a}) => {
		const tw = Math.abs(Math.sin(t * 3));
		return (
			<>
				<path d="M34 16H66V38C66 50 58 58 50 58C42 58 34 50 34 38Z" stroke={a} {...dr(0)} />
				<path d="M34 24H24C24 36 30 40 36 42M66 24H76C76 36 70 40 64 42" {...dr(0.15)} />
				<path d="M50 58V72M36 72H64V84H36Z" {...dr(0.25)} />
				<path d="M78 12L80 18L86 20L80 22L78 28L76 22L70 20L76 18Z" fill={a} stroke="none" opacity={tw * ramp(t, 0.9, 0.3)} />
			</>
		);
	},
	ship: ({t, dr, a}) => {
		const w = (t * 20) % 16;
		return (
			<>
				<g transform={`translate(0 ${Math.sin(t * 2) * 1.5})`}>
					<path d="M8 62H92L80 80H20Z" {...dr(0)} />
					<path d="M22 62V48H40V62M40 62V48H58V62M58 62V40H76V62" {...dr(0.2)} />
					<path d="M40 48V40H58V48" stroke={a} {...dr(0.35)} />
				</g>
				<path d={`M${-16 + w} 88${pts(8, (i) => `q4 -4 8 0t8 0`)}`} strokeOpacity=".6" opacity={ramp(t, 0.5, 0.4)} />
			</>
		);
	},
	factory: ({t, dr, a}) => (
		<>
			<path d="M10 86V52L30 62V52L50 62V52L70 62V28H84V86Z" {...dr(0)} />
			<path d="M20 76H28M40 76H48M60 76H68" stroke={a} {...dr(0.3)} />
			{[0, 1, 2].map((i) => {
				const k = ((t * 0.5 + i / 3) % 1);
				return <circle key={i} cx={77 + k * 8} cy={24 - k * 20} r={3 + k * 6} opacity={(1 - k) * 0.6 * ramp(t, 0.6, 0.4)} strokeOpacity=".7" />;
			})}
		</>
	),
	flag: ({t, dr, a}) => {
		const wv = (x: number) => Math.sin(t * 3 + x / 12) * 4;
		const top = pts(7, (i) => { const x = 30 + (i + 1) * 9; return `L${x} ${18 + wv(x)}`; });
		const bot = pts(7, (i) => { const x = 93 - (i + 1) * 9; return `L${x} ${48 + wv(x)}`; });
		return (
			<>
				<path d="M26 10V90" {...dr(0)} />
				<path d={`M26 18${top}L93 ${48 + wv(93)}${bot}L26 48`} stroke={a} {...dr(0.2)} />
			</>
		);
	},
	clock: ({t, dr, a}) => (
		<>
			<circle cx="50" cy="50" r="34" {...dr(0)} />
			<path d={pts(12, (i) => { const r = (i * Math.PI) / 6; return `M${50 + 28 * Math.cos(r)} ${50 + 28 * Math.sin(r)}L${50 + 32 * Math.cos(r)} ${50 + 32 * Math.sin(r)}`; })} {...dr(0.2)} />
			<path d="M50 50V30" transform={`rotate(${t * 30} 50 50)`} strokeWidth="3" />
			<path d="M50 50V22" stroke={a} transform={`rotate(${t * 240} 50 50)`} />
		</>
	),
	shield: ({t, dr, a}) => (
		<>
			<path d="M50 12L80 24V48C80 66 68 80 50 88C32 80 20 66 20 48V24Z" {...dr(0)} />
			<path d="M38 50L47 59L64 40" stroke={a} {...dr(0.35)} strokeWidth="3" />
			<path d="M50 12L80 24V48C80 66 68 80 50 88C32 80 20 66 20 48V24Z" strokeOpacity={0.4 * Math.abs(Math.sin(t * 2))} strokeWidth="6" />
		</>
	),
	server: ({t, dr, a}) => (
		<>
			{[14, 40, 66].map((y, i) => (
				<g key={y}>
					<path d={`M18 ${y}H82V${y + 20}H18Z`} {...dr(i * 0.12)} />
					<circle cx="28" cy={y + 10} r="2.5" fill={Math.sin(t * 6 + i * 2) > 0 ? a : 'none'} stroke={a} />
					<path d={`M40 ${y + 10}H72`} strokeOpacity=".5" {...dr(0.3 + i * 0.1)} />
				</g>
			))}
		</>
	),
	bolt: ({t, dr, a}) => <path d="M56 8L22 56H48L42 92L78 40H52Z" stroke={a} {...dr(0)} strokeWidth={2.5 + Math.abs(Math.sin(t * 6))} />,
};

export const FIGURES = Object.keys(FIG);

// words → figure. First match wins, so specific subjects come before generic ones.
const KEYS: [RegExp, string][] = [
	[/\b(ban(ned|s)?|prohibit|forbid|censor|blocked)\w*\b/i, 'ban'],
	[/\b(licen[cs]e|approv|permit|isbn|stamp)/i, 'license'],
	[/\b(regulat|rules?|laws?|criteria|policy|policies|legal|court)\w*\b/i, 'law'],
	[/\b(gpus?|graphics card|geforce|rtx|radeon|7g100|lisuan|moore threads|vram|gddr)\w*\b/i, 'gpu'],
	[/\b(chips?|semiconductor|silicon|wafer|h20|h100|processor|cpu)\w*\b/i, 'chip'],
	[/\b(export|ship(ping|ped)?|trade|tariff|import)\w*\b/i, 'ship'],
	[/\b(factory|manufactur|production|fab|plant|assembly)\w*\b/i, 'factory'],
	[/(\$|\b(price[ds]?|rmb|yuan|usd|dollars?|cost|revenue|billions?|earn|profit|funding|money)\b)/i, 'coins'],
	[/\b(copies|sold|units|reserv|pre-?orders?|sales|shipments?)\w*\b/i, 'box'],
	[/\b(players?|gamers?|people|users|audiences?|fans|population|citizens|minors|kids)\w*\b/i, 'crowd'],
	[/\b(fps|frames|benchmarks?|performance|3dmark|resolution|1080p|4k)\w*\b/i, 'monitor'],
	[/\b(games?|gaming|consoles?|wukong|myth|cyberpunk|studio|esports)\w*\b/i, 'controller'],
	[/\b(grow(th|s|ing)?|rise|rising|increase|accelerat|momentum|surge|boom|record)\w*\b/i, 'chart'],
	[/\b(global|world|international|abroad|overseas|countries)\w*\b/i, 'globe'],
	[/\b(china|chinese|beijing|u\.s\.|america\w*|washington|nation(al)?|pride|government)\b/i, 'flag'],
	[/\b(win|wins|won|success\w*|awards?|hits?|best)\b/i, 'trophy'],
	[/\b(hours?|minutes?|weeks?|hrs|deadlines?)\b/i, 'clock'],
	[/\b(security|protect|sanction|control|defen[cs]e|safe)\w*\b/i, 'shield'],
	[/\b(servers?|data ?cent\w*|cloud|ai)\b/i, 'server'],
	[/\b(power|energy|electric\w*|batter\w*)\b/i, 'bolt'],
];
export const figFor = (text?: string, fallback: string | null = null, only?: string[]): string | null => {
	const s = String(text || '');
	for (const [rx, f] of KEYS) if ((!only || only.includes(f)) && rx.test(s)) return f;
	return fallback;
};
export const STRONG = ['ban', 'license', 'law', 'gpu', 'chip', 'ship', 'factory', 'coins', 'box', 'crowd', 'monitor', 'controller', 'globe', 'server'];

// one figure: size px, draw 0→1 (strokes stagger in), t drives the idle motion
export const Figure: React.FC<{id: string | null; size: number; draw?: number; t: number; color?: string; accent?: string; stroke?: number; style?: React.CSSProperties}> =
	({id, size, draw = 1, t, color = C.cyan, accent = C.amber, stroke = 2.4, style}) => {
	if (isLib(id || '')) return <div style={{opacity: Math.min(1, draw * 2.5), transform: `translateY(${(1 - Math.min(1, draw * 2)) * 12}px)`, ...style}}><DioItem id={id!} size={size} t={t} /></div>;
	const f = id ? FIG[id] : null;
	if (!f) return null;
	const dr = (o = 0) => {
		const p = Math.max(0, Math.min(1, (draw - o) / 0.6));
		return {pathLength: 1, strokeDasharray: 1, strokeDashoffset: 1 - p};
	};
	return (
		<svg width={size} height={size} viewBox="0 0 100 100" style={{overflow: 'visible', ...style}} fill="none" stroke={color} strokeWidth={stroke}
			strokeLinecap="round" strokeLinejoin="round" opacity={Math.min(1, draw * 3)}>
			{f({t, dr, a: accent, c: color})}
		</svg>
	);
};

// the same, placed inside an SVG scene (x, y = centre)
export const SvgFigure: React.FC<{id: string | null; x: number; y: number; size: number; draw?: number; t: number; color?: string; accent?: string}> = (p) =>
	p.id ? <foreignObject x={p.x - p.size / 2} y={p.y - p.size / 2} width={p.size} height={p.size} style={{overflow: 'visible'}}>
		<Figure id={p.id} size={p.size} draw={p.draw} t={p.t} color={p.color} accent={p.accent} />
	</foreignObject> : null;
