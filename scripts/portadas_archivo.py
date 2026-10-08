#!/usr/bin/env python3
"""Genera con Gemini las portadas de los comunicados del archivo y las asigna como imagen destacada.

- Recorre content/archivo/*.md en orden de id; salta los que ya tienen images/archivo/<id>.jpg.
- El prompt de cada portada sale del título (escena genérica, sin marcas ni texto), dentro del
  prompt base de docs/sitio.yml.
- Solo cambia la imagen destacada de la entrada (no reenvía el contenido).
- Se detiene limpio cuando la API de Gemini devuelve límite de cuota o de frecuencia.
- Hace commit y push cada --lote imágenes para no perder avance.

Uso: python scripts/portadas_archivo.py [--max 400] [--lote 10]
"""
import argparse
import importlib.util
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "registro" / "portadas-archivo.log"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pub = load("publish")
gi = load("gemini_image")

LIMITE = ("429", "RESOURCE_EXHAUSTED", "quota", "Quota", "rate limit", "Rate limit")


def escena(titulo):
    return ("a realistic scene that evokes the topic of this business news headline without showing it "
            f"literally: \"{titulo}\". Show a generic real-world setting related to the industry (places, "
            "objects, people seen from behind or at a distance). Do not depict any of the companies, brands, "
            "products, packaging or people named in the headline")


def log(msg):
    print(msg, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def guardar(n):
    subprocess.run(["git", "add", "images/archivo", "registro/portadas-archivo.log"], cwd=ROOT, check=False)
    r = subprocess.run(["git", "commit", "-q", "-m", f"Portadas del archivo: {n} nuevas [skip ci]"], cwd=ROOT)
    if r.returncode == 0:
        subprocess.run("git pull --rebase -q origin main && git push -q origin HEAD:main", shell=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=400)
    ap.add_argument("--lote", type=int, default=10)
    a = ap.parse_args()
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    out_dir = ROOT / "images" / "archivo"
    out_dir.mkdir(parents=True, exist_ok=True)
    pendientes = []
    for f in sorted(ROOT.glob("content/archivo/*.md")):
        meta = yaml.safe_load(f.read_text(encoding="utf-8").split("---", 2)[1]) or {}
        if meta.get("status", "publish") != "publish":
            continue
        if not (out_dir / f"archivo-{meta['id']}.jpg").exists():
            pendientes.append(meta)
    log(f"== Inicio: {len(pendientes)} portadas pendientes")
    hechas = 0
    for meta in pendientes[: a.max]:
        out = out_dir / f"archivo-{meta['id']}.jpg"
        try:
            gi.generate({"image_prompt": escena(meta["title"])}, out)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if any(k in msg for k in LIMITE):
                log(f"LÍMITE de la API de Gemini alcanzado tras {hechas} portadas. Se retoma en la siguiente ejecución.")
                break
            log(f"ERROR {meta['id']} generación: {msg[:200]}")
            continue
        try:
            mid = wp.media_id(out, meta["title"][:120])
            wp.req("POST", f"posts/{meta['id']}", json={"featured_media": mid})
            hechas += 1
            log(f"ok {meta['id']} media={mid} {meta['slug'][:70]}")
        except Exception as e:  # noqa: BLE001
            log(f"ERROR {meta['id']} subida: {str(e)[:200]}")
            out.unlink(missing_ok=True)
            continue
        if hechas % a.lote == 0:
            guardar(hechas)
    restantes = len(pendientes) - hechas
    log(f"== Fin: {hechas} nuevas, {restantes} pendientes")
    guardar(hechas)
    sys.exit(0)


if __name__ == "__main__":
    main()
