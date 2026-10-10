#!/usr/bin/env python3
"""Directorio viejo (/listing/) hacia los rankings.

  python scripts/directorio.py --inventario   fichas y categorías del directorio -> registro/directorio-fichas.csv,
                                              registro/directorio-categorias.csv
  python scripts/directorio.py --mapa         con docs/directorio-rankings.yml arma registro/mapa-directorio-rankings.csv
                                              (no cambia nada en el sitio)
  python scripts/directorio.py --aplicar      SOLO tras aprobar los rankings: crea los 301 del mapa en Redirection
"""
import argparse
import csv
import importlib.util
import pathlib
import re
import sys

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("publish", ROOT / "scripts" / "publish.py")
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)
BASE = "https://www.publi20.com"
OUT = ROOT / "registro"


def paginar(wp, endpoint, params):
    out, page = [], 1
    while True:
        r = wp.s.get(f"{wp.api}/{endpoint}", params={**params, "per_page": 100, "page": page}, timeout=90)
        if r.status_code == 400:
            break
        r.raise_for_status()
        out += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    return out


def bases(wp):
    types = wp.req("GET", "types")
    taxes = wp.req("GET", "taxonomies")
    t = types.get("listing", {}).get("rest_base")
    x = taxes.get("listing_category", {}).get("rest_base")
    return t, x


def inventario(wp):
    t, x = bases(wp)
    print(f"REST: listing={t} listing_category={x}")
    if not t or not x:
        sys.exit("El tipo listing o su taxonomía no están en la API REST")
    cats = {c["id"]: c for c in paginar(wp, x, {"_fields": "id,slug,name,count,parent"})}
    with (OUT / "directorio-categorias.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "slug", "nombre", "fichas", "padre"])
        for c in sorted(cats.values(), key=lambda c: -c["count"]):
            w.writerow([c["id"], c["slug"], c["name"], c["count"], cats.get(c["parent"], {}).get("slug", "")])
    fichas = paginar(wp, t, {"status": "publish", "_fields": f"id,slug,link,title,content,{x}"})
    with (OUT / "directorio-fichas.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "slug", "url", "nombre", "categorias", "texto"])
        for p in fichas:
            w.writerow([p["id"], p["slug"], p["link"], re.sub(r"<[^>]+>", "", p["title"]["rendered"]),
                        "|".join(cats[c]["slug"] for c in p.get(x, []) if c in cats),
                        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p.get("content", {}).get("rendered", "")))[:700]])
    print(f"{len(cats)} categorías, {len(fichas)} fichas")


def ruta(u):
    return re.sub(r"^https?://(www\.)?publi20\.com", "", u or "").split("?")[0]


def clasificar(texto, reglas, defecto):
    t = texto.lower()
    for rx, dest in reglas:
        if re.search(rx, t):
            return dest
    return defecto


def limpio(t):
    """Quita la plantilla de contacto de la ficha (sitio, correo, teléfono, dirección) para no confundir reglas."""
    t = re.split(r"Sitio web:|Tel[eé]fono:|Email:|Direcci[oó]n:", t)[0]
    return re.sub(r"forma parte de la red de negocios de publicidad de \S+|es un proveedor del giro de la publicidad en mexico"
                  r"|ofrece servicios de publicidad", " ", t, flags=re.I)


def por_estado(texto, cfg):
    t = texto.lower()
    m = re.search(r"originario de ([a-záéíóúñ ]+?)\.", t) or re.search(r"direcci[oó]n:.*?,\s*([a-záéíóúñ ]+),\s*\d{5}", t)
    estado = (m.group(1).strip() if m else "")
    for rx, dest in cfg.get("estados", []):
        if estado and re.search(rx, estado):
            return dest
    return None


def mapa():
    cfg = yaml.safe_load((ROOT / "docs" / "directorio-rankings.yml").read_text(encoding="utf-8"))
    reglas, defecto = cfg["reglas"], cfg["por_defecto"]
    marcas = {k.lower(): v for k, v in (cfg.get("fichas") or {}).items()}
    destino, filas = {}, []
    for f in csv.DictReader((OUT / "directorio-fichas.csv").open(encoding="utf-8")):
        d = marcas.get(f["slug"].lower()) or clasificar(f"{f['slug']} {f['nombre']}", reglas, None) \
            or clasificar(limpio(f.get("texto", "")), reglas, None) or por_estado(f.get("texto", ""), cfg) or defecto
        destino[ruta(f["url"])] = d
        filas.append([ruta(f["url"]), d, "ficha del directorio", f["nombre"]])
    # Reglas viejas que hoy mandan a una ficha: se reapuntan directo al ranking (sin cadenas)
    for r in csv.DictReader((OUT / "auditoria-redirecciones.csv").open(encoding="utf-8")):
        dest = ruta(r["detalle"])
        if dest in destino:
            filas.append([r["origen"], destino[dest], f"regla {r['id']} reapuntada", ""])
    # URLs viejas /proveedores/... (hoy van al pilar): por la categoría de su ruta o su nombre
    for r in csv.DictReader((ROOT / "docs" / "redirecciones.csv").open(encoding="utf-8")):
        if r["origen"].startswith(("/proveedores/", "/directorio")) and "/listing/" not in r["destino"]:
            filas.append([r["origen"], clasificar(r["origen"], reglas, defecto), "URL vieja del directorio", ""])
    with (OUT / "mapa-directorio-rankings.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["origen", "destino", "motivo", "nombre_ficha"])
        w.writerows(filas)
    from collections import Counter
    print(f"{len(filas)} filas")
    for d, n in Counter(x[1] for x in filas).most_common():
        print(f"  {n:5} {d}")


GRUPO = "Directorio a rankings"


def red(wp, method, path, **kw):
    r = wp.s.request(method, f"{wp.api.replace('/wp/v2', '')}/redirection/v1/{path}", timeout=60, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def aplicar(wp):
    """Crea o reapunta los 301 del mapa hacia los rankings publicados. Un ranking que aún no existe se
    sustituye por el más cercano (docs/directorio-rankings.yml > sustitutos); al volver a correr, cuando ya
    esté publicado, sus reglas se reapuntan solas."""
    import concurrent.futures as cf
    from collections import Counter
    cfg = yaml.safe_load((ROOT / "docs" / "directorio-rankings.yml").read_text(encoding="utf-8"))
    cat = next(c for c in wp.req("GET", "categories", params={"slug": "rankings"}))
    publicados = {ruta(p["link"]) for p in paginar(wp, "posts", {"status": "publish", "categories": cat["id"], "_fields": "link"})}
    print(f"Rankings publicados: {len(publicados)}")
    sust = cfg.get("sustitutos") or {}

    def final(d):
        seen = 0
        while d not in publicados and seen < 5:
            d = sust.get(d, cfg["por_defecto"])
            seen += 1
        return d

    # Todas las reglas existentes, por origen
    items, page = [], 0
    while True:
        lote = red(wp, "GET", "redirect", params={"per_page": 200, "page": page}).get("items", [])
        items += lote
        if len(lote) < 200:
            break
        page += 1
    por_url = {}
    for i in items:
        por_url.setdefault(i["url"].rstrip("/"), i)
    grupos = red(wp, "GET", "group", params={"per_page": 200}).get("items", [])
    g = next((x for x in grupos if x["name"] == GRUPO), None)
    if not g:
        res = red(wp, "POST", "group", json={"name": GRUPO, "moduleId": 1, "enabled": True})
        g = next(x for x in res.get("items", []) if x["name"] == GRUPO)
    filas = list(csv.DictReader((OUT / "mapa-directorio-rankings.csv").open(encoding="utf-8")))
    filas.append({"origen": "/listing/", "destino": "/categoria/rankings/", "motivo": "archivo del directorio", "nombre_ficha": ""})
    publicados.add("/categoria/rankings/")
    hechos = []

    def una(f):
        origen = f["origen"]
        destino = final(f["destino"])
        source = {"flag_query": "ignore", "flag_case": True, "flag_trailing": True, "flag_regex": False}
        it = por_url.get(origen.rstrip("/"))
        try:
            if it:
                actual = it.get("action_data", {}).get("url", "") if isinstance(it.get("action_data"), dict) else ""
                if actual == destino and it.get("enabled", True):
                    return [origen, destino, f["destino"], f["motivo"], "sin cambio"]
                body = {"url": it["url"], "match_type": "url", "action_type": "url", "action_code": 301,
                        "action_data": {"url": destino}, "group_id": it["group_id"], "regex": False,
                        "title": it.get("title", ""), "position": it.get("position", 0), "status": "enabled",
                        "match_data": {"source": source}}
                red(wp, "POST", f"redirect/{it['id']}", json=body)
                if not it.get("enabled", True):
                    red(wp, "POST", "bulk/redirect/enable", json={"items": [it["id"]]})
                return [origen, destino, f["destino"], f["motivo"], "reapuntada"]
            body = {"status": "enabled", "position": 0, "url": origen, "regex": False, "match_type": "url",
                    "match_data": {"source": source}, "title": (f.get("nombre_ficha") or f["motivo"])[:50],
                    "group_id": g["id"], "action_type": "url", "action_code": 301, "action_data": {"url": destino}}
            red(wp, "POST", "redirect", json=body)
            return [origen, destino, f["destino"], f["motivo"], "creada"]
        except Exception as e:  # noqa: BLE001
            return [origen, destino, f["destino"], f["motivo"], f"ERROR {str(e)[:120]}"]

    with cf.ThreadPoolExecutor(6) as ex:
        hechos = list(ex.map(una, filas))
    with (OUT / "redirecciones-directorio.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["origen", "destino", "destino_previsto", "motivo", "accion"])
        w.writerows(hechos)
    print("Acciones: " + ", ".join(f"{k}={v}" for k, v in Counter(x[4].split(" ")[0] for x in hechos).items()))
    print("Por destino:")
    for d, n in Counter(x[1] for x in hechos).most_common():
        print(f"  {n:5} {d}")
    # Verificación de una muestra: un salto y destino 200
    import random
    muestra = random.sample([x for x in hechos if not x[4].startswith("ERROR")], min(80, len(hechos)))
    malos = 0
    for o, d, *_ in muestra:
        r = requests.get(BASE + o + f"?nc={random.randint(1, 10**9)}", allow_redirects=False, timeout=30,
                         headers={"User-Agent": "publi20-directorio/1.0", "Cache-Control": "no-cache"})
        loc = ruta(r.headers.get("location", ""))
        ok = r.status_code == 301 and loc.rstrip("/") == d.rstrip("/")
        if ok:
            ok = requests.get(BASE + d, timeout=30, headers={"User-Agent": "publi20-directorio/1.0"}).status_code == 200
        if not ok:
            malos += 1
            if malos <= 5:
                print(f"  FALLA {o} -> {r.status_code} {loc} (esperado {d})")
    print(f"Verificación: {len(muestra) - malos} de {len(muestra)} correctas")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventario", action="store_true")
    ap.add_argument("--mapa", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    if a.inventario:
        wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
        wp.whoami()
        inventario(wp)
    if a.mapa:
        mapa()
    if a.aplicar:
        wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
        wp.whoami()
        aplicar(wp)
