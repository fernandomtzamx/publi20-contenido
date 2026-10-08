#!/usr/bin/env python3
"""Genera la portada de una nota con Gemini: fotografía editorial, sin texto, sin logos, sin marca de agua visible.

Uso:
    GEMINI_API_KEY=... python scripts/gemini_image.py content/.../nota.md [--force]

Lee del frontmatter:
    image_prompt:   la escena a fotografiar (obligatorio)
    featured_image: ruta de salida (por defecto images/<slug>-portada.jpg)
La configuración (modelo, prompt base, tamaño) vive en docs/sitio.yml > imagenes.

Las imágenes de Gemini incluyen SynthID, una marca de agua invisible de Google que no altera la imagen.
"""
import base64
import io
import os
import pathlib
import sys

import requests
import yaml
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://generativelanguage.googleapis.com/v1beta"


def config():
    cfg = yaml.safe_load((ROOT / "docs" / "sitio.yml").read_text(encoding="utf-8")) or {}
    return cfg.get("imagenes") or {}


def _find_image_b64(obj):
    """Busca la primera imagen en base64 en cualquier forma de respuesta de la API."""
    if isinstance(obj, dict):
        if obj.get("type") == "image" and isinstance(obj.get("data"), str):
            return obj["data"]
        inline = obj.get("inlineData") or obj.get("inline_data")
        if isinstance(inline, dict) and isinstance(inline.get("data"), str):
            return inline["data"]
        for v in obj.values():
            found = _find_image_b64(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_image_b64(v)
            if found:
                return found
    return None


def _call(model, prompt, aspect, size, key):
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    errors = []
    # 1. API de Interactions (formato vigente)
    body = {"model": model, "input": prompt,
            "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": aspect, "image_size": size}}
    r = requests.post(f"{API}/interactions", headers=headers, json=body, timeout=180)
    if r.ok:
        data = _find_image_b64(r.json())
        if data:
            return data
        errors.append(f"interactions sin imagen: {r.text[:200]}")
    else:
        errors.append(f"interactions {r.status_code}: {r.text[:200]}")
    # 2. generateContent (formato clásico)
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}}
    r = requests.post(f"{API}/models/{model}:generateContent", headers=headers, json=body, timeout=180)
    if r.ok:
        data = _find_image_b64(r.json())
        if data:
            return data
        errors.append(f"generateContent sin imagen: {r.text[:200]}")
    else:
        errors.append(f"generateContent {r.status_code}: {r.text[:200]}")
    raise RuntimeError(" | ".join(errors))


def generate(meta, out_path):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("falta el secreto GEMINI_API_KEY")
    scene = str(meta.get("image_prompt", "")).strip()
    if not scene:
        raise RuntimeError("falta image_prompt en el frontmatter")
    cfg = config()
    prompt = cfg.get("prompt_base", "{escena}").replace("{escena}", scene)
    models = [cfg.get("modelo", "gemini-nano-banana-2.1")] + list(cfg.get("modelos_respaldo") or [])
    last = None
    for model in models:
        try:
            data = _call(model, prompt, cfg.get("aspecto", "16:9"), cfg.get("tamano", "2K"), key)
            break
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  ! {model}: {str(e)[:300]}")
    else:
        raise RuntimeError(f"Gemini no generó la imagen: {last}")
    img = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
    w, h = cfg.get("ancho", 1600), cfg.get("alto", 900)
    # Recorte centrado a 16:9 y redimensión
    target = w / h
    if img.width / img.height > target:
        nw = int(img.height * target)
        img = img.crop(((img.width - nw) // 2, 0, (img.width - nw) // 2 + nw, img.height))
    else:
        nh = int(img.width / target)
        img = img.crop((0, (img.height - nh) // 2, img.width, (img.height - nh) // 2 + nh))
    img = img.resize((w, h), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=86, optimize=True, progressive=True)
    print(f"  + portada generada con Gemini ({model}): {out_path.relative_to(ROOT)}")
    return out_path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    for f in args:
        p = ROOT / f
        meta = yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1]) or {}
        out = ROOT / meta.get("featured_image", f"images/{meta['slug']}-portada.jpg")
        if out.exists() and not force:
            print(f"{f}: ya tiene portada ({out.relative_to(ROOT)})")
            continue
        generate(meta, out)


if __name__ == "__main__":
    main()
