"""Build an ALTER edit prompt and its run parameters from a preset, so the tested rules hold every time.

Usage:
  python3 alter_prompt.py --list                              # every preset, its mode and what to fill
  python3 alter_prompt.py --show outfit                       # one preset in full
  python3 alter_prompt.py outfit --who "the man in the olive hoodie" \\
      --set outfit="a long camel wool overcoat, open, over a white t-shirt" \\
      --video asset_SOURCE --image asset_TARGET_FRAME [--json] [--out run.json]

The prompt is the mode's opening block (what must not change), the preset's change line (the one thing that does),
then the close block. The script refuses the combinations that failed in testing:
- a restyle that also asks to keep the light, the set or "everything" (the model returns the source unchanged);
- a restyle with more than one image (one target frame, or one style frame with --style-image);
- a preset that names @image1 but gets no reference image, or more images than the prompt names;
- an unfilled {slot}.
--json prints the model_run parameters for edit mode: the source as the only reference video, duration -1 (the
output follows the source), the source audio left alone (generateAudio false) and a 480p draft. Find the edit model
with search or recommend; this file never names one.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(HERE, '..', 'references', 'presets.json')
SLOT = re.compile(r'\{([a-z_]+)\}')
IMAGE_TAG = re.compile(r'@image(\d+)')
# phrases that make a restyle come back unchanged (tested: the model keeps the photo)
RESTYLE_KEEPS = re.compile(
    r'\b(keep|keeps|keeping|preserve|retain|maintain|leave|do not change|don\'t change|unchanged|same)\b[^.;]{0,40}?'
    r'\b(everything|light|lighting|sunlight|set|background|scenery|scene|look|colou?rs?|grade|photo|photographic|'
    r'photoreal(istic)?|realism|realistic)\b', re.I)
# clothes named in --who make an outfit swap contradict itself ("keep the man in the olive hoodie", then a new coat)
CLOTHES = re.compile(r'\b(hoodie|jacket|coat|shirt|t-shirt|tee|sweater|jumper|dress|suit|top|jeans|trousers|skirt|'
                     r'shorts|blazer|cardigan|uniform|outfit|vest)\b', re.I)
CLOTHING_PRESETS = {'outfit', 'costume', 'season-outfit'}
MAX_PROMPT = 10000


def load():
    with open(PRESETS, encoding='utf-8') as fh:
        return json.load(fh)


def find(data, name):
    for p in data['presets']:
        if p['name'] == name:
            return p
    names = ', '.join(p['name'] for p in data['presets'])
    raise SystemExit(f'unknown preset "{name}". Presets: {names}')


def fill(text, values):
    missing = sorted({k for k in SLOT.findall(text) if k not in values})
    if missing:
        return None, missing
    return SLOT.sub(lambda m: values[m.group(1)], text), []


def list_presets(data):
    group = None
    for p in data['presets']:
        if p['group'] != group:
            group = p['group']
            print(f'\n{group}')
        tf = p.get('target_frame')
        flags = p['mode'] + (' +target frame' if tf is True else ' (+target frame)' if tf == 'optional' else '') + \
            (' (unreliable)' if p.get('unreliable') else '')
        keys = ', '.join(['who'] + list(p.get('fill', {})))
        print(f"  {p['name']:<18} {flags:<20} fill: {keys}")
    print('\nModes: O = swap (keep everything), M = motion transfer (keep performance and camera), R = restyle '
          '(keep motion and composition). Run --show <preset> for the full text.')


def build(data, p, values, binding=None):
    mode = p['mode']
    key = p.get('opening', mode)
    parts = [data['openings'][key]]
    if mode == 'R':
        parts[0] = parts[0].replace('{style}', p['style'])
        if binding:
            first, rest = parts[0].split('. ', 1)
            parts[0] = f'{first}. {data[binding]} {rest}'
    parts += [p['change'], data['close'][key]]
    prompt = ' '.join(parts)
    out, missing = fill(prompt, values)
    if missing:
        hints = {**{'who': 'the person or subject as seen in the source, e.g. "the man in the olive hoodie"'},
                 **p.get('fill', {})}
        lines = '\n'.join(f'  --set {k}="..."   ({hints.get(k, "")})' if k != 'who' else f'  --who "..."   ({hints["who"]})'
                          for k in missing)
        print(f'error: preset {p["name"]} needs:\n{lines}', file=sys.stderr)
        sys.exit(2)
    # a {who} that opens a sentence is written in lower case by the user: capitalise sentence starts
    return re.sub(r'(^|[.!?] )([a-z])', lambda m: m.group(1) + m.group(2).upper(), out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('preset', nargs='?')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--show', metavar='PRESET')
    ap.add_argument('--who', help='the person or subject as seen in the source')
    ap.add_argument('--set', action='append', default=[], metavar='KEY=VALUE', help='fill one {slot}; repeatable')
    ap.add_argument('--extra', default='', help='one more sentence for this shot, placed before the close block')
    ap.add_argument('--video', help='asset id of the source clip (edit mode)')
    ap.add_argument('--image', action='append', default=[], help='asset id of a reference image, in @image order')
    ap.add_argument('--style-image', action='store_true',
                    help='restyle only: --image is a frame of a DIFFERENT film, used for its style alone (by default a '
                         'restyle --image is a target frame: this shot\'s first frame already redrawn in the style)')
    ap.add_argument('--new-audio', action='store_true', help='let the model make new sound (no dialogue to keep)')
    ap.add_argument('--resolution', default='480p', choices=['480p', '720p', '1080p'],
                    help='480p = a draft that can be finalised later; 720p or 1080p = a direct final')
    ap.add_argument('--json', action='store_true', help='print the model_run parameters, not just the prompt')
    ap.add_argument('--out', help='write the JSON to this file (refuses to overwrite without --force)')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    data = load()
    if a.list:
        list_presets(data)
        return 0
    if a.show:
        print(json.dumps(find(data, a.show), indent=1, ensure_ascii=False))
        return 0
    if not a.preset:
        ap.error('name a preset (see --list)')
    p = find(data, a.preset)
    values = {}
    for kv in a.set:
        if '=' not in kv:
            ap.error(f'--set needs KEY=VALUE, got "{kv}"')
        k, v = kv.split('=', 1)
        values[k.strip()] = v.strip()
    if a.who:
        values['who'] = a.who
    binding = None
    if p['mode'] == 'R' and a.image:
        binding = 'restyle_style_image' if a.style_image else 'restyle_target_frame'
    prompt = build(data, p, values, binding)
    if a.extra:
        close = data['close'][p.get('opening', p['mode'])]
        prompt = prompt[: -len(close)] + a.extra.strip().rstrip('.') + '. ' + close
    problems, notes = [], []
    used = set(SLOT.findall(' '.join([data['openings'][p.get('opening', p['mode'])], p.get('style', ''), p['change']])))
    unused = sorted(set(values) - used)
    if unused:
        notes.append(f'ignored --set keys (this preset has no such slot): {", ".join(unused)}')
    if p['name'] in CLOTHING_PRESETS and CLOTHES.search(values.get('who', '')):
        notes.append('--who names clothes while the clothes change; describe the person without them '
                     '(e.g. "the man with dark curly hair"), or the prompt asks to keep what it then replaces')
    if p['mode'] == 'R':
        user_text = ' '.join(list(values.values()) + [a.extra])
        if RESTYLE_KEEPS.search(user_text):
            problems.append('a restyle must not ask to keep the light, the set or everything: the model then returns '
                            'the source unchanged. Remove that wording.')
        if len(a.image) > 1:
            problems.append('a restyle takes one image: the target frame (or, with --style-image, one style frame)')
    named = sorted({int(n) for n in IMAGE_TAG.findall(prompt)})
    if named and not a.image:
        msg = f'this prompt names @image{named[-1]} but no --image was given: {"; ".join(p.get("refs", []))}'
        (problems if (a.json or a.out) else notes).append(msg)
    if a.image and named and len(a.image) > named[-1]:
        notes.append(f'{len(a.image)} images given, the prompt names {named[-1]}: bind the extra ones in --extra '
                     '(e.g. "@image2 shows the product from the side")')
    if len(prompt) > MAX_PROMPT:
        problems.append(f'prompt is {len(prompt)} characters; keep it under {MAX_PROMPT}')
    if p.get('unreliable'):
        notes.append('this preset is unreliable: in tests it often stayed photoreal. Offer 3d-feature or anime too.')
    if p.get('note'):
        notes.append(p['note'])
    if p.get('target_frame') is True and not a.image:
        notes.append('this preset works best with a target frame: references/realism-pass.md')
    if p['mode'] == 'R' and not a.image:
        notes.append('prompt-only restyle: if the check reports the background still photographic, re-run with a '
                     'target frame (this shot\'s first frame redrawn in the style) as --image')
    if problems:
        for s in problems:
            print('error:', s, file=sys.stderr)
        return 2
    if not (a.json or a.out):
        print(prompt)
        for s in notes:
            print('note:', s, file=sys.stderr)
        return 0
    params = {'prompt': prompt, 'duration': -1, 'generateAudio': bool(a.new_audio)}
    if a.video:
        params['referenceVideos'] = [a.video]
    if a.image:
        params['referenceImages'] = a.image
    if a.resolution == '480p':
        params['draft'] = True
    else:
        params['resolution'] = a.resolution
    payload = {'preset': p['name'], 'mode': p['mode'], 'parameters': params, 'notes': notes,
               'check': f'python3 scripts/alter_check.py source.mp4 output.mp4 --out qa/ --mode {p["check"]}',
               'next': 'search the edit model, model_schema_get, model_run with dry_run true, then run with wait false'}
    text = json.dumps(payload, indent=1, ensure_ascii=False)
    if a.out:
        if os.path.exists(a.out) and not a.force:
            raise SystemExit(f'{a.out} already exists. Pick another path or pass --force to replace it.')
        with open(a.out, 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
        print(f'wrote {a.out}')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
