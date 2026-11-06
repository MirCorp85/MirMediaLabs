r"""MOTION MINT image sprites (Nov 2 2026): one minted item / prop / animal drawn by Qwen-Image 2.1 in the locked Diorama sprite style,
cut out (BiRefNet), trimmed tight and saved as public/mg/library/mint/sprites/<id>.png. Prints one JSON line {src, pw, ph}.
Run with the mg-assets venv python (-I):  python -I mint_sprite.py --id coral --kind props --subject "a branching coral cluster" [--notes ".."] [--seed 7]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_art as BA  # noqa: E402

OUT = os.path.join(BA.ROOT, "public", "mg", "library", "mint", "sprites")
# THE locked Diorama sprite look (house style: charcoal, brushed metal, gold accents) — change it here only
# Diorama = THE look of every Motion Studio video
STYLE = ("clean flat-shaded isometric diorama illustration, crisp edges, soft cel shading, moody palette of deep charcoal and slate "
         "with silver highlights and small warm gold accents (materials stay true to the subject: rock is rock, never metal-plated); man-made things lean charcoal, steel and gold; animals, plants, shells and nature keep their true natural colours (rich but slightly muted), subtle rim light, premium game art, a single object, "
         "centered and fully visible with margin, isolated on a pure flat white background, no ground, no cast shadow, no text, no logo, no watermark")
VIEW = {"items": "a single hand-held {s} on its own, shown upright in clean side view, no stand, no base, no hands, no person",
        "props": "{s}, a standalone scenery piece seen from a three-quarter isometric angle, rising straight out of the ground, no pedestal, no display plate, no tile",
        "species": "{s}, the whole animal in clean side profile facing right, full body from nose to tail, all feet visible, natural standing pose"}


def cutout(src, dst):
    from PIL import Image
    from rembg import new_session, remove
    s = new_session("birefnet-general")
    rgba = remove(Image.open(src).convert("RGB"), session=s, post_process_mask=True)
    bb = rgba.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
    if not bb:
        raise RuntimeError("cutout found no subject")
    rgba = rgba.crop(bb)
    if max(rgba.size) > 768:
        k = 768 / max(rgba.size)
        rgba = rgba.resize((max(1, int(rgba.width * k)), max(1, int(rgba.height * k))), Image.LANCZOS)
    rgba.save(dst, optimize=True)
    return rgba.size


def main():
    a = sys.argv[1:]
    arg = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    sid, kind, subj = arg("--id"), arg("--kind"), arg("--subject")
    prompt = VIEW[kind].replace("{s}", subj) + ", " + STYLE + ((". " + arg("--notes")) if arg("--notes") else "")
    seed = int(arg("--seed", 1000 + sum(map(ord, sid)) % 9000))
    raw = BA.generate_direct(prompt, seed)
    os.makedirs(OUT, exist_ok=True)
    w, h = cutout(raw, os.path.join(OUT, sid + ".png"))
    print(json.dumps({"src": "mg/library/mint/sprites/%s.png" % sid, "pw": w, "ph": h, "seed": seed}), flush=True)


if __name__ == "__main__":
    main()
