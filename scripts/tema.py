#!/usr/bin/env python3
"""Ajustes visuales del tema Rehub que no pasan por el contenido.

  python scripts/tema.py --inspeccionar   logo de escritorio y de celular, favicon, rutas REST de Rehub
                                          -> registro/tema-inspeccion.log
  python scripts/tema.py --aplicar        logo de Publi2.0 en la versión móvil

El logo móvil y el del panel móvil son opciones de Rehub (no están en la API) y quedaron apuntando a las
imágenes del demo del tema (remag.wpsoul.net). Mientras no se cambien en Rehub > Theme Options, un widget
HTML invisible en el pie (presente en todas las páginas) reemplaza cualquier imagen del demo por el logo
de Publi2.0: con CSS (content: url) desde el primer pintado y con JS como respaldo.
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


MARCA = "publi20-logo-movil"
LOGO = "https://www.publi20.com/wp-content/uploads/2021/07/publi20-1.png"


def bloque(wid=""):
    oculto = f"#{wid}{{display:none!important}}" if wid else ""
    return (f"<!-- {MARCA} -->\n<style>{oculto}"
            f'img[src*="remag.wpsoul.net"]{{content:url("{LOGO}");object-fit:contain;width:auto!important;'
            "max-width:150px;height:32px!important}"
            "#mobpanelimg{height:40px!important;max-width:170px}</style>\n"
            "<script>(function(){function f(){document.querySelectorAll('img[src*=\"remag.wpsoul.net\"]')"
            f".forEach(function(i){{i.src='{LOGO}';i.removeAttribute('srcset');i.alt='Publi2.0';}});}}"
            "f();document.addEventListener('DOMContentLoaded',f);})();</script>")


CONTACTO = "contacto@publi20.com"
MARCA_CONTACTO = "publi20-contacto-editorial"


def contacto(wp, widgets, ids):
    """Bloque visible en el pie de todas las páginas con el contacto editorial y de redacción."""
    destino = "footersecond" if "footersecond" in ids else "footerfirst"
    html = (f'<!-- {MARCA_CONTACTO} --><p style="margin:0 0 6px">Para propuestas de nota, correcciones y datos de rankings:</p>'
            f'<p style="margin:0"><a href="mailto:{CONTACTO}" style="color:#ea3322;font-weight:700">{CONTACTO}</a></p>')
    body = {"id_base": "custom_html", "sidebar": destino,
            "instance": {"raw": {"title": "Contacto editorial y redacción", "content": html}}}
    previo = next((w for w in widgets if MARCA_CONTACTO in json.dumps(w.get("instance", {}))), None)
    w = wp.req("POST", f"widgets/{previo['id']}", json=body) if previo else wp.req("POST", "widgets", json=body)
    log(f"contacto editorial: widget {w['id']} en {w['sidebar']} ({CONTACTO})")


VIEJO = "fernando@publi20.com"


def reemplazar_correo(wp):
    """Cambia el correo viejo por el de contacto en entradas, páginas, fichas y widgets del sitio."""
    total = 0
    for tipo in ("posts", "pages", "listing"):
        page = 1
        while True:
            r = wp.s.get(f"{wp.api}/{tipo}", timeout=60, params={"search": VIEJO, "status": "any", "context": "edit",
                         "per_page": 100, "page": page, "_fields": "id,content,excerpt"})
            if r.status_code >= 400:
                break
            items = r.json()
            for it in items:
                body = {}
                for campo in ("content", "excerpt"):
                    raw = (it.get(campo) or {}).get("raw", "")
                    if VIEJO in raw:
                        body[campo] = raw.replace(VIEJO, CONTACTO)
                if body:
                    wp.req("POST", f"{tipo}/{it['id']}", json=body)
                    total += 1
            if page >= int(r.headers.get("X-WP-TotalPages", 1)):
                break
            page += 1
    for w in wp.req("GET", "widgets", params={"context": "edit", "per_page": 100}):
        raw = w.get("instance", {}).get("raw")
        if raw and VIEJO in json.dumps(raw):
            nuevo = json.loads(json.dumps(raw).replace(VIEJO, CONTACTO))
            wp.req("POST", f"widgets/{w['id']}", json={"instance": {"raw": nuevo}})
            total += 1
    log(f"correo {VIEJO} -> {CONTACTO}: {total} elementos actualizados")


def aplicar(wp):
    sidebars = wp.req("GET", "sidebars", params={"context": "edit"})
    log("sidebars: " + ", ".join(f"{b['id']}({b.get('name')}, {len(b.get('widgets', []))})" for b in sidebars))
    widgets = wp.req("GET", "widgets", params={"context": "edit", "per_page": 100})
    previo = next((w for w in widgets if MARCA in json.dumps(w.get("instance", {}))), None)
    # El pie (Pie de página 1) se pinta en todas las páginas, incluida la portada.
    ids = [b["id"] for b in sidebars]
    destino = "footerfirst" if "footerfirst" in ids else next(i for i in ids if "foot" in i.lower())
    log(f"barra elegida: {destino}")
    body = {"id_base": "custom_html", "sidebar": destino, "instance": {"raw": {"title": "", "content": bloque()}}}
    w = wp.req("POST", f"widgets/{previo['id']}", json=body) if previo else wp.req("POST", "widgets", json=body)
    body["instance"]["raw"]["content"] = bloque(w["id"])
    w = wp.req("POST", f"widgets/{w['id']}", json=body)
    log(f"widget {w['id']} en {w['sidebar']} con el logo {LOGO}")
    contacto(wp, widgets, ids)
    reemplazar_correo(wp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspeccionar", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    try:
        aplicar(wp) if a.aplicar else inspeccionar(wp)
    except Exception as e:  # noqa: BLE001
        log(f"ERROR: {e}")
    (ROOT / "registro" / ("tema.log" if a.aplicar else "tema-inspeccion.log")).write_text("\n".join(LOG) + "\n", encoding="utf-8")
    sys.exit(0)
