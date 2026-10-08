#!/usr/bin/env python3
"""Puerta de calidad mínima antes de publicar. Uso: python scripts/lint.py archivo.md [...]

Revisa: frontmatter obligatorio, guiones largos/medios, extensión por formato,
portada existente, enlaces a fuentes, longitud de título y extracto.
Sale con código 1 si hay errores (no avisos).
"""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQ = ["title", "slug", "type", "status", "excerpt"]


_INDEX = None


def slug_index():
    """slug -> fecha (AAAA-MM-DD, o '' para páginas y piezas sin fecha)."""
    global _INDEX
    if _INDEX is None:
        _INDEX = {}
        for p in (ROOT / "content").rglob("*.md"):
            fm = yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1]) or {}
            if fm.get("slug"):
                _INDEX[str(fm["slug"])] = str(fm.get("date", ""))[:10]
    return _INDEX


def check(path):
    errs, warns = [], []
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    meta = yaml.safe_load(fm) or {}
    for k in REQ:
        if not meta.get(k):
            errs.append(f"falta '{k}'")
    if "—" in text or "–" in text:
        errs.append("contiene guion largo o medio")
    plain = re.sub(r"\(https?://[^)]+\)|\(/[^)]*\)|<[^>]+>|```.*?```|\[TOC\]|[#*|`>\[\]-]", " ", body, flags=re.S)
    words = len(plain.split())  # mismo criterio que el texto visible publicado
    sources = len(re.findall(r"\]\(https?://", body))
    if meta.get("type", "post") == "post":
        if not meta.get("date") and meta.get("layout") != "raw":
            warns.append("sin fecha programada")
        cats = [str(c) for c in meta.get("categories") or []]
        portada = meta.get("portada", "plantilla" if "rankings" in cats else "gemini")
        img = meta.get("featured_image")
        if portada == "gemini":
            if not meta.get("image_prompt"):
                errs.append("falta image_prompt para la portada de Gemini")
            elif not img or not (ROOT / img).exists():
                warns.append("la portada se generará con Gemini al publicar")
        elif not img or not (ROOT / img).exists():
            errs.append("falta la portada de plantilla (scripts/cover.py)")
        if words < 900:
            errs.append(f"muy corto ({words} palabras)")
        if sources < 2:
            warns.append(f"pocas fuentes enlazadas ({sources})")
    # Enlaces internos (permalinks /slug/): deben existir y no apuntar a piezas posteriores (darían 404)
    my_date = str(meta.get("date", ""))[:10]
    index = slug_index()
    for target in re.findall(r"\]\(/([^)#?]*)\)", body):
        t = target.strip("/")
        if not t or t.startswith(("categoria/", "wp-content/")):
            continue
        if re.match(r"\d{4}/\d{2}/\d{2}/", t):
            errs.append(f"enlace con fecha en la URL, usa /slug/: /{t}/")
            continue
        if t not in index:
            errs.append(f"enlace interno a una página que no existe en el repo: /{t}/")
        elif my_date and index[t] and index[t] > my_date:
            errs.append(f"enlace interno a una pieza que aún no se publica (/{t}/, {index[t]})")
    if len(str(meta.get("title", ""))) > 80:
        warns.append("título de más de 80 caracteres")
    ex = len(str(meta.get("excerpt", "")))
    if not 120 <= ex <= 170:
        warns.append(f"extracto de {ex} caracteres (ideal 140 a 160)")
    return words, sources, errs, warns


def main():
    bad = 0
    for f in sys.argv[1:]:
        p = pathlib.Path(f)
        words, sources, errs, warns = check(p)
        status = "ERROR" if errs else "ok"
        print(f"{status:5} {p.name}: {words} palabras, {sources} fuentes")
        for e in errs:
            print(f"      x {e}")
        for w in warns:
            print(f"      ! {w}")
        bad += bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
