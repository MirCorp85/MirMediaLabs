// MIR MEDIA LABS · Stage — grey-clay shot blocking (port of OpenField stage.ts / stageView.ts, MIT).
// Shapes on a checker floor + a keyed camera → a clay clip rendered frame by frame here in the browser,
// sent to /api/ff/stage/blocking, then the Studio "Stage" app turns it into a finished LTX-2.5 shot.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const B = false ? '/' : '';
const $ = (id) => document.getElementById(id);
const FPS = 24;
const SIZES = { '16:9': { '480p': [768, 448], '720p': [1280, 704] }, '9:16': { '480p': [448, 768], '720p': [704, 1280] }, '1:1': { '480p': [576, 576], '720p': [960, 960] } };
const SENSOR = 36;                                   // lens mm → vertical FOV against a 36 mm long edge

// ── clay look (OpenField stage shader constants) ────────────────────────────────────────────────────────────
const CLAY = new THREE.ShaderMaterial({
  uniforms: { albedo: { value: 0.64 } },
  vertexShader: `varying vec3 vN; varying vec3 vW;
    void main(){ vec4 w = modelMatrix * vec4(position,1.0); vW = w.xyz; vN = normalize(mat3(modelMatrix) * normal);
      gl_Position = projectionMatrix * viewMatrix * w; }`,
  fragmentShader: `uniform float albedo; varying vec3 vN; varying vec3 vW;
    void main(){ vec3 n = normalize(vN);
      float key = max(dot(n, normalize(vec3(0.75,0.7,0.45))),0.0)*0.66;
      float fill = max(dot(n, normalize(vec3(-0.7,0.3,0.3))),0.0)*0.14;
      float c = albedo*(0.34+key+fill)*1.25; gl_FragColor = vec4(vec3(clamp(c,0.0,1.0)),1.0); }`,
});
const GROUND = new THREE.ShaderMaterial({
  vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }`,
  fragmentShader: `varying vec3 vW; void main(){ vec2 t = floor(vW.xz/2.0); float k = mod(t.x+t.y,2.0);
      float c = (0.44 + (k-0.5)*0.045*2.0)*(0.34+0.66*0.7+0.14*0.3)*1.25*0.82; gl_FragColor = vec4(vec3(clamp(c,0.0,1.0)),1.0); }`,
});

// ── scene ───────────────────────────────────────────────────────────────────────────────────────────────────
const view = $('sg-view');
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setClearColor(new THREE.Color(0.11, 0.11, 0.115));
view.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), GROUND);
ground.rotation.x = -Math.PI / 2;
scene.add(ground);
const cam = new THREE.PerspectiveCamera(40, 16 / 9, 0.1, 500);
cam.position.set(0, 1.6, 7);
const orbit = new OrbitControls(cam, renderer.domElement);
orbit.target.set(0, 1, 0);
orbit.enableDamping = false;
orbit.update();

const shapes = [];                                    // {mesh, kind, p0:{x,z}, p1:{x,z}|null}
let sel = null;

function geo(kind) {
  const g = new THREE.Group();
  const m = (geom, y) => { const x = new THREE.Mesh(geom, CLAY); x.position.y = y; g.add(x); return x; };
  if (kind === 'person') { m(new THREE.CapsuleGeometry(0.22, 0.95, 6, 16), 0.72); m(new THREE.SphereGeometry(0.15, 20, 14), 1.55); }
  else if (kind === 'box') m(new THREE.BoxGeometry(1, 1, 1), 0.5);
  else if (kind === 'ball') m(new THREE.SphereGeometry(0.5, 28, 18), 0.5);
  else if (kind === 'pillar') m(new THREE.CylinderGeometry(0.3, 0.3, 3, 24), 1.5);
  else if (kind === 'wall') m(new THREE.BoxGeometry(4, 2.6, 0.2), 1.3);
  else if (kind === 'car') { m(new THREE.BoxGeometry(1.8, 0.6, 4.2), 0.55); m(new THREE.BoxGeometry(1.6, 0.5, 2.2), 1.1); }
  return g;
}
function add(kind, at) {
  const mesh = geo(kind);
  const p = at || { x: (Math.random() - 0.5) * 3, z: (Math.random() - 0.5) * 2 };
  mesh.position.set(p.x, 0, p.z);
  scene.add(mesh);
  const s = { mesh, kind, p0: { x: p.x, z: p.z }, p1: null };
  shapes.push(s);
  pick(s);
  return s;
}
function pick(s) {
  sel = s;
  $('sg-sel').textContent = s ? s.kind + (s.p1 ? ' · moves' : '') : 'Click a shape. Drag it on the floor.';
  if (s) { $('sg-scale').value = s.mesh.scale.x; $('sg-rot').value = Math.round(THREE.MathUtils.radToDeg(s.mesh.rotation.y)); $('sg-lift').value = s.mesh.position.y; }
}

// drag shapes along the floor
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(), floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit = new THREE.Vector3();
let drag = null;
function toNdc(e) { const r = renderer.domElement.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ndc, cam); }
renderer.domElement.addEventListener('pointerdown', (e) => {
  toNdc(e);
  const hits = ray.intersectObjects(shapes.map((s) => s.mesh), true);
  if (!hits.length) return;
  let o = hits[0].object; while (o.parent && o.parent !== scene) o = o.parent;
  const s = shapes.find((x) => x.mesh === o); pick(s);
  ray.ray.intersectPlane(floor, hit);
  drag = { s, dx: s.mesh.position.x - hit.x, dz: s.mesh.position.z - hit.z, end: e.altKey && !!s.p1 };
  orbit.enabled = false;
  renderer.domElement.setPointerCapture(e.pointerId);
});
renderer.domElement.addEventListener('pointermove', (e) => {
  if (!drag) return;
  toNdc(e);
  if (!ray.ray.intersectPlane(floor, hit)) return;
  const p = { x: hit.x + drag.dx, z: hit.z + drag.dz };
  if (drag.end) drag.s.p1 = p; else drag.s.p0 = p;
  setTime(+$('sg-time').value);
});
renderer.domElement.addEventListener('pointerup', () => { drag = null; orbit.enabled = true; });

$('sg-scale').oninput = (e) => { if (sel) sel.mesh.scale.setScalar(+e.target.value); };
$('sg-rot').oninput = (e) => { if (sel) sel.mesh.rotation.y = THREE.MathUtils.degToRad(+e.target.value); };
$('sg-lift').oninput = (e) => { if (sel) sel.mesh.position.y = +e.target.value; };
$('sg-del').onclick = () => { if (!sel) return; scene.remove(sel.mesh); shapes.splice(shapes.indexOf(sel), 1); pick(null); };
$('sg-dup').onclick = () => { if (!sel) return; const s = add(sel.kind, { x: sel.p0.x + 1, z: sel.p0.z }); s.mesh.scale.copy(sel.mesh.scale); s.mesh.rotation.y = sel.mesh.rotation.y; };
$('sg-end').onclick = () => {
  if (!sel) return;
  if (sel.p1) { sel.p1 = null; msg('The shape stays put.'); }
  else { sel.p1 = { x: sel.p0.x + 1.5, z: sel.p0.z }; msg('End spot set. Scrub to the end and Alt-drag the shape to move its end spot.'); }
  pick(sel); setTime(+$('sg-time').value);
};
document.querySelectorAll('[data-add]').forEach((b) => (b.onclick = () => add(b.dataset.add)));

// ── camera keys + moves ─────────────────────────────────────────────────────────────────────────────────────
const lensFov = (mm, aspect) => { const longEdge = SENSOR, v = aspect >= 1 ? longEdge / aspect : longEdge; return THREE.MathUtils.radToDeg(2 * Math.atan(v / 2 / mm)); };
const snap = () => ({ p: cam.position.clone(), t: orbit.target.clone(), lens: +$('sg-lens').value });
let K0 = null, K1 = null;
const smooth = (u) => u * u * (3 - 2 * u);
function moveKeys() {
  const mv = $('sg-move').value, a = K0 || snap();
  if (mv === 'keys') return [a, K1 || a];
  const b = { p: a.p.clone(), t: a.t.clone(), lens: a.lens };
  const fwd = a.t.clone().sub(a.p), dist = fwd.length(); fwd.normalize();
  const side = new THREE.Vector3().crossVectors(fwd, new THREE.Vector3(0, 1, 0)).normalize();
  const orbitBy = (deg) => { const off = a.p.clone().sub(a.t).applyAxisAngle(new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(deg)); b.p.copy(a.t).add(off); };
  if (mv === 'pushin') b.p.addScaledVector(fwd, dist * 0.35);
  else if (mv === 'pullback') b.p.addScaledVector(fwd, -dist * 0.35);
  else if (mv === 'orbitl') orbitBy(-30);
  else if (mv === 'orbitr') orbitBy(30);
  else if (mv === 'crane') { b.p.y += 2.2; b.t.y += 0.6; }
  else if (mv === 'panl' || mv === 'panr') { const off = a.t.clone().sub(a.p).applyAxisAngle(new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(mv === 'panl' ? 25 : -25)); b.t.copy(a.p).add(off); }
  else if (mv === 'truck') { b.p.addScaledVector(side, dist * 0.3); b.t.addScaledVector(side, dist * 0.3); }
  return [a, b];
}
function camAt(u) {
  const [a, b] = moveKeys(), e = smooth(u);
  const [w, h] = size();
  cam.position.lerpVectors(a.p, b.p, e);
  const t = new THREE.Vector3().lerpVectors(a.t, b.t, e);
  cam.fov = lensFov(a.lens + (b.lens - a.lens) * e, w / h);
  cam.aspect = w / h;
  cam.lookAt(t);
  cam.updateProjectionMatrix();
}
function shapesAt(u) {
  const e = smooth(u);
  for (const s of shapes) { const q = s.p1 || s.p0; s.mesh.position.x = s.p0.x + (q.x - s.p0.x) * e; s.mesh.position.z = s.p0.z + (q.z - s.p0.z) * e; }
}
$('sg-k0').onclick = () => { K0 = snap(); msg('Start camera set.'); };
$('sg-k1').onclick = () => { K1 = snap(); $('sg-move').value = 'keys'; msg('End camera set; move is now "My keys".'); };

// ── frame size + time ───────────────────────────────────────────────────────────────────────────────────────
function size() { return SIZES[$('sg-aspect').value][$('sg-q').value]; }
function frames() { const n = Math.round(+$('sg-secs').value * FPS); return Math.max(9, Math.floor((n - 1) / 8) * 8 + 1); }
function fit() {
  const [w, h] = size(), box = view.getBoundingClientRect(), k = Math.min((box.width - 24) / w, (box.height - 24) / h, 1);
  renderer.setSize(w, h, false);
  renderer.domElement.style.width = Math.round(w * k) + 'px';
  renderer.domElement.style.height = Math.round(h * k) + 'px';
  $('sg-secs-v').textContent = $('sg-secs').value + ' s';
  $('sg-lens-v').textContent = $('sg-lens').value + ' mm';
  $('sg-frames').textContent = frames() + ' frames · ' + w + '×' + h;
  if (!playing && +$('sg-time').value === 0) { cam.aspect = w / h; cam.fov = lensFov(+$('sg-lens').value, w / h); cam.updateProjectionMatrix(); }
}
let playing = false, scrubbing = false;
function setTime(u) { scrubbing = u > 0; if (scrubbing) { camAt(u); } shapesAt(u); }
$('sg-time').oninput = (e) => setTime(+e.target.value);
['sg-aspect', 'sg-q', 'sg-secs', 'sg-lens'].forEach((id) => $(id).addEventListener('input', fit));
$('sg-play').onclick = () => {
  if (playing) return;
  playing = true; orbit.enabled = false;
  const t0 = performance.now(), dur = frames() / FPS * 1000;
  const step = (now) => {
    const u = Math.min(1, (now - t0) / dur);
    $('sg-time').value = u; camAt(u); shapesAt(u);
    if (u < 1) requestAnimationFrame(step); else { playing = false; orbit.enabled = true; }
  };
  requestAnimationFrame(step);
};
// leaving a scrub: hand the camera back to the start key so orbiting edits the start pose
renderer.domElement.addEventListener('pointerdown', () => {
  if (!playing && scrubbing && !drag) { const a = moveKeys()[0]; cam.position.copy(a.p); orbit.target.copy(a.t); orbit.update(); $('sg-time').value = 0; scrubbing = false; shapesAt(0); }
}, true);

function loop() {
  requestAnimationFrame(loop);
  const [w, h] = size();
  if (!playing && !scrubbing) { cam.aspect = w / h; cam.fov = lensFov(+$('sg-lens').value, w / h); cam.updateProjectionMatrix(); orbit.update(); }
  renderer.render(scene, cam);
  $('sg-hud').textContent = shapes.length ? '' : 'Add a person or a box to start. Right-drag pans, wheel zooms.';
}

// ── render the clay clip + hand it to Studio ────────────────────────────────────────────────────────────────
function msg(t) { $('sg-msg').textContent = t || ''; }
function sceneJson() {
  return { shapes: shapes.map((s) => ({ kind: s.kind, p0: s.p0, p1: s.p1, scale: s.mesh.scale.x, rot: s.mesh.rotation.y, lift: s.mesh.position.y })),
    move: $('sg-move').value, keys: moveKeys().map((k) => ({ p: k.p.toArray(), t: k.t.toArray(), lens: k.lens })), aspect: $('sg-aspect').value, q: $('sg-q').value, secs: +$('sg-secs').value };
}
$('sg-go').onclick = async () => {
  const prompt = $('sg-prompt').value.trim();
  if (!shapes.length) return msg('Add at least one shape first.');
  if (!prompt) { $('sg-prompt').focus(); return msg('Say what the shot looks like.'); }
  const go = $('sg-go'); go.disabled = true;
  if (!scrubbing) K0 = K0 || snap();
  const n = frames(), [w, h] = size(), clay = [];
  try {
    for (let i = 0; i < n; i++) {
      const u = n > 1 ? i / (n - 1) : 0;
      camAt(u); shapesAt(u);
      renderer.render(scene, cam);
      clay.push(renderer.domElement.toDataURL('image/jpeg', 0.92));
      if (i % 6 === 0) { msg('Rendering clay ' + (i + 1) + ' / ' + n); await new Promise((r) => setTimeout(r)); }
    }
    msg('Sending the blocking…');
    const r = await fetch(B + '/api/ff/stage/blocking', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
      body: JSON.stringify({ clay, width: w, height: h, scene: sceneJson() }) });
    const d = await r.json().catch(() => ({ error: 'HTTP ' + r.status }));
    if (d.error) throw new Error(d.error);
    const q = new URLSearchParams({ app: 'stage', clay: d.up, prompt, era: $('sg-era').value, ramp: $('sg-ramp').value });
    location.href = B + '/studio?' + q.toString();
  } catch (e) { msg('Not sent: ' + e.message); }
  finally { go.disabled = false; $('sg-time').value = 0; shapesAt(0); scrubbing = false; }
};
$('sg-back').href = B + '/studio';

addEventListener('resize', fit);
add('person', { x: 0, z: 0 });
fit();
loop();
if (window.MI && MI.scan) MI.scan();
