#!/usr/bin/env python3
"""Ajustes visuales del tema Rehub que no pasan por el contenido.

  python scripts/tema.py --inspeccionar   logo de escritorio y de celular, favicon, rutas REST de Rehub
                                          -> registro/tema-inspeccion.log
"""
import argparse
import importlib.util
import json
import pathlib
import random
import re
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("publish", ROOT / "scripts" / "publish.py")
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)
BASE = "https://www.publi20.com"
LOG = []
MOVIL = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


def log(m):
    print(m, flush=True)
    LOG.append(str(m))


def inspeccionar(wp):
    st = wp.req("GET", "settings")
    log("settings: " + json.dumps({k: v for k, v in st.items() if re.search(r"logo|icon", k)}, ensure_ascii=False))
    idx = requests.get(BASE + "/wp-json/", timeout=40).json()
    log("namespaces: " + ", ".join(n for n in idx.get("namespaces", []) if re.search(r"rehub|wpsoul|redux|theme|customiz|elementor", n)))
    for r in sorted(idx.get("routes", {})):
        if re.search(r"rehub|wpsoul|redux|customiz|global-styles|kit", r):
            log(f"  ruta {r} {idx['routes'][r].get('methods')}")
    for nombre, ua in (("escritorio", "Mozilla/5.0 (X11; Linux x86_64) Chrome/126"), ("movil", MOVIL)):
        h = requests.get(f"{BASE}/?nc={random.randint(1, 10**9)}", headers={"User-Agent": ua, "Cache-Control": "no-cache"}, timeout=40).text
        log(f"== {nombre}: {len(h)} bytes")
        for m in re.finditer(r'<(?:div|span|a)[^>]*(?:logo)[^>]*>.{0,600}', h, re.S | re.I):
            log("  " + re.sub(r"\s+", " ", m.group(0))[:700])
        for src in sorted(set(re.findall(r'(?:src|srcset|data-src)="([^"]*(?:logo|rehub|lightning|icon)[^"]*)"', h, re.I))):
            log(f"  img {src}")
        for m in re.finditer(r'[^{}]*logo_mobile[^{}]*\{[^}]*\}', h):
            log("  css " + re.sub(r"\s+", " ", m.group(0))[:300])
    try:
        th = wp.req("GET", "themes", params={"status": "active", "context": "edit"})
        log("tema: " + json.dumps(th[0].get("theme_supports", {}), ensure_ascii=False)[:1500])
    except Exception as e:  # noqa: BLE001
        log(f"tema: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspeccionar", action="store_true")
    a = ap.parse_args()
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    try:
        inspeccionar(wp)
    except Exception as e:  # noqa: BLE001
        log(f"ERROR: {e}")
    (ROOT / "registro" / "tema-inspeccion.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    sys.exit(0)
