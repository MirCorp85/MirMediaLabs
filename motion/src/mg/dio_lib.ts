// @ts-nocheck
/* DIORAMA LIBRARY — the shared motion library (Oct 29 2026, user: "a complete library … places, characters, objects,
   animals"; "characters need more movement sets, the arms don't move right"; "the actions should do what the narrator says";
   "driving inside a car, riding a bike, playing soccer, fighting in a war").
   Everything here is drawn in the RIG frame of a person (feet at 0,0, up = -y, 400 units tall, facing +x) so the same code
   draws: the Diorama hero + cast, Explainer "dio" pictures (DioItem), EXPLAINED figures and the library thumbnails.
   ACTS   = movement sets: per-frame hand targets + legs + body + held items + rides + set pieces (pure functions of time).
   ITEMS  = held objects.  RIDES = vehicles / mounts.  PIECES = set pieces beside the actor.  AMBIENT = screen weather/war.
   SPECIES = animals (one quadruped / bird / fish / critter rig, many species).  HATS = headwear. */
const PI = Math.PI;
const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x), frac = (x) => x - Math.floor(x), lerp = (a, b, u) => a + (b - a) * u;
const hash = (n) => frac(Math.sin(n * 127.1 + 311.7) * 43758.5453);
const ss = (u) => {u = clamp(u); return u * u * (3 - 2 * u);};
const pulse = (u, per, on) => {const q = frac(u / per); return ss(q / on) * (1 - ss((q - on) / on));};       // 0→1→0 inside each period
export const LC = {char0: '#0B0B0D', char1: '#131418', graph: '#1E2026', graph2: '#2A2D34', steel: '#4A4F58', steel2: '#6B717C', silver: '#A7ADB6', silver2: '#D8DCE2',
	bronze: '#7A5226', brass: '#B8862E', gold: '#FFB547', champ: '#F2D49B', pale: '#FFF3DC', white: '#F2F6FA', ember: '#E0703A', olive: '#4B5340', olive2: '#6A7458', glass: 'rgba(120,140,160,.35)'};
const C = LC, BRONZE = LC.bronze;
const NL = [-58, -188], NR = [58, -188];                     // neutral hands (far, near)
const W = (a, b) => [a, b];
const sway = (u, ph, k = 2) => Math.sin(u * 1.6 + ph) * k;

/* ── movement sets. f(u, ph, t) → spec. u = seconds into the beat, ph = per-actor phase. Spec fields:
   arms [[far],[near]] hand targets · hold [far item, near item] · two (an item held in both hands) · legs stand|walk|run|step|sit|
   kneel|crouch|jump|pedal|straddle|hidden|tiptoe · drop (body lowered) · lift (whole body up) · lean (about the hips, + = forward) ·
   rot (whole body, fall/swim) · tilt (head) · look [x,y] eyes · face {o,b,f,m,eyes,tears,yawn} · talk · shake · ride · piece ·
   hat · amb (screen ambience) · walk (legs keep walking in place, 0..1) · speed (gait speed) ── */
const A = (cat, desc, f) => ({cat, desc, f});
export const ACTS = {
	// ── everyday ──
	stand: A('basic', 'stands, relaxed', (u, ph) => ({arms: [[-58, -188 + sway(u, ph)], [58, -188 + sway(u, ph + 1)]]})),
	sleep: A('basic', 'asleep in bed', () => ({arms: [[-30, -175], [30, -175]], face: {eyes: 'closed'}})),
	shock: A('react', 'jolted, arms flung out', (u) => ({arms: [[-74, -300 - Math.exp(-u * 4) * 30], [74, -300 - Math.exp(-u * 4) * 30]], face: {o: 1.3, m: 1}})),
	listen: A('react', 'hand cupped to the ear', (u, ph) => ({arms: [NL, [48, -392]], tilt: -.12, look: [-2.5, 0]})),
	ears: A('react', 'both hands at the ears', () => ({arms: [[-48, -392], [48, -392]]})),
	cover: A('react', 'hands over the ears', () => ({arms: [[-46, -388], [46, -388]], face: {eyes: 'closed', f: 1}})),
	flinch: A('react', 'winces', (u) => ({arms: [[-54, -232], [54, -232]], shrug: Math.exp(-frac(u / .5) * 10) * 10})),
	heart: A('react', 'hand on the chest', () => ({arms: [NL, [-2, -286]]})),
	point: A('talk', 'points at something', (u) => ({arms: [NL, [128, -372 + Math.sin(u * 3) * 4]], look: [2.5, -2]})),
	think: A('talk', 'hand at the chin, thinking', (u, ph) => ({arms: [[18, -262], [24, -362]], tilt: .08, look: [1.5, -2.5]})),
	explain: A('talk', 'talks with open hands', (u, ph) => ({arms: [[-86 + Math.sin(u * 3 + ph) * 10, -268 + Math.cos(u * 2.4 + ph) * 8], [92 + Math.cos(u * 3.4 + ph) * 12, -282 + Math.sin(u * 2.8 + ph) * 10]], talk: true})),
	talk: A('talk', 'chats, one hand gesturing', (u, ph) => ({arms: [[-58, -194], [78 + Math.sin(u * 2.6 + ph) * 14, -262 + Math.cos(u * 3.1 + ph) * 12]], talk: true})),
	celebrate: A('react', 'arms up, celebrating', (u) => ({arms: [[-70, -452 + Math.sin(u * 8) * 14], [70, -452 - Math.sin(u * 8) * 14]], lift: Math.abs(Math.sin(u * 4)) * 14, face: {m: 1, eyes: 'laugh'}})),
	type: A('work', 'types at a keyboard', (u, ph) => ({arms: [[50 + Math.sin(u * 30 + ph) * 3, -236 + Math.abs(Math.sin(u * 22)) * 4], [78 + Math.sin(u * 27) * 3, -232 + Math.abs(Math.sin(u * 19 + 1)) * 4]], look: [1, 1.5]})),
	shrug: A('talk', 'shrugs', () => ({arms: [[-84, -250], [84, -250]], shrug: 12})),
	wave: A('talk', 'waves hello / goodbye', (u) => ({arms: [NL, [72 + Math.sin(u * 9) * 26, -440]], face: {m: .6}})),
	phone: A('phone', 'on a phone call, phone at the ear', (u, ph) => ({arms: [[-30, -386], [64 + Math.sin(u * 2.2 + ph) * 10, -236 + Math.cos(u * 2.7) * 12]], hold: ['phone', null], talk: true, tilt: -.06})),
	text: A('phone', 'texting, looking down at the phone', (u) => ({arms: [[8 + Math.sin(u * 18) * 2, -262], [30, -258 + Math.abs(Math.sin(u * 15)) * 3]], two: 'phone', look: [1, 3], tilt: .14})),
	scroll: A('phone', 'scrolls a phone, thumb flicking', (u) => ({arms: [[-58, -190], [34, -270 + pulse(u, .9, .3) * 8]], hold: [null, 'phone'], look: [1.5, 3], tilt: .12})),
	selfie: A('phone', 'takes a selfie, phone held out', (u) => ({arms: [NL, [96, -430]], hold: [null, 'phone'], face: {m: .8}, look: [2, -2]})),
	drink: A('food', 'drinks from a cup', (u) => {const k = pulse(u, 3.2, .35); return {arms: [NL, [lerp(46, 24, k), lerp(-252, -370, k)]], hold: [null, 'cup'], tilt: -.1 * k};}),
	eat: A('food', 'eats with a fork, plate in hand', (u) => {const k = pulse(u, 1.8, .3); return {arms: [[-4, -252], [lerp(40, 22, k), lerp(-262, -372, k)]], hold: ['plate', 'fork'], look: [1, 1.5 - k * 2]};}),
	cook: A('food', 'cooks at the stove, tossing the pan', (u) => ({arms: [NL, [118, -262 - Math.abs(Math.sin(u * 5)) * 18]], hold: [null, 'pan'], piece: 'stove', look: [2, 2]})),
	read: A('work', 'reads a book', (u) => ({arms: [[-8, -264], [36, -260]], two: 'book', look: [1, 2.5], tilt: .1})),
	write: A('work', 'writes in a notebook', (u) => ({arms: [[-6, -252], [22 + Math.sin(u * 14) * 6, -258 + Math.cos(u * 11) * 4]], hold: ['note', 'pen'], look: [1, 3], tilt: .12})),
	present: A('talk', 'presents, palm toward a screen', (u, ph) => ({arms: [NL, [124, -334 + Math.sin(u * 2) * 8]], talk: true, look: [2.5, -1]})),
	carry: A('work', 'carries a box', () => ({arms: [[-22, -262], [38, -262]], two: 'box'})),
	lift: A('sport', 'lifts a barbell overhead', (u) => {const k = pulse(u, 2.6, .4); return {arms: [[-46, lerp(-262, -452, k)], [46, lerp(-262, -452, k)]], two: 'barbell', drop: (1 - k) * 16, face: {f: 1, m: -1}};}),
	push: A('work', 'pushes something heavy', (u) => ({arms: [[118, -292], [134, -282]], lean: .2, legs: 'step', walk: .4, face: {f: 1, m: -1}})),
	pull: A('work', 'pulls a rope', (u) => {const k = Math.sin(u * 3) * .5 + .5; return {arms: [[lerp(130, 70, k), -300], [lerp(150, 90, k), -296]], lean: -.15, two: 'rope', face: {f: 1}};}),
	reach: A('work', 'reaches up for something', (u) => ({arms: [NL, [96, -456 + Math.sin(u * 4) * 6]], lift: 8, look: [2, -3]})),
	knock: A('work', 'knocks on a door', (u) => ({arms: [NL, [112 - Math.abs(Math.sin(u * 9)) * 14, -362]]})),
	open: A('work', 'opens a door', (u) => {const k = ss(u / .8); return {arms: [NL, [lerp(110, 70, k), -250]], piece: 'door', pieceU: k};}),
	look: A('react', 'looks far away, hand shading the eyes', (u, ph) => ({arms: [NL, [30, -420]], look: [3, -1], tilt: -.04})),
	search: A('react', 'looks around, searching', (u) => ({arms: [[-60, -215], [62, -215]], look: [Math.sin(u * 1.4) * 3, 0], tilt: Math.sin(u * 1.4) * .06})),
	clap: A('react', 'claps', (u) => {const o = Math.abs(Math.sin(u * 7)) * 20; return {arms: [[8 + o * .3, -296], [40 - o, -296]], face: {m: .8}};}),
	cheer: A('react', 'fist pump, yes!', (u) => ({arms: [NL, [58, -430 + Math.sin(u * 10) * 18]], face: {m: 1, eyes: 'laugh'}, lift: Math.abs(Math.sin(u * 5)) * 8})),
	thumbs: A('react', 'thumbs up', () => ({arms: [NL, [86, -300]], hold: [null, 'thumb'], face: {m: .6}})),
	dance: A('fun', 'dances', (u) => {const s = Math.sin(u * 6); return {arms: [[-80 - s * 20, -360 + s * 70], [80 - s * 20, -360 - s * 70]], legs: 'step', walk: 1, speed: 6, lean: s * .06, lift: Math.abs(Math.cos(u * 6)) * 10, face: {m: 1}};}),
	jump: A('sport', 'jumps for joy', (u) => {const k = Math.abs(Math.sin(u * PI / .75)); return {arms: [[-70, lerp(-260, -450, k)], [70, lerp(-260, -450, k)]], lift: k * 70, legs: k > .2 ? 'jump' : 'stand', face: {m: 1}};}),
	run: A('sport', 'runs', (u, ph) => {const s = Math.sin(u * 13 + ph); return {arms: [[-20 + s * 34, -258], [52 - s * 34, -258]], legs: 'run', walk: 1, speed: 13, lean: .16};}),
	jog: A('sport', 'jogs', (u, ph) => {const s = Math.sin(u * 9 + ph); return {arms: [[-24 + s * 24, -256], [50 - s * 24, -256]], legs: 'run', walk: .7, speed: 9, lean: .08};}),
	walk: A('basic', 'walks', (u, ph) => ({arms: [NL, NR], legs: 'walk', walk: 1, speed: 8.5})),
	// Oct 29 (user: "when it says he crawls nothing happens"): real ground movements. shift = slides forward along the facing (rig units)
	crawl: A('basic', 'crawls on the ground on elbows and knees', (u) => {const s = Math.sin(u * 4.5); return {arms: [[-20 + s * 46, -470], [40 - s * 46, -470]], legs: 'walk', walk: .55, speed: 4.5, rot: PI / 2 * ss(u / .45), shift: Math.min(u * 55, 260) * ss(u / .45), face: {f: 1}, move: true};}),
	climb: A('basic', 'climbs a ladder / a wall', (u) => {const s = Math.sin(u * 4); return {arms: [[-34, -470 + s * 34], [40, -470 - s * 34]], legs: 'step', walk: 1, speed: 4, lift: Math.min(u * 45, 220), piece: 'ladder', look: [0, -3], tilt: -.08};}),
	lie: A('basic', 'lies on the ground, resting or hurt', (u) => ({arms: [[-80, -300], [60, -200]], rot: -PI / 2 * ss(u / .5), face: {eyes: 'closed'}, sq: Math.sin(u * 2) * .01})),
	limp: A('feel', 'limps, wounded, a hand on the leg', (u, ph) => ({arms: [[-58, -194], [30, -150 + Math.sin(u * 3) * 6]], legs: 'step', walk: .45, speed: 3, lean: .12 + Math.sin(u * 3) * .04, face: {f: 1, m: -1}, shift: Math.min(u * 18, 120), move: true})),
	wounded: A('feel', 'clutches a wound, in pain', (u) => ({arms: [[4, -262], [24, -250]], lean: .2, drop: 20, face: {eyes: 'closed', f: 1, m: -1}, shake: Math.sin(u * 30) * 1.2})),
	aim: A('war', 'aims a rifle, steady', (u) => ({arms: [[70, -352], [118, -368]], two: 'rifle', hat: 'helmet', lean: .05, look: [3, 0], face: {f: 1}})),
	duck: A('react', 'ducks, head down, hands over the head', (u) => ({arms: [[-6, -404], [22, -410]], legs: 'crouch', drop: 52, face: {eyes: 'closed', f: 1}})),
	sleepground: A('basic', 'sleeps on the ground', (u) => ({arms: [[-30, -175], [30, -175]], rot: -PI / 2, face: {eyes: 'closed'}, zz: 1})),
	sneak: A('fun', 'sneaks on tiptoe', (u) => ({arms: [[56, -300], [86, -322]], legs: 'step', walk: .5, speed: 3, drop: 28, lean: .14, look: [2, 0], move: true})),
	sit: A('basic', 'sits on a chair', (u, ph) => ({arms: [[12, -198], [48, -198 + sway(u, ph)]], legs: 'sit', drop: 74, piece: 'chair'})),
	sitdesk: A('work', 'sits at a desk typing', (u, ph) => ({arms: [[62 + Math.sin(u * 30) * 3, -240], [90 + Math.sin(u * 27) * 3, -236]], legs: 'sit', drop: 74, piece: 'desk', look: [1, 1]})),
	kneel: A('basic', 'kneels', () => ({arms: [[20, -206], [60, -214]], legs: 'kneel', drop: 62})),
	crouch: A('basic', 'crouches low', () => ({arms: [[40, -230], [70, -224]], legs: 'crouch', drop: 44})),
	cry: A('feel', 'cries, face in hands', (u) => ({arms: [[8, -386], [30, -382]], face: {eyes: 'closed', tears: 1, m: -1, b: 4}, shrug: Math.abs(Math.sin(u * 7)) * 4, tilt: .15})),
	laugh: A('feel', 'laughs out loud', (u) => ({arms: [[10, -238], [70, -250]], face: {eyes: 'laugh', m: 1}, sq: Math.sin(u * 16) * .012, tilt: -.08})),
	facepalm: A('feel', 'facepalm', () => ({arms: [NL, [26, -410]], face: {eyes: 'closed', f: 1}, tilt: .16})),
	worry: A('feel', 'hands on the head, worried', () => ({arms: [[-26, -430], [30, -432]], face: {o: 1.15, b: 5, f: 1, m: -1}})),
	panic: A('feel', 'panics, arms flailing', (u) => ({arms: [[-90 + Math.sin(u * 11) * 20, -380 + Math.cos(u * 9) * 50], [90 + Math.cos(u * 12) * 20, -380 + Math.sin(u * 10) * 50]], legs: 'run', walk: .6, speed: 14, face: {o: 1.4, m: 1}})),
	tired: A('feel', 'slumps, exhausted', (u) => ({arms: [[-50, -176], [50, -176]], lean: .14, tilt: .22, face: {o: .35}})),
	yawn: A('feel', 'yawns and stretches', (u) => ({arms: [[-46, -460], [22, -372]], face: {eyes: 'closed', yawn: 1}})),
	stretch: A('feel', 'stretches, arms up', (u) => ({arms: [[-40, -472], [40, -472]], lift: 6, face: {eyes: 'closed'}})),
	cross: A('talk', 'arms crossed', () => ({arms: [[30, -278], [-12, -272]], face: {f: 1}})),
	hips: A('talk', 'hands on the hips', () => ({arms: [[-60, -212], [62, -212]]})),
	pray: A('feel', 'hands together, praying / hoping', () => ({arms: [[14, -302], [24, -302]], face: {eyes: 'closed'}, tilt: .12})),
	nod: A('talk', 'nods yes', (u) => ({arms: [NL, NR], tilt: Math.sin(u * 7) * .1})),
	no: A('talk', 'shakes the head no', (u) => ({arms: [[-60, -215], [62, -215]], look: [Math.sin(u * 8) * 3.5, 0], tilt: Math.sin(u * 8) * .04, face: {f: 1}})),
	salute: A('talk', 'salutes', () => ({arms: [NL, [22, -420]]})),
	bow: A('talk', 'bows', (u) => ({arms: [[-50, -200], [40, -210]], lean: .5 * ss(u / .5)})),
	fall: A('feel', 'trips and falls flat', (u) => ({arms: [[-90, -330], [90, -330]], rot: -PI / 2 * ss(u / .45), face: {o: 1.3, m: 1}})),
	hide: A('fun', 'hides, peeking out', (u) => ({arms: [[40, -300], [62, -330]], legs: 'crouch', drop: 44, look: [3, 0], piece: 'crate'})),
	hug: A('people', 'hugs someone', () => ({arms: [[100, -300], [118, -296]], face: {eyes: 'closed', m: .6}})),
	handshake: A('people', 'shakes hands', (u) => ({arms: [NL, [118, -250 + Math.sin(u * 10) * 8]], face: {m: .5}})),
	give: A('people', 'hands something over', () => ({arms: [NL, [116, -266]], hold: [null, 'gift']})),
	receive: A('people', 'receives something, palms up', () => ({arms: [[98, -250], [118, -252]], two: 'letter', face: {o: 1.1}})),
	throw: A('sport', 'throws a ball', (u) => {const q = frac(u / 1.6), k = q < .55 ? ss(q / .55) : 1 - ss((q - .55) / .45); return {arms: [NL, [lerp(-70, 130, 1 - k), lerp(-420, -350, 1 - k)]], hold: [null, q < .6 ? 'ball' : null], ballFly: q >= .6 ? (q - .6) / .4 : -1, lean: (1 - k) * .1};}),
	catch: A('sport', 'catches', () => ({arms: [[96, -382], [112, -374]], two: 'ball', face: {o: 1.2}})),
	pet: A('people', 'pets an animal', (u) => ({arms: [NL, [102 + Math.sin(u * 4) * 14, -128]], legs: 'crouch', drop: 44, face: {m: .6}})),
	photo: A('fun', 'takes a photo', (u) => ({arms: [[20, -392], [46, -392]], two: 'camera', flash: pulse(u, 2.4, .05)})),
	sing: A('fun', 'sings into a mic', (u) => ({arms: [[-90 + Math.sin(u * 2) * 10, -300], [34, -368]], hold: [null, 'mic'], talk: true, face: {eyes: 'closed'}})),
	guitar: A('fun', 'plays the guitar', (u) => ({arms: [[90, -292], [18, -240 + Math.sin(u * 14) * 10]], two: 'guitar', face: {m: .5}})),
	paint: A('fun', 'paints on an easel', (u) => ({arms: [[-8, -250], [118 + Math.sin(u * 5) * 8, -330 + Math.cos(u * 4) * 16]], hold: ['palette', 'brush'], piece: 'easel', look: [2.5, -.5]})),
	water: A('outdoor', 'waters plants', (u) => ({arms: [NL, [112, -246]], hold: [null, 'can'], look: [2.5, 3]})),
	dig: A('outdoor', 'digs with a shovel', (u) => {const k = pulse(u, 1.6, .4); return {arms: [[50, lerp(-300, -250, k)], [96, lerp(-250, -170, k)]], two: 'shovel', lean: .15 + k * .1};}),
	build: A('work', 'hammers, building something', (u) => ({arms: [[90, -230], [100, -330 + Math.abs(Math.sin(u * 6)) * 80]], hold: ['nail', 'hammer'], piece: 'crate', hat: 'hardhat', look: [2, 2]})),
	sweep: A('work', 'sweeps the floor', (u) => ({arms: [[30 + Math.sin(u * 4) * 20, -290], [60 + Math.sin(u * 4) * 30, -224]], two: 'broom', look: [1, 3]})),
	fish: A('outdoor', 'fishes with a rod', (u) => ({arms: [[60, -320], [80, -350 + Math.sin(u * 2) * 6]], two: 'rod', piece: 'water'})),
	umbrella: A('outdoor', 'walks in the rain under an umbrella', (u) => ({arms: [NL, [34, -420]], hold: [null, 'umbrella'], amb: 'rain'})),
	shiver: A('outdoor', 'shivers in the cold', (u) => ({arms: [[30, -286], [-6, -290]], shake: Math.sin(u * 60) * 2.5, hat: 'beanie', amb: 'snow', face: {f: 1}})),
	campfire: A('outdoor', 'warms hands at a campfire', (u) => ({arms: [[104, -230], [118, -226]], legs: 'crouch', drop: 44, piece: 'fire'})),
	swim: A('sport', 'swims', (u) => {const s = Math.sin(u * 5); return {arms: [[-10 + s * 120, -330 - Math.abs(s) * 80], [30 - s * 120, -330 - Math.abs(Math.cos(u * 5)) * 80]], rot: PI / 2.2, piece: 'pool', legs: 'walk', walk: .6, speed: 10};}),
	// ── sports ──
	kick: A('sport', 'kicks the ball into the goal (soccer)', (u) => {const q = frac(u / 2.4); return {arms: [[-80, -300], [70, -250]], legs: 'kick', kick: q, piece: 'goal', ballShot: q, lean: -.05};}),
	dribble: A('sport', 'dribbles a soccer ball', (u, ph) => ({arms: [[-40, -240], [70, -250]], legs: 'run', walk: .8, speed: 11, lean: .1, ball: 'feet'})),
	goalie: A('sport', 'goalkeeper, arms spread', (u) => ({arms: [[-100, -360 + Math.sin(u * 3) * 10], [100, -360 - Math.sin(u * 3) * 10]], legs: 'crouch', drop: 30, piece: 'goalback', hat: 'gloves'})),
	shoot: A('sport', 'shoots a basketball at the hoop', (u) => {const q = frac(u / 2.2), up = ss(q / .4); return {arms: [[30, lerp(-280, -460, up)], [50, lerp(-290, -470, up)]], two: q < .42 ? 'bball' : null, hoopShot: q >= .42 ? (q - .42) / .58 : -1, piece: 'hoop', lift: up * (1 - ss((q - .4) / .2)) * 30};}),
	box: A('fight', 'boxes, punching', (u) => {const q = frac(u / .9), a = pulse(q, 1, .2), b = pulse(frac(q + .5), 1, .2); return {arms: [[lerp(50, 150, a), -346], [lerp(76, 160, b), -340]], hold: ['glove', 'glove'], legs: 'step', walk: .3, speed: 7, lean: .1, face: {f: 1, m: -1}};}),
	sword: A('fight', 'fights with a sword', (u) => {const k = pulse(u, 1.2, .25); return {arms: [[-80, -300], [lerp(40, 150, k), lerp(-440, -300, k)]], hold: [null, 'sword'], lean: k * .12, face: {f: 1}};}),
	// ── war (stylised, no gore) ──
	soldier: A('war', 'a soldier on guard, rifle ready', (u) => ({arms: [[60, -290], [100, -312]], two: 'rifle', hat: 'helmet', amb: 'war', face: {f: 1}})),
	fire: A('war', 'fires a rifle from cover', (u) => ({arms: [[64, -300], [110, -322]], two: 'rifle', muzzle: pulse(u, .5, .08), hat: 'helmet', legs: 'kneel', drop: 62, piece: 'sandbags', amb: 'war', face: {f: 1}})),
	charge: A('war', 'charges into battle', (u, ph) => {const s = Math.sin(u * 12 + ph); return {arms: [[64, -300], [104, -318]], two: 'rifle', hat: 'helmet', legs: 'run', walk: 1, speed: 12, lean: .2, amb: 'war', face: {o: 1.1, m: 1}};}),
	takecover: A('war', 'ducks for cover, hands on the helmet', (u) => ({arms: [[-10, -400], [26, -406]], legs: 'crouch', drop: 44, hat: 'helmet', piece: 'sandbags', amb: 'war', shake: Math.sin(u * 50) * 1.5, face: {eyes: 'closed', f: 1}})),
	march: A('war', 'marches', (u) => {const s = Math.sin(u * 7); return {arms: [[-30 + s * 30, -200], [40 - s * 30, -200]], legs: 'step', walk: 1, speed: 7, hat: 'helmet'};}),
	// ── rides ──
	drive: A('ride', 'drives a car, hands on the wheel', (u) => ({arms: [[96, -300 + Math.sin(u * 1.3) * 4], [118, -292 - Math.sin(u * 1.3) * 4]], ride: 'car', legs: 'hidden', drop: 52, look: [2.5, 0]})),
	passenger: A('ride', 'rides as a passenger, looking out', (u) => ({arms: [[20, -230], [52, -226]], ride: 'car', legs: 'hidden', drop: 52, look: [3, 0]})),
	bike: A('ride', 'rides a bicycle', (u) => ({arms: [[146, -262], [158, -258]], ride: 'bike', legs: 'pedal', drop: -64, lean: .22, speed: 7})),
	moto: A('ride', 'rides a motorbike', (u) => ({arms: [[140, -250], [152, -246]], ride: 'moto', legs: 'straddle', drop: -40, lean: .2, hat: 'helmetm'})),
	horse: A('ride', 'rides a horse', (u) => ({arms: [[104, -250], [118, -246]], ride: 'horse', legs: 'straddle', drop: -192, lean: .06, hold: ['rein', 'rein']})),
	row: A('ride', 'rows a boat', (u) => {const s = Math.sin(u * 3); return {arms: [[lerp(60, 130, s * .5 + .5), -240], [lerp(80, 150, s * .5 + .5), -236]], ride: 'boat', legs: 'hidden', drop: 80, lean: s * .12};}),
	skate: A('ride', 'skateboards', (u) => ({arms: [[-110, -300 + Math.sin(u * 2) * 20], [110, -300 - Math.sin(u * 2) * 20]], ride: 'skate', lift: 22, legs: 'stand', lean: .04})),
	scooter: A('ride', 'rides a kick scooter', (u) => ({arms: [[120, -330], [132, -326]], ride: 'scooter', lift: 20, legs: 'stand'})),
	bus: A('ride', 'sits on a bus / train, city passing by', (u) => ({arms: [[14, -200], [48, -200]], ride: 'bus', legs: 'sit', drop: 74, look: [-2, 0]})),
	fly: A('ride', 'flies a plane', (u) => ({arms: [[96, -300], [116, -296]], ride: 'plane', legs: 'hidden', drop: 40, look: [2.5, 0]})),
	wheelchair: A('ride', 'in a wheelchair', (u) => ({arms: [[-20, -200], [10, -190]], ride: 'wheelchair', legs: 'sit', drop: 74})),
};
export const ACT_NAMES = Object.keys(ACTS);
export const ACT_CATS = [...new Set(ACT_NAMES.map((k) => ACTS[k].cat))];
export const actSpec = (name, u, ph, t) => {const a = ACTS[name] || ACTS.stand; const s = a.f(Math.max(0, u), ph || 0, t || 0) || {}; return s;};

/* ── held items: drawn at a hand (x, y) with the forearm angle `ang` ── */
const rr = (c, x, y, w, h, r, fill, stroke, lw) => {c.beginPath(); c.roundRect(x, y, w, h, r); if (fill) {c.fillStyle = fill; c.fill();} if (stroke) {c.strokeStyle = stroke; c.lineWidth = lw || 2; c.stroke();}};
const grad = (c, x0, y0, x1, y1, a, b) => {const g = c.createLinearGradient(x0, y0, x1, y1); g.addColorStop(0, a); g.addColorStop(1, b); return g;};
export const ITEMS = {
	phone: (c, t) => {rr(c, -8, -18, 16, 32, 4, C.char0, C.steel2, 2); rr(c, -6, -15, 12, 24, 2, 'rgba(255,181,71,.85)');},
	cup: (c, t) => {c.fillStyle = grad(c, -12, 0, 12, 0, C.champ, C.brass); c.beginPath(); c.moveTo(-12, -22); c.lineTo(12, -22); c.lineTo(9, 10); c.lineTo(-9, 10); c.closePath(); c.fill(); c.strokeStyle = C.bronze; c.lineWidth = 4; c.beginPath(); c.arc(14, -6, 7, -PI / 2, PI / 2); c.stroke();
		for (let i = 0; i < 2; i++) {const q = frac(t * .8 + i / 2); c.globalAlpha = Math.sin(q * PI) * .5; c.strokeStyle = C.silver2; c.lineWidth = 3; c.beginPath(); c.moveTo(-3 + i * 6, -26 - q * 30); c.quadraticCurveTo(4 + i * 6, -34 - q * 30, -2 + i * 6, -44 - q * 30); c.stroke();} c.globalAlpha = 1;},
	plate: (c) => {c.fillStyle = C.silver2; c.beginPath(); c.ellipse(0, 0, 30, 8, 0, 0, 7); c.fill(); c.fillStyle = C.brass; c.beginPath(); c.ellipse(-4, -5, 14, 6, 0, 0, 7); c.fill();},
	fork: (c) => {c.strokeStyle = C.silver2; c.lineWidth = 3; c.beginPath(); c.moveTo(0, 10); c.lineTo(0, -26); c.moveTo(-5, -26); c.lineTo(-5, -36); c.moveTo(5, -26); c.lineTo(5, -36); c.stroke();},
	pan: (c, t) => {c.strokeStyle = C.char1; c.lineWidth = 8; c.beginPath(); c.moveTo(0, 0); c.lineTo(28, 0); c.stroke(); c.fillStyle = C.graph; c.beginPath(); c.ellipse(56, 2, 30, 9, 0, 0, 7); c.fill(); c.fillStyle = C.gold; c.beginPath(); c.ellipse(56 + Math.sin(t * 10) * 4, -6 - Math.abs(Math.sin(t * 5)) * 18, 8, 5, 0, 0, 7); c.fill();},
	book: (c) => {c.fillStyle = C.bronze; c.beginPath(); c.moveTo(-30, -16); c.lineTo(0, -10); c.lineTo(30, -16); c.lineTo(30, 18); c.lineTo(0, 24); c.lineTo(-30, 18); c.closePath(); c.fill(); c.fillStyle = C.pale; c.beginPath(); c.moveTo(-26, -13); c.lineTo(-2, -8); c.lineTo(-2, 19); c.lineTo(-26, 14); c.closePath(); c.moveTo(26, -13); c.lineTo(2, -8); c.lineTo(2, 19); c.lineTo(26, 14); c.closePath(); c.fill();
		c.strokeStyle = 'rgba(122,82,38,.5)'; c.lineWidth = 1.5; for (let i = 0; i < 4; i++) {c.beginPath(); c.moveTo(-22, -6 + i * 6); c.lineTo(-6, -3 + i * 6); c.moveTo(6, -3 + i * 6); c.lineTo(22, -6 + i * 6); c.stroke();}},
	note: (c) => {rr(c, -18, -24, 36, 44, 3, C.pale, C.brass, 2);},
	pen: (c) => {c.strokeStyle = C.gold; c.lineWidth = 4; c.beginPath(); c.moveTo(0, 6); c.lineTo(10, -24); c.stroke();},
	letter: (c) => {rr(c, -24, -16, 48, 30, 2, C.pale); c.strokeStyle = C.brass; c.lineWidth = 2; c.beginPath(); c.moveTo(-24, -16); c.lineTo(0, 2); c.lineTo(24, -16); c.stroke(); c.fillStyle = C.ember; c.beginPath(); c.arc(0, 2, 4, 0, 7); c.fill();},
	box: (c) => {c.fillStyle = grad(c, -40, 0, 40, 0, C.bronze, C.brass); c.fillRect(-42, -36, 84, 66); c.fillStyle = C.champ; c.fillRect(-6, -36, 12, 66); c.strokeStyle = C.bronze; c.lineWidth = 2; c.strokeRect(-42, -36, 84, 66);},
	gift: (c) => {c.fillStyle = C.gold; c.fillRect(-20, -22, 40, 36); c.fillStyle = C.ember; c.fillRect(-4, -22, 8, 36); c.fillRect(-20, -8, 40, 7); c.strokeStyle = C.ember; c.lineWidth = 3; c.beginPath(); c.ellipse(-7, -27, 7, 5, .4, 0, 7); c.ellipse(7, -27, 7, 5, -.4, 0, 7); c.stroke();},
	barbell: (c) => {c.strokeStyle = C.silver2; c.lineWidth = 6; c.beginPath(); c.moveTo(-110, 0); c.lineTo(110, 0); c.stroke(); [-96, 96].forEach((x) => {rr(c, x - 9, -32, 18, 64, 4, C.char1, C.steel2, 2);});},
	rope: (c) => {c.strokeStyle = C.brass; c.lineWidth = 6; c.beginPath(); c.moveTo(-60, 4); c.lineTo(150, -6); c.stroke();},
	thumb: (c) => {c.fillStyle = 'rgba(0,0,0,0)';},
	ball: (c, t) => {const g = c.createRadialGradient(-5, -5, 2, 0, 0, 16); g.addColorStop(0, C.white); g.addColorStop(1, C.silver); c.fillStyle = g; c.beginPath(); c.arc(0, 0, 15, 0, 7); c.fill(); c.fillStyle = C.char1; c.beginPath(); c.arc(0, 0, 5, 0, 7); c.fill(); [0, 1.26, 2.5, 3.8, 5].forEach((a) => {c.beginPath(); c.arc(Math.cos(a + t * 3) * 11, Math.sin(a + t * 3) * 11, 3, 0, 7); c.fill();});},
	bball: (c) => {c.fillStyle = C.ember; c.beginPath(); c.arc(0, 0, 18, 0, 7); c.fill(); c.strokeStyle = C.char0; c.lineWidth = 2; c.beginPath(); c.moveTo(-18, 0); c.lineTo(18, 0); c.moveTo(0, -18); c.lineTo(0, 18); c.arc(0, 0, 18, 0, 7); c.stroke();},
	camera: (c, t) => {rr(c, -30, -18, 60, 36, 6, C.char1, C.steel2, 2); c.fillStyle = C.steel2; c.beginPath(); c.arc(14, 0, 12, 0, 7); c.fill(); c.fillStyle = C.char0; c.beginPath(); c.arc(14, 0, 7, 0, 7); c.fill(); rr(c, -24, -24, 14, 7, 2, C.gold);},
	mic: (c) => {c.strokeStyle = C.char1; c.lineWidth = 7; c.beginPath(); c.moveTo(0, 14); c.lineTo(0, -10); c.stroke(); c.fillStyle = C.silver; c.beginPath(); c.arc(0, -18, 10, 0, 7); c.fill();},
	guitar: (c) => {c.fillStyle = grad(c, -50, 0, 30, 0, C.bronze, C.brass); c.beginPath(); c.ellipse(-20, 10, 34, 26, -.3, 0, 7); c.fill(); c.beginPath(); c.ellipse(8, 0, 22, 18, -.3, 0, 7); c.fill(); c.fillStyle = C.char0; c.beginPath(); c.arc(-6, 4, 7, 0, 7); c.fill();
		c.strokeStyle = C.char1; c.lineWidth = 8; c.beginPath(); c.moveTo(14, -4); c.lineTo(96, -36); c.stroke();},
	palette: (c) => {c.fillStyle = C.champ; c.beginPath(); c.ellipse(0, 0, 26, 18, -.2, 0, 7); c.fill(); [C.gold, C.ember, C.steel, C.char0].forEach((k, i) => {c.fillStyle = k; c.beginPath(); c.arc(-12 + i * 8, -6 + (i % 2) * 8, 4, 0, 7); c.fill();});},
	brush: (c) => {c.strokeStyle = C.brass; c.lineWidth = 4; c.beginPath(); c.moveTo(0, 8); c.lineTo(0, -30); c.stroke(); c.fillStyle = C.gold; c.beginPath(); c.ellipse(0, -34, 4, 7, 0, 0, 7); c.fill();},
	can: (c, t) => {c.fillStyle = C.steel2; c.fillRect(-14, -14, 30, 28); c.strokeStyle = C.steel2; c.lineWidth = 5; c.beginPath(); c.moveTo(16, -6); c.lineTo(40, -22); c.stroke(); c.fillStyle = C.silver2;
		for (let i = 0; i < 5; i++) {const q = frac(t * 1.6 + i / 5); c.globalAlpha = 1 - q; c.beginPath(); c.arc(42 + q * 22, -20 + q * 60, 3, 0, 7); c.fill();} c.globalAlpha = 1;},
	shovel: (c) => {c.strokeStyle = C.brass; c.lineWidth = 6; c.beginPath(); c.moveTo(-50, -40); c.lineTo(60, 60); c.stroke(); c.fillStyle = C.steel2; c.beginPath(); c.moveTo(56, 52); c.lineTo(84, 66); c.lineTo(72, 92); c.lineTo(50, 74); c.closePath(); c.fill();},
	hammer: (c) => {c.strokeStyle = C.brass; c.lineWidth = 6; c.beginPath(); c.moveTo(0, 8); c.lineTo(0, -34); c.stroke(); rr(c, -14, -44, 28, 12, 2, C.steel2);},
	nail: (c) => {c.strokeStyle = C.silver2; c.lineWidth = 2; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 14); c.stroke();},
	broom: (c) => {c.strokeStyle = C.brass; c.lineWidth = 5; c.beginPath(); c.moveTo(-40, -60); c.lineTo(40, 110); c.stroke(); c.fillStyle = C.champ; c.beginPath(); c.moveTo(30, 100); c.lineTo(62, 114); c.lineTo(54, 140); c.lineTo(20, 134); c.closePath(); c.fill();},
	rod: (c, t) => {c.strokeStyle = C.char1; c.lineWidth = 4; c.beginPath(); c.moveTo(-20, 20); c.lineTo(160, -110); c.stroke(); c.strokeStyle = 'rgba(216,220,226,.55)'; c.lineWidth = 1.5; c.beginPath(); c.moveTo(160, -110); c.quadraticCurveTo(200, -40, 210 + Math.sin(t) * 4, 150); c.stroke();},
	umbrella: (c) => {c.strokeStyle = C.char1; c.lineWidth = 4; c.beginPath(); c.moveTo(0, 20); c.lineTo(0, -110); c.stroke(); c.fillStyle = grad(c, -90, 0, 90, 0, C.bronze, C.gold); c.beginPath(); c.moveTo(-96, -96); c.quadraticCurveTo(0, -190, 96, -96);
		for (let i = 3; i >= -3; i--) c.quadraticCurveTo(i * 32 + 16, -110, i * 32 - 16 + (i === -3 ? -16 : 0), -96); c.closePath(); c.fill();},
	glove: (c) => {c.fillStyle = C.ember; c.beginPath(); c.ellipse(0, 0, 17, 15, 0, 0, 7); c.fill(); c.fillStyle = C.pale; c.fillRect(-14, 10, 28, 7);},
	sword: (c) => {c.strokeStyle = C.silver2; c.lineWidth = 6; c.beginPath(); c.moveTo(0, -8); c.lineTo(0, -120); c.stroke(); c.strokeStyle = C.gold; c.lineWidth = 6; c.beginPath(); c.moveTo(-16, -8); c.lineTo(16, -8); c.stroke(); c.strokeStyle = C.bronze; c.beginPath(); c.moveTo(0, -6); c.lineTo(0, 14); c.stroke();},
	rifle: (c) => {c.fillStyle = C.char1; c.save(); c.rotate(-.12); rr(c, -60, -9, 170, 14, 4, C.graph, C.char0, 2); rr(c, -76, -6, 34, 24, 5, C.bronze); rr(c, 10, 2, 14, 26, 3, C.char0); c.restore();},
	rein: (c) => {},
	flowers: (c) => {c.strokeStyle = C.olive2; c.lineWidth = 3; [-8, 0, 8].forEach((x) => {c.beginPath(); c.moveTo(0, 14); c.lineTo(x, -24); c.stroke();}); [[-8, -28], [0, -32], [8, -27]].forEach(([x, y], i) => {c.fillStyle = [C.gold, C.ember, C.champ][i]; c.beginPath(); c.arc(x, y, 8, 0, 7); c.fill();});},
	bag: (c) => {rr(c, -22, -4, 44, 40, 6, C.bronze); c.strokeStyle = C.brass; c.lineWidth = 4; c.beginPath(); c.arc(0, -4, 14, PI, 0); c.stroke();},
	briefcase: (c) => {rr(c, -30, 0, 60, 40, 4, C.char1, C.brass, 2); c.strokeStyle = C.brass; c.lineWidth = 4; c.beginPath(); c.moveTo(-10, 0); c.lineTo(-10, -8); c.lineTo(10, -8); c.lineTo(10, 0); c.stroke();},
	key: (c) => {c.strokeStyle = C.gold; c.lineWidth = 4; c.beginPath(); c.arc(0, -12, 7, 0, 7); c.moveTo(0, -5); c.lineTo(0, 16); c.lineTo(6, 16); c.moveTo(0, 10); c.lineTo(6, 10); c.stroke();},
	flashlight: (c, t) => {rr(c, -6, -26, 12, 34, 3, C.steel2); const g = c.createLinearGradient(0, -26, 0, -200); g.addColorStop(0, 'rgba(255,243,220,.6)'); g.addColorStop(1, 'rgba(255,243,220,0)'); c.fillStyle = g; c.beginPath(); c.moveTo(-6, -26); c.lineTo(-60, -200); c.lineTo(60, -200); c.lineTo(6, -26); c.closePath(); c.fill();},
	money: (c) => {[0, 1, 2].forEach((i) => {rr(c, -24 + i * 3, -14 - i * 4, 48, 26, 3, i === 2 ? C.champ : C.brass, C.bronze, 1.5);}); c.fillStyle = C.bronze; c.font = '800 16px sans-serif'; c.textAlign = 'center'; c.fillText('$', 6, 6);},
	trophy: (c) => {c.fillStyle = grad(c, -20, 0, 20, 0, C.brass, C.gold); c.beginPath(); c.moveTo(-20, -40); c.lineTo(20, -40); c.quadraticCurveTo(20, -8, 0, -4); c.quadraticCurveTo(-20, -8, -20, -40); c.fill(); c.fillRect(-4, -4, 8, 14); c.fillRect(-14, 10, 28, 7);},
	sign: (c) => {c.strokeStyle = C.brass; c.lineWidth = 5; c.beginPath(); c.moveTo(0, 20); c.lineTo(0, -80); c.stroke(); rr(c, -50, -140, 100, 64, 4, C.pale, C.brass, 3);},
	map: (c) => {c.fillStyle = C.champ; c.beginPath(); c.moveTo(-36, -20); c.lineTo(-12, -26); c.lineTo(12, -20); c.lineTo(36, -26); c.lineTo(36, 20); c.lineTo(12, 26); c.lineTo(-12, 20); c.lineTo(-36, 26); c.closePath(); c.fill(); c.strokeStyle = C.ember; c.setLineDash([4, 4]); c.lineWidth = 2; c.beginPath(); c.moveTo(-26, 10); c.quadraticCurveTo(0, -20, 24, 4); c.stroke(); c.setLineDash([]);},
	tablet: (c) => {rr(c, -30, -22, 60, 44, 5, C.char0, C.steel2, 2); rr(c, -26, -18, 52, 36, 2, 'rgba(255,181,71,.7)');},
	laptop: (c) => {rr(c, -40, -40, 80, 50, 4, C.steel, C.steel2, 2); rr(c, -35, -35, 70, 40, 2, 'rgba(255,181,71,.7)'); c.fillStyle = C.silver; c.fillRect(-46, 10, 92, 7);},
};
export const ITEM_NAMES = Object.keys(ITEMS).filter((k) => !['thumb', 'rein', 'nail'].includes(k));
export function drawItem(c, name, x, y, ang, t, s = 1) {const f = ITEMS[name]; if (!f) return; c.save(); c.translate(x, y); c.rotate((ang || 0) * .35); c.scale(s, s); f(c, t); c.restore();}

/* ── headwear (head-local coords: head centre 0,0, radius ~35-43, face to +x) ── */
export const HATS = {
	helmet: (c) => {c.fillStyle = grad(c, -40, -40, 40, 0, C.olive, C.olive2); c.beginPath(); c.ellipse(0, -18, 46, 34, 0, PI, 0); c.fill(); c.fillStyle = C.olive; c.beginPath(); c.ellipse(0, -18, 52, 8, 0, 0, 7); c.fill(); c.strokeStyle = C.char0; c.lineWidth = 2; c.beginPath(); c.moveTo(30, -6); c.lineTo(36, 32); c.stroke();},
	helmetm: (c) => {c.fillStyle = grad(c, -40, -40, 40, 30, C.char1, C.steel); c.beginPath(); c.arc(0, -4, 48, 0, 7); c.fill(); c.fillStyle = 'rgba(255,181,71,.45)'; c.beginPath(); c.ellipse(26, -4, 22, 16, 0, -1.2, 1.2); c.fill();},
	hardhat: (c) => {c.fillStyle = grad(c, -40, -40, 40, 0, C.brass, C.gold); c.beginPath(); c.ellipse(0, -22, 42, 32, 0, PI, 0); c.fill(); c.beginPath(); c.ellipse(4, -22, 54, 7, 0, 0, 7); c.fill(); c.strokeStyle = C.bronze; c.lineWidth = 3; c.beginPath(); c.moveTo(0, -54); c.lineTo(0, -24); c.stroke();},
	cap: (c) => {c.fillStyle = C.char1; c.beginPath(); c.ellipse(0, -24, 40, 28, 0, PI, 0); c.fill(); c.beginPath(); c.ellipse(36, -24, 30, 6, .1, 0, 7); c.fill(); c.fillStyle = C.gold; c.beginPath(); c.arc(0, -50, 4, 0, 7); c.fill();},
	chef: (c) => {c.fillStyle = C.white; c.fillRect(-32, -60, 64, 30); [[-22, -72], [0, -82], [22, -72]].forEach(([x, y]) => {c.beginPath(); c.arc(x, y, 22, 0, 7); c.fill();});},
	police: (c) => {c.fillStyle = C.char1; c.beginPath(); c.moveTo(-44, -36); c.lineTo(44, -36); c.lineTo(36, -62); c.lineTo(-36, -62); c.closePath(); c.fill(); c.fillStyle = C.char0; c.beginPath(); c.ellipse(26, -32, 30, 6, .1, 0, 7); c.fill(); c.fillStyle = C.gold; c.beginPath(); c.arc(6, -50, 6, 0, 7); c.fill();},
	beanie: (c) => {c.fillStyle = C.bronze; c.beginPath(); c.ellipse(0, -18, 42, 36, 0, PI, 0); c.fill(); c.fillStyle = C.brass; c.fillRect(-42, -22, 84, 10); c.beginPath(); c.arc(0, -56, 8, 0, 7); c.fill();},
	tophat: (c) => {c.fillStyle = C.char0; c.fillRect(-28, -104, 56, 66); c.beginPath(); c.ellipse(0, -38, 50, 8, 0, 0, 7); c.fill(); c.fillStyle = C.gold; c.fillRect(-28, -52, 56, 8);},
	crown: (c) => {c.fillStyle = grad(c, -30, -70, 30, -30, C.gold, C.brass); c.beginPath(); c.moveTo(-32, -36); c.lineTo(-32, -66); c.lineTo(-16, -50); c.lineTo(0, -74); c.lineTo(16, -50); c.lineTo(32, -66); c.lineTo(32, -36); c.closePath(); c.fill(); c.fillStyle = C.ember; c.beginPath(); c.arc(0, -46, 4, 0, 7); c.fill();},
	cowboy: (c) => {c.fillStyle = C.bronze; c.beginPath(); c.ellipse(0, -36, 66, 12, 0, 0, 7); c.fill(); c.beginPath(); c.moveTo(-30, -38); c.quadraticCurveTo(-30, -84, 0, -72); c.quadraticCurveTo(30, -84, 30, -38); c.fill(); c.fillStyle = C.brass; c.fillRect(-30, -46, 60, 6);},
	grad: (c) => {c.fillStyle = C.char0; c.beginPath(); c.moveTo(-60, -50); c.lineTo(0, -66); c.lineTo(60, -50); c.lineTo(0, -34); c.closePath(); c.fill(); c.fillRect(-26, -46, 52, 14); c.strokeStyle = C.gold; c.lineWidth = 3; c.beginPath(); c.moveTo(0, -50); c.lineTo(40, -40); c.lineTo(42, -18); c.stroke();},
	bubble: (c) => {c.strokeStyle = 'rgba(216,220,226,.8)'; c.lineWidth = 4; c.fillStyle = 'rgba(120,140,160,.18)'; c.beginPath(); c.arc(2, -2, 60, 0, 7); c.fill(); c.stroke(); c.fillStyle = 'rgba(255,255,255,.25)'; c.beginPath(); c.ellipse(-22, -30, 12, 20, .6, 0, 7); c.fill();},
	gloves: () => {},
};
export const HAT_NAMES = Object.keys(HATS).filter((k) => k !== 'gloves');

/* ── vehicles / mounts in the rig frame. back = before the rider, front = after (covers the legs, wheels, glass).
   mv = 0..1 how much it is moving (wheels spin, speed lines) ── */
const wheel = (c, x, y, r, t, mv, spokes = 5) => {c.fillStyle = C.char0; c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); c.fillStyle = C.steel; c.beginPath(); c.arc(x, y, r * .55, 0, 7); c.fill();
	c.strokeStyle = C.silver; c.lineWidth = Math.max(2, r * .06); for (let i = 0; i < spokes; i++) {const a = i * 2 * PI / spokes + t * 9 * mv; c.beginPath(); c.moveTo(x, y); c.lineTo(x + Math.cos(a) * r * .55, y + Math.sin(a) * r * .55); c.stroke();}
	c.fillStyle = C.gold; c.beginPath(); c.arc(x, y, r * .12, 0, 7); c.fill();};
const spoked = (c, x, y, r, t, mv) => {c.strokeStyle = C.char0; c.lineWidth = 9; c.beginPath(); c.arc(x, y, r, 0, 7); c.stroke(); c.strokeStyle = 'rgba(216,220,226,.5)'; c.lineWidth = 1.5;
	for (let i = 0; i < 12; i++) {const a = i * PI / 6 + t * 8 * mv; c.beginPath(); c.moveTo(x, y); c.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); c.stroke();} c.fillStyle = C.gold; c.beginPath(); c.arc(x, y, 6, 0, 7); c.fill();};
const speedLines = (c, t, mv, y0, y1, x0) => {if (mv <= 0.05) return; c.strokeStyle = 'rgba(242,212,155,.5)'; c.lineWidth = 3; for (let i = 0; i < 7; i++) {const y = lerp(y0, y1, hash(i)), q = frac(t * 2.2 + hash(i + 3)); c.globalAlpha = mv * (1 - q);
	c.beginPath(); c.moveTo(x0 - q * 260, y); c.lineTo(x0 - q * 260 - 90 - hash(i + 9) * 80, y); c.stroke();} c.globalAlpha = 1;};
export const RIDES = {
	car: {back: (c, t, mv) => {c.fillStyle = C.char1; c.beginPath(); c.moveTo(-250, -250); c.quadraticCurveTo(-200, -440, -40, -450); c.lineTo(110, -450); c.quadraticCurveTo(230, -440, 300, -260); c.closePath(); c.fill();
			rr(c, -200, -330, 90, 120, 18, C.graph2);},
		front: (c, t, mv) => {const b = Math.sin(t * 22) * 2 * mv; c.save(); c.translate(0, b); speedLines(c, t, mv, -380, -80, -400);
			c.fillStyle = grad(c, -420, 0, 420, 0, C.graph, C.steel); c.beginPath(); c.moveTo(-420, -110); c.lineTo(-410, -250); c.lineTo(-250, -262); c.lineTo(300, -262); c.lineTo(420, -220); c.lineTo(430, -110); c.quadraticCurveTo(430, -70, 400, -70); c.lineTo(-400, -70); c.quadraticCurveTo(-420, -70, -420, -110); c.fill();
			c.strokeStyle = C.gold; c.lineWidth = 4; c.beginPath(); c.moveTo(-400, -200); c.lineTo(410, -200); c.stroke();
			c.strokeStyle = C.steel2; c.lineWidth = 12; c.beginPath(); c.moveTo(-250, -262); c.quadraticCurveTo(-200, -440, -40, -450); c.lineTo(110, -450); c.quadraticCurveTo(230, -440, 300, -262); c.stroke(); c.beginPath(); c.moveTo(40, -450); c.lineTo(40, -262); c.stroke();
			c.fillStyle = 'rgba(160,180,200,.12)'; c.beginPath(); c.moveTo(48, -440); c.lineTo(110, -440); c.quadraticCurveTo(220, -430, 288, -268); c.lineTo(48, -268); c.closePath(); c.fill();
			c.strokeStyle = C.char0; c.lineWidth = 9; c.beginPath(); c.ellipse(116, -300, 10, 40, -.3, 0, 7); c.stroke();
			const hl = c.createRadialGradient(424, -170, 2, 424, -170, 120); hl.addColorStop(0, 'rgba(255,243,220,.9)'); hl.addColorStop(1, 'rgba(255,181,71,0)'); c.fillStyle = hl; c.beginPath(); c.arc(424, -170, 120, 0, 7); c.fill(); rr(c, -424, -190, 12, 30, 3, C.ember);
			wheel(c, -250, -70, 72, t, mv, 6); wheel(c, 270, -70, 72, t, mv, 6); c.restore();}},
	bike: {back: () => {}, front: (c, t, mv) => {spoked(c, -180, -96, 96, t, mv); spoked(c, 200, -96, 96, t, mv); speedLines(c, t, mv, -420, -60, -300);
		c.strokeStyle = C.gold; c.lineWidth = 9; c.lineCap = 'round'; c.beginPath(); c.moveTo(-180, -96); c.lineTo(-30, -250); c.lineTo(150, -250); c.lineTo(200, -96); c.moveTo(-30, -250); c.lineTo(20, -96); c.lineTo(-180, -96); c.moveTo(20, -96); c.lineTo(150, -250); c.lineTo(160, -320); c.stroke();
		c.strokeStyle = C.char0; c.lineWidth = 10; c.beginPath(); c.moveTo(140, -322); c.lineTo(176, -318); c.stroke(); rr(c, -66, -268, 70, 16, 8, C.char0);
		c.strokeStyle = C.steel2; c.lineWidth = 6; const a = t * 7 * Math.max(mv, .6); c.beginPath(); c.moveTo(20 + Math.cos(a) * 40, -96 + Math.sin(a) * 40); c.lineTo(20 - Math.cos(a) * 40, -96 - Math.sin(a) * 40); c.stroke();}},
	moto: {back: () => {}, front: (c, t, mv) => {speedLines(c, t, mv, -420, -60, -320); wheel(c, -210, -86, 86, t, mv, 8); wheel(c, 230, -86, 86, t, mv, 8);
		c.fillStyle = grad(c, -200, 0, 200, 0, C.char1, C.steel); c.beginPath(); c.moveTo(-200, -150); c.lineTo(-80, -250); c.lineTo(120, -250); c.lineTo(210, -180); c.lineTo(150, -110); c.lineTo(-120, -110); c.closePath(); c.fill();
		c.fillStyle = C.gold; c.beginPath(); c.moveTo(-20, -250); c.quadraticCurveTo(40, -300, 110, -250); c.closePath(); c.fill(); c.strokeStyle = C.steel2; c.lineWidth = 10; c.beginPath(); c.moveTo(230, -86); c.lineTo(170, -300); c.lineTo(150, -310); c.stroke();
		rr(c, -150, -120, 200, 20, 8, C.silver);}},
	horse: {back: (c, t, mv, R) => {drawAnimal(c, t, {kind: 'horse', act: mv > .1 ? 'run' : 'idle', mv: R && R.walk ? 1 : 0, ph: 0, dir: 1, scale: 1.45}, -20, 0, true);}, front: () => {}},
	boat: {back: (c, t) => {c.fillStyle = C.char1; c.beginPath(); c.moveTo(-320, -160); c.lineTo(320, -160); c.lineTo(260, -230); c.lineTo(-300, -230); c.closePath(); c.fill();},
		front: (c, t, mv) => {const b = Math.sin(t * 2) * 6; c.save(); c.translate(0, b); c.fillStyle = grad(c, -330, 0, 330, 0, C.bronze, C.brass); c.beginPath(); c.moveTo(-340, -170); c.lineTo(360, -170); c.quadraticCurveTo(300, -20, 200, -10); c.lineTo(-240, -10); c.quadraticCurveTo(-320, -40, -340, -170); c.fill();
			c.strokeStyle = C.champ; c.lineWidth = 5; c.beginPath(); c.moveTo(-330, -150); c.lineTo(350, -150); c.stroke(); c.restore();
			c.strokeStyle = 'rgba(216,220,226,.5)'; c.lineWidth = 3; for (let i = 0; i < 6; i++) {const x = -400 + i * 160 + frac(t * .3) * 160; c.beginPath(); c.moveTo(x, 4); c.quadraticCurveTo(x + 40, -8, x + 80, 4); c.stroke();}}},
	skate: {back: () => {}, front: (c, t, mv) => {rr(c, -110, -26, 220, 14, 7, C.bronze); [-70, 70].forEach((x) => {c.fillStyle = C.silver; c.beginPath(); c.arc(x, -6, 10, 0, 7); c.fill();}); speedLines(c, t, Math.max(mv, .5), -300, -40, -120);}},
	scooter: {back: () => {}, front: (c, t, mv) => {rr(c, -100, -32, 200, 14, 6, C.steel2); c.strokeStyle = C.steel2; c.lineWidth = 9; c.beginPath(); c.moveTo(90, -26); c.lineTo(130, -340); c.moveTo(110, -340); c.lineTo(150, -340); c.stroke(); [-90, 110].forEach((x) => wheel(c, x, -14, 18, t, mv, 3));}},
	bus: {back: (c, t) => {rr(c, -260, -520, 520, 470, 20, C.graph); for (let k = 0; k < 2; k++) {rr(c, -230 + k * 250, -490, 210, 200, 12, '#0B0E13'); c.save(); c.beginPath(); c.rect(-230 + k * 250, -490, 210, 200); c.clip();
			for (let i = 0; i < 9; i++) {const x = -230 + k * 250 + frac(-t * .5 + hash(i)) * 300 - 40, h = 40 + hash(i + 2) * 120; c.fillStyle = 'rgba(30,32,38,.9)'; c.fillRect(x, -290 - h, 50, h); c.fillStyle = i % 2 ? C.gold : C.champ; c.fillRect(x + 10, -290 - h + 14, 8, 8);} c.restore();
			c.strokeStyle = C.brass; c.lineWidth = 5; c.strokeRect(-230 + k * 250, -490, 210, 200);} rr(c, -110, -300, 140, 230, 14, C.bronze);},
		front: () => {}},
	plane: {back: (c) => {c.fillStyle = C.char1; c.beginPath(); c.ellipse(60, -330, 230, 140, 0, 0, 7); c.fill();},
		front: (c, t) => {c.fillStyle = grad(c, -700, 0, 600, 0, C.steel, C.silver2); c.beginPath(); c.moveTo(-720, -250); c.quadraticCurveTo(-600, -330, -200, -320); c.lineTo(400, -310); c.quadraticCurveTo(620, -280, 640, -200); c.quadraticCurveTo(620, -120, 400, -110); c.lineTo(-640, -150); c.closePath(); c.fill();
			c.fillStyle = 'rgba(30,40,50,.0)'; c.save(); c.beginPath(); c.ellipse(60, -330, 230, 140, 0, PI, 0); c.lineTo(290, -310); c.lineTo(-170, -310); c.closePath(); c.restore();
			c.fillStyle = C.steel2; c.beginPath(); c.moveTo(-100, -200); c.lineTo(160, -200); c.lineTo(40, -40); c.lineTo(-60, -40); c.closePath(); c.fill(); c.fillStyle = C.gold; c.beginPath(); c.moveTo(-620, -250); c.lineTo(-700, -420); c.lineTo(-620, -420); c.lineTo(-540, -260); c.closePath(); c.fill();
			c.strokeStyle = C.gold; c.lineWidth = 6; c.beginPath(); c.moveTo(-600, -220); c.lineTo(560, -220); c.stroke(); for (let i = 0; i < 6; i++) {c.fillStyle = C.char0; c.beginPath(); c.arc(-500 + i * 80, -260, 14, 0, 7); c.fill();}
			c.strokeStyle = 'rgba(216,220,226,.6)'; c.lineWidth = 6; const a = t * 40; c.beginPath(); c.moveTo(646, -200 + Math.sin(a) * 90); c.lineTo(646, -200 - Math.sin(a) * 90); c.stroke(); speedLines(c, t, 1, -500, -60, -700);}},
	wheelchair: {back: (c, t) => {rr(c, -70, -330, 22, 160, 8, C.steel);}, front: (c, t, mv) => {spoked(c, -10, -110, 104, t, mv); c.fillStyle = C.char1; c.beginPath(); c.arc(110, -24, 20, 0, 7); c.fill(); c.strokeStyle = C.steel2; c.lineWidth = 8; c.beginPath(); c.moveTo(-60, -190); c.lineTo(90, -190); c.lineTo(110, -30); c.stroke();}},
};
export const RIDE_NAMES = Object.keys(RIDES);

/* ── set pieces beside the actor (rig frame; the actor faces +x). u = 0..1 progress for one-shot pieces ── */
const ballAt = (c, t, x, y, r = 16) => {c.save(); c.translate(x, y); c.scale(r / 15, r / 15); ITEMS.ball(c, t); c.restore();};
export const PIECES = {
	chair: {back: (c) => {rr(c, -96, -330, 20, 260, 6, C.graph2); rr(c, -100, -118, 170, 18, 6, C.steel); [-90, 54].forEach((x) => rr(c, x, -100, 12, 100, 4, C.graph2));}, front: () => {}},
	desk: {back: (c) => {rr(c, -96, -330, 20, 260, 6, C.graph2); rr(c, -100, -118, 170, 18, 6, C.steel);}, front: (c, t) => {rr(c, 40, -258, 260, 18, 4, C.silver); rr(c, 270, -240, 16, 240, 4, C.graph2); rr(c, 120, -400, 150, 104, 8, C.char1, C.steel2, 3); rr(c, 128, -392, 134, 88, 4, 'rgba(255,181,71,.55)'); rr(c, 180, -296, 30, 38, 2, C.steel2);}},
	stove: {back: () => {}, front: (c, t) => {rr(c, 120, -230, 240, 230, 8, C.steel, C.silver, 2); rr(c, 140, -200, 200, 120, 6, C.char1); for (let i = 0; i < 6; i++) {const q = frac(t * 2 + i / 6); c.fillStyle = `rgba(255,${120 + i * 15},60,${1 - q})`; c.beginPath(); c.ellipse(176 + i * 4, -236 - q * 20, 10, 6 + q * 10, 0, 0, 7); c.fill();}}},
	door: {back: () => {}, front: (c, t, S) => {const k = S.pieceU || 0; rr(c, 120, -470, 14, 470, 4, C.bronze); c.save(); c.translate(134, -470); c.scale(Math.cos(k * 1.2), 1); rr(c, 0, 0, 170, 470, 4, grad(c, 0, 0, 170, 0, C.bronze, C.brass)); c.fillStyle = C.gold; c.beginPath(); c.arc(20, 230, 9, 0, 7); c.fill(); c.restore();}},
	easel: {back: () => {}, front: (c, t) => {c.strokeStyle = C.bronze; c.lineWidth = 8; c.beginPath(); c.moveTo(180, 0); c.lineTo(230, -440); c.lineTo(280, 0); c.stroke(); rr(c, 160, -440, 160, 200, 4, C.pale, C.brass, 3);
		c.strokeStyle = C.gold; c.lineWidth = 8; c.beginPath(); c.moveTo(180, -280); c.quadraticCurveTo(230, -330 + Math.sin(t) * 6, 300, -300); c.stroke(); c.fillStyle = C.ember; c.beginPath(); c.arc(260, -390, 20, 0, 7); c.fill();}},
	ladder: {back: (c) => {c.strokeStyle = BRONZE; c.lineWidth = 12; c.beginPath(); c.moveTo(-70, 40); c.lineTo(-60, -720); c.moveTo(70, 40); c.lineTo(80, -720); c.stroke(); c.lineWidth = 8;
		for (let y = -20; y > -720; y -= 70) {c.beginPath(); c.moveTo(-68, y); c.lineTo(72, y); c.stroke();}}, front: () => {}},
	crate: {back: () => {}, front: (c) => {c.fillStyle = grad(c, 120, 0, 320, 0, C.bronze, C.brass); c.fillRect(120, -200, 200, 200); c.strokeStyle = C.bronze; c.lineWidth = 6; c.strokeRect(120, -200, 200, 200); c.beginPath(); c.moveTo(120, -200); c.lineTo(320, 0); c.moveTo(320, -200); c.lineTo(120, 0); c.stroke();}},
	fire: {back: () => {}, front: (c, t) => {c.fillStyle = C.bronze; [[-40, .3], [40, -.3]].forEach(([dx, a]) => {c.save(); c.translate(200 + dx * .5, -16); c.rotate(a); c.fillRect(-60, -8, 120, 16); c.restore();});
		for (let i = 0; i < 9; i++) {const q = frac(t * 1.8 + i / 9), x = 200 + Math.sin(i * 2.3 + t * 4) * 20 * (1 - q); c.fillStyle = `rgba(255,${180 - q * 110},${60},${(1 - q) * .9})`; c.beginPath(); c.ellipse(x, -30 - q * 120, 24 * (1 - q) + 6, 34 * (1 - q) + 8, 0, 0, 7); c.fill();}
		const g = c.createRadialGradient(200, -60, 10, 200, -60, 260); g.addColorStop(0, 'rgba(255,181,71,.35)'); g.addColorStop(1, 'rgba(255,181,71,0)'); c.fillStyle = g; c.beginPath(); c.arc(200, -60, 260, 0, 7); c.fill();}},
	water: {back: () => {}, front: (c, t) => {c.fillStyle = 'rgba(40,60,70,.6)'; c.beginPath(); c.ellipse(260, -4, 160, 20, 0, 0, 7); c.fill(); c.strokeStyle = 'rgba(216,220,226,.5)'; c.lineWidth = 2; for (let i = 0; i < 3; i++) {const q = frac(t * .5 + i / 3); c.globalAlpha = 1 - q; c.beginPath(); c.ellipse(320, -4, 20 + q * 60, 4 + q * 8, 0, 0, 7); c.stroke();} c.globalAlpha = 1;}},
	pool: {back: (c, t) => {c.fillStyle = 'rgba(40,70,90,.55)'; c.fillRect(-460, -150, 920, 170);}, front: (c, t) => {c.fillStyle = 'rgba(70,110,130,.45)'; c.fillRect(-460, -110, 920, 130); c.strokeStyle = 'rgba(216,220,226,.6)'; c.lineWidth = 3;
		for (let i = 0; i < 9; i++) {const x = -440 + i * 110 + Math.sin(t * 2 + i) * 10; c.beginPath(); c.moveTo(x, -112); c.quadraticCurveTo(x + 30, -124, x + 60, -112); c.stroke();}}},
	sandbags: {back: () => {}, front: (c) => {for (let r = 0; r < 3; r++) for (let i = 0; i < 4 - (r ? 1 : 0); i++) {const x = 60 + i * 86 + (r % 2) * 43, y = -40 - r * 46; c.fillStyle = grad(c, x - 40, y, x + 40, y, C.bronze, '#8E7A55'); c.beginPath(); c.ellipse(x, y, 44, 24, 0, 0, 7); c.fill(); c.strokeStyle = 'rgba(11,11,13,.4)'; c.lineWidth = 2; c.stroke();}}},
	goal: {back: (c, t, S) => {const x0 = 560; c.strokeStyle = 'rgba(216,220,226,.25)'; c.lineWidth = 1.5; for (let i = 0; i <= 10; i++) {c.beginPath(); c.moveTo(x0 + i * 36, -330); c.lineTo(x0 + i * 36 + 40, -10); c.stroke(); c.beginPath(); c.moveTo(x0, -330 + i * 32); c.lineTo(x0 + 400, -330 + i * 32); c.stroke();}},
		front: (c, t, S) => {const x0 = 560; c.strokeStyle = C.white; c.lineWidth = 12; c.beginPath(); c.moveTo(x0, 0); c.lineTo(x0, -336); c.lineTo(x0 + 400, -336); c.lineTo(x0 + 400, 0); c.stroke();
			const q = S.ballShot ?? -1; if (q < 0) return; let bx, by; if (q < .3) {bx = 96; by = -16;} else {const k = clamp((q - .3) / .3); bx = lerp(96, 820, k); by = -16 - Math.sin(k * PI) * 160 - k * 120;}
			if (q > .6) {bx = 820 + Math.sin((q - .6) * 20) * 6; by = lerp(-136, -16, ss((q - .6) / .4));} ballAt(c, t, bx, by, 18);
			if (q > .58 && q < .9) {c.save(); c.globalAlpha = 1 - (q - .58) / .32; c.fillStyle = C.gold; c.font = '900 72px "MG Outfit", sans-serif'; c.textAlign = 'center'; c.fillText('GOAL!', 760, -400 - (q - .58) * 100); c.restore();}}},
	goalback: {back: (c) => {c.strokeStyle = C.white; c.lineWidth = 12; c.beginPath(); c.moveTo(-200, 0); c.lineTo(-200, -336); c.lineTo(200, -336); c.lineTo(200, 0); c.stroke(); c.strokeStyle = 'rgba(216,220,226,.25)'; c.lineWidth = 1.5; for (let i = 0; i <= 10; i++) {c.beginPath(); c.moveTo(-200 + i * 40, -336); c.lineTo(-200 + i * 40, 0); c.stroke();}}, front: () => {}},
	hoop: {back: (c, t, S) => {rr(c, 560, -760, 16, 760, 4, C.steel2); rr(c, 470, -800, 110, 90, 4, C.pale, C.steel2, 3);},
		front: (c, t, S) => {c.strokeStyle = C.ember; c.lineWidth = 6; c.beginPath(); c.ellipse(440, -700, 44, 9, 0, 0, 7); c.stroke(); c.strokeStyle = 'rgba(242,246,250,.7)'; c.lineWidth = 2; for (let i = 0; i < 6; i++) {c.beginPath(); c.moveTo(400 + i * 16, -700); c.lineTo(416 + i * 9, -640); c.stroke();}
			const q = S.hoopShot ?? -1; if (q < 0) return; const k = clamp(q / .55), bx = lerp(40, 440, k), by = lerp(-470, -710, k) - Math.sin(k * PI) * 220 + (q > .55 ? ss((q - .55) / .45) * 680 : 0);
			c.save(); c.translate(bx, by); ITEMS.bball(c, t); c.restore(); if (q > .55 && q < .85) {c.save(); c.globalAlpha = 1 - (q - .55) / .3; c.fillStyle = C.gold; c.font = '900 60px "MG Outfit", sans-serif'; c.textAlign = 'center'; c.fillText('SWISH!', 440, -840); c.restore();}}},
};
export const PIECE_NAMES = Object.keys(PIECES);

/* ── screen ambience (drawn over the whole frame, under captions) ── */
export function ambient(c, kind, t, VW, VH, a) {if (!kind || a <= 0) return; c.save(); c.globalAlpha = a;
	if (kind === 'rain') {c.strokeStyle = 'rgba(216,220,226,.35)'; c.lineWidth = 2; for (let i = 0; i < 140; i++) {const x = hash(i) * (VW + 300) - 150, y = frac(hash(i + 7) + t * (1.2 + hash(i + 3))) * (VH + 100) - 50; c.beginPath(); c.moveTo(x, y); c.lineTo(x - 10, y + 34); c.stroke();}}
	if (kind === 'snow') {c.fillStyle = 'rgba(242,246,250,.8)'; for (let i = 0; i < 120; i++) {const x = hash(i) * VW + Math.sin(t + i) * 24, y = frac(hash(i + 7) + t * (.06 + hash(i + 3) * .08)) * VH; c.beginPath(); c.arc(x, y, 1.5 + hash(i + 1) * 3, 0, 7); c.fill();}}
	if (kind === 'confetti') for (let i = 0; i < 90; i++) {const x = hash(i) * VW + Math.sin(t * 2 + i) * 30, y = frac(hash(i + 7) + t * (.15 + hash(i + 3) * .2)) * VH; c.fillStyle = [LC.gold, LC.champ, LC.ember, LC.silver2][i % 4]; c.save(); c.translate(x, y); c.rotate(t * 4 + i); c.fillRect(-5, -2, 10, 4); c.restore();}
	if (kind === 'war') {for (let i = 0; i < 4; i++) {const q = frac(t * .23 + hash(i * 3)), x = hash(i + 11 + Math.floor(t * .23 + hash(i * 3))) * VW, y = VH * (.25 + hash(i + 5) * .25);    // distant flashes
			if (q < .12) {const g = c.createRadialGradient(x, y, 2, x, y, 260 * (1 - q * 4)); g.addColorStop(0, `rgba(255,220,160,${.6 * (1 - q / .12)})`); g.addColorStop(1, 'rgba(255,140,60,0)'); c.fillStyle = g; c.fillRect(x - 300, y - 300, 600, 600);}}
		for (let i = 0; i < 14; i++) {const q = frac(t * .05 + hash(i)), x = hash(i + 2) * VW + q * 160, y = VH * (.7 - q * .5) + hash(i + 4) * 120; c.fillStyle = `rgba(110,112,118,${.22 * Math.sin(q * PI)})`; c.beginPath(); c.arc(x, y, 80 + q * 160, 0, 7); c.fill();}
		c.fillStyle = 'rgba(255,181,71,.85)'; for (let i = 0; i < 40; i++) {const x = hash(i + 30) * VW + Math.sin(t + i) * 20, y = VH - frac(hash(i + 50) + t * (.08 + hash(i) * .08)) * VH; c.fillRect(x, y, 3, 3);}}
	if (kind === 'fireflies') for (let i = 0; i < 46; i++) {const x = hash(i) * VW + Math.sin(t * .4 + i) * 60, y = VH * (.3 + hash(i + 7) * .6) + Math.cos(t * .5 + i * 2) * 40, b = Math.max(0, Math.sin(t * 2 + i * 1.7)); const g = c.createRadialGradient(x, y, 0, x, y, 14); g.addColorStop(0, `rgba(255,236,150,${b})`); g.addColorStop(1, 'rgba(255,200,80,0)'); c.fillStyle = g; c.fillRect(x - 14, y - 14, 28, 28);}
	if (kind === 'speed') {c.strokeStyle = 'rgba(242,212,155,.35)'; c.lineWidth = 3; for (let i = 0; i < 30; i++) {const y = hash(i) * VH, q = frac(t * 1.5 + hash(i + 3)); c.beginPath(); c.moveTo(VW - q * VW * 1.4, y); c.lineTo(VW - q * VW * 1.4 - 200, y); c.stroke();}}
	c.restore();}
export const AMBIENTS = ['rain', 'snow', 'confetti', 'war', 'speed', 'fireflies'];

/* ── ANIMALS. One quadruped rig + bird + fish + critters, many species, all in the Diorama palette.
   Rig frame like people (feet at 0, up = -y, 400 units = an adult person). A = {kind, act, ph, dir, scale} ── */
const Q = (o) => ({type: 'quad', ...o});
export const SPECIES = {
	dog: Q({name: 'Dog', len: 120, h: 62, leg: 58, head: 32, neck: 22, snout: 24, ear: 'flop', tail: 'wag', c0: '#7A5226', c1: '#B8862E', belly: '#F2D49B', tags: 'pet puppy dog hound'}),
	puppy: Q({name: 'Puppy', len: 78, h: 44, leg: 34, head: 28, neck: 12, snout: 14, ear: 'flop', tail: 'wag', c0: '#B8862E', c1: '#F2D49B', belly: '#FFF3DC', tags: 'puppy pet small dog'}),
	cat: Q({name: 'Cat', len: 92, h: 44, leg: 40, head: 26, neck: 12, snout: 8, ear: 'point', tail: 'curl', c0: '#2A2D34', c1: '#4A4F58', belly: '#6B717C', tags: 'cat kitten pet'}),
	horse: Q({name: 'Horse', len: 230, h: 110, leg: 150, head: 34, neck: 92, snout: 50, ear: 'point', tail: 'long', mane: true, c0: '#4A2E16', c1: '#7A5226', belly: '#9C6B37', tags: 'horse pony ride farm'}),
	cow: Q({name: 'Cow', len: 230, h: 120, leg: 96, head: 40, neck: 30, snout: 34, ear: 'side', horns: true, tail: 'tuft', spots: '#16171B', c0: '#A7ADB6', c1: '#D8DCE2', belly: '#F2F6FA', tags: 'cow cattle farm milk'}),
	sheep: Q({name: 'Sheep', len: 130, h: 82, leg: 50, head: 26, neck: 16, snout: 18, ear: 'side', tail: 'short', wool: true, c0: '#D8DCE2', c1: '#FFF3DC', face: '#2A2D34', tags: 'sheep lamb wool farm'}),
	pig: Q({name: 'Pig', len: 130, h: 72, leg: 36, head: 34, neck: 6, snout: 18, nose: 'pig', ear: 'point', tail: 'curl', c0: '#C98F78', c1: '#E8B8A0', belly: '#F2D0BE', tags: 'pig piglet farm'}),
	goat: Q({name: 'Goat', len: 120, h: 66, leg: 70, head: 26, neck: 30, snout: 22, ear: 'side', horns: true, tail: 'short', beard: true, c0: '#A7ADB6', c1: '#D8DCE2', tags: 'goat farm'}),
	fox: Q({name: 'Fox', len: 104, h: 46, leg: 44, head: 26, neck: 16, snout: 28, ear: 'point', tail: 'bushy', c0: '#A4522A', c1: '#E0703A', belly: '#FFF3DC', tags: 'fox wild forest'}),
	wolf: Q({name: 'Wolf', len: 140, h: 66, leg: 70, head: 32, neck: 22, snout: 30, ear: 'point', tail: 'bushy', c0: '#4A4F58', c1: '#A7ADB6', belly: '#D8DCE2', tags: 'wolf wild forest howl'}),
	deer: Q({name: 'Deer', len: 150, h: 68, leg: 112, head: 26, neck: 64, snout: 26, ear: 'side', antlers: true, tail: 'short', c0: '#7A5226', c1: '#B8862E', belly: '#F2D49B', tags: 'deer forest wild'}),
	rabbit: Q({name: 'Rabbit', len: 64, h: 44, leg: 16, head: 22, neck: 4, snout: 8, ear: 'long', tail: 'puff', hop: true, c0: '#A7ADB6', c1: '#D8DCE2', belly: '#F2F6FA', tags: 'rabbit bunny pet'}),
	mouse: Q({name: 'Mouse', len: 40, h: 22, leg: 8, head: 13, neck: 2, snout: 10, ear: 'round', tail: 'thin', c0: '#6B717C', c1: '#A7ADB6', tags: 'mouse rat small'}),
	bear: Q({name: 'Bear', len: 200, h: 120, leg: 64, head: 42, neck: 16, snout: 22, ear: 'round', tail: 'short', c0: '#16171B', c1: '#3A2A1E', belly: '#4A2E16', tags: 'bear wild forest'}),
	lion: Q({name: 'Lion', len: 190, h: 96, leg: 80, head: 38, neck: 20, snout: 24, ear: 'round', tail: 'tuft', lionmane: true, c0: '#B8862E', c1: '#F2D49B', belly: '#FFF3DC', tags: 'lion king wild safari'}),
	tiger: Q({name: 'Tiger', len: 200, h: 92, leg: 76, head: 36, neck: 18, snout: 22, ear: 'round', tail: 'long', stripes: '#16171B', c0: '#C46A2A', c1: '#E0903A', belly: '#FFF3DC', tags: 'tiger wild jungle'}),
	elephant: Q({name: 'Elephant', len: 260, h: 170, leg: 120, head: 70, neck: 0, snout: 0, ear: 'big', trunk: true, tusks: true, tail: 'thin', c0: '#4A4F58', c1: '#6B717C', tags: 'elephant safari zoo'}),
	giraffe: Q({name: 'Giraffe', len: 170, h: 90, leg: 190, head: 26, neck: 230, snout: 30, ear: 'side', ossicones: true, tail: 'tuft', patches: '#7A5226', c0: '#F2D49B', c1: '#FFF3DC', tags: 'giraffe safari zoo'}),
	zebra: Q({name: 'Zebra', len: 200, h: 100, leg: 130, head: 32, neck: 80, snout: 46, ear: 'point', tail: 'tuft', mane: true, stripes: '#16171B', c0: '#D8DCE2', c1: '#F2F6FA', tags: 'zebra safari'}),
	monkey: Q({name: 'Monkey', len: 70, h: 60, leg: 46, head: 28, neck: 10, snout: 10, ear: 'round', tail: 'curl', c0: '#5A4024', c1: '#7A5226', belly: '#F2D49B', tags: 'monkey jungle zoo ape'}),
	camel: Q({name: 'Camel', len: 220, h: 100, leg: 160, head: 28, neck: 110, snout: 40, ear: 'side', tail: 'tuft', hump: true, c0: '#B89A6A', c1: '#F2D49B', tags: 'camel desert'}),
	turtle: {type: 'turtle', name: 'Turtle', c0: '#4B5340', c1: '#6A7458', tags: 'turtle tortoise slow'},
	frog: {type: 'frog', name: 'Frog', c0: '#4B5340', c1: '#8C9A5A', tags: 'frog pond'},
	snake: {type: 'snake', name: 'Snake', c0: '#7A5226', c1: '#B8862E', tags: 'snake reptile'},
	bird: {type: 'bird', name: 'Songbird', size: 26, c0: '#B8862E', c1: '#FFB547', beak: '#E0703A', tags: 'bird sparrow songbird'},
	pigeon: {type: 'bird', name: 'Pigeon', size: 32, c0: '#4A4F58', c1: '#A7ADB6', beak: '#2A2D34', tags: 'pigeon city bird'},
	chicken: {type: 'bird', name: 'Chicken', size: 44, c0: '#D8DCE2', c1: '#FFF3DC', beak: '#FFB547', comb: true, ground: true, tags: 'chicken hen rooster farm'},
	duck: {type: 'bird', name: 'Duck', size: 40, c0: '#F2D49B', c1: '#FFF3DC', beak: '#FFB547', flat: true, ground: true, tags: 'duck pond'},
	owl: {type: 'bird', name: 'Owl', size: 44, c0: '#5A4024', c1: '#9C6B37', beak: '#FFB547', owl: true, tags: 'owl night wise'},
	eagle: {type: 'bird', name: 'Eagle', size: 60, c0: '#4A2E16', c1: '#7A5226', beak: '#FFB547', white: true, tags: 'eagle hawk bird of prey'},
	parrot: {type: 'bird', name: 'Parrot', size: 40, c0: '#E0703A', c1: '#FFB547', beak: '#2A2D34', tags: 'parrot jungle'},
	penguin: {type: 'bird', name: 'Penguin', size: 56, c0: '#16171B', c1: '#2A2D34', beak: '#FFB547', penguin: true, ground: true, tags: 'penguin ice cold'},
	fish: {type: 'fish', name: 'Fish', size: 40, c0: '#B8862E', c1: '#FFB547', tags: 'fish aquarium sea'},
	shark: {type: 'fish', name: 'Shark', size: 140, c0: '#4A4F58', c1: '#A7ADB6', fin: true, tags: 'shark ocean'},
	whale: {type: 'fish', name: 'Whale', size: 260, c0: '#2A2D34', c1: '#4A4F58', whale: true, tags: 'whale ocean'},
	butterfly: {type: 'fly', name: 'Butterfly', size: 22, c0: '#FFB547', c1: '#E0703A', tags: 'butterfly garden'},
	bee: {type: 'fly', name: 'Bee', size: 12, c0: '#FFB547', c1: '#16171B', bee: true, tags: 'bee insect garden'},
	dragon: Q({name: 'Dragon', len: 240, h: 100, leg: 80, head: 40, neck: 70, snout: 44, ear: 'horn', tail: 'long', wings: true, c0: '#7A5226', c1: '#B8862E', belly: '#FFB547', tags: 'dragon fantasy myth'}),
	dinosaur: Q({name: 'Dinosaur', len: 260, h: 110, leg: 110, head: 52, neck: 50, snout: 50, ear: 'none', tail: 'long', biped: true, c0: '#4B5340', c1: '#6A7458', belly: '#B89A6A', tags: 'dinosaur t-rex prehistoric'}),
	unicorn: Q({name: 'Unicorn', len: 220, h: 104, leg: 146, head: 34, neck: 88, snout: 48, ear: 'point', tail: 'long', mane: true, horn: true, c0: '#D8DCE2', c1: '#FFF3DC', tags: 'unicorn fantasy magic'}),
};
export const SPECIES_NAMES = Object.keys(SPECIES);
export const ANIMAL_ACTS = ['idle', 'walk', 'run', 'sit', 'sleep', 'eat', 'speak', 'wag', 'jump', 'fly', 'swim', 'follow', 'beg'];

function quad(c, t, S, a, ph, mv, rideMode) {const L = S.len, H = S.h, G = S.leg, hr = S.head, run = a === 'run', sit = a === 'sit' || a === 'beg', lie = a === 'sleep', eat = a === 'eat';
	const gait = run ? 14 : 7, sw = mv > .05 ? (run ? .7 : .42) * mv : 0, p = t * gait + ph, bob = mv > .05 ? Math.abs(Math.sin(p)) * (run ? 10 : 4) : Math.sin(t * 2 + ph) * 1.5;
	const hop = S.hop && mv > .05 ? Math.abs(Math.sin(p * .5)) * 30 : 0, jmp = a === 'jump' ? Math.abs(Math.sin(t * 4 + ph)) * 50 : 0;
	const bodyY = -(lie ? H * .55 : G + H * .5) - bob - hop - jmp, tilt = sit ? -.42 : 0;
	const grd = (x0, x1) => {const g = c.createLinearGradient(0, bodyY - H / 2, 0, bodyY + H / 2); g.addColorStop(0, S.c1); g.addColorStop(1, S.c0); return g;};
	c.save(); c.translate(0, 0);
	if (!lie && !rideMode) {c.fillStyle = 'rgba(0,0,0,.32)'; c.beginPath(); c.ellipse(0, 4, L * .55, 10 + L * .04, 0, 0, 7); c.fill();}
	c.translate(0, bodyY); c.rotate(tilt); if (sit) c.translate(-L * .05, H * .2);
	// legs (far pair first, darker)
	const legs = (far) => {const k = far ? 1 : 0, col = far ? S.c0 : (S.belly && !S.stripes ? S.c0 : S.c0); c.strokeStyle = far ? shadeC(col) : col; c.lineCap = 'round'; c.lineWidth = Math.max(6, L * .085);
		[[L * .32, 0], [-L * .32, PI]].forEach(([x, o], j) => {if (S.biped && j === 0) return; if (lie) return; const ang = Math.sin(p + o + k * PI) * sw, back = j === 1;
			if (sit && back) {c.beginPath(); c.moveTo(x, H * .2); c.lineTo(x + L * .18, H * .4 + G * .2); c.lineTo(x + L * .1, H * .25 + G * .55); c.stroke(); return;}
			const len = G + H * .3 + (sit && !back ? H * .15 : 0), kx = x + Math.sin(ang) * len * .5 + (back ? -6 : 6), ky = H * .2 + len * .5, fx = x + Math.sin(ang) * len * .9, fy = H * .2 + len - (Math.max(0, Math.sin(p + o + k * PI)) * sw * 18);
			c.beginPath(); c.moveTo(x, H * .1); c.quadraticCurveTo(kx, ky, fx, fy); c.stroke(); c.fillStyle = far ? shadeC(S.c0) : S.c0; c.beginPath(); c.ellipse(fx + 3, fy, c.lineWidth * .7, c.lineWidth * .4, 0, 0, 7); c.fill();});};
	legs(true);
	// tail
	const tw = (a === 'wag' || a === 'beg' || a === 'follow' || (S.tail === 'wag' && mv < .05)) ? Math.sin(t * (a === 'wag' ? 18 : 8) + ph) * .5 : Math.sin(t * 2 + ph) * .15;
	c.save(); c.translate(-L * .48, -H * .12); c.rotate(tw);
	c.strokeStyle = S.c1; c.fillStyle = S.c1; c.lineCap = 'round';
	if (S.tail === 'bushy') {c.beginPath(); c.ellipse(-30, -16, 34, 16, -.6, 0, 7); c.fill(); c.fillStyle = S.belly || C.pale; c.beginPath(); c.ellipse(-52, -30, 10, 8, -.6, 0, 7); c.fill();}
	else if (S.tail === 'curl') {c.lineWidth = Math.max(5, L * .06); c.beginPath(); c.moveTo(0, 0); c.quadraticCurveTo(-30, -10, -26, -40); c.quadraticCurveTo(-22, -56, -8, -50); c.stroke();}
	else if (S.tail === 'long') {c.lineWidth = Math.max(8, L * .07); c.strokeStyle = S.mane ? C.char1 : S.c0; c.beginPath(); c.moveTo(0, 0); c.quadraticCurveTo(-40, 20, -50, H * .9); c.stroke();}
	else if (S.tail === 'tuft' || S.tail === 'thin') {c.lineWidth = S.tail === 'thin' ? 3 : 5; c.strokeStyle = S.c0; c.beginPath(); c.moveTo(0, 0); c.quadraticCurveTo(-26, 20, -30, H * .7); c.stroke(); if (S.tail === 'tuft') {c.fillStyle = C.char1; c.beginPath(); c.ellipse(-30, H * .74, 6, 12, 0, 0, 7); c.fill();}}
	else if (S.tail === 'puff') {c.fillStyle = C.white; c.beginPath(); c.arc(-4, -4, 12, 0, 7); c.fill();}
	else if (S.tail === 'wag') {c.lineWidth = Math.max(6, L * .07); c.beginPath(); c.moveTo(0, 0); c.quadraticCurveTo(-24, -24, -34, -46); c.stroke();}
	else {c.lineWidth = 8; c.beginPath(); c.moveTo(0, 0); c.lineTo(-12, -8); c.stroke();}
	c.restore();
	// body
	if (S.wings) {const f = Math.sin(t * 3 + ph) * .3; c.fillStyle = shadeC(S.c0); c.save(); c.translate(-L * .05, -H * .4); c.rotate(-.5 + f); c.beginPath(); c.moveTo(0, 0); c.lineTo(-L * .5, -H * 1.3); c.lineTo(-L * .2, -H * .9); c.lineTo(-L * .05, -H * 1.1); c.lineTo(L * .1, -H * .2); c.closePath(); c.fill(); c.restore();}
	c.fillStyle = grd(); c.beginPath(); c.ellipse(0, 0, L * .5, H * .5, 0, 0, 7); c.fill();
	if (S.hump) {c.beginPath(); c.ellipse(-L * .05, -H * .5, L * .2, H * .4, 0, PI, 0); c.fill();}
	if (S.belly) {c.fillStyle = S.belly; c.globalAlpha = .55; c.beginPath(); c.ellipse(L * .04, H * .22, L * .36, H * .2, 0, 0, 7); c.fill(); c.globalAlpha = 1;}
	if (S.wool) {c.fillStyle = S.c1; for (let i = 0; i < 12; i++) {const a = i / 12 * 2 * PI; c.beginPath(); c.arc(Math.cos(a) * L * .44, Math.sin(a) * H * .44, H * .22, 0, 7); c.fill();}}
	if (S.spots) {c.fillStyle = S.spots; [[-.2, -.1, .16], [.15, .05, .12], [-.05, .25, .09], [.3, -.2, .08]].forEach(([x, y, r]) => {c.beginPath(); c.ellipse(x * L, y * H, r * L, r * H * 1.2, .3, 0, 7); c.fill();});}
	if (S.patches) {c.fillStyle = S.patches; for (let i = 0; i < 10; i++) {c.beginPath(); c.arc((hash(i) - .5) * L * .8, (hash(i + 4) - .5) * H * .7, 9 + hash(i + 2) * 8, 0, 7); c.fill();}}
	if (S.stripes) {c.strokeStyle = S.stripes; c.lineWidth = Math.max(4, L * .025); for (let i = 0; i < 7; i++) {const x = -L * .38 + i * L * .12; c.beginPath(); c.moveTo(x, -H * .48); c.quadraticCurveTo(x + 8, -H * .1, x - 4, H * .15); c.stroke();}}
	c.strokeStyle = 'rgba(255,181,71,.5)'; c.lineWidth = 2.5; c.beginPath(); c.ellipse(0, 0, L * .5, H * .5, 0, PI * 1.12, PI * 1.88); c.stroke();     // gold rim light on the back
	legs(false);
	if (S.saddle) {rr(c, -L * .2, -H * .6, L * .36, H * .3, 8, C.bronze); c.fillStyle = C.gold; c.fillRect(-L * .02, -H * .3, 6, H * .6);}
	// neck + head
	const nk = S.neck, hx = L * .44 + nk * .35, hy = -H * .2 - nk * .9 - (S.biped ? H * .3 : 0), HY = eat ? (lie ? H * .3 : G + H * .5) - hr * 1.05 + Math.sin(t * 5 + ph) * 3 : hy;   // grazing: the mouth reaches the ground
	if (nk > 4) {c.strokeStyle = S.c1; c.lineWidth = Math.max(hr * 1.1, 12); c.lineCap = 'round'; c.beginPath(); c.moveTo(L * .34, -H * .1); c.lineTo(hx, HY); c.stroke();
		if (S.mane) {c.strokeStyle = C.char1; c.lineWidth = 9; c.beginPath(); c.moveTo(L * .3, -H * .4); c.lineTo(hx - 8, hy - hr * .6); c.stroke();}
		if (S.patches) {c.fillStyle = S.patches; for (let i = 0; i < 6; i++) {const u = i / 6; c.beginPath(); c.arc(lerp(L * .34, hx, u), lerp(-H * .1, hy, u), 7, 0, 7); c.fill();}}}
	const nod = a === 'speak' ? Math.sin(t * 12) * .08 : Math.sin(t * 1.3 + ph) * .04;
	c.save(); c.translate(hx, HY); c.rotate(nod + (lie ? .3 : 0));
	if (S.lionmane) {c.fillStyle = C.bronze; for (let i = 0; i < 14; i++) {const a2 = i / 14 * 2 * PI; c.beginPath(); c.arc(Math.cos(a2) * hr * .95, Math.sin(a2) * hr * .95, hr * .45, 0, 7); c.fill();}}
	if (S.ear === 'big') {c.fillStyle = S.c0; c.beginPath(); c.ellipse(-hr * .5, hr * .1, hr * .7, hr * .9, -.2, 0, 7); c.fill();}
	c.fillStyle = S.face || S.c1; c.beginPath(); c.ellipse(0, 0, hr, hr * .9, 0, 0, 7); c.fill();
	if (S.snout) {c.fillStyle = S.face || S.c1; c.beginPath(); c.ellipse(hr * .7 + S.snout * .3, hr * .25, S.snout * .75 + 4, hr * .5, .15, 0, 7); c.fill();
		c.fillStyle = S.nose === 'pig' ? '#B8786A' : C.char0; c.beginPath(); c.ellipse(hr * .7 + S.snout * .95, hr * .12, S.nose === 'pig' ? 8 : 5, S.nose === 'pig' ? 10 : 4, 0, 0, 7); c.fill();
		if (a === 'speak') {c.strokeStyle = C.char0; c.lineWidth = 3; c.beginPath(); c.moveTo(hr * .5, hr * .5); c.lineTo(hr * .7 + S.snout, hr * .5 + Math.abs(Math.sin(t * 12)) * 8); c.stroke();}}
	if (S.trunk) {c.strokeStyle = S.c1; c.lineWidth = hr * .32; c.lineCap = 'round'; c.beginPath(); c.moveTo(hr * .7, hr * .1); c.quadraticCurveTo(hr * 1.2, hr * 1.2 + Math.sin(t * 2) * 8, hr * .9 + Math.sin(t * 1.7) * 10, hr * 1.9); c.stroke();}
	if (S.tusks) {c.strokeStyle = C.pale; c.lineWidth = 6; c.beginPath(); c.moveTo(hr * .5, hr * .5); c.quadraticCurveTo(hr * 1.1, hr * .9, hr * 1.3, hr * .6); c.stroke();}
	if (S.beard) {c.fillStyle = S.c0; c.beginPath(); c.moveTo(hr * .8, hr * .6); c.lineTo(hr * 1.0, hr * 1.3); c.lineTo(hr * 1.2, hr * .6); c.fill();}
	// eye
	const closed = lie || frac(t / 3.1 + ph * .1) > .96; c.fillStyle = C.char0; if (closed) {c.strokeStyle = C.char0; c.lineWidth = 2.5; c.beginPath(); c.arc(hr * .35, -hr * .15, hr * .14, .2, PI - .2); c.stroke();}
	else {c.beginPath(); c.arc(hr * .35, -hr * .15, Math.max(3, hr * .14), 0, 7); c.fill(); c.fillStyle = C.white; c.beginPath(); c.arc(hr * .39, -hr * .2, Math.max(1.2, hr * .05), 0, 7); c.fill();}
	// ears / horns / antlers
	c.fillStyle = S.c0;
	if (S.ear === 'flop') {c.beginPath(); c.ellipse(-hr * .35, hr * .1, hr * .3, hr * .65, .25 + Math.sin(t * 6 + ph) * .1 * mv, 0, 7); c.fill();}
	else if (S.ear === 'point') {c.beginPath(); c.moveTo(-hr * .5, -hr * .5); c.lineTo(-hr * .25, -hr * 1.35); c.lineTo(hr * .05, -hr * .7); c.fill();}
	else if (S.ear === 'round') {c.beginPath(); c.arc(-hr * .45, -hr * .7, hr * .3, 0, 7); c.fill();}
	else if (S.ear === 'long') {c.fillStyle = S.c1; c.beginPath(); c.ellipse(-hr * .3, -hr * 1.4, hr * .25, hr * .85, -.2 + Math.sin(t * 1.5) * .08, 0, 7); c.fill(); c.fillStyle = '#E8B8A0'; c.beginPath(); c.ellipse(-hr * .3, -hr * 1.4, hr * .12, hr * .6, -.2, 0, 7); c.fill();}
	else if (S.ear === 'side') {c.beginPath(); c.ellipse(-hr * .6, -hr * .3, hr * .45, hr * .18, -.4, 0, 7); c.fill();}
	else if (S.ear === 'horn') {c.fillStyle = C.pale; c.beginPath(); c.moveTo(-hr * .4, -hr * .6); c.lineTo(-hr * 1.0, -hr * 1.4); c.lineTo(-hr * .1, -hr * .8); c.fill();}
	if (S.horns) {c.strokeStyle = C.pale; c.lineWidth = 6; c.lineCap = 'round'; c.beginPath(); c.moveTo(-hr * .1, -hr * .8); c.quadraticCurveTo(-hr * .2, -hr * 1.5, -hr * .8, -hr * 1.4); c.stroke();}
	if (S.horn) {c.fillStyle = C.gold; c.beginPath(); c.moveTo(hr * .2, -hr * .7); c.lineTo(hr * .9, -hr * 2); c.lineTo(hr * .55, -hr * .6); c.fill();}
	if (S.ossicones) {c.strokeStyle = S.patches || C.bronze; c.lineWidth = 5; [-.2, .1].forEach((x) => {c.beginPath(); c.moveTo(hr * x, -hr * .7); c.lineTo(hr * x, -hr * 1.3); c.stroke();});}
	if (S.antlers) {c.strokeStyle = C.champ; c.lineWidth = 4; c.lineCap = 'round'; c.beginPath(); c.moveTo(0, -hr * .8); c.lineTo(-hr * .4, -hr * 2.2); c.moveTo(-hr * .2, -hr * 1.5); c.lineTo(hr * .4, -hr * 1.9); c.moveTo(-hr * .32, -hr * 1.9); c.lineTo(-hr * 1, -hr * 2.3); c.stroke();}
	c.restore(); c.restore();
	if (a === 'sleep') zzz(c, t, hx, HY + bodyY - 30); if (a === 'speak') rings(c, t, hx + hr * 2, HY + bodyY);}
const shadeC = (hex) => {if (!hex || hex[0] !== '#') return hex; const n = parseInt(hex.slice(1), 16); return '#' + [16, 8, 0].map((s) => Math.round(((n >> s) & 255) * .72).toString(16).padStart(2, '0')).join('');};
const zzz = (c, t, x, y) => {c.fillStyle = C.silver2; c.font = '800 26px "MG Outfit", sans-serif'; for (let i = 0; i < 2; i++) {const q = frac(t * .5 + i / 2); c.globalAlpha = Math.sin(q * PI); c.fillText('z', x + q * 30 + i * 14, y - q * 60);} c.globalAlpha = 1;};
const rings = (c, t, x, y) => {c.strokeStyle = C.gold; c.lineWidth = 3; for (let i = 0; i < 3; i++) {const q = frac(t * 1.5 + i / 3); c.globalAlpha = 1 - q; c.beginPath(); c.arc(x, y, 6 + q * 34, -.8, .8); c.stroke();} c.globalAlpha = 1;};
function bird(c, t, S, a, ph, mv) {const s = S.size, fly = a === 'fly' || (!S.ground && mv > .3), f = fly ? Math.sin(t * 16 + ph) : 0, alt = fly ? -s * 4 - Math.sin(t * 2 + ph) * s * .6 : 0, peck = a === 'eat' ? Math.max(0, Math.sin(t * 6 + ph)) : 0;
	c.save(); if (!fly) {c.fillStyle = 'rgba(0,0,0,.3)'; c.beginPath(); c.ellipse(0, 3, s * .8, 5, 0, 0, 7); c.fill();}
	c.translate(0, alt - (S.penguin ? s * 1.3 : s * .9) - (mv > .05 && !fly ? Math.abs(Math.sin(t * 10 + ph)) * 4 : 0));
	if (!fly) {c.strokeStyle = S.beak; c.lineWidth = 3; [[-4, 1], [6, -1]].forEach(([x, k]) => {const sw = mv > .05 ? Math.sin(t * 10 + ph + k) * 6 : 0; c.beginPath(); c.moveTo(x, s * .4); c.lineTo(x + sw, S.penguin ? s * 1.3 : s * .9); c.stroke();});}
	c.fillStyle = S.c0; c.beginPath(); c.moveTo(-s * .8, -s * .1); c.lineTo(-s * 1.4, -s * .3 - (S.penguin ? 0 : 6)); c.lineTo(-s * 1.3, s * .1); c.closePath(); c.fill();        // tail
	const g = c.createLinearGradient(0, -s * .6, 0, s * .6); g.addColorStop(0, S.c1); g.addColorStop(1, S.c0); c.fillStyle = g;
	c.beginPath(); S.penguin ? c.ellipse(0, 0, s * .55, s * 1.05, 0, 0, 7) : c.ellipse(0, 0, s * (S.owl ? .7 : .9), s * (S.owl ? .8 : .55), S.owl ? 0 : -.15, 0, 7); c.fill();
	if (S.penguin) {c.fillStyle = C.white; c.beginPath(); c.ellipse(s * .12, s * .1, s * .36, s * .8, 0, 0, 7); c.fill();}
	// wing
	c.fillStyle = shadeC(S.c0); c.save(); c.translate(-s * .1, -s * .1); c.rotate(fly ? -f * .9 - .2 : .1); c.beginPath(); c.ellipse(-s * .2, fly ? -s * .4 : 0, s * (fly ? .9 : .55), s * .28, fly ? -.6 : .2, 0, 7); c.fill(); c.restore();
	// head
	const hx = S.owl || S.penguin ? s * .1 : s * .75, hy = S.owl ? -s * .65 : S.penguin ? -s * .9 : -s * .45 + peck * s * .5;
	c.fillStyle = S.white ? C.pale : S.c1; c.beginPath(); c.arc(hx, hy, s * (S.owl ? .5 : .38), 0, 7); c.fill();
	if (S.comb) {c.fillStyle = C.ember; [0, 1, 2].forEach((i) => {c.beginPath(); c.arc(hx - s * .15 + i * s * .14, hy - s * .4, s * .12, 0, 7); c.fill();});}
	if (S.owl) {[[-.18, 1], [.22, 1]].forEach(([x]) => {c.fillStyle = C.pale; c.beginPath(); c.arc(hx + x * s, hy, s * .17, 0, 7); c.fill(); c.fillStyle = C.char0; c.beginPath(); c.arc(hx + x * s, hy, s * .08, 0, 7); c.fill();}); c.fillStyle = S.c0; c.beginPath(); c.moveTo(hx - s * .4, hy - s * .3); c.lineTo(hx - s * .3, hy - s * .7); c.lineTo(hx - s * .15, hy - s * .4); c.fill();}
	else {c.fillStyle = C.char0; c.beginPath(); c.arc(hx + s * .15, hy - s * .06, Math.max(2, s * .07), 0, 7); c.fill();}
	c.fillStyle = S.beak; c.beginPath(); if (S.flat) {c.ellipse(hx + s * .45, hy + s * .08, s * .3, s * .1, 0, 0, 7);} else {c.moveTo(hx + s * .32, hy - s * .08); c.lineTo(hx + s * (S.owl ? .3 : .62), hy + s * .04); c.lineTo(hx + s * .32, hy + s * .12);} c.fill();
	c.restore(); if (a === 'speak') rings(c, t, hx + s, hy + alt - s);}
function fish(c, t, S, a, ph) {const s = S.size, w = Math.sin(t * 6 + ph); c.save(); c.translate(Math.sin(t * .7 + ph) * s * .8, -s * .8 + Math.sin(t * 1.3 + ph) * 6);
	const g = c.createLinearGradient(0, -s * .5, 0, s * .5); g.addColorStop(0, S.c1); g.addColorStop(1, S.c0); c.fillStyle = g;
	c.save(); c.translate(-s * .7, 0); c.rotate(w * .35); c.beginPath(); c.moveTo(0, 0); c.lineTo(-s * .55, -s * .4); c.lineTo(-s * .55, s * .4); c.closePath(); c.fill(); c.restore();
	c.beginPath(); c.ellipse(0, 0, s * .85, s * (S.whale ? .45 : .38), 0, 0, 7); c.fill();
	if (S.fin) {c.fillStyle = S.c0; c.beginPath(); c.moveTo(-s * .1, -s * .3); c.lineTo(s * .1, -s * .8); c.lineTo(s * .3, -s * .3); c.fill();}
	if (S.whale) {c.fillStyle = C.silver; c.beginPath(); c.ellipse(s * .1, s * .2, s * .6, s * .2, 0, 0, 7); c.fill(); for (let i = 0; i < 3; i++) {const q = frac(t + i / 3); c.globalAlpha = 1 - q; c.fillStyle = C.silver2; c.beginPath(); c.arc(s * .3 + i * 6, -s * .5 - q * s * .8, 6, 0, 7); c.fill();} c.globalAlpha = 1;}
	c.fillStyle = C.char0; c.beginPath(); c.arc(s * .5, -s * .08, Math.max(2.5, s * .07), 0, 7); c.fill(); c.restore();}
function critter(c, t, S, a, ph, mv) {const tp = S.type;
	if (tp === 'fly') {const s = S.size, f = Math.abs(Math.sin(t * (S.bee ? 40 : 10) + ph)); c.save(); c.translate(Math.sin(t * .9 + ph) * 60, -260 + Math.sin(t * 1.7 + ph) * 40);
		if (S.bee) {c.fillStyle = 'rgba(216,220,226,.6)'; c.beginPath(); c.ellipse(-2, -s * .8, s * .7, s * .4 * f + 1, 0, 0, 7); c.fill(); c.fillStyle = S.c0; c.beginPath(); c.ellipse(0, 0, s, s * .65, 0, 0, 7); c.fill(); c.fillStyle = S.c1; [-.3, .3].forEach((x) => c.fillRect(x * s - 2, -s * .6, 4, s * 1.2));}
		else {[S.c0, S.c1].forEach((col, i) => {c.fillStyle = col; c.save(); c.scale(1, i ? 1 : f * .9 + .1); c.beginPath(); c.ellipse(-s * .5, -s * .5, s * .7, s * .55, -.4, 0, 7); c.ellipse(s * .5, -s * .5, s * .7, s * .55, .4, 0, 7); c.fill(); c.restore();}); c.fillStyle = C.char0; c.fillRect(-2, -s * .8, 4, s * 1.2);}
		c.restore(); return;}
	if (tp === 'turtle') {const mvx = mv > .05 ? Math.sin(t * 4 + ph) * 6 : 0; c.fillStyle = S.c1; c.beginPath(); c.ellipse(52, -22, 16, 12, 0, 0, 7); c.fill(); [[-30, 1], [26, -1]].forEach(([x, k]) => {c.beginPath(); c.ellipse(x + mvx * k, -6, 12, 8, 0, 0, 7); c.fill();});
		c.fillStyle = S.c0; c.beginPath(); c.ellipse(0, -26, 52, 32, 0, PI, 0); c.fill(); c.strokeStyle = C.brass; c.lineWidth = 2.5; c.beginPath(); c.moveTo(-26, -26); c.lineTo(-12, -48); c.lineTo(12, -48); c.lineTo(26, -26); c.stroke(); c.fillStyle = C.char0; c.beginPath(); c.arc(58, -26, 3, 0, 7); c.fill(); return;}
	if (tp === 'frog') {const h = a === 'jump' || mv > .05 ? Math.abs(Math.sin(t * 4 + ph)) * 40 : 0; c.save(); c.translate(0, -h); c.fillStyle = S.c0; c.beginPath(); c.ellipse(-10, -10, 26, 16, 0, 0, 7); c.fill(); c.fillStyle = S.c1; c.beginPath(); c.ellipse(4, -22, 30, 20, -.2, 0, 7); c.fill();
		[[10, -40], [26, -38]].forEach(([x, y]) => {c.fillStyle = S.c1; c.beginPath(); c.arc(x, y, 9, 0, 7); c.fill(); c.fillStyle = C.char0; c.beginPath(); c.arc(x + 2, y, 4, 0, 7); c.fill();}); c.restore(); return;}
	if (tp === 'snake') {c.strokeStyle = S.c0; c.lineCap = 'round'; c.lineWidth = 16; c.beginPath(); for (let i = 0; i <= 30; i++) {const u = i / 30, x = -120 + u * 200, y = -10 - Math.sin(u * 9 - t * 4 + ph) * 14 * (1 - u * .3); i ? c.lineTo(x, y) : c.moveTo(x, y);} c.stroke();
		c.strokeStyle = S.c1; c.lineWidth = 5; c.setLineDash([8, 14]); c.stroke(); c.setLineDash([]); const hy = -10 - Math.sin(9 - t * 4 + ph) * 10; c.fillStyle = S.c0; c.beginPath(); c.ellipse(90, hy - 4, 18, 12, 0, 0, 7); c.fill();
		c.fillStyle = C.char0; c.beginPath(); c.arc(96, hy - 8, 3, 0, 7); c.fill(); c.strokeStyle = C.ember; c.lineWidth = 2; c.beginPath(); c.moveTo(108, hy - 2); c.lineTo(122, hy - 2 + Math.sin(t * 20) * 3); c.stroke();}}
/* draw one animal. x,y = feet in the CURRENT transform (already scaled to rig units). rideMode = under a rider */
export function drawAnimal(c, t, A, x = 0, y = 0, rideMode = false) {const S = SPECIES[A.kind] || SPECIES.dog, a = A.act || 'idle', mv = A.mv ?? (['walk', 'follow'].includes(a) ? 1 : a === 'run' ? 1 : 0), ph = A.ph || 0;
	c.save(); c.translate(x, y); c.scale((A.dir || 1) * (A.scale || 1), A.scale || 1);
	if (S.draw) S.draw(c, t, a, ph, mv); else if (S.type === 'quad') quad(c, t, S, a === 'follow' ? (mv > .05 ? 'walk' : 'wag') : a, ph, mv, rideMode); else if (S.type === 'bird') bird(c, t, S, a, ph, mv); else if (S.type === 'fish') fish(c, t, S, a, ph); else critter(c, t, S, a, ph, mv);
	c.restore();}
