#!/usr/bin/env python3
"""SEO de publi20.com con Rank Math.

  python scripts/seo.py --inspeccionar   rutas de Rank Math en la API, metadatos expuestos, <head> de muestras,
                                         sitemap y robots.txt -> registro/seo-inspeccion.log
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


def log(m):
    print(m, flush=True)
    LOG.append(str(m))


def cabeza(url):
    r = requests.get(url + ("&" if "?" in url else "?") + f"nc={random.randint(1, 10**9)}", timeout=40,
                     headers={"User-Agent": "publi20-seo/1.0", "Cache-Control": "no-cache"})
    h = r.text.split("</head>")[0]
    out = [f"== {url} -> {r.status_code}"]
    for pat in (r"<title>[^<]*</title>", r'<meta name="(?:description|robots)"[^>]*>', r'<link rel="canonical"[^>]*>',
                r'<meta property="og:(?:title|description|image|type)"[^>]*>', r'<meta name="twitter:card"[^>]*>',
                r'<!-- [^>]*(?:Rank Math|Yoast|SEO)[^>]*-->'):
        out += re.findall(pat, h)
    for s in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S)[:2]:
        try:
            g = json.loads(s)
            types = [x.get("@type") for x in g.get("@graph", [g])]
            out.append(f"  schema: {types}")
        except Exception:  # noqa: BLE001
            out.append("  schema: (no JSON)")
    return "\n".join(out)


def inspeccionar(wp):
    idx = requests.get(BASE + "/wp-json/", timeout=40).json()
    rm = sorted(r for r in idx.get("routes", {}) if "rankmath" in r)
    log(f"Namespaces: {[n for n in idx.get('namespaces', []) if 'rank' in n]}")
    for r in rm:
        log(f"  ruta {r} {idx['routes'][r].get('methods')}")
    for pl in wp.req("GET", "plugins"):
        if "rank" in pl["plugin"] or "seo" in pl["plugin"]:
            log(f"plugin {pl['status']}: {pl['plugin']} {pl.get('version')}")
    p = wp.req("GET", "posts", params={"per_page": 1, "context": "edit", "_fields": "id,meta,link"})[0]
    log(f"Meta expuesto en posts: {sorted((p.get('meta') or {}).keys())}")
    sch = wp.s.options(f"{wp.api}/posts", timeout=30).json()
    log(f"Campos de posts: {sorted(sch['schema']['properties'].keys())}")
    for path in ("/", "/publicidad/creatividad/comerciales-prohibidos-censurados/", "/categoria/publicidad/",
                 "/noticias/converse-x-brain-dead/"):
        log(cabeza(BASE + path))
    for path in ("/sitemap_index.xml", "/robots.txt", "/wp-sitemap.xml"):
        r = requests.get(BASE + path, timeout=40, headers={"User-Agent": "publi20-seo/1.0"})
        log(f"== {path} -> {r.status_code}\n{r.text[:1500]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspeccionar", action="store_true")
    a = ap.parse_args()
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    (ROOT / "registro").mkdir(exist_ok=True)
    try:
        if a.inspeccionar:
            inspeccionar(wp)
    except Exception as ex:  # noqa: BLE001
        log(f"ERROR: {ex}")
    (ROOT / "registro" / ("seo-inspeccion.log" if a.inspeccionar else "seo.log")).write_text("\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
    sys.exit(0)
