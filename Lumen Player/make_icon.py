"""Generates icon.ico (multi-size) and icon.png for Lumen. Needs: pip install pillow"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageChops

S = 1024
HERE = os.path.dirname(os.path.abspath(__file__))


def solid(c):
    return Image.new("RGB", (S, S), c)


def build():
    # diagonal violet -> pink gradient
    v = Image.linear_gradient("L").resize((S, S))
    h = v.rotate(90)
    t = ImageChops.add(v, h, scale=2)
    base = Image.composite(solid((236, 72, 153)), solid((109, 40, 217)), t).convert("RGBA")

    # soft top-left light
    glow = Image.radial_gradient("L").resize((S * 2, S * 2))
    glow = ImageChops.invert(glow).point(lambda p: int(p * 0.38))
    layer = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    layer.paste(Image.new("RGBA", (S * 2, S * 2), (255, 255, 255, 255)), (-int(S * 0.95), -int(S * 0.95)), glow)
    base = Image.alpha_composite(base, layer)

    # rounded play triangle (inner triangle grown by a disk of radius r)
    cx, cy, r = S // 2 + 22, S // 2, 46
    pts = [(cx - 118, cy - 176), (cx - 118, cy + 176), (cx + 156, cy)]

    def tri_mask():
        m = Image.new("L", (S, S), 0)
        d = ImageDraw.Draw(m)
        d.polygon(pts, fill=255)
        for i in range(3):
            a, b = pts[i], pts[(i + 1) % 3]
            d.line([a, b], fill=255, width=2 * r)
            d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=255)
        return m

    mask = tri_mask()
    shadow = Image.new("RGBA", (S, S), (40, 8, 80, 0))
    shadow.putalpha(mask.point(lambda p: int(p * 0.45)))
    shadow = ImageChops.offset(shadow, 0, 26).filter(ImageFilter.GaussianBlur(26))
    base = Image.alpha_composite(base, shadow)
    tri = Image.composite(solid((255, 255, 255)), solid((233, 224, 255)), Image.linear_gradient("L").resize((S, S)).point(lambda p: 255 - p)).convert("RGBA")
    tri.putalpha(mask)
    base = Image.alpha_composite(base, tri)

    # thin inner rim
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle([8, 8, S - 9, S - 9], radius=222, outline=(255, 255, 255, 60), width=6)
    base = Image.alpha_composite(base, rim)

    # app-icon rounded square
    sq = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sq).rounded_rectangle([0, 0, S - 1, S - 1], radius=230, fill=255)
    base.putalpha(ImageChops.multiply(base.getchannel("A"), sq))
    return base


if __name__ == "__main__":
    img = build()
    img.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "icon.png"))
    img.save(os.path.join(HERE, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon.ico + icon.png written")
