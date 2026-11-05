// Layout audit: renders every mg-* beat kind in one style at 9:16 / 16:9 / 1:1 with captions ON, at the moment the most
// content is on screen, and tiles them into out/mg_audit/<style>_<aspect>.png. Usage: node mg_assets/layout_audit.mjs [style] [aspects]
import fs from 'node:fs';
import path from 'node:path';

const st = process.argv[2] || 'liquid';
const aspects = (process.argv[3] || '9:16,16:9').split(',');
const SIZE = {'16:9': [1920, 1080], '9:16': [1080, 1920], '1:1': [1080, 1080]};
const OUT = path.resolve('out/mg_audit');
fs.mkdirSync(OUT, {recursive: true});
const icons = JSON.parse(fs.readFileSync('public/mg/icons.json', 'utf8'));
const words = 'Light from the Sun takes about eight minutes to reach the Earth every single day'.split(' ').map((w, i) => ({w, s: 0.2 + i * 0.32, e: 0.48 + i * 0.32}));
const V = (kind, id, label, at) => ({kind, id, label, at, nodes: kind === 'icon' ? icons[id].n : undefined, motion: 'float'});
const jfk = {outfit: 'suit', hair: 'side', hairColor: '#6b4a32', skin: '#f0c8a8', accessory: 'tie', color: '#1f2a44'};
const BEATS = [
	['mg-title', {kicker: 'Chapter one', title: 'The speed of light is the universe speed limit', sub: 'Why nothing can ever go faster', visuals: [V('art', 'sun', '', 0.3), V('vec', 'rocket', '', 0.5)]}],
	['mg-stat', {kicker: 'In a vacuum', value: 299792, suffix: ' km/s', label: 'kilometres every second', visuals: [V('vec', 'zap', 'energy', 0.3)]}],
	['mg-visuals', {headline: 'Three things that light does every day', visuals: [V('art', 'sun', 'warms', 0.2), V('vec', 'eye', 'shows', 0.3), V('vec', 'leaf', 'feeds', 0.4), V('vec', 'zap', 'powers', 0.5)]}],
	['mg-relation', {headline: 'Sunlight is eight minutes old', link: '8 min 20 s', visuals: [V('art', 'sun', 'Sun', 0.1), V('art', 'earth', 'Earth', 0.2)]}],
	['mg-action', {action: 'speech', who: 'John F. Kennedy · Berlin 1963', headline: 'A speech that shook the world', figure: jfk, at: 0.1}],
	['mg-action', {action: 'score', who: 'The winning goal', headline: 'One kick changed everything', figure: {outfit: 'jersey', number: 10, skin: '#B07A55'}, at: 0.1}],
	['mg-list', {headline: 'Why nothing beats light', items: [{text: 'Speed costs energy', at: 0.2, visual: V('vec', 'zap', '', 0.2)}, {text: 'Mass grows as you speed up', at: 0.3, visual: V('vec', 'weight', '', 0.3)}, {text: 'Time slows down for you', at: 0.4, visual: V('vec', 'clock', '', 0.4)}, {text: 'Infinite energy is impossible', at: 0.5, visual: V('vec', 'infinity', '', 0.5)}]}],
	['mg-compare', {headline: 'The impossible energy bill', a: 'Energy available', aval: 'Finite', b: 'Energy needed', bval: 'Infinite', visuals: [V('vec', 'battery', '', 0.2), V('vec', 'orbit', '', 0.3)]}],
	['mg-quote', {text: 'We choose to go to the Moon not because it is easy, but because it is hard.', by: 'John F. Kennedy, 1962', visuals: [V('art', 'moon', '', 0.3)]}],
	['mg-endcard', {}],
];
for (const asp of aspects) {
	const [w, h] = SIZE[asp];
	const files = [];
	for (const [i, [type, props]] of BEATS.entries()) {
		const project = {w, h, fps: 30, style: st, tracks: [{kind: 'scene', clips: [{id: 'b', type, start: 0, dur: 7, props: {style: st, n: i + 1, words, ...props}}]}]};
		const out = path.join(OUT, `${st}_${asp.replace(':', 'x')}_${i}.jpg`);
		const r = await fetch('http://127.0.0.1:5420/still', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({project, frame: 105, out, scale: 0.4})});
		const j = await r.json();
		if (!j.ok) console.log(type, asp, JSON.stringify(j).slice(0, 160));
		else files.push(out);
	}
	console.log(asp, files.length, 'stills');
}
