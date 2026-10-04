"""Build the setup wizard's showcase gallery + mobile-companion QR code (run by installer\\build.ps1).

    python make_showcase.py <out_dir>

Reads installer\\showcase_src\\showcase.json ([{"file", "caption"}]; the images are real MIR MEDIA LABS
renders) and writes, for every slide, 16:9 PNGs Tk can show without Pillow at run time:
    <name>_1x.png / _2x.png       welcome page      (560x315 / 840x473)
    <name>_1x_s.png / _2x_s.png   install page      (440x248 / 660x371)
Tall or square pictures sit on a blurred copy of themselves instead of being cropped.
Plus qr_1x.png / qr_2x.png (Android app download) and index.json for the wizard.
"""
import json
import os
import sys

import qrcode
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "showcase_src")
APK_URL = "https://github.com/MirCorp85/MirMediaLabs/releases/latest/download/MirMediaLabs.apk"
SIZES = {"_1x": (560, 315), "_2x": (840, 473), "_1x_s": (440, 248), "_2x_s": (660, 371)}


def slide(im, w, h):
    im = im.convert("RGB")
    r = im.width / im.height
    if abs(r - w / h) < 0.25:                              # close to 16:9 -> cover-crop
        s = max(w / im.width, h / im.height)
        t = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        x, y = (t.width - w) // 2, (t.height - h) // 2
        return t.crop((x, y, x + w, y + h))
    s = max(w / im.width, h / im.height)                   # otherwise: fit on a blurred backdrop
    bg = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (bg.width - w) // 2, (bg.height - h) // 2
    bg = bg.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(18))
    bg = Image.blend(bg, Image.new("RGB", (w, h), (12, 14, 19)), 0.45)
    s = min(w / im.width, h / im.height) * 0.94
    fg = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
    return bg


def main(out):
    os.makedirs(out, exist_ok=True)
    idx = []
    for i, s in enumerate(json.load(open(os.path.join(SRC, "showcase.json"), encoding="utf-8"))):
        im = Image.open(os.path.join(SRC, s["file"]))
        name = "%02d" % i
        for suf, (w, h) in SIZES.items():
            slide(im, w, h).save(os.path.join(out, name + suf + ".png"), optimize=True)
        idx.append({"file": name, "caption": s["caption"]})
    json.dump(idx, open(os.path.join(out, "index.json"), "w", encoding="utf-8"), indent=1)
    for suf, box in (("1x", 5), ("2x", 8)):
        q = qrcode.QRCode(border=2, box_size=box, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data(APK_URL)
        q.make_image(fill_color="#0c0e13", back_color="white").save(os.path.join(out, "qr_%s.png" % suf))
    print("showcase: %d slides + QR -> %s" % (len(idx), out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "build", "showcase"))
