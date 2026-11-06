/* MIR MEDIA LABS · Motion Editor on MIR KINETIC (Nov 5 2026)
   A film is scene BLOCKS placed on the music's beat grid, plus OpenKatana EFFECTS, a caption track and the music.
   The preview iframe (kinetic/engine/film.html) builds the film from this project JSON and is a pure function of time;
   rendering happens on this PC (api/kinetic/render → Chrome over CDP + ffmpeg). Everything is in beats: B(k) = k·60/bpm. */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); }, $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var Q = new URLSearchParams(location.search);
  var B_ = false ? '/' : '';
  var API = B_ + '/api/kinetic/';
  var ic = function (n) { return '<i class="mi" data-ic="' + n + '"></i>'; };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var toast = function (m, ms) { var t = $('#kn-toast'); t.textContent = m; t.classList.add('on'); clearTimeout(toast._); toast._ = setTimeout(function () { t.classList.remove('on'); }, ms || 2400); };
  var uid = function () { return Math.random().toString(36).slice(2, 9); };
  var icons = function (r) { if (window.MI && MI.hydrate) { try { MI.hydrate(r || document); } catch (e) { } } };

  /* ── theme (same palette table as the lab) ── */
  var THEMES = { claude: ['#262624', '#30302e', '#3a3936', '#f5f4ef', '#d97757'], graphite: ['#111214', '#18191c', '#212327', '#eceef1', '#7c8cff'],
    obsidian: ['#0e0d0b', '#171512', '#211e19', '#f3eee4', '#e3a949'], midnight: ['#0b1220', '#101929', '#172236', '#e6ecf5', '#3fb8c9'],
    paper: ['#f6f5f1', '#ffffff', '#f1efe9', '#1e1d1a', '#c2582f'] };
  function theme(id) { var t = THEMES[id] || THEMES.claude, r = document.documentElement.style; ['--bg', '--panel', '--panel2', '--ink', '--acc'].forEach(function (k, i) { r.setProperty(k, t[i]); }); }
  try { theme(localStorage.getItem('mml.theme') || 'claude'); } catch (e) { theme('claude'); }
  fetch('/api/prefs', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) { if (d && d.mltheme && d.mltheme.id) theme(d.mltheme.id); }).catch(function () { });

  /* ── block + effect catalogues ── */
  var PAL = ['bg', 'paper', 'accent', 'hot', 'ink'];
  var BLOCKS = {
    Words: { N: 8, ic: 'type', d: 'Kinetic type: one word per beat. punch3d, slam, stack, pair, split, cut.', def: function (k) { return { charge: true, shots: [{ at: k + 1, style: 'punch3d', text: 'EVERY', fx: 'punch' }, { at: k + 2, style: 'slam', text: 'BEAT', ground: 'accent' }, { at: k + 3, style: 'stack', text: ['ONE', 'IDEA.'], ground: 'paper', in: 'whipX', fx: 'none' }, { at: k + 5, style: 'split', text: ['AND THEN', 'HIT.'], in: 'whipY', fx: 'punch', big: true }] }; } },
    Strike: { N: 10, ic: 'x-circle', d: '"NO <thing>." over a mock of the thing, then the thing dies (timeline / tiles / rack).', def: function (k) { return { no: 'NO', items: [{ at: k, word: 'WAITING.', ui: { type: 'timeline', title: 'export_final_v3', tag: 'EXPORTING  4%' } }, { at: k + 3, word: 'PLUGINS.', ground: 'paper', ui: { type: 'tiles', tiles: [['ONE', '◆', 'v1.0'], ['TWO', '●', 'v2.1'], ['THREE', '▲', 'v3.2'], ['FOUR', '■', 'v1.4']] } }, { at: k + 6, word: 'SERVERS.', ui: { type: 'rack', rows: ['NODE 01', 'NODE 02', 'NODE 03'] } }] }; } },
    Graph: { N: 6, ic: 'activity', d: 'Comets draw a graph, a number lands, the camera flies through its counter.', def: function () { return { number: '0', label: 'KEYFRAMES', sub: 'DRAGGED BY HAND', ground: 'paper' }; } },
    Hero: { N: 8, ic: 'star', d: 'The name in 3D: kicker, extruded title orbits, light sweeps, sub line types.', def: function () { return { kicker: 'INTRODUCING', title: 'PRODUCT', sub: 'one line about what it does', whipOut: [0, 1150, .13] }; } },
    Prompt: { N: 19, ic: 'keyboard', d: 'A brief types itself, keywords pop, the camera dives into Enter: the drop.', def: function () { return { label: 'BRIEF.md', text: [['make it '], ['fast', 1], [', '], ['loud', 1], [' and all in code.']], unit: 'CHARS' }; } },
    Stretch: { N: 8, ic: 'expand', d: 'One word on the width axis: slam, stretch, squeeze, ghost rows, a live ruler.', def: function () { return { word: 'ELASTIC.', grounds: [[0, 'accent'], [4, 'paper'], [5, 'accent']], code: true }; } },
    Fly: { N: 11, ic: 'compass', d: 'Extruded words in depth; the camera flies through them with a banked roll.', def: function () { return { words: [['CAMERA', 'paper'], ['FLIES', 'accent'], ['THROUGH', 'paper'], ['THE TYPE.', 'accent']] }; } },
    Notes: { N: 16, ic: 'note', d: 'Three notes typed into a panel; each note\'s effect plays on the preview.', def: function () { return { preview: 'ELASTIC.', notes: [['hotter orange', 'recolor'], ['cut the intro in half', 'trim'], ['more punch', 'punch']], segments: [['INTRO', 220], ['DROP', 300], ['END', 180]] }; } },
    Counters: { N: 11, ic: 'cpu', d: 'Giant numbers on slot reels over the film\'s own source code.', def: function () { return { counters: [['1', 'WEB PAGE'], ['{lines}', 'LINES OF CODE'], ['{frames}', 'FRAMES. ALL CODE.']] }; } },
    Progress: { N: 9, ic: 'hourglass', d: 'A line renders itself, frames ride a conveyor past a render head, a bar runs to done.', def: function () { return { lines: ['RENDERED', 'ON A LAPTOP.'], cards: [['EVERY', 'bg', 'paper'], ['FRAME', 'accent', 'ink'], ['CODE', 'paper', 'ink']], ground: 'paper' }; } },
    Chain: { N: 12, ic: 'chain', d: 'Three words 2,000 px apart; the camera rides a comet from node to node.', def: function () { return { nodes: [['BRIEF', 'brief.md · 142 chars'], ['CODE', 'film.js · {lines} lines'], ['FILM.', '4K · 60 FPS', 'accent']] }; } },
    Rewind: { N: 8, ic: 'rewind', d: 'The film so far plays backwards in a tilting playback window.', def: function () { return { label: 'PLAYBACK' }; } },
    Picture: { N: 8, ic: 'image', d: 'Key art cuts in on a slash, pushes, punches in on every word, with weather.', def: function (k) { return { src: '', words: [[1, 'PICTURE'], [3, 'THIS.', 'accent']], reveal: 'slash', tint: .3, weather: 'rain' }; } },
    Logo: { N: 11, ic: 'diamond', d: 'The end card: a line, a slash, a hit; the wordmark types, tagline, slow push.', def: function () { return { wordmark: 'PRODUCT', tagline: 'One line that says what it does.', small: 'AVAILABLE NOW' }; } }
  };
  // inspector fields per block (the rest of a block's options is reachable in the JSON box)
  var F = function (k, t, o) { o = o || {}; o.key = k; o.type = t; return o; };
  var FIELDS = {
    Words: [F('charge', 'bool', { label: 'Charge-up' }), F('exit', 'json', { label: 'Exit', hint: '{"type":"zoom","at":8.1,"char":1} · collapse · flash' })],
    Strike: [F('no', 'text', { label: 'NO word' }), F('items', 'json', { label: 'Items', rows: 8 }), F('tvOff', 'bool', { label: 'TV switch-off', def: true })],
    Graph: [F('number', 'text'), F('label', 'text'), F('sub', 'text'), F('ground', 'pal'), F('portal', 'bool', { def: true })],
    Hero: [F('kicker', 'text'), F('title', 'text'), F('sub', 'text'), F('chevron', 'text'), F('landZoom', 'num', { min: 1, max: 3, step: .1 }), F('whipOut', 'json', { hint: '[dx, dy, dur, roll]' })],
    Prompt: [F('label', 'text'), F('text', 'json', { label: 'Text', hint: '[["plain "],["keyword",1],...]', rows: 5 }), F('unit', 'text'), F('doodles', 'bool')],
    Stretch: [F('word', 'text'), F('grounds', 'json', { hint: '[[beat, ground], ...]' }), F('code', 'bool')],
    Fly: [F('words', 'json', { hint: '[["WORD","paper"], ...] 3 to 5 words', rows: 5 })],
    Notes: [F('preview', 'text'), F('notes', 'json', { hint: '[[note, effect: recolor|trim|punch], ...]', rows: 4 }), F('segments', 'json', { hint: '[["INTRO", 220], ...]' }), F('tag', 'text'), F('file', 'text')],
    Counters: [F('counters', 'json', { hint: '[["{lines}","LINES OF CODE"], ...] {lines} {frames} {seconds}', rows: 4 }), F('title', 'text'), F('source', 'text')],
    Progress: [F('lines', 'json', { hint: '["LINE ONE","LINE TWO."]' }), F('cards', 'json', { hint: '[["WORD","bg","paper"], ...]', rows: 4 }), F('label', 'text'), F('doneLabel', 'text'), F('ground', 'pal')],
    Chain: [F('nodes', 'json', { hint: '[["WORD","sub line","accent"], ...]', rows: 5 })],
    Rewind: [F('label', 'text'), F('from', 'num', { label: 'From (s)', min: 0, step: .1 })],
    Picture: [F('src', 'media', { label: 'Image', kind: 'image' }), F('words', 'json', { hint: '[[beat, "WORD", "accent"], ...]' }), F('reveal', 'sel', { opts: ['slash', 'zoom'] }), F('tint', 'num', { min: 0, max: 1, step: .05 }), F('weather', 'sel', { opts: ['rain', 'snow', 'dust', 'none'] }), F('focus', 'json', { hint: '[.5, .45]' }), F('cutIns', 'json', { hint: '[[beat, scale, [fx, fy], "cue"], ...]' }), F('x', 'num'), F('y', 'num')],
    Logo: [F('wordmark', 'text'), F('tagline', 'text'), F('small', 'text'), F('width', 'num', { min: 200, max: 1800 }), F('mark', 'json', { hint: 'SVG path ids that drop in' }), F('word', 'json', { hint: 'SVG path ids that wipe on' })]
  };
  var SHOT_STYLES = ['punch3d', 'slam', 'stack', 'pair', 'split', 'cut'], SHOT_IN = ['cut', 'whipX', 'whipXr', 'whipY'], SHOT_FX = ['punch', 'hit', 'beat', 'none'];
  // OpenKatana effects: the main parameters (full parameter sets are in TOOLS\MirKinetic\engine\fx and OpenKatana's TIMELINE.md)
  var N = function (k, d, mn, mx, st) { return { k: k, t: 'num', d: d, min: mn, max: mx, step: st || 1 }; }, S = function (k, d, o) { return { k: k, t: 'sel', d: d, o: o }; },
    C = function (k, d) { return { k: k, t: 'color', d: d }; }, Pt = function (k, d) { return { k: k, t: 'point', d: d }; }, Bo = function (k, d) { return { k: k, t: 'bool', d: d }; };
  var FXS = {
    local_rgb_split: { g: 'Stylize', d: 'Chromatic aberration: red and blue move apart.', p: [S('mode', 'linear', ['linear', 'radial']), N('amount', 10, -200, 200), N('angle', 0, -360, 360), Pt('center', [.5, .5])] },
    local_motion_tile: { g: 'Stylize', d: 'The frame repeated as tiles; keyframe the centre to scroll.', p: [N('tile_width', 100, .5, 1000), N('tile_height', 100, .5, 1000), Pt('tile_center', [.5, .5]), Bo('mirror_edges', false), N('phase', 0, 0, 360)] },
    local_find_edges: { g: 'Stylize', d: 'A pencil drawing of the edges.', p: [Bo('invert', false), N('blend_with_original', 0, 0, 1, .05)] },
    local_emboss: { g: 'Stylize', d: 'Relief lit from one direction.', p: [N('direction', 45, 0, 360), N('relief', 1, 0, 200), N('contrast', 100, 0, 1000), N('blend_with_original', 0, 0, 1, .05)] },
    local_mosaic: { g: 'Stylize', d: 'Pixelate; keyframe the block counts for a pixelate-in.', p: [N('horizontal_blocks', 10, 1, 800), N('vertical_blocks', 10, 1, 800), Bo('sharp_colors', false)] },
    local_scatter: { g: 'Stylize', d: 'Every pixel scattered up to a distance.', p: [N('scatter_amount', 20, 0, 1000), S('grain', 'both', ['both', 'horizontal', 'vertical']), Bo('randomize_every_frame', false)] },
    local_halftone: { g: 'Stylize', d: 'Dark dots on paper.', p: [N('spacing', 8, 2, 60), N('mix', 1, 0, 1, .05), C('ink', '#16181e'), C('paper', '#f4efdf')] },
    local_posterize: { g: 'Stylize', d: 'Colour levels per channel.', p: [N('levels', 4, 2, 32)] },
    local_selective_color: { g: 'Stylize', d: 'Keep one hue, the rest goes grey.', p: [N('hue', 30, 0, 360), N('tolerance', 25, 0, 180), N('soft', 5, 0, 60)] },
    local_speed_lines: { g: 'Stylize', d: 'Radial manga speed lines.', p: [N('count', 48, 4, 300), N('opacity', .5, 0, 1, .05), N('inner', .55, 0, 1, .05), N('width', 1.5, .5, 8, .5), C('color', '#ffffff')] },
    local_frame_slices: { g: 'Stylize', d: 'Horizontal bands shifted sideways.', p: [N('amount', .1, 0, 1, .01), N('n', 9, 2, 40), Bo('continuous', true), N('d', .15, .02, 2, .01)] },
    local_paper_frame: { g: 'Stylize', d: 'Torn paper edge or a film strip.', p: [S('mode', 'paper', ['paper', 'filmstrip']), C('color', '#f2ece0'), N('margin', .045, 0, .2, .005)] },
    local_whip: { g: 'Motion', d: 'Echo smear in one direction from its start.', p: [N('amount', .3, 0, 1.5, .05), N('d', .3, .05, 2, .05), N('at', 0, 0, 60, .05), S('dir', 'right', ['right', 'left', 'up', 'down'])] },
    local_zoom_blur: { g: 'Motion', d: 'Radial smear fading from its start.', p: [N('amount', .3, 0, 1.5, .05), N('d', .3, .05, 2, .05), N('at', 0, 0, 60, .05), Pt('center', [.5, .5])] },
    local_gaussian_blur: { g: 'Blur', d: 'Soft blur; keyframe blurriness for a blur-in.', p: [N('blurriness', 20, 0, 400), S('dimensions', 'both', ['both', 'horizontal', 'vertical'])] },
    local_directional_blur: { g: 'Blur', d: 'Smear along one direction.', p: [N('direction', 90, 0, 360), N('blur_length', 30, 0, 600)] },
    local_radial_blur: { g: 'Blur', d: 'Spin or zoom blur round a centre.', p: [S('type', 'zoom', ['zoom', 'spin']), N('amount', 10, 0, 100), Pt('center', [.5, .5]), S('quality', 'low', ['low', 'high'])] },
    local_camera_lens_blur: { g: 'Blur', d: 'Lens bokeh with an iris shape.', p: [N('blur_radius', 20, 0, 200), S('iris_shape', 'hexagon', ['triangle', 'square', 'pentagon', 'hexagon', 'octagon']), N('highlight_gain', 0, 0, 100)] },
    local_unsharp_mask: { g: 'Blur', d: 'Sharpen.', p: [N('amount', 50, 0, 500), N('radius', 1, 0, 50, .5), N('threshold', 0, 0, 255)] },
    local_channel_blur: { g: 'Blur', d: 'Blur each colour channel on its own.', p: [N('red_blurriness', 0, 0, 400), N('green_blurriness', 0, 0, 400), N('blue_blurriness', 20, 0, 400)] },
    local_tilt_shift: { g: 'Blur', d: 'The miniature look: a sharp band, blur beyond it.', p: [N('center', .5, 0, 1, .02), N('angle', 0, -90, 90), N('band', .25, 0, 1, .02), N('blur_radius', 30, 0, 200), N('saturation', 1.3, 0, 4, .1)] },
    local_wave_warp: { g: 'Distort', d: 'Waves travelling across the frame.', p: [S('wave_type', 'sine', ['sine', 'square', 'triangle', 'sawtooth', 'circle', 'noise', 'smooth_noise']), N('wave_height', 10, 0, 300), N('wave_width', 40, 2, 1000), N('direction', 90, 0, 360), N('wave_speed', 1, -10, 10, .1), S('pinning', 'none', ['none', 'all', 'center', 'horizontal', 'vertical'])] },
    local_ripple: { g: 'Distort', d: 'Circular ripples from a centre.', p: [Pt('center', [.5, .5]), N('radius', .5, 0, 2, .05), N('wavelength', 40, 2, 600), N('amplitude', 20, 0, 300), N('wave_speed', 1, -10, 10, .1)] },
    local_shockwave: { g: 'Distort', d: 'A beat-drop ring pushing the picture outward.', p: [Pt('center', [.5, .5]), N('at', 0, 0, 60, .05), N('d', .6, .05, 4, .05), N('max_radius', .6, .05, 2, .05), N('width', 80, 2, 800), N('amount', 40, -300, 300), N('split', 0, 0, 60)] },
    local_twirl: { g: 'Distort', d: 'Turn the picture round a centre.', p: [N('angle', 50, -720, 720), N('radius', .3, 0, 1, .02), Pt('center', [.5, .5])] },
    local_bulge: { g: 'Distort', d: 'Magnify or pinch an ellipse.', p: [Pt('center', [.5, .5]), N('horizontal_radius', 300, 10, 2000), N('vertical_radius', 300, 10, 2000), N('height', 1, -4, 4, .1), N('taper', 0, 0, 1, .05)] },
    local_polar: { g: 'Distort', d: 'Polar coordinates.', p: [S('conversion', 'rect_to_polar', ['rect_to_polar', 'polar_to_rect']), N('interpolation', 1, 0, 1, .05)] },
    local_kaleidoscope: { g: 'Distort', d: 'Fold the picture into wedges.', p: [Pt('center', [.5, .5]), N('segments', 6, 2, 32), N('rotation', 0, -360, 360), N('size', 360, 20, 2000), S('mirroring', 'on', ['on', 'off'])] },
    local_mirror: { g: 'Distort', d: 'Reflect across a line.', p: [Pt('reflection_center', [.5, .5]), N('reflection_angle', 0, -180, 180)] },
    local_turbulent_displace: { g: 'Distort', d: 'Noise warps: turbulent, bulge, twist.', p: [S('displacement', 'turbulent', ['turbulent', 'bulge', 'twist', 'turbulent_smoother', 'horizontal', 'vertical', 'cross']), N('amount', 20, 0, 400), N('size', 100, 5, 1000), N('complexity', 1, 1, 10, .5), N('speed', .5, 0, 10, .1), S('pin', 'all', ['all', 'none', 'horizontal', 'vertical'])] },
    local_deep_glow: { g: 'Light', d: 'A deep layered glow on the bright parts.', p: [N('threshold', .6, 0, 1, .02), N('radius', 120, 2, 600), N('exposure', 1, 0, 20, .1), N('layers', 6, 2, 8), N('saturation', 1, 0, 4, .1), S('blend', 'add', ['add', 'screen'])] },
    local_lens_flare: { g: 'Light', d: 'A lens flare drawn with gradients.', p: [Pt('position', [.3, .3]), N('brightness', 1, 0, 3, .05), S('lens', '50_300mm_zoom', ['50_300mm_zoom', '35mm_prime', '105mm_prime']), N('streak', 0, 0, 1, .05), N('flicker', 0, 0, 1, .05)] },
    local_light_rays: { g: 'Light', d: 'Volumetric rays from a centre.', p: [Pt('center', [.5, .5]), N('intensity', 1, 0, 10, .1), N('length', .4, 0, 1, .02), N('threshold', .5, 0, 1, .02), S('blend', 'add', ['add', 'screen'])] },
    local_light_sweep: { g: 'Light', d: 'A shine passing over the frame.', p: [N('angle', 30, -90, 90), N('width', 80, 2, 800), N('softness', .5, 0, 1, .05), N('intensity', 1, 0, 10, .1), C('color', '#ffffff'), N('d', 1, .1, 10, .1), N('at', 0, 0, 60, .05), S('reception', 'add', ['add', 'luma'])] },
    local_fractal_noise: { g: 'Generate', d: 'Noise texture, smoke, light leaks (over the frame).', p: [S('fractal_type', 'basic', ['basic', 'turbulent_smooth', 'turbulent_sharp']), N('scale', 100, 5, 1000), N('complexity', 6, 1, 20), N('speed', .3, 0, 10, .1), N('contrast', 100, 0, 400), N('brightness', 0, -100, 100), S('blend', 'screen', ['normal', 'screen', 'add', 'multiply', 'overlay']), N('opacity', .5, 0, 1, .05)] },
    local_cell_pattern: { g: 'Generate', d: 'Bubbles, crystals, plates, tubes.', p: [S('cell_pattern', 'bubbles', ['bubbles', 'crystals', 'plates', 'tubular']), N('size', 60, 4, 600), N('disperse', 1, 0, 1, .05), N('speed', .2, 0, 10, .1), S('blend', 'screen', ['normal', 'screen', 'add', 'multiply', 'overlay']), N('opacity', .4, 0, 1, .05)] },
    local_gradient_ramp: { g: 'Generate', d: 'A two-colour gradient over the frame.', p: [Pt('start', [.5, 0]), C('start_color', '#000000'), Pt('end', [.5, 1]), C('end_color', '#ffffff'), S('shape', 'linear', ['linear', 'radial']), S('blend', 'multiply', ['normal', 'screen', 'add', 'multiply', 'overlay']), N('opacity', .5, 0, 1, .05)] },
    local_four_color_gradient: { g: 'Generate', d: 'Four colours at four points.', p: [C('color_1', '#ffd34d'), C('color_2', '#3dd68c'), C('color_3', '#ff4fa3'), C('color_4', '#3d7bff'), N('blend_amount', 100, 1, 1000), S('blend', 'overlay', ['normal', 'screen', 'add', 'multiply', 'overlay']), N('opacity', .4, 0, 1, .05)] },
    local_grid: { g: 'Generate', d: 'A grid of lines.', p: [N('width', 100, 4, 1000), N('height', 100, 4, 1000), N('border', 3, 1, 60), N('feather', 0, 0, 60), C('color', '#ffffff'), Bo('invert', false), N('opacity', .3, 0, 1, .05)] },
    local_radio_waves: { g: 'Generate', d: 'Rings born at a point, growing and fading.', p: [Pt('producer', [.5, .5]), N('frequency', 1, .1, 20, .1), N('expansion', 200, 10, 3000), N('lifespan', 3, .1, 20, .1), S('shape', 'circle', ['circle', 'square', 'polygon']), C('stroke_color', '#ffffff'), N('start_width', 5, 1, 60), N('end_width', 5, 0, 60), N('opacity', .7, 0, 1, .05)] },
    local_lightning: { g: 'Generate', d: 'A fractal lightning bolt.', p: [Pt('origin', [.3, .2]), Pt('direction', [.7, .8]), S('lightning_type', 'strike', ['strike', 'breaking', 'bouncy', 'omni', 'anywhere']), N('core_radius', 3, 1, 30), C('core_color', '#ffffff'), N('glow_radius', 50, 0, 400), C('glow_color', '#4a6cff'), N('forking', .25, 0, 1, .05), N('flicker', 2, 0, 30)] },
    local_curve: { g: 'Motion', d: 'Scale / offset / blur / glow curves from the start (arrays per frame).', p: [N('glow', 0, 0, 4, .1), N('exposure', 1, 0, 3, .05)] }
  };

  /* ── state ── */
  var P = blank(), sel = null, t = 0, playing = false, DUR = 0, hist = [], fut = [], dirty = false, snap = true, loop = false, fxprev = true;
  var HEALTH = null, FONTS = [], LIB = { image: [], audio: [], video: [] }, ready = false, frameOK = false, infoCues = 0;
  var zoom = +localStorage.getItem('kn.zoom') || 28;    // px per beat
  var SESSION = Q.get('session') != null ? Q.get('session') : (function () { try { return localStorage.getItem('mml.session') || ''; } catch (e) { return ''; } })();
  var B = function (k) { return k * 60 / P.bpm; }, K = function (s) { return s * P.bpm / 60; };
  function blank() {
    return { id: '', name: 'Untitled film', w: 1920, h: 1080, fps: 60, bpm: 120, beats: 32, palette: { bg: '#08080A', paper: '#F2F6FA', accent: '#FFB547', hot: '#FF8A1F', ink: '#0B0B0D' },
      font: '', hud: 'MIR  ·  LAUNCH', hudOut: null, logo: '', music: null, sounds: {}, kit: {}, cues: [], scenes: [], captions: [], fx: [], session: SESSION };
  }
  var clone = function (o) { return JSON.parse(JSON.stringify(o)); };
  function snapK(k) { return snap ? Math.round(k * 2) / 2 : Math.round(k * 100) / 100; }
  function scene(id) { for (var i = 0; i < P.scenes.length; i++) if (P.scenes[i].id === id) return P.scenes[i]; }
  function fxOf(id) { for (var i = 0; i < P.fx.length; i++) if (P.fx[i].id === id) return P.fx[i]; }
  function selected() { if (!sel) return null; if (sel.type === 'scene') return scene(sel.id); if (sel.type === 'fx') return fxOf(sel.id); if (sel.type === 'cap') return P.captions[sel.i]; return null; }

  /* ── history + save ── */
  function push() { hist.push(JSON.stringify(P)); if (hist.length > 80) hist.shift(); fut = []; }
  function changed(rebuild, keepHist) {
    if (!keepHist) push();
    dirty = true; $('#kn-save').textContent = 'unsaved';
    P.scenes.sort(function (a, b) { return a.k0 - b.k0; });
    DUR = B(P.beats);
    renderTL(); renderInsp();
    if (rebuild !== false) load();
    clearTimeout(changed._); changed._ = setTimeout(save, 1500);
  }
  function undo() { if (!hist.length) return; fut.push(JSON.stringify(P)); P = JSON.parse(hist.pop()); sel = null; changed(true, true); }
  function redo() { if (!fut.length) return; hist.push(JSON.stringify(P)); P = JSON.parse(fut.pop()); sel = null; changed(true, true); }
  function save() {
    if (!dirty) return;
    P.name = $('#kn-name').value.trim() || 'Untitled film'; P.session = SESSION;
    return fetch(API + 'project', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(P) }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.id) { P.id = d.id; dirty = false; $('#kn-save').textContent = 'saved'; history.replaceState(null, '', location.pathname + '?p=' + d.id + (SESSION ? '&session=' + encodeURIComponent(SESSION) : '')); }
      else $('#kn-save').textContent = d.error || 'save failed';
    }).catch(function () { $('#kn-save').textContent = 'offline'; });
  }

  /* ── the preview iframe ── */
  var frame = $('#kn-frame');
  function post(m) { try { frame.contentWindow.postMessage(m, '*'); } catch (e) { } }
  function load() { clearTimeout(load._); load._ = setTimeout(function () { if (frameOK) post({ type: 'load', project: P }); }, 120); }
  addEventListener('message', function (e) {
    var m = e.data || {};
    if (m.src !== 'kinetic') return;
    if (m.type === 'hello') { frameOK = true; post({ type: 'load', project: P }); }
    else if (m.type === 'ready') { ready = true; DUR = m.info.dur; infoCues = (m.info.cues || []).length; seek(Math.min(t, DUR), true); fxStill(); }
    else if (m.type === 'error') toast('film: ' + m.msg, 5000);
    else if (m.type === 'time') { t = m.t; tick(); }
  });
  // the lab's library side panel: a click or drop → the same as picking it in the media bin
  addEventListener('message', function (e) {
    var m = e.data || {};
    if (m.mml !== 'motion-add' || !m.src) return;
    var n = String(m.src).replace(/^lib:/, ''), kind = /\.(mp4|webm|mov|m4v|mkv)$/i.test(n) ? 'video' : /\.(mp3|wav|flac|ogg|m4a|aac)$/i.test(n) ? 'audio' : 'image';
    if (kind === 'image') { if (/\.svg$/i.test(n)) { P.logo = 'lib:' + n; changed(); toast('logo set'); } else { var o = BLOCKS.Picture.def(); o.src = 'lib:' + n; addBlock('Picture', o); toast('Picture block added'); } }
    else if (kind === 'audio') { P.music = { src: 'lib:' + n, offset: 0, stopBeat: null, gain: -3.5 }; sel = { type: 'film' }; changed(); toast('music set — measure it in Film to lock the tempo'); }
    else toast('video goes in a Picture block as a still for now');
  });
  function fit() {
    var w = $('#kn-stage').clientWidth - 24, h = $('#kn-stage').clientHeight - 24, s = Math.min(w / 1920, h / 1080);
    frame.style.transform = 'translate(-50%,-50%) scale(' + s + ')'; $('#kn-fxstill').style.transform = frame.style.transform;
  }
  new ResizeObserver(fit).observe($('#kn-stage')); fit();
  function tick() {
    $('#kn-tc').textContent = t.toFixed(2) + ' s · beat ' + K(t).toFixed(1) + ' / ' + P.beats;
    $('#kn-ph').style.left = (K(t) * zoom) + 'px';
    if (playing) { var sc = $('#kn-scroll'), x = K(t) * zoom; if (x < sc.scrollLeft || x > sc.scrollLeft + sc.clientWidth - 40) sc.scrollLeft = Math.max(0, x - 80); }
  }
  function seek(s, quiet) { t = Math.max(0, Math.min(DUR || B(P.beats), s)); post({ type: 'seek', t: t }); tick(); if (!quiet) fxStill(); }
  function play(on) {
    playing = on == null ? !playing : on;
    if (playing) { if (t >= DUR - .02) t = 0; post({ type: 'play', t: t }); hideStill(); } else { post({ type: 'pause' }); fxStill(); }
    $('#kn-play').innerHTML = ic(playing ? 'pause' : 'play'); icons($('#kn-play'));
  }
  // effects can only be seen on real pixels: when paused, a still of this frame is rendered on the PC and laid over the preview
  var stillImg = $('#kn-fxstill');
  function hideStill() { stillImg.hidden = true; $('#kn-fxbadge').hidden = true; }
  function fxActive(tt) { return P.fx.some(function (f) { return tt >= B(f.k0) && tt < B(f.k1); }); }
  function fxStill() {
    hideStill(); clearTimeout(fxStill._);
    if (!fxprev || playing || !HEALTH || !HEALTH.ok || !fxActive(t) || !P.scenes.length) return;
    var at = t, body = JSON.stringify({ project: P, frame: Math.round(t * P.fps), scale: .6 });
    fxStill._ = setTimeout(function () {
      $('#kn-fxbadge').hidden = false; $('#kn-fxbadge').textContent = 'rendering FX preview…';
      fetch(API + 'still', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body }).then(function (r) { return r.ok ? r.blob() : null; }).then(function (b) {
        if (!b || playing || Math.abs(at - t) > 1e-6) { if (!b) hideStill(); return; }
        stillImg.src = URL.createObjectURL(b); stillImg.hidden = false; $('#kn-fxbadge').textContent = 'FX preview';
      }).catch(hideStill);
    }, 500);
  }

  /* ── timeline ── */
  var TL = $('#kn-scroll');
  function renderTL() {
    var beats = P.beats, W = beats * zoom + 200;
    TL.style.setProperty('--bw', zoom + 'px');
    var r = $('#kn-ruler'); r.style.width = W + 'px'; var h = '';
    var every = zoom >= 24 ? 1 : zoom >= 12 ? 2 : 4;
    for (var k = 0; k <= beats; k += every) h += '<i class="' + (k % 4 === 0 ? 'bar' : '') + '" style="left:' + (k * zoom) + 'px"></i>' + (k % 4 === 0 ? '<b style="left:' + (k * zoom) + 'px">' + k + '</b>' : '');
    r.innerHTML = h;
    $$('.kn-lane').forEach(function (l) { l.style.width = W + 'px'; });
    var sc = '';
    P.scenes.forEach(function (s) {
      var shots = (s.block === 'Words' ? (s.opts.shots || []).map(function (x) { return x.at; }) : s.block === 'Strike' ? (s.opts.items || []).map(function (x) { return x.at; }) : []);
      sc += '<div class="kn-clip scene' + (sel && sel.type === 'scene' && sel.id === s.id ? ' sel' : '') + '" data-id="' + s.id + '" style="left:' + (s.k0 * zoom) + 'px;width:' + ((s.k1 - s.k0) * zoom - 2) + 'px"><i class="h l"></i><b>' + s.block + '</b><span>' + esc(label(s)) + '</span>' +
        shots.map(function (a) { return '<i class="shot" style="left:' + ((a - s.k0) * zoom) + 'px"></i>'; }).join('') + '<i class="h r"></i></div>';
    });
    $('#kn-lane-scenes').innerHTML = sc;
    $('#kn-lane-fx').innerHTML = P.fx.map(function (f) {
      return '<div class="kn-clip fx' + (sel && sel.type === 'fx' && sel.id === f.id ? ' sel' : '') + '" data-id="' + f.id + '" style="left:' + (f.k0 * zoom) + 'px;width:' + ((f.k1 - f.k0) * zoom - 2) + 'px"><i class="h l"></i><span>' + f.type.replace('local_', '').replace(/_/g, ' ') + '</span><i class="h r"></i></div>';
    }).join('');
    $('#kn-lane-cap').innerHTML = P.captions.map(function (c, i) {
      return '<div class="kn-clip cap' + (sel && sel.type === 'cap' && sel.i === i ? ' sel' : '') + '" data-i="' + i + '" style="left:' + (c[0] * zoom) + 'px;width:' + ((c[1] - c[0]) * zoom - 2) + 'px"><i class="h l"></i><span>' + esc(c[2].map(function (w) { return w[0]; }).join(' ')) + '</span><i class="h r"></i></div>';
    }).join('');
    var m = P.music;
    $('#kn-lane-music').innerHTML = m ? '<div class="kn-clip music" style="left:0;width:' + ((m.stopBeat || beats) * zoom - 2) + 'px"><b>' + ic('music') + '</b><span>' + esc(m.src.slice(4)) + ' · offset ' + (+m.offset || 0).toFixed(2) + ' s' + (m.stopBeat ? ' · stops at beat ' + m.stopBeat : '') + '</span></div>'
      : '<div class="kn-clip music" style="left:0;width:' + (beats * zoom - 2) + 'px;opacity:.55"><span>no music — pick a track in Library, or Film → Music</span></div>';
    icons($('#kn-lane-music'));
    tick();
  }
  function label(s) {
    var o = s.opts || {};
    if (s.block === 'Words') return (o.shots || []).map(function (x) { return Array.isArray(x.text) ? x.text.join(' ') : x.text; }).join(' · ');
    if (s.block === 'Strike') return (o.items || []).map(function (x) { return x.word; }).join(' · ');
    return o.title || o.word || o.wordmark || o.label || o.number || (o.words ? o.words.map(function (w) { return w[0] || w[1]; }).join(' ') : '') || '';
  }
  // drag: move or resize a clip in beats, scenes clamped to their neighbours (blocks never overlap)
  TL.addEventListener('pointerdown', function (e) {
    if (e.target.closest('.kn-ruler')) { seekAt(e); var mv = function (ev) { seekAt(ev); }; var up = function () { removeEventListener('pointermove', mv); removeEventListener('pointerup', up); fxStill(); }; addEventListener('pointermove', mv); addEventListener('pointerup', up); return; }
    var el = e.target.closest('.kn-clip'); if (!el) { if (e.target.closest('.kn-lane')) { sel = null; renderTL(); renderInsp(); seekAt(e); } return; }
    if (el.classList.contains('music')) { sel = { type: 'film' }; renderInsp(); return; }
    var kind = el.classList.contains('scene') ? 'scene' : el.classList.contains('fx') ? 'fx' : 'cap';
    var item = kind === 'cap' ? P.captions[+el.dataset.i] : kind === 'scene' ? scene(el.dataset.id) : fxOf(el.dataset.id);
    sel = kind === 'cap' ? { type: 'cap', i: +el.dataset.i } : { type: kind, id: el.dataset.id };
    renderTL(); renderInsp();
    var mode = e.target.classList.contains('h') ? (e.target.classList.contains('l') ? 'l' : 'r') : 'move';
    var x0 = e.clientX, k0 = kind === 'cap' ? item[0] : item.k0, k1 = kind === 'cap' ? item[1] : item.k1, moved = false, snap0 = JSON.stringify(P);
    var lo = 0, hi = P.beats;
    if (kind === 'scene') { var i = P.scenes.indexOf(item); if (i > 0) lo = P.scenes[i - 1].k1; if (i < P.scenes.length - 1) hi = P.scenes[i + 1].k0; }
    var mv = function (ev) {
      var dk = (ev.clientX - x0) / zoom; if (Math.abs(ev.clientX - x0) < 3 && !moved) return; moved = true;
      var a = k0, b = k1;
      if (mode === 'move') { var len = k1 - k0; a = snapK(k0 + dk); a = Math.max(lo, Math.min(hi - len, a)); b = a + len; }
      else if (mode === 'l') { a = Math.max(lo, Math.min(k1 - .5, snapK(k0 + dk))); }
      else { b = Math.min(hi, Math.max(k0 + .5, snapK(k1 + dk))); }
      if (kind === 'cap') { item[0] = a; item[1] = b; } else { if (kind === 'scene' && mode === 'move') shiftScene(item, a - item.k0); item.k0 = a; item.k1 = b; }
      renderTL(); renderInsp();
    };
    var up = function () { removeEventListener('pointermove', mv); removeEventListener('pointerup', up); if (moved) { hist.push(snap0); fut = []; changed(true, true); } };
    addEventListener('pointermove', mv); addEventListener('pointerup', up);
  });
  function seekAt(e) { var r = $('#kn-ruler').getBoundingClientRect(); var k = Math.max(0, (e.clientX - r.left) / zoom); if (playing) play(false); seek(B(snap ? Math.round(k * 4) / 4 : k), true); }
  function shiftScene(s, dk) {   // Words shots and Strike items are timed in absolute beats
    if (!dk) return;
    if (s.block === 'Words') { (s.opts.shots || []).forEach(function (x) { x.at = Math.round((x.at + dk) * 100) / 100; }); if (s.opts.exit && s.opts.exit.at != null) s.opts.exit.at = Math.round((s.opts.exit.at + dk) * 100) / 100; }
    if (s.block === 'Strike') (s.opts.items || []).forEach(function (x) { x.at = Math.round((x.at + dk) * 100) / 100; });
  }
  // add a block at the playhead: it takes the free span there (up to its nominal length), or goes after the last block
  function addBlock(name, opts) {
    var N_ = BLOCKS[name].N, k = snapK(K(t)), free = null;
    for (var i = 0; i <= P.scenes.length; i++) {
      var a = i === 0 ? 0 : P.scenes[i - 1].k1, b = i === P.scenes.length ? P.beats : P.scenes[i].k0;
      if (k >= a && k < b && b - k >= 2) { free = [k, Math.min(b, k + N_)]; break; }
    }
    if (!free) { var last = P.scenes.length ? P.scenes[P.scenes.length - 1].k1 : 0; if (last + 2 > P.beats) P.beats = Math.ceil(last + N_); free = [last, Math.min(P.beats, last + N_)]; }
    var s = { id: uid(), block: name, k0: free[0], k1: free[1], opts: opts || BLOCKS[name].def(free[0]) };
    P.scenes.push(s); sel = { type: 'scene', id: s.id }; changed(); seek(B(s.k0)); return s;
  }
  function addFx(type) {
    var k = snapK(K(t)), f = { id: uid(), type: type, k0: k, k1: Math.min(P.beats, k + 4), params: {} };
    (FXS[type] ? FXS[type].p : []).forEach(function (p) { if (p.d != null && p.k !== 'at') f.params[p.k] = clone(p.d); });
    P.fx.push(f); sel = { type: 'fx', id: f.id }; changed(); fxStill();
  }
  function del() {
    if (!sel || sel.type === 'film') return;
    if (sel.type === 'scene') P.scenes = P.scenes.filter(function (s) { return s.id !== sel.id; });
    else if (sel.type === 'fx') P.fx = P.fx.filter(function (f) { return f.id !== sel.id; });
    else if (sel.type === 'cap') P.captions.splice(sel.i, 1);
    sel = null; changed();
  }
  function dup() {
    var it = selected(); if (!it || sel.type === 'film') return;
    if (sel.type === 'scene') { var len = it.k1 - it.k0, c = clone(it); c.id = uid(); var i = P.scenes.indexOf(it), next = i < P.scenes.length - 1 ? P.scenes[i + 1].k0 : P.beats; if (next - it.k1 < len) { P.beats = Math.ceil(it.k1 + len); next = P.beats; } shiftScene(c, it.k1 - it.k0); c.k0 = it.k1; c.k1 = it.k1 + len; P.scenes.splice(i + 1, 0, c); sel = { type: 'scene', id: c.id }; }
    else if (sel.type === 'fx') { var c2 = clone(it); c2.id = uid(); c2.k0 = it.k1; c2.k1 = Math.min(P.beats, it.k1 + (it.k1 - it.k0)); P.fx.push(c2); sel = { type: 'fx', id: c2.id }; }
    else { var c3 = clone(it), d = it[1] - it[0]; c3[0] += d; c3[1] += d; c3[2].forEach(function (w) { w[1] += d; }); P.captions.push(c3); sel = { type: 'cap', i: P.captions.length - 1 }; }
    changed();
  }

  /* ── inspector ── */
  var INS = $('#kn-insp');
  function field(f, v, pre) {
    var id = 'f_' + pre + '_' + f.key, lab = esc(f.label || f.key), hint = f.hint ? '<div class="kn-note">' + esc(f.hint) + '</div>' : '';
    if (f.type === 'text') return '<div class="kn-f"><label>' + lab + '</label><input data-k="' + f.key + '" data-t="text" value="' + esc(v == null ? '' : v) + '"></div>';
    if (f.type === 'num') return '<div class="kn-f"><label>' + lab + '</label><input type="number" data-k="' + f.key + '" data-t="num" value="' + (v == null ? '' : v) + '"' + (f.min != null ? ' min="' + f.min + '"' : '') + (f.max != null ? ' max="' + f.max + '"' : '') + ' step="' + (f.step || 1) + '"></div>';
    if (f.type === 'bool') return '<div class="kn-f"><label>' + lab + '</label><input type="checkbox" data-k="' + f.key + '" data-t="bool"' + ((v == null ? f.def : v) ? ' checked' : '') + '></div>';
    if (f.type === 'pal') return '<div class="kn-f"><label>' + lab + '</label><select data-k="' + f.key + '" data-t="text"><option value="">default</option>' + PAL.map(function (p) { return '<option' + (v === p ? ' selected' : '') + '>' + p + '</option>'; }).join('') + '</select></div>';
    if (f.type === 'sel') return '<div class="kn-f"><label>' + lab + '</label><select data-k="' + f.key + '" data-t="text">' + f.opts.map(function (p) { return '<option value="' + p + '"' + ((v == null ? 'none' : v) === p ? ' selected' : '') + '>' + p + '</option>'; }).join('') + '</select></div>';
    if (f.type === 'media') return '<div class="kn-f"><label>' + lab + '</label><select data-k="' + f.key + '" data-t="text"><option value="">— pick from the library —</option>' + (LIB[f.kind] || []).map(function (m) { return '<option value="lib:' + esc(m.name) + '"' + (v === 'lib:' + m.name ? ' selected' : '') + '>' + esc(m.name) + '</option>'; }).join('') + '</select></div>';
    return '<div class="kn-f"><label>' + lab + '</label><textarea data-k="' + f.key + '" data-t="json" rows="' + (f.rows || 3) + '">' + esc(v == null ? '' : JSON.stringify(v)) + '</textarea></div>' + hint;
  }
  function renderInsp() {
    var it = selected(), h = '';
    if (sel && sel.type === 'film') return renderFilm();
    if (!it) { INS.innerHTML = '<div class="pad"><div class="dim">Select a block, effect or caption — or add one from the left.</div><h3>Film</h3><button class="eb wide" data-a="film">' + ic('palette') + ' Palette, font, HUD, logo, music</button><div class="kn-note" style="margin-top:10px">' + P.scenes.length + ' blocks · ' + P.fx.length + ' effects · ' + P.beats + ' beats at ' + P.bpm + ' BPM = ' + B(P.beats).toFixed(1) + ' s · ' + infoCues + ' sound cues</div></div>'; icons(INS); return; }
    if (sel.type === 'scene') {
      var bd = BLOCKS[it.block];
      h += '<div class="pad"><h3>' + it.block + ' block</h3><div class="kn-note">' + esc(bd.d) + (bd.N ? ' Nominal length ' + bd.N + ' beats (it scales its timing to the span you give it).' : '') + '</div>';
      h += '<div class="kn-f"><label>Beats</label><div class="pair"><input type="number" step="0.5" data-k="k0" data-t="span" value="' + it.k0 + '"><input type="number" step="0.5" data-k="k1" data-t="span" value="' + it.k1 + '"></div></div>';
      h += '<div class="kn-f"><label>Whip in</label><input data-k="whipIn" data-t="json" value="' + esc(it.opts.whipIn ? JSON.stringify(it.opts.whipIn) : '') + '" placeholder="[dx, dy, dur, roll] e.g. [1150,0,.13]"></div>';
      h += '<div class="kn-f"><label>Whip out</label><input data-k="whipOut" data-t="json" value="' + esc(it.opts.whipOut ? JSON.stringify(it.opts.whipOut) : '') + '" placeholder="[0, 1150, .13]"></div>';
      (FIELDS[it.block] || []).forEach(function (f) { h += field(f, it.opts[f.key], 's'); });
      if (it.block === 'Words') {
        h += '<h3>Shots <button class="eb sm" data-a="addshot" style="float:right">' + ic('plus') + ' shot</button></h3>';
        (it.opts.shots || []).forEach(function (s, i) {
          var txt = Array.isArray(s.text) ? s.text.join(' | ') : (s.text || '');
          h += '<div class="kn-shot" data-i="' + i + '"><div class="hd"><span>shot ' + (i + 1) + '</span><button data-a="delshot" data-i="' + i + '" title="remove">' + ic('x-circle') + '</button></div>' +
            '<div class="kn-f"><label>Beat</label><input type="number" step="0.5" data-sk="at" data-i="' + i + '" value="' + s.at + '"></div>' +
            '<div class="kn-f"><label>Text</label><input data-sk="text" data-i="' + i + '" value="' + esc(txt) + '" placeholder="WORD  (two lines: A | B)"></div>' +
            '<div class="kn-f"><label>Style</label><select data-sk="style" data-i="' + i + '">' + SHOT_STYLES.map(function (x) { return '<option' + (s.style === x ? ' selected' : '') + '>' + x + '</option>'; }).join('') + '</select></div>' +
            '<div class="kn-f"><label>Ground</label><select data-sk="ground" data-i="' + i + '"><option value="">—</option>' + PAL.map(function (x) { return '<option' + (s.ground === x ? ' selected' : '') + '>' + x + '</option>'; }).join('') + '</select></div>' +
            '<div class="kn-f"><label>Colour</label><select data-sk="color" data-i="' + i + '"><option value="">auto</option>' + PAL.map(function (x) { return '<option' + (s.color === x ? ' selected' : '') + '>' + x + '</option>'; }).join('') + '</select></div>' +
            '<div class="kn-f"><label>In</label><select data-sk="in" data-i="' + i + '">' + SHOT_IN.map(function (x) { return '<option' + ((s.in || 'cut') === x ? ' selected' : '') + '>' + x + '</option>'; }).join('') + '</select></div>' +
            '<div class="kn-f"><label>FX</label><select data-sk="fx" data-i="' + i + '">' + SHOT_FX.map(function (x) { return '<option' + ((s.fx || 'punch') === x ? ' selected' : '') + '>' + x + '</option>'; }).join('') + '</select></div>' +
            '<div class="kn-f"><label>Size / rot</label><div class="pair"><input type="number" data-sk="size" data-i="' + i + '" value="' + (s.size == null ? '' : s.size) + '" placeholder="px"><input type="number" data-sk="rot" data-i="' + i + '" value="' + (s.rot == null ? '' : s.rot) + '" placeholder="°"></div></div>' +
            '<div class="kn-f"><label>Big hit</label><input type="checkbox" data-sk="big" data-i="' + i + '"' + (s.big ? ' checked' : '') + '></div></div>';
        });
      }
      h += '<h3>All options (JSON)</h3><div class="kn-f" style="grid-template-columns:1fr"><textarea data-k="__opts" data-t="opts" rows="6">' + esc(JSON.stringify(it.opts, null, 1)) + '</textarea></div>';
      h += '<button class="eb wide" data-a="aiprops">' + ic('sparkle') + ' Rewrite this block with AI</button><button class="eb wide" data-a="del">' + ic('trash') + ' Delete block</button></div>';
    } else if (sel.type === 'fx') {
      var fd = FXS[it.type] || { g: '', d: '', p: [] };
      h += '<div class="pad"><h3>' + it.type.replace('local_', '').replace(/_/g, ' ') + ' <span class="dim" style="font-weight:400;letter-spacing:0;text-transform:none">· ' + fd.g + '</span></h3><div class="kn-note">' + esc(fd.d) + ' Seen on renders and on the paused frame preview.</div>';
      h += '<div class="kn-f"><label>Beats</label><div class="pair"><input type="number" step="0.5" data-k="k0" data-t="span" value="' + it.k0 + '"><input type="number" step="0.5" data-k="k1" data-t="span" value="' + it.k1 + '"></div></div>';
      fd.p.forEach(function (p) {
        var v = it.params[p.k];
        if (p.t === 'num') h += '<div class="kn-f"><label>' + p.k.replace(/_/g, ' ') + '</label><input type="number" data-pk="' + p.k + '" data-t="num" value="' + (v == null ? p.d : v) + '" min="' + p.min + '" max="' + p.max + '" step="' + p.step + '"></div>';
        else if (p.t === 'sel') h += '<div class="kn-f"><label>' + p.k.replace(/_/g, ' ') + '</label><select data-pk="' + p.k + '" data-t="text">' + p.o.map(function (o) { return '<option' + ((v == null ? p.d : v) === o ? ' selected' : '') + '>' + o + '</option>'; }).join('') + '</select></div>';
        else if (p.t === 'bool') h += '<div class="kn-f"><label>' + p.k.replace(/_/g, ' ') + '</label><input type="checkbox" data-pk="' + p.k + '" data-t="bool"' + ((v == null ? p.d : v) ? ' checked' : '') + '></div>';
        else if (p.t === 'color') h += '<div class="kn-f"><label>' + p.k.replace(/_/g, ' ') + '</label><input type="color" data-pk="' + p.k + '" data-t="text" value="' + esc(v || p.d) + '"></div>';
        else if (p.t === 'point') { var pt = Array.isArray(v) ? v : p.d; h += '<div class="kn-f"><label>' + p.k.replace(/_/g, ' ') + '</label><div class="pair"><input type="number" step="0.05" data-pk="' + p.k + '" data-t="pt0" value="' + pt[0] + '"><input type="number" step="0.05" data-pk="' + p.k + '" data-t="pt1" value="' + pt[1] + '"></div></div>'; }
      });
      h += '<h3>All parameters (JSON)</h3><div class="kn-note">Keyframes: a parameter can be [[t, value], ...] in seconds from the effect\'s start; region [x0,y0,x1,y1] confines it.</div><div class="kn-f" style="grid-template-columns:1fr"><textarea data-k="__params" data-t="params" rows="5">' + esc(JSON.stringify(it.params, null, 1)) + '</textarea></div>';
      h += '<button class="eb wide" data-a="del">' + ic('trash') + ' Remove effect</button></div>';
    } else if (sel.type === 'cap') {
      h += '<div class="pad"><h3>Caption phrase</h3><div class="kn-note">Karaoke caption, top left: each word lights on its beat.</div>';
      h += '<div class="kn-f"><label>Beats</label><div class="pair"><input type="number" step="0.5" data-k="k0" data-t="span" value="' + it[0] + '"><input type="number" step="0.5" data-k="k1" data-t="span" value="' + it[1] + '"></div></div>';
      h += '<div class="kn-f" style="grid-template-columns:1fr"><textarea data-k="__words" data-t="words" rows="6">' + esc(it[2].map(function (w) { return w[0] + ' @ ' + w[1]; }).join('\n')) + '</textarea></div><div class="kn-note">one per line: word @ beat</div>';
      h += '<button class="eb wide" data-a="del">' + ic('trash') + ' Delete phrase</button></div>';
    }
    INS.innerHTML = h; icons(INS);
  }
  function renderFilm() {
    var h = '<div class="pad"><h3>Film</h3>';
    h += '<div class="kn-pal">' + PAL.map(function (k) { return '<label>' + k + '<input type="color" data-pal="' + k + '" value="' + P.palette[k] + '"></label>'; }).join('') + '</div>';
    h += '<div class="kn-note">bg = dark ground · paper = light ground and light type · accent = the brand colour · hot = hotter accent · ink = type on light grounds. One palette rebrands the whole film.</div>';
    h += '<div class="kn-f"><label>Display font</label><select data-film="font"><option value="">Archivo (variable: width axis animates)</option>' + FONTS.map(function (f) { return '<option value="' + f.id + '"' + (P.font === f.id ? ' selected' : '') + '>' + esc(f.name) + '</option>'; }).join('') + '</select></div>';
    h += '<div class="kn-f"><label>HUD label</label><input data-film="hud" value="' + esc(P.hud === false ? '' : P.hud) + '" placeholder="empty = no HUD"></div>';
    h += '<div class="kn-f"><label>HUD out</label><div class="pair"><input type="number" data-film="hudOut0" value="' + (P.hudOut ? P.hudOut[0] : '') + '" placeholder="beat"><input type="number" data-film="hudOut1" value="' + (P.hudOut ? P.hudOut[1] : '') + '" placeholder="beat"></div></div>';
    h += '<div class="kn-f"><label>Logo (SVG)</label><select data-film="logo"><option value="">— none: the Logo block types the wordmark —</option>' + LIB.image.filter(function (m) { return /\.svg$/i.test(m.name); }).map(function (m) { return '<option value="lib:' + esc(m.name) + '"' + (P.logo === 'lib:' + m.name ? ' selected' : '') + '>' + esc(m.name) + '</option>'; }).join('') + '</select></div>';
    h += '<h3>Music</h3><div class="kn-f"><label>Track</label><select data-film="music"><option value="">— none —</option>' + LIB.audio.map(function (m) { return '<option value="lib:' + esc(m.name) + '"' + (P.music && P.music.src === 'lib:' + m.name ? ' selected' : '') + '>' + esc(m.name) + '</option>'; }).join('') + '</select></div>';
    if (P.music) {
      h += '<div class="kn-f"><label>Offset (s)</label><input type="number" step="0.01" data-film="offset" value="' + P.music.offset + '"></div><div class="kn-f"><label>Stop at beat</label><input type="number" step="1" data-film="stopBeat" value="' + (P.music.stopBeat == null ? '' : P.music.stopBeat) + '" placeholder="dead stop (the logo hit)"></div><div class="kn-f"><label>Gain (dB)</label><input type="number" step="0.5" data-film="gain" value="' + P.music.gain + '"></div>';
      h += '<button class="eb wide" data-a="beats">' + ic('activity') + ' Measure the track: tempo, downbeat, drops</button><div id="kn-beatinfo" class="kn-note"></div>';
    }
    h += '<h3>Sound</h3><div class="kn-note">Every block registers its own cues (whooshes, slams, keys, pops). They play from a kit synthesised on this PC; put a library file on a name to replace it, and set levels in dB.</div>';
    h += '<div class="kn-f"><label>Levels</label><textarea data-film="sounds" rows="2">' + esc(JSON.stringify(P.sounds)) + '</textarea></div><div class="kn-f"><label>Kit</label><textarea data-film="kit" rows="2" placeholder=\'{"impact":"lib:boom.wav"}\'>' + esc(JSON.stringify(P.kit)) + '</textarea></div>';
    h += '<div class="kn-f"><label>Extra cues</label><textarea data-film="cues" rows="2" placeholder="[[beat, name, gain], ...]">' + esc(JSON.stringify(P.cues)) + '</textarea></div>';
    h += '<button class="eb wide" data-a="captions">' + ic('cc') + ' Captions from the music\'s words (Whisper)</button></div>';
    INS.innerHTML = h; icons(INS);
  }
  INS.addEventListener('change', function (e) {
    var el = e.target, it = selected();
    if (el.dataset.pal) { P.palette[el.dataset.pal] = el.value.toUpperCase(); changed(); return; }
    if (el.dataset.film) {
      var k = el.dataset.film, v = el.value;
      if (k === 'font') P.font = v; else if (k === 'hud') P.hud = v.trim() || false;
      else if (k === 'hudOut0' || k === 'hudOut1') { var a = +$('[data-film=hudOut0]', INS).value, b = +$('[data-film=hudOut1]', INS).value; P.hudOut = a && b ? [a, b] : null; }
      else if (k === 'logo') P.logo = v;
      else if (k === 'music') P.music = v ? { src: v, offset: 0, stopBeat: null, gain: -3.5 } : null;
      else if (k === 'offset') P.music.offset = +v || 0; else if (k === 'stopBeat') P.music.stopBeat = v === '' ? null : +v; else if (k === 'gain') P.music.gain = +v || 0;
      else if (k === 'sounds' || k === 'kit' || k === 'cues') { try { P[k] = JSON.parse(v || (k === 'cues' ? '[]' : '{}')); } catch (err) { toast('not valid JSON'); return; } }
      changed(k !== 'sounds' && k !== 'kit'); if (k === 'music') renderFilm(); return;
    }
    if (!it) return;
    if (el.dataset.sk != null) {   // a Words shot
      var s = it.opts.shots[+el.dataset.i], key = el.dataset.sk;
      if (key === 'text') { var tx = el.value; s.text = tx.indexOf('|') >= 0 ? tx.split('|').map(function (x) { return x.trim(); }) : tx; }
      else if (key === 'big') s.big = el.checked; else if (key === 'at' || key === 'size' || key === 'rot') { if (el.value === '') delete s[key]; else s[key] = +el.value; }
      else { if (el.value === '') delete s[key]; else s[key] = el.value; }
      changed(); return;
    }
    if (el.dataset.pk) {   // an effect parameter
      var pk = el.dataset.pk, tt = el.dataset.t;
      if (tt === 'num') it.params[pk] = +el.value; else if (tt === 'bool') it.params[pk] = el.checked;
      else if (tt === 'pt0' || tt === 'pt1') { var pt = Array.isArray(it.params[pk]) ? it.params[pk].slice() : [.5, .5]; pt[tt === 'pt0' ? 0 : 1] = +el.value; it.params[pk] = pt; }
      else it.params[pk] = el.value;
      changed(false); fxStill(); return;
    }
    var key2 = el.dataset.k, ty = el.dataset.t;
    if (ty === 'span') {
      var k0 = +$('[data-k=k0]', INS).value, k1 = +$('[data-k=k1]', INS).value;
      if (sel.type === 'cap') { it[0] = k0; it[1] = k1; } else { if (sel.type === 'scene') shiftScene(it, k0 - it.k0); it.k0 = k0; it.k1 = Math.max(k0 + .5, k1); }
      changed(); return;
    }
    if (ty === 'opts' || ty === 'params') { try { var o = JSON.parse(el.value); if (ty === 'opts') it.opts = o; else it.params = o; } catch (err) { toast('not valid JSON'); return; } changed(); return; }
    if (ty === 'words') { it[2] = el.value.split('\n').map(function (l) { var m = l.match(/^(.*?)\s*@\s*([\d.]+)\s*$/); return m ? [m[1].trim(), +m[2]] : null; }).filter(Boolean); changed(); return; }
    if (ty === 'json') { if (el.value.trim() === '') delete it.opts[key2]; else { try { it.opts[key2] = JSON.parse(el.value); } catch (err) { toast('not valid JSON in ' + key2); return; } } changed(); return; }
    if (ty === 'num') { if (el.value === '') delete it.opts[key2]; else it.opts[key2] = +el.value; changed(); return; }
    if (ty === 'bool') { it.opts[key2] = el.checked; changed(); return; }
    if (el.value === '' || el.value === 'none') delete it.opts[key2]; else it.opts[key2] = el.value;
    changed();
  });

  /* ── bins ── */
  function renderBlocks() {
    $('#kn-blocks').innerHTML = Object.keys(BLOCKS).map(function (n) { var b = BLOCKS[n]; return '<div class="kn-card" data-block="' + n + '">' + ic(b.ic) + '<div><b>' + n + '</b><small>' + esc(b.d) + '</small></div><span class="n">' + (b.N ? b.N + ' beats' : '') + '</span></div>'; }).join('');
    icons($('#kn-blocks'));
  }
  function renderFx(q) {
    q = (q || '').toLowerCase(); var groups = {};
    Object.keys(FXS).forEach(function (n) { var f = FXS[n]; if (q && (n + ' ' + f.d + ' ' + f.g).toLowerCase().indexOf(q) < 0) return; (groups[f.g] = groups[f.g] || []).push(n); });
    $('#kn-fxlist').innerHTML = Object.keys(groups).map(function (g) { return '<div class="grp">' + g + '</div>' + groups[g].map(function (n) { return '<div class="kn-card" data-fx="' + n + '">' + ic('wand') + '<div><b>' + n.replace('local_', '').replace(/_/g, ' ') + '</b><small>' + esc(FXS[n].d) + '</small></div></div>'; }).join(''); }).join('');
    icons($('#kn-fxlist'));
  }
  function loadLib(kind) {
    var cur = $('#kn-lib .chips button.on, .chips button.on');
    return fetch(B_ + '/api/library?kind=' + kind + '&limit=120').then(function (r) { return r.json(); }).then(function (d) {
      LIB[kind] = d.items || [];
      if ($('.chips button.on').dataset.k === kind) renderLib(kind);
    }).catch(function () { });
  }
  function renderLib(kind) {
    var items = LIB[kind] || [];
    $('#kn-lib').innerHTML = items.length ? items.map(function (it) {
      return '<div class="mi-card" data-name="' + esc(it.name) + '" data-kind="' + kind + '" title="' + esc(it.prompt || it.name) + '">' + (it.thumb ? '<img src="' + esc(B_ + it.thumb) + '" loading="lazy" alt="">' : '<div class="au">' + ic('music') + esc(it.name) + '</div>') + '<div class="nm">' + esc(it.name) + '</div></div>';
    }).join('') : '<div class="dim" style="grid-column:1/-1">nothing here yet — make or upload ' + kind + 's in the lab</div>';
    icons($('#kn-lib'));
  }
  function renderTpl(tpls) {
    $('#kn-tpl').innerHTML = '<div class="kn-card tpl" data-tpl="blank">' + ic('plus') + '<div><b>Blank film</b><small>32 beats at 120 BPM, nothing on it.</small></div></div>' + tpls.map(function (t, i) {
      return '<div class="kn-card tpl" data-tpl="' + i + '">' + ic('film') + '<div><b>' + esc(t.name) + '</b><small>' + t.beats + ' beats at ' + t.bpm + ' BPM · ' + t.project.scenes.length + ' blocks</small></div></div>';
    }).join('');
    $('#kn-tpl').onclick = function (e) {
      var c = e.target.closest('[data-tpl]'); if (!c) return;
      if (P.scenes.length && !confirm('Replace the current film with this template?')) return;
      var np = c.dataset.tpl === 'blank' ? blank() : clone(tpls[+c.dataset.tpl].project);
      np.id = ''; np.session = SESSION; P = np; sel = null; $('#kn-name').value = P.name; syncTop(); changed(); seek(0);
    };
    icons($('#kn-tpl'));
  }

  /* ── AI ── */
  var aiMode = 'project';
  $('#kn-aimode').onclick = function (e) { var b = e.target.closest('button'); if (!b) return; aiMode = b.dataset.m; $$('#kn-aimode button').forEach(function (x) { x.classList.toggle('on', x === b); }); };
  function ai(ask, mode) {
    ask = ask || $('#kn-aiprompt').value.trim(); mode = mode || aiMode;
    if (!ask) { toast('say what you want'); return; }
    var btn = $('#kn-aigo'); btn.disabled = true; btn.innerHTML = ic('hourglass') + ' writing…'; icons(btn);
    var body = { ask: ask, mode: mode, project: P, secs: +$('#kn-aisecs').value || 0 };
    if (mode === 'props' && sel && sel.type === 'scene') body.scene = selected();
    fetch(API + 'ai', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) { toast(d.error, 5000); return; }
      if (mode === 'project') { d.id = P.id; d.session = SESSION; d.name = d.name || P.name; P = d; sel = null; $('#kn-name').value = P.name; syncTop(); }
      else if (mode === 'scene') { var k = snapK(K(t)); (d.scenes || []).forEach(function (s) { var len = s.k1 - s.k0; shiftScene(s, k - s.k0); addBlock(s.block, s.opts); var ns = P.scenes[P.scenes.length - 1]; ns.k1 = Math.min(P.beats, ns.k0 + len); }); (d.fx || []).forEach(function (f) { f.id = uid(); f.k0 += k; f.k1 += k; P.fx.push(f); }); }
      else if (mode === 'props' && sel && sel.type === 'scene' && d.scenes && d.scenes[0]) { var cur = selected(), nw = d.scenes[0]; cur.opts = nw.opts; cur.block = nw.block in BLOCKS ? nw.block : cur.block; }
      changed(); toast('written');
    }).catch(function () { toast('the writer is offline'); }).finally(function () { btn.disabled = false; btn.innerHTML = ic('sparkle') + ' Write it'; icons(btn); });
  }

  /* ── renders ── */
  var JOBS = [];
  function pollJobs() {
    fetch(API + 'jobs').then(function (r) { return r.json(); }).then(function (d) { JOBS = d.jobs || []; renderJobs(); if (JOBS.some(function (j) { return j.status === 'running'; })) setTimeout(pollJobs, 2000); }).catch(function () { });
  }
  function renderJobs() {
    var h = JOBS.length ? JOBS.map(function (j) {
      var chk = j.check && !j.check.error ? '<div class="chk ' + (j.check.pass ? 'ok' : 'bad') + '">' + (j.check.pass ? 'PASS' : 'CHECK') + ' · ' + Math.round(j.check.still_share * 100) + '% still frames · longest hold ' + j.check.longest_hold_s + ' s · ' + j.check.cuts_per_10s + ' cuts / 10 s' + (j.check.holds && j.check.holds.length ? ' · holds at beat ' + j.check.holds.map(function (x) { return x.beat; }).join(', ') : '') + '</div>' : '';
      return '<div class="job"><div><b>' + esc(j.purpose || 'film') + '</b> · ' + j.dur + ' s · ' + esc(j.size_px || '') + ' <span class="dim">' + esc(j.stage || j.status) + '</span></div>' +
        (j.status === 'running' ? '<div class="bar"><i style="width:' + Math.round((j.pct || 0) * 100) + '%"></i></div><button class="eb sm" data-cancel="' + j.id + '">cancel</button>' : '') +
        (j.status === 'done' ? '<div><a href="' + esc(B_ + '/' + j.url) + '" target="_blank">open ' + esc(j.name) + '</a> · ' + (j.size / 1e6).toFixed(1) + ' MB</div>' + chk : '') +
        (j.status === 'error' ? '<div class="chk bad">' + esc(j.error) + '</div>' : '') + '</div>';
    }).join('') : '<div class="dim">nothing rendering</div>';
    $('#kn-jobs').innerHTML = h;
  }
  $('#kn-jobs').onclick = function (e) { var b = e.target.closest('[data-cancel]'); if (b) fetch(API + 'job/' + b.dataset.cancel + '/cancel', { method: 'POST' }).then(pollJobs); };
  function exportDlg() {
    if (!P.scenes.length) { toast('add a block first'); return; }
    if (!HEALTH || !HEALTH.ok) { toast('render engine offline: ' + (HEALTH ? ['node', 'chrome', 'ffmpeg', 'engine'].filter(function (k) { return !HEALTH[k]; }).join(', ') : 'no answer'), 5000); return; }
    var secs = B(P.beats).toFixed(1), frames = Math.round(B(P.beats) * P.fps);
    modal('<h2>Render on this PC</h2><div class="kn-note">' + P.w + '×' + P.h + ' · ' + P.fps + ' fps · ' + secs + ' s · ' + frames + ' frames · Chrome ' + (HEALTH.chrome || '') + ' + ffmpeg, ' + HEALTH.cpus + ' CPUs, ' + HEALTH.ram_gb + ' GB. A 1080p check render takes a few minutes; 4K is slower.</div>' +
      '<div class="kn-f"><label>Motion blur</label><input type="checkbox" id="x-blur" checked></div><div class="kn-f"><label>Bloom</label><input type="checkbox" id="x-bloom" checked></div>' +
      '<div class="kn-f"><label>Film grain</label><input type="number" id="x-grain" value="2.2" min="0" max="8" step="0.2"></div><div class="kn-f"><label>Quality (CRF)</label><input type="number" id="x-crf" value="16" min="10" max="30"></div>' +
      '<div class="kn-f"><label>Preset</label><select id="x-preset"><option value="fast">fast</option><option value="medium" selected>medium</option><option value="slow">slow</option></select></div>' +
      '<div class="kn-f"><label>Loudness</label><input type="number" id="x-lufs" value="-14" min="-24" max="-8"></div>' +
      '<div class="row2"><button class="eb" data-a="close">Cancel</button><button class="eb pri" id="x-go">' + ic('upload') + ' Render to library</button></div>');
    $('#x-go').onclick = function () {
      var o = { blur: $('#x-blur').checked, bloom: $('#x-bloom').checked, grain: +$('#x-grain').value, crf: +$('#x-crf').value, preset: $('#x-preset').value, lufs: +$('#x-lufs').value };
      fetch(API + 'render', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project: P, options: o, session: SESSION, purpose: P.name }) }).then(function (r) { return r.json(); }).then(function (d) {
        closeModal(); if (d.error) { toast(d.error, 5000); return; } toast('rendering — see Renders'); showTab('jobs'); pollJobs();
      });
    };
  }

  /* ── modals ── */
  function modal(h) { var m = $('#kn-modal'); m.innerHTML = '<div class="box">' + h + '</div>'; m.hidden = false; icons(m); }
  function closeModal() { $('#kn-modal').hidden = true; }
  $('#kn-modal').onclick = function (e) { if (e.target === $('#kn-modal') || e.target.closest('[data-a=close]')) closeModal(); };
  function projectsDlg() {
    fetch(API + 'projects').then(function (r) { return r.json(); }).then(function (d) {
      modal('<h2>Your films</h2><div class="kn-list">' + ((d.projects || []).map(function (p) { return '<div class="it" data-open="' + p.id + '">' + ic('film') + '<div><b>' + esc(p.name) + '</b><div class="dim" style="font-size:11px">' + p.scenes + ' blocks · ' + p.secs + ' s · ' + p.bpm + ' BPM</div></div><small>' + new Date(p.updated * 1000).toLocaleString() + '</small><button class="eb sm" data-del="' + p.id + '" title="delete">' + ic('trash') + '</button></div>'; }).join('') || '<div class="dim">no films yet</div>') + '</div><div class="row2"><button class="eb" data-a="new">' + ic('plus') + ' New film</button><button class="eb" data-a="close">Close</button></div>');
      $('#kn-modal').querySelector('.box').onclick = function (e) {
        var o = e.target.closest('[data-open]'), dl = e.target.closest('[data-del]'), nw = e.target.closest('[data-a=new]');
        if (dl) { e.stopPropagation(); if (confirm('Delete this film?')) fetch(API + 'project/' + dl.dataset.del + '/delete', { method: 'POST' }).then(projectsDlg); return; }
        if (nw) { P = blank(); sel = null; $('#kn-name').value = P.name; syncTop(); changed(); closeModal(); return; }
        if (o) { open(o.dataset.open); closeModal(); }
      };
    });
  }
  function versionsDlg() {
    if (!P.id) { toast('save first'); return; }
    fetch(API + 'project/' + P.id + '/versions').then(function (r) { return r.json(); }).then(function (d) {
      modal('<h2>Earlier versions</h2><div class="kn-list">' + ((d.versions || []).map(function (v) { return '<div class="it" data-v="' + v.i + '">' + ic('clock') + '<b>' + esc(v.name) + '</b> · ' + v.scenes + ' blocks<small>' + new Date(v.updated * 1000).toLocaleString() + '</small></div>'; }).join('') || '<div class="dim">no earlier versions</div>') + '</div><div class="row2"><button class="eb" data-a="close">Close</button></div>');
      $('#kn-modal').querySelector('.box').onclick = function (e) {
        var v = e.target.closest('[data-v]'); if (!v) return;
        fetch(API + 'project/' + P.id + '/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ i: +v.dataset.v }) }).then(function (r) { return r.json(); }).then(function (p) { if (p.scenes) { p.id = P.id; P = p; sel = null; $('#kn-name').value = P.name; syncTop(); changed(); closeModal(); } });
      };
    });
  }
  function open(id) {
    return fetch(API + 'project/' + id).then(function (r) { return r.json(); }).then(function (p) {
      if (!p || p.error) { toast('no such film'); return; }
      P = p; P.session = SESSION || P.session; sel = null; dirty = false; $('#kn-name').value = P.name; $('#kn-save').textContent = 'saved'; syncTop(); hist = []; fut = []; DUR = B(P.beats); renderTL(); renderInsp(); load(); seek(0);
    });
  }
  function syncTop() { $('#kn-bpm').value = P.bpm; $('#kn-beats').value = P.beats; $('#kn-fps').value = P.fps; $('#kn-size').value = P.w + 'x' + P.h; }

  /* ── measuring + captions ── */
  function measure() {
    if (!P.music) return;
    var el = $('#kn-beatinfo'); el.textContent = 'measuring…';
    fetch(API + 'beats', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ src: P.music.src, bpm: P.bpm }) }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) { el.textContent = d.error; return; }
      el.innerHTML = 'tempo <b>' + d.bpm + ' BPM</b> (grid strength ' + d.grid_strength + ') · first downbeat ' + d.offset + ' s · ' + d.film_beats_available + ' beats available · drops: ' + (d.drops || []).map(function (x) { return 'beat ' + x.film_beat + ' (' + x.music_s + ' s, ×' + x.rise + ')'; }).join(', ') +
        '<br><button class="eb sm" id="kn-applybeat">Use ' + d.bpm + ' BPM and offset ' + d.offset + ' s</button>';
      $('#kn-applybeat').onclick = function () { P.bpm = d.bpm; P.music.offset = d.offset; syncTop(); changed(); renderFilm(); };
    }).catch(function () { el.textContent = 'measure failed'; });
  }
  function captionsFromMusic() {
    if (!P.music) { toast('pick a track first'); return; }
    toast('listening to the track…', 8000);
    fetch(API + 'words', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ src: P.music.src, bpm: P.bpm, offset: P.music.offset }) }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) { toast(d.error, 5000); return; }
      P.captions = (d.captions || []).filter(function (c) { return c[0] < P.beats; }); changed(); toast(P.captions.length + ' caption phrases');
    });
  }

  /* ── actions ── */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-a]'); if (b) {
      var a = b.dataset.a;
      if (a === 'close') { save(); if (window.parent !== window) { window.parent.postMessage({ mml: 'motion-close' }, '*'); return; } location.href = B_ + '/' + (SESSION ? '?session=' + encodeURIComponent(SESSION) : ''); }
      else if (a === 'undo') undo(); else if (a === 'redo') redo();
      else if (a === 'film') { sel = { type: 'film' }; renderTL(); renderInsp(); $('#kn-insp').classList.add('open'); }
      else if (a === 'projects') projectsDlg(); else if (a === 'versions') versionsDlg(); else if (a === 'export') exportDlg();
      else if (a === 'play') play(); else if (a === 'start') seek(0); else if (a === 'end') seek(DUR - .001);
      else if (a === 'stepb') seek(B(Math.max(0, Math.round(K(t) * 2) / 2 - 1))); else if (a === 'stepf') seek(B(Math.round(K(t) * 2) / 2 + 1));
      else if (a === 'loop') { loop = !loop; $('#kn-loop').classList.toggle('on', loop); var it = selected(); post({ type: 'loop', a: loop && it ? B(sel.type === 'cap' ? it[0] : it.k0) : null, b: loop && it ? B(sel.type === 'cap' ? it[1] : it.k1) : null }); }
      else if (a === 'fxprev') { fxprev = !fxprev; $('#kn-fxprev').classList.toggle('on', fxprev); fxStill(); }
      else if (a === 'still') { if (!P.scenes.length) return; toast('rendering the still…', 6000); fetch(API + 'still', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project: P, frame: Math.round(t * P.fps), scale: 1 }) }).then(function (r) { return r.ok ? r.blob() : null; }).then(function (bl) { if (!bl) { toast('still failed'); return; } var u = URL.createObjectURL(bl), l = document.createElement('a'); l.href = u; l.download = (P.name || 'film').replace(/[^a-z0-9]+/gi, '-') + '_' + Math.round(t * P.fps) + '.jpg'; l.click(); }); }
      else if (a === 'dup') dup(); else if (a === 'del') del();
      else if (a === 'snap') { snap = !snap; $('#kn-snap').classList.toggle('on', snap); }
      else if (a === 'bin') $('#kn-bin').classList.toggle('open'); else if (a === 'insp') $('#kn-insp').classList.toggle('open');
      else if (a === 'addshot') { var it2 = selected(); if (it2 && it2.block === 'Words') { it2.opts.shots = it2.opts.shots || []; var last = it2.opts.shots.length ? it2.opts.shots[it2.opts.shots.length - 1].at + 1 : it2.k0 + 1; it2.opts.shots.push({ at: Math.min(it2.k1 - .5, last), style: 'cut', text: 'WORD', fx: 'beat' }); changed(); } }
      else if (a === 'delshot') { var it3 = selected(); if (it3 && it3.opts.shots) { it3.opts.shots.splice(+b.dataset.i, 1); changed(); } }
      else if (a === 'aiprops') { showTab('ai'); $$('#kn-aimode button').forEach(function (x) { x.classList.toggle('on', x.dataset.m === 'props'); }); aiMode = 'props'; $('#kn-aiprompt').focus(); }
      else if (a === 'beats') measure(); else if (a === 'captions') captionsFromMusic();
      return;
    }
    var bl = e.target.closest('[data-block]'); if (bl) { addBlock(bl.dataset.block); return; }
    var fx = e.target.closest('[data-fx]'); if (fx) { addFx(fx.dataset.fx); return; }
    var tab = e.target.closest('.tabs button'); if (tab) { showTab(tab.dataset.t); return; }
    var chip = e.target.closest('.chips button'); if (chip) { $$('.chips button').forEach(function (x) { x.classList.toggle('on', x === chip); }); renderLib(chip.dataset.k); loadLib(chip.dataset.k); return; }
    var mc = e.target.closest('.mi-card'); if (mc) {
      if (mc.dataset.kind === 'image') { if (/\.svg$/i.test(mc.dataset.name)) { P.logo = 'lib:' + mc.dataset.name; changed(); toast('logo set'); } else { var o = BLOCKS.Picture.def(); o.src = 'lib:' + mc.dataset.name; addBlock('Picture', o); } }
      else if (mc.dataset.kind === 'audio') { P.music = { src: 'lib:' + mc.dataset.name, offset: 0, stopBeat: null, gain: -3.5 }; sel = { type: 'film' }; changed(); toast('music set — measure it in Film to lock the tempo'); }
      else toast('video goes in a Picture block as a still for now');
    }
  });
  function showTab(name) { $$('.tabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.t === name); }); $$('.pane').forEach(function (p) { p.hidden = p.dataset.p !== name; }); if (name === 'jobs') pollJobs(); if (name === 'lib') loadLib($('.chips button.on').dataset.k); }
  $('#kn-aigo').onclick = function () { ai(); };
  $('#kn-fxq').oninput = function () { renderFx(this.value); };
  $('#kn-name').onchange = function () { P.name = this.value.trim() || 'Untitled film'; changed(false); };
  $('#kn-bpm').onchange = function () { P.bpm = Math.max(40, Math.min(300, +this.value || 120)); changed(); };
  $('#kn-beats').onchange = function () { P.beats = Math.max(4, Math.min(4000, Math.round(+this.value || 32))); P.scenes.forEach(function (s) { s.k1 = Math.min(s.k1, P.beats); }); P.scenes = P.scenes.filter(function (s) { return s.k1 - s.k0 >= .5; }); changed(); };
  $('#kn-fps').onchange = function () { P.fps = +this.value; changed(); };
  $('#kn-size').onchange = function () { var s = this.value.split('x'); P.w = +s[0]; P.h = +s[1]; changed(false); };
  $('#kn-zoom').value = zoom; $('#kn-zoom').oninput = function () { zoom = +this.value; localStorage.setItem('kn.zoom', zoom); renderTL(); };
  addEventListener('keydown', function (e) {
    if (e.target.matches('input,textarea,select') || !$('#kn-modal').hidden) return;
    if (e.code === 'Space') { e.preventDefault(); play(); }
    else if (e.code === 'ArrowLeft') seek(B(Math.max(0, Math.round(K(t) * 2) / 2 - (e.shiftKey ? 4 : 1))));
    else if (e.code === 'ArrowRight') seek(B(Math.round(K(t) * 2) / 2 + (e.shiftKey ? 4 : 1)));
    else if (e.code === 'Home') seek(0); else if (e.code === 'End') seek(DUR - .001);
    else if (e.code === 'Delete' || e.code === 'Backspace') del();
    else if (e.key === 'l' || e.key === 'L') $('[data-a=loop]').click();
    else if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); } else if ((e.ctrlKey || e.metaKey) && e.key === 'y') { e.preventDefault(); redo(); }
    else if ((e.ctrlKey || e.metaKey) && e.key === 'd') { e.preventDefault(); dup(); } else if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); dirty = true; save(); toast('saved'); }
    else if (e.key === '+' || e.key === '=') { zoom = Math.min(120, zoom + 4); $('#kn-zoom').value = zoom; renderTL(); } else if (e.key === '-') { zoom = Math.max(6, zoom - 4); $('#kn-zoom').value = zoom; renderTL(); }
    else if (/^[0-9]$/.test(e.key)) seek(DUR * (+e.key) / 10);
  });
  addEventListener('beforeunload', function () { if (dirty) save(); });

  /* ── boot ── */
  renderBlocks(); renderFx(''); syncTop(); DUR = B(P.beats); renderTL(); renderInsp();
  fetch(API + 'health').then(function (r) { return r.json(); }).then(function (h) {
    HEALTH = h; var el = $('#kn-eng'); el.textContent = h.ok ? 'engine: ' + (h.chrome || 'chrome') + ' + ffmpeg' + (h.cv2 ? ' + motion blur' : '') : 'engine offline: ' + ['engine', 'node', 'chrome', 'ffmpeg'].filter(function (k) { return !h[k]; }).join(', ');
    el.className = 'mo-eng ' + (h.ok ? 'ok' : 'bad'); fxStill();
  }).catch(function () { $('#kn-eng').textContent = 'engine: no answer'; $('#kn-eng').className = 'mo-eng bad'; });
  fetch(API + 'fonts').then(function (r) { return r.json(); }).then(function (d) { FONTS = d.fonts || []; }).catch(function () { });
  fetch(API + 'templates').then(function (r) { return r.json(); }).then(function (d) { renderTpl(d.templates || []); }).catch(function () { renderTpl([]); });
  ['image', 'audio'].forEach(loadLib);
  pollJobs();
  if (Q.get('p')) open(Q.get('p')).then(function () { if (Q.get('ask')) { $('#kn-aiprompt').value = Q.get('ask'); showTab('ai'); } });
  else if (Q.get('ask')) { $('#kn-aiprompt').value = Q.get('ask'); showTab('ai'); ai(Q.get('ask'), 'project'); }
})();
