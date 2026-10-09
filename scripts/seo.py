#!/usr/bin/env python3
"""SEO de publi20.com con Rank Math.

  python scripts/seo.py --inspeccionar   rutas y ajustes de Rank Math -> registro/seo-inspeccion.log
  python scripts/seo.py --aplicar        aplica docs/seo.yml: módulos, ajustes globales (organización, logo, imagen
                                         social, migas, sitemap, robots), SEO de portada, categorías y de cada entrada
                                         publicada (palabra clave, título, descripción, robots, categoría principal).
                                         Verifica el resultado -> registro/seo.log, seo-entradas.csv, seo-verificacion.log
"""
import argparse
import concurrent.futures as cf
import csv
import html
import importlib.util
import json
import pathlib
import random
import re
import sys

import requests
import yaml

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


# ---------------------------------------------------------------- aplicar

CFG = yaml.safe_load((ROOT / "docs" / "seo.yml").read_text(encoding="utf-8"))


def plano(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def corta(s, n=158):
    s = re.sub(r"/\s*PR\s?Newswire[^/]*/", " ", s, flags=re.I)
    # Línea de agencia de los comunicados: "AUSTIN, Texas, 9 de marzo de 2017 ..."
    s = re.sub(r"^[A-ZÁÉÍÓÚÑ][^,]{1,40},(?:\s*[^,]{1,30},)?\s*\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s*[,.:\-]?\s*", "", s)
    s = re.sub(r"\s*[\u2013\u2014]+\s*", ", ", s).strip(" ,")
    if len(s) <= n:
        return s
    s = s[:n]
    return s[:s.rfind(" ")].rstrip(",;:.") + "…"


def exportar(wp):
    code, data = rm(wp, "POST", "status/exportSettings", json={"panels": ["general", "titles", "sitemap"]})
    if code != 200:
        raise RuntimeError(f"exportSettings -> {code}: {str(data)[:200]}")
    return json.loads(data) if isinstance(data, str) else data


def guardar_panel(wp, panel, cambios):
    actual = exportar(wp)[panel]
    nuevo = {**actual, **cambios}
    pendientes = lambda d: [k for k, v in cambios.items() if str(d.get(k)) != str(v)]  # noqa: E731
    if not pendientes(actual):
        log(f"  ajustes {panel}: ya estaban aplicados")
        return True
    intentos = [
        ("updateSettings", {"type": panel, "settings": nuevo, "updated": list(cambios), "isReset": False}),
        ("updateSettings", {"type": panel, "settings": json.dumps(nuevo)}),
        ("status/importSettings", {"data": json.dumps({panel: nuevo})}),
    ]
    for ruta, body in intentos:
        code, res = rm(wp, "POST", ruta, json=body)
        despues = exportar(wp)[panel]
        if len(despues) < len(actual) * 0.8:
            log(f"  AVISO {panel}: {ruta} dejó {len(despues)} de {len(actual)} claves; restauro")
            rm(wp, "POST", ruta, json={**body, "settings": actual} if "settings" in body else {"data": json.dumps({panel: actual})})
            continue
        faltan = pendientes(despues)
        log(f"  ajustes {panel} vía {ruta} -> {code}; sin aplicar: {faltan or 'ninguno'}")
        if not faltan:
            return True
    return False


def gsc():
    out = {}
    for f in csv.DictReader((ROOT / "docs" / "gsc-paginas.csv").open(encoding="utf-8")):
        r = f["ruta"].rstrip("/") or "/"
        c, i = out.get(r, (0, 0))
        out[r] = (c + int(float(f["clics"] or 0)), i + int(float(f["impresiones"] or 0)))
    return out


def ruta(u):
    u = re.sub(r"^https?://(www\.)?publi20\.com", "", u or "")
    return (u.split("?")[0].rstrip("/") or "/")


def aplicar(wp):
    log("== Módulos")
    for m, st in CFG["modulos"].items():
        code, res = rm(wp, "POST", "saveModule", json={"module": m, "state": st})
        log(f"  {m}: {st} -> {code} {str(res)[:80]}")

    log("== Logo e imagen social")
    cambios = {k: dict(v) for k, v in CFG["ajustes"].items()}
    lid = wp.media_id(ROOT / CFG["logo"], "Publi2.0")
    oid = wp.media_id(ROOT / CFG["imagen_social"], "Publi2.0: publicidad, mercadotecnia, negocios y emprendimiento")
    lurl = wp.req("GET", f"media/{lid}")["source_url"]
    ourl = wp.req("GET", f"media/{oid}")["source_url"]
    cambios["titles"].update({"knowledgegraph_logo": lurl, "knowledgegraph_logo_id": lid,
                              "open_graph_image": ourl, "open_graph_image_id": oid})
    log(f"  logo {lurl}\n  imagen social {ourl}")

    log("== Ajustes globales")
    for panel, c in cambios.items():
        if not guardar_panel(wp, panel, c):
            log(f"  ERROR: no pude guardar los ajustes de {panel}")

    log("== Entradas")
    cats = {c["id"]: c for c in paginar(wp, "categories", {"_fields": "id,slug,name,count,parent,description"})}
    por_slug = {c["slug"]: c for c in cats.values()}
    noticias = por_slug.get("noticias", {}).get("id")
    posts = paginar(wp, "posts", {"status": "publish", "_fields": "id,slug,title,link,categories,excerpt"})
    antes = {p["id"]: p["link"] for p in posts}
    datos = gsc()
    legado = {}
    inv = ROOT / "legacy" / "inventario.csv"
    if inv.exists():
        legado = {int(f["id"]): ruta(f["link"]) for f in csv.DictReader(inv.open(encoding="utf-8"))}
    origenes = {}
    for f in csv.DictReader((ROOT / "docs" / "redirecciones.csv").open(encoding="utf-8")):
        origenes.setdefault(ruta(f["destino"]), set()).add(ruta(f["origen"]))
    kws = CFG.get("palabras_clave") or {}

    def una(p):
        titulo = plano(p["title"]["rendered"])
        rutas = {ruta(p["link"]), legado.get(p["id"], "")} - {""}
        for r in list(rutas):
            rutas |= origenes.get(r, set())
        clics = sum(datos.get(r, (0, 0))[0] for r in rutas)
        impr = sum(datos.get(r, (0, 0))[1] for r in rutas)
        es_archivo = noticias in p["categories"] and p["slug"] not in kws
        indexar = not (es_archivo and CFG.get("archivo_noindex_sin_clics") and clics == 0)
        meta = {"rank_math_robots": ["index"] if indexar else ["noindex"]}
        if len(titulo) > 48:
            meta["rank_math_title"] = "%title%"
        ex = corta(plano(p["excerpt"]["rendered"]))
        if ex:
            meta["rank_math_description"] = ex
        if p["slug"] in kws:
            meta["rank_math_focus_keyword"] = kws[p["slug"]]
        seg = ruta(p["link"]).strip("/").split("/")
        if len(seg) >= 2 and seg[-2] in por_slug and por_slug[seg[-2]]["id"] in p["categories"]:
            meta["rank_math_primary_category"] = str(por_slug[seg[-2]]["id"])
        code, res = rm(wp, "POST", "updateMeta", json={"objectType": "post", "objectID": p["id"], "meta": meta})
        return [p["id"], p["link"], "archivo" if es_archivo else "editorial", "index" if indexar else "noindex",
                clics, impr, meta.get("rank_math_focus_keyword", ""), len(titulo), len(ex), code,
                "" if code == 200 else str(res)[:120]]

    with cf.ThreadPoolExecutor(4) as ex:
        filas = list(ex.map(una, posts))
    with (ROOT / "registro" / "seo-entradas.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "url", "tipo", "robots", "clics_gsc", "impresiones_gsc", "palabra_clave", "largo_titulo",
                    "largo_descripcion", "codigo", "error"])
        w.writerows(filas)
    from collections import Counter
    log(f"  {len(filas)} entradas: " + ", ".join(f"{k}={v}" for k, v in Counter((x[2], x[3]) for x in filas).items()))
    log(f"  errores: {sum(1 for x in filas if x[9] != 200)}" + (f" (ej. {next(x[10] for x in filas if x[9] != 200)})"
                                                               if any(x[9] != 200 for x in filas) else ""))

    log("== Portada")
    st = wp.req("GET", "settings")
    pc = CFG["portada"]
    code, res = rm(wp, "POST", "updateMeta", json={"objectType": "post", "objectID": st["page_on_front"], "meta": {
        "rank_math_title": pc["titulo"], "rank_math_description": pc["descripcion"],
        "rank_math_focus_keyword": pc["palabra_clave"], "rank_math_robots": ["index"]}})
    log(f"  página {st['page_on_front']} -> {code}")

    log("== Categorías")
    for sl, c in (CFG.get("categorias") or {}).items():
        t = por_slug.get(sl)
        if not t:
            continue
        desc = plano(t.get("description")) or c.get("descripcion", "")
        if not plano(t.get("description")) and c.get("descripcion"):
            wp.req("POST", f"categories/{t['id']}", json={"description": c["descripcion"]})
        titulo = c["titulo"] if len(c["titulo"]) > 48 else c["titulo"] + " %sep% %sitename%"
        meta = {"rank_math_title": titulo, "rank_math_focus_keyword": c["palabra_clave"]}
        if desc:
            meta["rank_math_description"] = corta(desc)
        code, res = rm(wp, "POST", "updateMeta", json={"objectType": "term", "objectID": t["id"], "meta": meta})
        log(f"  {sl} -> {code}")

    verificar(wp, antes)


def verificar(wp, antes):
    v = []
    despues = {p["id"]: p["link"] for p in paginar(wp, "posts", {"status": "publish", "_fields": "id,link"})}
    cambiadas = [(i, antes[i], despues.get(i)) for i in antes if despues.get(i) != antes[i]]
    v.append(f"URLs de entradas que cambiaron: {len(cambiadas)} {cambiadas[:5]}")
    for path in ("/sitemap_index.xml", "/post-sitemap.xml", "/category-sitemap.xml", "/robots.txt"):
        r = requests.get(BASE + path + f"?nc={random.randint(1, 10**9)}", timeout=40, headers={"User-Agent": "publi20-seo/1.0"})
        cuerpo = r.text if path == "/robots.txt" else f"{r.text.count('<loc>')} URLs"
        v.append(f"== {path} -> {r.status_code} {cuerpo[:600]}")
    muestras = ["/", "/publicidad/creatividad/comerciales-prohibidos-censurados/", "/categoria/publicidad/",
                "/negocios/automotriz/autofintech-mexico/"]
    filas = list(csv.reader((ROOT / "registro" / "seo-entradas.csv").open(encoding="utf-8")))[1:]
    muestras += [ruta(x[1]) + "/" for x in filas if x[3] == "noindex"][:1] + [ruta(x[1]) + "/" for x in filas if x[2] == "archivo" and x[3] == "index"][:1]
    for m in muestras:
        v.append(cabeza(BASE + m))
    (ROOT / "registro" / "seo-verificacion.log").write_text("\n".join(v) + "\n", encoding="utf-8")
    log("\n".join(v[:6]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspeccionar", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args()
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    (ROOT / "registro").mkdir(exist_ok=True)
    try:
        if a.inspeccionar:
            inspeccionar2(wp)
        elif a.aplicar:
            aplicar(wp)
    except Exception as ex:  # noqa: BLE001
        log(f"ERROR: {ex}")
    (ROOT / "registro" / ("seo-inspeccion.log" if a.inspeccionar else "seo.log")).write_text("\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
    sys.exit(0)
