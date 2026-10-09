#!/usr/bin/env python3
"""Portada de publi20.com como medio editorial.

  python scripts/home.py --inspeccionar   solo escribe registro/home-inspeccion.log (tema, plantillas, menús, plugins)
  python scripts/home.py                  arma la portada con las notas publicadas y la aplica:
                                          página "portada" (bloque HTML), portada estática, lema y menú principal

Reglas: sin directorio, con los cuatro pilares, notas patrocinadas señaladas, enlaces externos nofollow,
paleta de Publi2.0 (negro, rojo #EA3322, blanco y grises). La configuración vive en docs/home.yml.
"""
import argparse
import html
import importlib.util
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("publish", ROOT / "scripts" / "publish.py")
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)
CFG = yaml.safe_load((ROOT / "docs" / "home.yml").read_text(encoding="utf-8"))
LOG = []
MARCA = "p20-home"


def log(m):
    print(m, flush=True)
    LOG.append(str(m))


def paginar(wp, endpoint, params):
    out, page = [], 1
    while True:
        r = wp.s.get(f"{wp.api}/{endpoint}", params={**params, "per_page": 100, "page": page}, timeout=60)
        if r.status_code == 400:
            break
        r.raise_for_status()
        out += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    return out


def texto(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def corta(s, n):
    if len(s) <= n:
        return s
    s = s[:n]
    return s[:s.rfind(" ")].rstrip(",;:.") + "…"


def e(s):
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- inspección

def inspeccionar(wp):
    try:
        th = wp.req("GET", "themes", params={"status": "active"})
        log("Tema activo: " + ", ".join(f"{t['stylesheet']} ({texto(t['name'].get('rendered', '') if isinstance(t['name'], dict) else t['name'])}) "
                                        f"plantilla={t.get('template')} bloques={t.get('is_block_theme')}" for t in th))
    except Exception as ex:  # noqa: BLE001
        log(f"Tema: {ex}")
    st = wp.req("GET", "settings")
    log("Ajustes: " + json.dumps({k: st.get(k) for k in ("title", "description", "show_on_front", "page_on_front",
                                                         "page_for_posts", "posts_per_page")}, ensure_ascii=False))
    try:
        sch = wp.s.options(f"{wp.api}/pages", timeout=30).json()
        tpl = sch["schema"]["properties"]["template"].get("enum")
        log(f"Plantillas de página: {tpl}")
    except Exception as ex:  # noqa: BLE001
        log(f"Plantillas: {ex}")
    if st.get("page_on_front"):
        p = wp.req("GET", f"pages/{st['page_on_front']}", params={"context": "edit"})
        log(f"Portada actual: id {p['id']} slug={p['slug']} estado={p['status']} plantilla={p.get('template')} "
            f"título={texto(p['title']['raw'])} elementor={'elementor' in json.dumps(p.get('meta', {}))}")
    pages = paginar(wp, "pages", {"status": "publish,draft,private", "context": "edit", "_fields": "id,slug,status,title,template,link"})
    for p in pages:
        log(f"  página {p['id']} {p['status']} {p['slug']} [{p.get('template')}] {texto(p['title']['raw'])} {p['link']}")
    try:
        for pl in wp.req("GET", "plugins"):
            log(f"  plugin {pl['status']}: {pl['plugin']} {pl.get('version')}")
    except Exception as ex:  # noqa: BLE001
        log(f"Plugins: {ex}")
    try:
        locs = wp.req("GET", "menu-locations")
        log("Ubicaciones de menú: " + json.dumps({k: (v.get("description"), v.get("menu")) for k, v in locs.items()}, ensure_ascii=False))
        for m in wp.req("GET", "menus", params={"context": "edit"}):
            log(f"  menú {m['id']} {m['name']} ubicaciones={m.get('locations')}")
            for it in wp.req("GET", "menu-items", params={"menus": m["id"], "per_page": 100, "context": "edit"}):
                log(f"    - {it['id']} {texto(it['title'].get('raw', ''))} {it.get('type')} {it.get('url')} padre={it.get('parent')}")
    except Exception as ex:  # noqa: BLE001
        log(f"Menús: {ex}")
    cats = paginar(wp, "categories", {"_fields": "id,slug,name,count,parent,link"})
    log("Categorías: " + ", ".join(f"{c['slug']}({c['count']})" for c in cats if c["count"]))


# ---------------------------------------------------------------- datos

def datos(wp):
    cats = {c["id"]: c for c in paginar(wp, "categories", {"_fields": "id,slug,name,count,parent,link"})}
    por_slug = {c["slug"]: c for c in cats.values()}
    tags = paginar(wp, "tags", {"search": "patrocinado", "_fields": "id,slug,name"})
    patro = {t["id"] for t in tags if "patrocinado" in t["slug"]}
    posts = paginar(wp, "posts", {"status": "publish", "_fields": "id,slug,title,link,date,excerpt,categories,tags,featured_media"})
    ids = sorted({p["featured_media"] for p in posts if p["featured_media"]})
    media = {}
    for k in range(0, len(ids), 100):
        for m in wp.req("GET", "media", params={"include": ",".join(map(str, ids[k:k + 100])), "per_page": 100,
                                                "_fields": "id,source_url,alt_text,media_details"}):
            media[m["id"]] = m
    return cats, por_slug, patro, posts, media


def raiz(cats, cid):
    c = cats.get(cid)
    while c and c.get("parent"):
        c = cats.get(c["parent"])
    return c


def imagen(media, p, tam):
    m = media.get(p["featured_media"])
    if not m:
        return None
    sizes = (m.get("media_details") or {}).get("sizes") or {}
    for t in tam:
        if t in sizes:
            s = sizes[t]
            return s["source_url"], s.get("width"), s.get("height"), m.get("alt_text") or ""
    md = m.get("media_details") or {}
    return m["source_url"], md.get("width"), md.get("height"), m.get("alt_text") or ""


# ---------------------------------------------------------------- HTML

def armar(cats, por_slug, patro, posts, media):
    noticias = por_slug.get("noticias", {}).get("id")
    rankings = por_slug.get("rankings", {}).get("id")
    es_patro = lambda p: bool(patro & set(p["tags"]))  # noqa: E731
    editoriales = [p for p in posts if noticias not in p["categories"] and rankings not in p["categories"]]
    editoriales.sort(key=lambda p: p["date"], reverse=True)
    archivo = sorted([p for p in posts if noticias in p["categories"] and p not in editoriales],
                     key=lambda p: p["date"], reverse=True)
    ranks = sorted([p for p in posts if rankings in p["categories"]], key=lambda p: p["date"], reverse=True)

    def seccion(p):
        """Subsección (o pilar) más específica de la nota, sin contar Noticias."""
        cs = [cats[c] for c in p["categories"] if c in cats and c != noticias]
        hijas = [c for c in cs if c.get("parent")]
        return (hijas or cs or [None])[0]

    def kicker(p):
        c = seccion(p)
        k = f'<a class="p20-h-kicker" href="{e(c["link"])}">{e(c["name"])}</a>' if c else ""
        if es_patro(p):
            k += '<span class="p20-h-patro">Patrocinado</span>'
        return f'<div class="p20-h-meta">{k}</div>' if k else ""

    def foto(p, tam, clase, prioridad=False):
        im = imagen(media, p, tam)
        if not im:
            return f'<a class="{clase} p20-h-sinfoto" href="{e(p["link"])}" tabindex="-1" aria-hidden="true"></a>'
        url, w, h, alt = im
        carga = 'fetchpriority="high"' if prioridad else 'loading="lazy"'
        dims = f' width="{w}" height="{h}"' if w and h else ""
        return (f'<a class="{clase}" href="{e(p["link"])}" tabindex="-1" aria-hidden="true">'
                f'<img src="{e(url)}" alt="{e(alt)}"{dims} {carga} decoding="async"></a>')

    def tarjeta(p, tam=("medium_large", "large", "full"), extracto=True):
        t = texto(p["title"]["rendered"])
        ex = f'<p class="p20-h-ex">{e(corta(texto(p["excerpt"]["rendered"]), 140))}</p>' if extracto else ""
        return (f'<article class="p20-h-card">{foto(p, tam, "p20-h-img")}{kicker(p)}'
                f'<h3 class="p20-h-t"><a href="{e(p["link"])}">{e(t)}</a></h3>{ex}</article>')

    def elegir(cands, n):
        """Hasta n notas por fecha, con una patrocinada como máximo por bloque (puede devolver menos)."""
        propias = [p for p in cands if not es_patro(p)]
        patros = [p for p in cands if es_patro(p)][:1]
        sel = propias[: n - 1] + patros if patros else propias[:n]
        if len(sel) < n:
            sel += [p for p in propias if p not in sel][: n - len(sel)]
        return sorted(sel, key=lambda p: p["date"], reverse=True)

    usados = set()
    dest = next((p for p in editoriales if p["slug"] == (CFG.get("destacada") or "")), None)
    if not dest:
        dest = next((p for p in editoriales if not es_patro(p)), editoriales[0] if editoriales else None)
    if not dest:
        raise RuntimeError("No hay notas editoriales publicadas para armar la portada")
    usados.add(dest["id"])
    laterales = elegir([p for p in editoriales if p["id"] not in usados], 4)
    usados |= {p["id"] for p in laterales}

    h = []
    h.append(f'<header class="p20-h-masthead"><p class="p20-h-sobre">Revista digital · México</p>'
             f'<h1>{e(CFG["h1"])}</h1><p class="p20-h-entrada">{e(CFG["entradilla"])}</p>'
             '<nav class="p20-h-pilares" aria-label="Secciones">'
             + "".join(f'<a href="{e(por_slug[x["slug"]]["link"])}">{e(por_slug[x["slug"]]["name"])}</a>'
                       for x in CFG["pilares"] if x["slug"] in por_slug)
             + (f'<a href="{e(por_slug["rankings"]["link"])}">Rankings</a>' if ranks else "")
             + "</nav></header>")

    t = texto(dest["title"]["rendered"])
    lateral = "".join(
        f'<li>{foto(p, ("medium", "thumbnail"), "p20-h-mini")}<div>{kicker(p)}'
        f'<h3 class="p20-h-t"><a href="{e(p["link"])}">{e(texto(p["title"]["rendered"]))}</a></h3></div></li>'
        for p in laterales)
    h.append('<section class="p20-h-portada" aria-label="Lo más reciente">'
             f'<article class="p20-h-lead">{foto(dest, ("large", "full", "medium_large"), "p20-h-img", True)}'
             f'<div class="p20-h-leadtxt">{kicker(dest)}<h2 class="p20-h-t"><a href="{e(dest["link"])}">{e(t)}</a></h2>'
             f'<p class="p20-h-ex">{e(corta(texto(dest["excerpt"]["rendered"]), 220))}</p>'
             '<p class="p20-h-firma">Por Fernando Martínez</p></div></article>'
             f'<div class="p20-h-side"><h2 class="p20-h-label">Lo más reciente</h2><ul>{lateral}</ul></div></section>')

    for i, x in enumerate(CFG["pilares"]):
        c = por_slug.get(x["slug"])
        if not c:
            continue
        familia = {c["id"]} | {k for k, v in cats.items() if raiz(cats, k) and raiz(cats, k)["id"] == c["id"]}
        propias = [p for p in editoriales if familia & set(p["categories"])]
        lista = elegir([p for p in propias if p["id"] not in usados], 3)
        if len(lista) < 3:
            lista += [p for p in archivo if familia & set(p["categories"]) and p not in lista][: 3 - len(lista)]
        if len(lista) < 3:
            lista += [p for p in propias if p not in lista][: 3 - len(lista)]
        if not lista:
            continue
        usados |= {p["id"] for p in lista}
        subs = [v for v in cats.values() if v.get("parent") == c["id"] and v["count"]]
        chips = "".join(f'<a href="{e(v["link"])}">{e(v["name"])}</a>' for v in sorted(subs, key=lambda v: -v["count"]))
        h.append(f'<section class="p20-h-pilar{" p20-h-alt" if i % 2 else ""}" aria-labelledby="p20-{c["slug"]}">'
                 f'<div class="p20-h-cab"><div><h2 id="p20-{c["slug"]}"><a href="{e(c["link"])}">{e(c["name"])}</a></h2>'
                 f'<p>{e(x["bajada"])}</p></div><a class="p20-h-mas" href="{e(c["link"])}">Ver {e(c["name"].lower())} →</a></div>'
                 + (f'<nav class="p20-h-subs" aria-label="{e(c["name"])}">{chips}</nav>' if chips else "")
                 + f'<div class="p20-h-grid">{"".join(tarjeta(p) for p in lista)}</div></section>')

    if ranks:
        h.append('<section class="p20-h-pilar" aria-labelledby="p20-rankings"><div class="p20-h-cab"><div>'
                 f'<h2 id="p20-rankings"><a href="{e(por_slug["rankings"]["link"])}">Rankings</a></h2>'
                 '<p>Con metodología pública. Nadie paga por aparecer.</p></div>'
                 f'<a class="p20-h-mas" href="{e(por_slug["rankings"]["link"])}">Ver rankings →</a></div>'
                 f'<div class="p20-h-grid">{"".join(tarjeta(p) for p in ranks[:3])}</div></section>')

    v = CFG["video"]
    h.append(f'<section class="p20-h-video"><div><p class="p20-h-sobre">YouTube</p><h2>{e(v["titulo"])}</h2>'
             f'<p>{e(v["texto"])}</p></div><a class="p20-h-btn" href="{e(v["canal"])}" rel="nofollow noopener" '
             'target="_blank">Ver el canal de Publi2.0</a></section>')

    if archivo:
        items = "".join(f'<li><span class="p20-h-anio">{p["date"][:4]}</span>'
                        f'<a href="{e(p["link"])}">{e(texto(p["title"]["rendered"]))}</a></li>' for p in [x for x in archivo if x["id"] not in usados][:8])
        h.append('<section class="p20-h-archivo" aria-labelledby="p20-archivo"><div class="p20-h-cab"><div>'
                 '<h2 id="p20-archivo"><a href="' + e(por_slug["noticias"]["link"]) + '">Archivo de noticias</a></h2>'
                 '<p>Comunicados y lanzamientos de la industria que conservamos como referencia.</p></div>'
                 f'<a class="p20-h-mas" href="{e(por_slug["noticias"]["link"])}">Ver el archivo →</a></div>'
                 f'<ol>{items}</ol></section>')

    s = CFG["sobre"]
    h.append(f'<section class="p20-h-about"><h2>{e(s["titulo"])}</h2><p>{e(s["texto"])}</p></section>')

    css = (ROOT / "scripts" / "home.css").read_text(encoding="utf-8")
    css = re.sub(r"\s*\n\s*", "", css)
    cuerpo = f'<style>{css}</style><div class="{MARCA}">{"".join(h)}</div>'
    return "<!-- wp:html -->\n" + cuerpo + "\n<!-- /wp:html -->", dest, laterales


# ---------------------------------------------------------------- aplicar

def plantilla(wp):
    try:
        enum = wp.s.options(f"{wp.api}/pages", timeout=30).json()["schema"]["properties"]["template"].get("enum") or []
    except Exception:  # noqa: BLE001
        enum = []
    for pref in ("elementor_header_footer", "page-templates/full-width.php", "template-fullwidth.php"):
        if pref in enum:
            return pref
    full = [t for t in enum if t and re.search(r"full|ancho|wide", t, re.I)]
    # Rehub no publica la lista de plantillas en la API; Elementor registra elementor_header_footer
    # (ancho completo con el encabezado y pie del tema, sin título de página).
    return full[0] if full else "elementor_header_footer"


def menu(wp, por_slug, hay_rankings):
    locs = wp.req("GET", "menu-locations")
    principal = next((k for k in locs if re.search(r"primary|main|principal", k, re.I)), None)
    if not principal:
        log(f"Menú: no encontré ubicación principal entre {list(locs)}; no se cambió")
        return
    mid = locs[principal].get("menu")
    if not mid:
        mid = wp.req("POST", "menus", json={"name": "Principal", "locations": [principal]})["id"]
    for it in wp.req("GET", "menu-items", params={"menus": mid, "per_page": 100, "context": "edit"}):
        wp.req("DELETE", f"menu-items/{it['id']}", params={"force": "true"})
    orden = 1
    wp.req("POST", "menu-items", json={"menus": mid, "title": "Inicio", "type": "custom",
                                       "url": wp.api.split("/wp-json")[0] + "/", "status": "publish", "menu_order": orden})
    slugs = [x["slug"] for x in CFG["pilares"]] + (["rankings"] if hay_rankings else []) + ["noticias"]
    for sl in slugs:
        c = por_slug.get(sl)
        if not c:
            continue
        orden += 1
        wp.req("POST", "menu-items", json={"menus": mid, "title": c["name"], "type": "taxonomy", "object": "category",
                                           "object_id": c["id"], "status": "publish", "menu_order": orden})
    usadas = [k for k, v in locs.items() if v.get("menu") == mid] or [principal]
    log(f"Menú {mid} con {orden} elementos ({', '.join(['Inicio'] + slugs)}) en {usadas}")


def aplicar(wp):
    cats, por_slug, patro, posts, media = datos(wp)
    contenido, dest, lat = armar(cats, por_slug, patro, posts, media)
    (ROOT / "registro").mkdir(exist_ok=True)
    (ROOT / "registro" / "home-contenido.html").write_text(contenido, encoding="utf-8")
    log(f"Portada armada con {len(posts)} entradas publicadas. Principal: {texto(dest['title']['rendered'])}")
    st = wp.req("GET", "settings")
    anterior = st.get("page_on_front") if st.get("show_on_front") == "page" else 0
    tpl = plantilla(wp)
    payload = {"title": CFG["titulo"], "slug": CFG["pagina_slug"], "content": contenido, "status": "publish",
               "comment_status": "closed", "ping_status": "closed", "author": pub.author_id(wp),
               "excerpt": CFG["entradilla"], "template": tpl}
    existente = wp.find_by_slug("pages", CFG["pagina_slug"])
    if not existente:
        existente = wp.find_by_slug("pages", CFG["pagina_slug"] + "-publi20")
    if existente and MARCA not in existente["content"]["raw"] and existente["id"] == anterior:
        existente = None  # no sobrescribir la portada anterior si casualmente usa el mismo slug
    ruta = f"pages/{existente['id']}" if existente else "pages"
    try:
        pag = wp.req("POST", ruta, json=payload)
    except RuntimeError as ex:
        log(f"Aviso al guardar con plantilla '{tpl}': {str(ex)[:160]}; reintento con la plantilla del tema")
        payload["template"] = ""
        pag = wp.req("POST", ruta, json=payload)
    log(f"Página de portada: id {pag['id']} plantilla='{tpl}' {pag['link']}")
    wp.req("POST", "settings", json={"show_on_front": "page", "page_on_front": pag["id"],
                                     "title": CFG["titulo"], "description": CFG["lema"]})
    log(f"Portada estática = página {pag['id']}; título del sitio = {CFG['titulo']}; lema = {CFG['lema']}")
    if anterior and anterior != pag["id"] and CFG.get("retirar_portada_anterior"):
        old = wp.req("POST", f"pages/{anterior}", json={"status": "draft"})
        log(f"Portada anterior (id {anterior}, {old['slug']}) pasada a borrador")
    try:
        menu(wp, por_slug, any(por_slug.get("rankings", {}).get("id") in p["categories"] for p in posts))
    except Exception as ex:  # noqa: BLE001
        log(f"Menú: {str(ex)[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspeccionar", action="store_true")
    a = ap.parse_args()
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    out = ROOT / "registro"
    out.mkdir(exist_ok=True)
    try:
        if a.inspeccionar:
            inspeccionar(wp)
            (out / "home-inspeccion.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")
        else:
            aplicar(wp)
            (out / "home.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    except Exception as ex:  # noqa: BLE001
        log(f"ERROR: {ex}")
        (out / ("home-inspeccion.log" if a.inspeccionar else "home.log")).write_text("\n".join(LOG) + "\n", encoding="utf-8")
        sys.exit(1)


if __name__ == "__main__":
    main()
