// MIR MOTION GRAPHICS — vector art library. Every Lucide glyph (public/mg/icons.json, 1,539 shapes, ISC) becomes a
// styled illustration in each of the four motion styles — layered SVG, no AI, seconds for the whole set:
//   signature  brushed graphite plate + silver stroke stack + one amber glow accent (studio product look)
//   grid       vermilion block, offset black duplicate, halftone dots, thick paper-white stroke (Swiss poster)
//   liquid     glossy inflated badge (radial gradient + specular) with a soft white glyph and pastel glow
//   paper      three stacked cut-paper layers with hard shadows, mustard/tomato/blue, kraft texture noise
// Output: public/mg/vec/<style>/<name>.svg + public/mg/vec/manifest.json {name: tags}.
// The AI cut-outs (build_art.py) are nicer for hero concepts and win when they exist; these cover EVERY word.
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const OUT = path.join(ROOT, 'public', 'mg', 'vec');
const ICONS = JSON.parse(fs.readFileSync(path.join(ROOT, 'public', 'mg', 'icons.json'), 'utf8'));
const STYLES = JSON.parse(fs.readFileSync(path.join(HERE, 'styles.json'), 'utf8'));

const nodes = (ns, extra) => ns.map(([tag, a]) => `<${tag} ${Object.entries(a).map(([k, v]) => `${k}="${v}"`).join(' ')} ${extra || ''}/>`).join('');
// the 24-unit glyph drawn at scale `k` centred in a 512 box
const glyph = (ns, k, attrs, dx = 0, dy = 0) => `<g transform="translate(${256 - 12 * k + dx} ${256 - 12 * k + dy}) scale(${k})" fill="none" stroke-linecap="round" stroke-linejoin="round" ${attrs}>${nodes(ns)}</g>`;
const svg = (body, defs = '') => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512"><defs>${defs}</defs>${body}</svg>`;

const R = {
	signature(ns, P) {
		const defs = `<linearGradient id="m" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5A5B62"/><stop offset=".5" stop-color="#2C2C31"/><stop offset="1" stop-color="#4A4B52"/></linearGradient>
<linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#A9AFB7"/></linearGradient>
<radialGradient id="a" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="${P.acc3}"/><stop offset=".4" stop-color="${P.acc}" stop-opacity=".9"/><stop offset="1" stop-color="${P.acc}" stop-opacity="0"/></radialGradient>
<filter id="sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="18" stdDeviation="16" flood-color="#000" flood-opacity=".55"/></filter>
<filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>`;
		return svg(`<circle cx="256" cy="256" r="214" fill="url(#m)" filter="url(#sh)"/>
<circle cx="256" cy="256" r="214" fill="none" stroke="#8A8E96" stroke-width="3"/>
<circle cx="256" cy="256" r="196" fill="none" stroke="#1B1B1F" stroke-width="10"/>
<circle cx="256" cy="256" r="196" fill="none" stroke="#C7CBD1" stroke-width="1.5" stroke-dasharray="3 9" opacity=".7"/>
<circle cx="256" cy="256" r="120" fill="url(#a)" opacity=".55" filter="url(#gl)"/>
${glyph(ns, 11, 'stroke="#000" stroke-width="3.4" opacity=".6"', 0, 6)}
${glyph(ns, 11, 'stroke="url(#s)" stroke-width="1.9"')}
${glyph(ns, 11, `stroke="${P.acc3}" stroke-width=".55" opacity=".9"`)}`, defs);
	},
	grid(ns, P) {
		const defs = `<pattern id="ht" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(25)"><circle cx="7" cy="7" r="2.6" fill="${P.ink}"/></pattern>`;
		return svg(`<rect x="86" y="86" width="340" height="340" fill="${P.ink}"/>
<rect x="60" y="60" width="340" height="340" fill="${P.acc}"/>
<rect x="60" y="300" width="340" height="100" fill="url(#ht)" opacity=".55"/>
${glyph(ns, 11.5, `stroke="${P.ink}" stroke-width="2.6"`, 14, 14)}
${glyph(ns, 11.5, `stroke="${P.bg}" stroke-width="2.6"`)}`, defs);
	},
	liquid(ns, P, i) {
		const cols = [P.acc, P.acc2, P.acc3, P.acc4];
		const c = cols[i % 4], c2 = cols[(i + 1) % 4];
		const defs = `<radialGradient id="b" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".18" stop-color="${c}"/><stop offset="1" stop-color="${c2}"/></radialGradient>
<radialGradient id="g" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="${c}" stop-opacity=".6"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></radialGradient>
<radialGradient id="hl" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff" stop-opacity=".95"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<filter id="sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="22" stdDeviation="18" flood-color="${c2}" flood-opacity=".55"/></filter>`;
		return svg(`<circle cx="256" cy="276" r="250" fill="url(#g)"/>
<circle cx="256" cy="256" r="200" fill="url(#b)" filter="url(#sh)"/>
<ellipse cx="200" cy="170" rx="86" ry="54" fill="url(#hl)"/>
<ellipse cx="256" cy="420" rx="150" ry="26" fill="#000" opacity=".18"/>
${glyph(ns, 9.5, 'stroke="#000" stroke-width="2.4" opacity=".18"', 0, 8)}
${glyph(ns, 9.5, 'stroke="#fff" stroke-width="2.2"')}`, defs);
	},
	dusk(ns, P, i) {
		// Cinematic Dusk: a dark violet disc lit by a sunset gradient, warm rim light, white glyph
		const defs = `<linearGradient id="d" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#04161A"/><stop offset=".62" stop-color="#0E3B42"/><stop offset="1" stop-color="#2C6E6A"/></linearGradient>
<radialGradient id="sg" cx=".5" cy=".85" r=".6"><stop offset="0" stop-color="#FF8A4C" stop-opacity=".55"/><stop offset="1" stop-color="#FF8A4C" stop-opacity="0"/></radialGradient>
<filter id="sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="18" stdDeviation="16" flood-color="#000" flood-opacity=".5"/></filter>`;
		return svg(`<circle cx="256" cy="256" r="212" fill="url(#d)" filter="url(#sh)"/>
<circle cx="256" cy="256" r="212" fill="url(#sg)"/>
<path d="M60 230 A212 212 0 0 1 256 44" stroke="${P.line}" stroke-width="6" fill="none" opacity=".85" stroke-linecap="round"/>
${glyph(ns, 10, 'stroke="#0B0912" stroke-width="2.6" opacity=".5"', 4, 7)}
${glyph(ns, 10, 'stroke="#FFF6EA" stroke-width="2.2"')}`, defs);
	},
	paper(ns, P, i) {
		const cols = [P.acc, P.acc2, P.acc3];
		const c = cols[i % 3], c2 = cols[(i + 1) % 3];
		const defs = `<filter id="p" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="9" dy="11" stdDeviation="1.2" flood-color="#3B2A17" flood-opacity=".35"/></filter>
<filter id="nz"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="${i % 50}"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="table" tableValues="0 .14"/></feComponentTransfer></filter>`;
		const rot = ((i * 37) % 11) - 5;
		return svg(`<g transform="rotate(${rot} 256 256)">
<polygon points="70,96 448,70 436,436 84,420" fill="${c2}" filter="url(#p)"/>
<polygon points="98,120 420,100 410,408 110,392" fill="${P.acc4}" filter="url(#p)"/>
<circle cx="256" cy="256" r="118" fill="${c}" filter="url(#p)"/>
<rect x="60" y="60" width="392" height="392" filter="url(#nz)" opacity=".9"/>
${glyph(ns, 7.6, `stroke="${P.dark}" stroke-width="3.2" opacity=".35"`, 5, 6)}
${glyph(ns, 7.6, `stroke="${P.acc4}" stroke-width="3.2"`)}
</g>`, defs);
	},
};

const man = {};
let n = 0;
for (const st of Object.keys(STYLES)) fs.mkdirSync(path.join(OUT, st), {recursive: true});
Object.entries(ICONS).forEach(([name, {t, n: ns}], i) => {
	man[name] = t;
	for (const st of Object.keys(STYLES)) {
		fs.writeFileSync(path.join(OUT, st, name + '.svg'), R[st](ns, STYLES[st].palette, i));
		n++;
	}
});
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(man));
console.log('vector library:', n, 'svgs in', Object.keys(STYLES).length, 'styles');
