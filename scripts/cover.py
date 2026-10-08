"""Portadas de Publi2.0 (1200x630) con la identidad del logo: negro #000000, rojo #EA3322 y blanco.

Uso:
  python scripts/cover.py --out images/slug.png --kicker "PUBLICIDAD · CREATIVIDAD" \
      --title "Comerciales prohibidos y censurados" \
      [--stat "5" --stat-label "comerciales que se cayeron"] \
      [--chips "Pepsi,Coca-Cola,Dove"]

Siempre lleva el logo de Publi2.0 (brand/logo-publi20.png). Ningún logotipo de terceros.
"""
import argparse
import hashlib
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
W, H, S = 1200, 630, 2
F = "/usr/share/fonts/opentype/inter/"
NEGRO, ROJO, BLANCO = (0, 0, 0), (234, 51, 34), (255, 255, 255)
GRIS, GRIS_CLARO, ROJO_SUAVE = (64, 64, 64), (238, 238, 238), (250, 204, 200)


def font(name, size):
    return ImageFont.truetype(F + name, int(size * S))


def wrap(draw, text, fnt, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w * S:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--kicker", default="PUBLI2.0")
    ap.add_argument("--stat")
    ap.add_argument("--stat-label", default="")
    ap.add_argument("--chips")
    a = ap.parse_args()

    img = Image.new("RGB", (W * S, H * S), BLANCO)
    d = ImageDraw.Draw(img)
    x0, text_w = 64, 560

    # Franja roja superior y logo
    d.rectangle([0, 0, W * S, 12 * S], fill=ROJO)
    logo = Image.open(ROOT / "brand" / "logo-publi20.png").convert("RGBA")
    lw = 220
    logo = logo.resize((lw * S, int(logo.height * lw / logo.width) * S), Image.LANCZOS)
    img.paste(logo, (x0 * S - 6 * S, 52 * S), logo)

    d.text((x0 * S, 124 * S), a.kicker.upper(), font=font("Inter-Bold.otf", 16), fill=ROJO)

    # Titular: el tamaño más grande que quepa en 5 líneas
    for size in (56, 52, 48, 44, 40, 36):
        f = font("InterDisplay-Black.otf", size)
        lines = wrap(d, a.title, f, text_w)
        if len(lines) <= 5:
            break
    lh = int(size * 1.12)
    y = 168 + (5 - len(lines)) * lh // 2
    for ln in lines:
        d.text((x0 * S, y * S), ln, font=f, fill=NEGRO)
        y += lh
    d.rectangle([x0 * S, (H - 56) * S, (x0 + 72) * S, (H - 48) * S], fill=ROJO)

    # Panel negro a la derecha
    px, py, pw, ph = 680, 60, 464, 510
    d.rounded_rectangle([px * S, py * S, (px + pw) * S, (py + ph) * S], radius=20 * S, fill=NEGRO)

    if a.stat:
        sf = None
        for size in (150, 130, 110, 92, 78, 64):
            sf = font("InterDisplay-Black.otf", size)
            if d.textlength(a.stat, font=sf) <= (pw - 64) * S:
                break
        d.text(((px + 32) * S, (py + 140) * S), a.stat, font=sf, fill=ROJO)
        lf = font("Inter-Medium.otf", 24)
        yy = py + 140 + int(size * 1.15) + 10
        for ln in wrap(d, a.stat_label, lf, pw - 64):
            d.text(((px + 32) * S, yy * S), ln, font=lf, fill=BLANCO)
            yy += 32
    elif a.chips:
        chips = [c.strip() for c in a.chips.split(",") if c.strip()][:6]
        cf = font("InterDisplay-Bold.otf", 34)
        yy = py + (ph - (len(chips) * 78 - 14)) // 2
        for i, c in enumerate(chips):
            tw = d.textlength(c, font=cf) / S
            if i == 0:
                d.rounded_rectangle([(px + 32) * S, yy * S, (px + 32 + tw + 40) * S, (yy + 64) * S],
                                    radius=14 * S, fill=ROJO)
            else:
                d.rounded_rectangle([(px + 32) * S, yy * S, (px + 32 + tw + 40) * S, (yy + 64) * S],
                                    radius=14 * S, outline=BLANCO, width=2 * S)
            d.text(((px + 52) * S, (yy + 12) * S), c, font=cf, fill=BLANCO)
            yy += 78
    else:
        seed = int(hashlib.md5(a.title.encode()).hexdigest(), 16)
        for i in range(8):
            v = 0.25 + ((seed >> (i * 4)) & 15) / 20
            bw = int((pw - 64) * min(v, 1.0))
            yy = py + 44 + i * 56
            col = ROJO if i == (seed % 8) else GRIS
            d.rounded_rectangle([(px + 32) * S, yy * S, (px + 32 + bw) * S, (yy + 34) * S],
                                radius=10 * S, fill=col)

    img = img.resize((W, H), Image.LANCZOS)
    img.save(a.out, "PNG", optimize=True)
    print("ok", a.out)


if __name__ == "__main__":
    main()
