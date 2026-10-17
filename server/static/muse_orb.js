/* MUSE 3D — her live look (4 styles), shared by the header button, the live-voice card and the app (muse_orb.html).
   window.MuseOrb.mount(canvas, {style, small}) -> {state(s), level(v), style(s), destroy()}
   styles: pearl · halo · particles · crystal   states: idle · listening · hearing · thinking · speaking */
import * as THREE from './three.module.js';

const STYLES = [
  {id: 'pearl', name: 'Liquid Pearl', desc: 'a glossy orb that ripples like liquid with your voice'},
  {id: 'halo', name: 'Neural Halo', desc: 'a glowing core in three rings that spin faster as she thinks'},
  {id: 'particles', name: 'Particle Soul', desc: 'a cloud of sparks that breathes, swirls and bursts when she talks'},
  {id: 'crystal', name: 'Crystal Muse', desc: 'a faceted gem with an inner light that pulses to the words'},
];
const COL = {idle: 0x8a7cff, listening: 0x3ddc97, hearing: 0xffd23f, thinking: 0x7aa2ff, speaking: 0xff5fd2, error: 0xff4d4d};

function pearl(g, small) {
  const geo = new THREE.IcosahedronGeometry(1.15, small ? 24 : 56), base = geo.attributes.position.array.slice();
  const m = new THREE.MeshPhysicalMaterial({color: 0xffffff, roughness: .12, metalness: .3, clearcoat: 1});
  g.add(new THREE.Mesh(geo, m));
  return (t, lv, col) => {
    const p = geo.attributes.position.array;
    for (let i = 0; i < p.length; i += 3) {
      const x = base[i], y = base[i + 1], z = base[i + 2];
      // three octaves of fast, crashing waves + a sharp chop that spikes with the voice
      const w1 = Math.sin(x * 2.6 + t * 4.2) * Math.sin(y * 2.9 + t * 3.6) * Math.sin(z * 2.4 + t * 4.8);
      const w2 = Math.sin(x * 5.3 - t * 7.1 + y * 1.7) * Math.cos(z * 4.9 + t * 6.3);
      const w3 = Math.sin((x + y - z) * 9 + t * 11);
      const chop = Math.pow(Math.abs(w2), .6) * Math.sign(w2);
      const k = 1 + w1 * (.16 + lv * .4) + chop * (.08 + lv * .3) + w3 * (.025 + lv * .09);
      p[i] = x * k; p[i + 1] = y * k; p[i + 2] = z * k;
    }
    geo.attributes.position.needsUpdate = true; geo.computeVertexNormals();
    m.color.copy(col); m.emissive.copy(col).multiplyScalar(.15 + lv * .35);
  };
}
function halo(g, small, S) {
  const core = new THREE.Mesh(new THREE.SphereGeometry(.6, 40, 40), new THREE.MeshBasicMaterial({color: 0xffffff})); g.add(core);
  const glow = new THREE.Mesh(new THREE.SphereGeometry(.85, 40, 40), new THREE.MeshBasicMaterial({color: 0xffffff, transparent: true, opacity: .18})); g.add(glow);
  const rings = [0, 1, 2].map(i => {
    const r = new THREE.Mesh(new THREE.TorusGeometry(1.25 + i * .22, small ? .05 : .025, 12, 120), new THREE.MeshBasicMaterial({color: 0xffffff}));
    r.rotation.x = i * 1.1; r.rotation.y = i * .7; g.add(r); return r;
  });
  return (t, lv, col) => {
    core.material.color.copy(col); glow.material.color.copy(col);
    core.scale.setScalar(1 + lv * .35); glow.scale.setScalar(1 + lv * .6); glow.material.opacity = .15 + lv * .3;
    const sp = S.state === 'thinking' ? .05 : .012 + lv * .03;
    rings.forEach((r, i) => { r.rotation.z += sp * (i % 2 ? 1 : -1) * (1 + i * .3); r.rotation.x += sp * .4; r.material.color.copy(col).offsetHSL(i * .06, 0, 0); });
  };
}
function particles(g, small, S) {
  const N = small ? 700 : 3000, pos = new Float32Array(N * 3), dir = [];
  for (let i = 0; i < N; i++) { const u = Math.random() * 2 - 1, a = Math.random() * 6.283, s = Math.sqrt(1 - u * u); dir.push([s * Math.cos(a), u, s * Math.sin(a), .8 + Math.random() * .6]); }
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const m = new THREE.PointsMaterial({size: small ? .08 : .035, color: 0xffffff, transparent: true, opacity: .9, blending: THREE.AdditiveBlending, depthWrite: false});
  g.add(new THREE.Points(geo, m));
  return (t, lv, col) => {
    m.color.copy(col);
    for (let i = 0; i < N; i++) {
      const d = dir[i], sw = S.state === 'thinking' ? t * 1.5 + d[3] * 4 : 0;
      const r = d[3] * (1 + lv * .7 * Math.sin(t * 6 + i)) * 1.1 + Math.sin(t * 1.3 + i * .01) * .05;
      const c = Math.cos(sw), s = Math.sin(sw);
      pos[i * 3] = (d[0] * c - d[2] * s) * r; pos[i * 3 + 1] = d[1] * r; pos[i * 3 + 2] = (d[0] * s + d[2] * c) * r;
    }
    geo.attributes.position.needsUpdate = true;
  };
}
function crystal(g) {
  const gem = new THREE.Mesh(new THREE.OctahedronGeometry(1.25, 1), new THREE.MeshPhysicalMaterial({color: 0xffffff, roughness: .05, transparent: true, opacity: .85, flatShading: true, clearcoat: 1}));
  g.add(gem);
  const wire = new THREE.LineSegments(new THREE.EdgesGeometry(gem.geometry), new THREE.LineBasicMaterial({color: 0xffffff, transparent: true, opacity: .6})); g.add(wire);
  const inner = new THREE.Mesh(new THREE.SphereGeometry(.4, 32, 32), new THREE.MeshBasicMaterial({color: 0xffffff})); g.add(inner);
  const pl = new THREE.PointLight(0xffffff, 2, 6); g.add(pl);
  return (t, lv, col) => {
    gem.material.color.copy(col); wire.material.color.copy(col); inner.material.color.copy(col); pl.color.copy(col);
    pl.intensity = 1 + lv * 4; inner.scale.setScalar(.8 + lv * 1.2);
    const s = 1 + lv * .12; gem.scale.setScalar(s); wire.scale.setScalar(s);
  };
}
const MAKERS = {pearl, halo, particles, crystal};

function mount(cv, opt = {}) {
  const small = !!opt.small;
  const S = {state: opt.state || 'idle', level: 0, style: MAKERS[opt.style] ? opt.style : 'pearl', alive: true};
  const r = new THREE.WebGLRenderer({canvas: cv, antialias: true, alpha: true});
  r.useLegacyLights = true; r.setPixelRatio(Math.min(2, devicePixelRatio || 1));
  const sc = new THREE.Scene(), cam = new THREE.PerspectiveCamera(40, 1, .1, 100); cam.position.z = small ? 4.4 : 5.2;
  sc.add(new THREE.AmbientLight(0xffffff, .35));
  const L = new THREE.PointLight(0xffffff, 1.2); L.position.set(3, 3, 5); sc.add(L);
  let grp, upd;
  function build() {
    if (grp) { sc.remove(grp); grp.traverse(o => { o.geometry && o.geometry.dispose(); o.material && o.material.dispose(); }); }
    grp = new THREE.Group(); sc.add(grp); upd = MAKERS[S.style](grp, small, S);
  }
  build();
  let drag = null, moved = 0, vx = 0, vy = .004, poke = 0;
  if (!opt.still) {
    cv.addEventListener('pointerdown', e => { drag = [e.clientX, e.clientY]; moved = 0; poke = 1; });
    addEventListener('pointermove', e => { if (!drag) return; const dx = e.clientX - drag[0], dy = e.clientY - drag[1]; moved += Math.abs(dx) + Math.abs(dy);
      vy = dx * .004; vx = dy * .004; drag = [e.clientX, e.clientY]; });
    addEventListener('pointerup', () => { drag = null; });
  }
  cv.museMoved = () => moved > 6;                 // a drag isn't a click
  const col = new THREE.Color(COL[S.state]), tgt = new THREE.Color();
  function size() { const w = cv.clientWidth || 40, h = cv.clientHeight || 40; r.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
  const ro = new ResizeObserver(size); ro.observe(cv); size();
  let sm = 0;
  (function f(ms) {
    if (!S.alive) return;
    if (document.hidden) { requestAnimationFrame(f); return; }
    const t = ms / 1000;
    let lv = S.level;
    if (S.state === 'speaking' && lv < .05) lv = .3 + .45 * Math.abs(Math.sin(t * 7.1) * Math.cos(t * 3.7));   // no meter for her voice: animate
    if (S.state === 'thinking') lv = Math.max(lv, .25);
    if (S.state === 'idle') lv = Math.max(lv, .06 + .04 * Math.sin(t * 1.4));
    sm += (lv - sm) * .25; poke *= .92;
    col.lerp(tgt.setHex(COL[S.state] || COL.idle), .06);
    grp.rotation.y += vy; grp.rotation.x += vx;
    if (!drag) { vx *= .95; vy = vy * .97 + .004 * .03; }
    upd(t, Math.min(1.2, sm + poke * .6), col);
    r.render(sc, cam);
    requestAnimationFrame(f);
  })(0);
  return {
    state(s) { if (s) S.state = s; return S.state; },
    level(v) { S.level = Math.max(0, Math.min(1, v || 0)); },
    style(s) { if (s && MAKERS[s] && s !== S.style) { S.style = s; build(); } return S.style; },
    destroy() { S.alive = false; ro.disconnect(); r.dispose(); },
  };
}
window.MuseOrb = {mount, STYLES};
window.dispatchEvent(new Event('museorb-ready'));
