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


def rm(wp, method, path, **kw):
    r = wp.s.request(method, BASE + "/wp-json/rankmath/v1/" + path, timeout=90, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text[:500]


def tapar(o):
    if isinstance(o, dict):
        return {k: ("***" if re.search(r"key|token|secret|password|license", k, re.I) and v else tapar(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [tapar(x) for x in o]
    return o


def inspeccionar2(wp):
    for path in ("updateSettings", "updateMeta", "updateMetaBulk", "saveModule", "toolsAction", "status/exportSettings",
                 "setupWizard/updateStepData", "setupWizard/getStepData", "updateSchemas"):
        r = wp.s.options(BASE + "/wp-json/rankmath/v1/" + path, timeout=40)
        try:
            args = {m["methods"][0]: m.get("args") for m in r.json().get("endpoints", [])}
        except Exception:  # noqa: BLE001
            args = r.text[:200]
        log(f"OPTIONS {path}: {json.dumps(args, ensure_ascii=False)[:1500]}")
    code, data = rm(wp, "POST", "status/exportSettings", json={"panels": ["general", "titles", "sitemap", "role-manager", "redirections"]})
    log(f"exportSettings -> {code}")
    (ROOT / "registro" / "rankmath-ajustes.json").write_text(json.dumps(tapar(data), ensure_ascii=False, indent=1), encoding="utf-8")
    for step in ("yoursite", "optimization", "sitemaps", "schema-markup"):
        code, data = rm(wp, "POST", "setupWizard/getStepData", json={"step": step})
        log(f"getStepData {step} -> {code}: {json.dumps(tapar(data), ensure_ascii=False)[:1500]}")
    code, data = rm(wp, "GET", "")
    log(f"GET rankmath/v1 -> {code}: {str(data)[:300]}")


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
            inspeccionar2(wp)
    except Exception as ex:  # noqa: BLE001
        log(f"ERROR: {ex}")
    (ROOT / "registro" / ("seo-inspeccion.log" if a.inspeccionar else "seo.log")).write_text("\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
    sys.exit(0)
