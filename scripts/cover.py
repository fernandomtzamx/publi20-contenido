"""Portadas de Publi2.0 (1200x630) con el sistema visual de la marca.

Uso:
  python scripts/cover.py --out images/slug.png --kicker "MARKETING DIGITAL" \
      --title "Cuánto cuesta una agencia de marketing digital" \
      [--stat "13-17" --stat-label "de noviembre, Buen Fin 2026"] \
      [--chips "CPM,CPC,CPA,ROAS"]

Sin --stat ni --chips dibuja un patrón geométrico. Ningún logotipo de terceros.
"""
import argparse
import hashlib
from PIL import Image, ImageDraw, ImageFont

W, H, S = 1200, 630, 2
F = "/usr/share/fonts/opentype/inter/"
INK, PANEL, TEXT, MUTED = (15, 18, 34), (24, 28, 50), (245, 243, 238), (150, 155, 180)
ACCENT, BAR = (255, 90, 60), (92, 99, 140)


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

    img = Image.new("RGB", (W * S, H * S), INK)
    d = ImageDraw.Draw(img)
    x0, text_w = 64, 560

    d.text((x0 * S, 60 * S), "PUBLI2.0", font=font("InterDisplay-Black.otf", 20), fill=ACCENT)
    d.text((x0 * S, 92 * S), a.kicker.upper(), font=font("Inter-SemiBold.otf", 16), fill=MUTED)

    # Titular: busca el tamaño más grande que quepa en 5 líneas
    for size in (58, 54, 50, 46, 42, 38):
        f = font("InterDisplay-ExtraBold.otf", size)
        lines = wrap(d, a.title, f, text_w)
        if len(lines) <= 5:
            break
    lh = int(size * 1.14)
    y = 150 + (5 - len(lines)) * lh // 2
    for ln in lines:
        d.text((x0 * S, y * S), ln, font=f, fill=TEXT)
        y += lh

    px, py, pw, ph = 680, 56, 464, 518
    d.rounded_rectangle([px * S, py * S, (px + pw) * S, (py + ph) * S], radius=20 * S, fill=PANEL)

    if a.stat:
        sf = None
        for size in (150, 130, 110, 92, 78, 64):
            sf = font("InterDisplay-Black.otf", size)
            if d.textlength(a.stat, font=sf) <= (pw - 64) * S:
                break
        d.text(((px + 32) * S, (py + 150) * S), a.stat, font=sf, fill=ACCENT)
        lf = font("Inter-Medium.otf", 24)
        yy = py + 150 + int(size * 1.15) + 10
        for ln in wrap(d, a.stat_label, lf, pw - 64):
            d.text(((px + 32) * S, yy * S), ln, font=lf, fill=TEXT)
            yy += 32
    elif a.chips:
        chips = [c.strip() for c in a.chips.split(",") if c.strip()][:6]
        cf = font("InterDisplay-Bold.otf", 34)
        yy = py + (ph - (len(chips) * 78 - 14)) // 2
        for i, c in enumerate(chips):
            tw = d.textlength(c, font=cf) / S
            col = ACCENT if i == 0 else BAR
            d.rounded_rectangle([(px + 32) * S, yy * S, (px + 32 + tw + 40) * S, (yy + 64) * S],
                                radius=14 * S, fill=col)
            d.text(((px + 52) * S, (yy + 12) * S), c, font=cf, fill=TEXT)
            yy += 78
    else:
        # Patrón determinista a partir del título: barras redondeadas
        seed = int(hashlib.md5(a.title.encode()).hexdigest(), 16)
        for i in range(8):
            v = 0.25 + ((seed >> (i * 4)) & 15) / 20
            bw = int((pw - 64) * min(v, 1.0))
            yy = py + 48 + i * 56
            col = ACCENT if i == (seed % 8) else BAR
            d.rounded_rectangle([(px + 32) * S, yy * S, (px + 32 + bw) * S, (yy + 34) * S],
                                radius=10 * S, fill=col)

    img = img.resize((W, H), Image.LANCZOS)
    img.save(a.out, "PNG", optimize=True)
    print("ok", a.out)


if __name__ == "__main__":
    main()
