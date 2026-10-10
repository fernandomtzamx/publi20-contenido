#!/usr/bin/env python3
"""Categorías del directorio viejo hacia secciones de los rankings (docs/directorio-categorias.yml).

  python scripts/categorias.py --insertar   escribe en cada ranking la sección "Servicios relacionados"
                                            (entre marcadores, se puede volver a correr sin duplicar)
  python scripts/categorias.py --aplicar    crea o reapunta los 301 de cada categoría hacia su ranking y ancla
                                            -> registro/redirecciones-categorias.csv
"""
import argparse
import csv
import importlib.util
import pathlib
import random
import re
import sys

import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "docs" / "directorio-categorias.yml").read_text(encoding="utf-8"))
INI, FIN = "<!-- directorio:inicio -->", "<!-- directorio:fin -->"
HUB = "/categoria/rankings/"


def insertar():
    for ranking, secciones in CFG["secciones"].items():
        f = ROOT / "content" / "rankings" / f"{ranking}.md"
        t = f.read_text(encoding="utf-8")
        t = re.sub(re.escape(INI) + r".*?" + re.escape(FIN) + r"\n*", "", t, flags=re.S)
        bloque = [INI, "", "## Servicios relacionados con este ranking", "",
                  "Si llegaste buscando alguno de estos servicios, esto es lo que conviene saber antes de contratar.", ""]
        for s in secciones:
            bloque += [f"### {s['titulo']} {{#{s['id']}}}", "", s["texto"].strip(), ""]
        bloque += [FIN, "", ""]
        marca = "## Preguntas frecuentes"
        if marca not in t:
            sys.exit(f"{f.name}: no encuentro '{marca}'")
        t = t.replace(marca, "\n".join(bloque) + marca, 1)
        f.write_text(t, encoding="utf-8")
        print(f"{f.name}: {len(secciones)} secciones")


def destino(r, ancla):
    base = HUB if r == "hub" else f"/rankings/{r}/"
    return base + (f"#{ancla}" if ancla else "")


def rutas():
    cats = {c["slug"]: c for c in csv.DictReader((ROOT / "registro" / "directorio-categorias.csv").open(encoding="utf-8"))}

    def cadena(slug):
        out, s = [], slug
        while s:
            out.insert(0, s)
            s = cats.get(s, {}).get("padre", "")
        return out

    filas = [("/directorio/", HUB, "raíz del directorio")]
    for slug, (r, ancla) in CFG["categorias"].items():
        d = destino(r, ancla)
        completa = "/directorio/" + "/".join(cadena(slug)) + "/"
        corta = f"/directorio/{slug}/"
        filas.append((completa, d, f"categoría {slug}"))
        if corta != completa:
            filas.append((corta, d, f"categoría {slug} (ruta corta)"))
    return filas


def aplicar():
    spec = importlib.util.spec_from_file_location("directorio", ROOT / "scripts" / "directorio.py")
    dr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dr)
    pub = dr.pub
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    from urllib.parse import unquote
    items, page = [], 0
    while True:
        lote = dr.red(wp, "GET", "redirect", params={"per_page": 200, "page": page}).get("items", [])
        items += lote
        if len(lote) < 200:
            break
        page += 1
    por_url = {unquote(i["url"]).rstrip("/").lower(): i for i in items}
    grupos = dr.red(wp, "GET", "group", params={"per_page": 200}).get("items", [])
    g = next(x for x in grupos if x["name"] == dr.GRUPO)
    source = {"flag_query": "ignore", "flag_case": True, "flag_trailing": True, "flag_regex": False}
    hechos = []
    for origen, dest, motivo in rutas():
        it = por_url.get(origen.rstrip("/").lower())
        try:
            if it:
                actual = it.get("action_data", {}).get("url", "") if isinstance(it.get("action_data"), dict) else ""
                if actual == dest:
                    hechos.append([origen, dest, motivo, "sin cambio"])
                    continue
                dr.red(wp, "POST", f"redirect/{it['id']}", json={
                    "url": it["url"], "match_type": "url", "action_type": "url", "action_code": 301,
                    "action_data": {"url": dest}, "group_id": it["group_id"], "regex": False, "title": motivo[:50],
                    "position": it.get("position", 0), "status": "enabled", "match_data": {"source": source}})
                hechos.append([origen, dest, motivo, "reapuntada"])
            else:
                dr.red(wp, "POST", "redirect", json={
                    "status": "enabled", "position": 0, "url": origen, "regex": False, "match_type": "url",
                    "match_data": {"source": source}, "title": motivo[:50], "group_id": g["id"],
                    "action_type": "url", "action_code": 301, "action_data": {"url": dest}})
                hechos.append([origen, dest, motivo, "creada"])
        except Exception as e:  # noqa: BLE001
            hechos.append([origen, dest, motivo, f"ERROR {str(e)[:120]}"])
    with (ROOT / "registro" / "redirecciones-categorias.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["origen", "destino", "motivo", "accion"])
        w.writerows(hechos)
    from collections import Counter
    print("Acciones: " + ", ".join(f"{k}={v}" for k, v in Counter(x[3].split(" ")[0] for x in hechos).items()))
    # Verificación: cada categoría responde 301 al ranking correcto y el ranking carga
    malos = 0
    for o, d, *_ in hechos:
        r = requests.get(dr.BASE + o + f"?nc={random.randint(1, 10**9)}", allow_redirects=False, timeout=30,
                         headers={"User-Agent": "publi20-categorias/1.0", "Cache-Control": "no-cache"})
        loc = dr.ruta(r.headers.get("location", ""))
        if r.status_code != 301 or loc.split("#")[0].rstrip("/") != d.split("#")[0].rstrip("/"):
            malos += 1
            if malos <= 8:
                print(f"  FALLA {o} -> {r.status_code} {r.headers.get('location', '')} (esperado {d})")
    print(f"Verificación: {len(hechos) - malos} de {len(hechos)} correctas")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--insertar", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    if a.insertar:
        insertar()
    if a.aplicar:
        aplicar()
