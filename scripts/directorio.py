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


def mapa():
    cfg = yaml.safe_load((ROOT / "docs" / "directorio-rankings.yml").read_text(encoding="utf-8"))
    reglas, defecto = cfg["reglas"], cfg["por_defecto"]
    marcas = {k.lower(): v for k, v in (cfg.get("fichas") or {}).items()}
    destino, filas = {}, []
    for f in csv.DictReader((OUT / "directorio-fichas.csv").open(encoding="utf-8")):
        d = marcas.get(f["slug"].lower()) or clasificar(f"{f['slug']} {f['nombre']}", reglas, None) \
            or clasificar(f.get("texto", ""), reglas, defecto)
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventario", action="store_true")
    ap.add_argument("--mapa", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    if a.aplicar:
        sys.exit("Aplicar queda bloqueado hasta que se aprueben los rankings (falta implementar con el mapa final).")
    if a.inventario:
        wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
        wp.whoami()
        inventario(wp)
    if a.mapa:
        mapa()
