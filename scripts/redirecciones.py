#!/usr/bin/env python3
"""Revisión y aplicación de redirecciones 301 en publi20.com.

  python scripts/redirecciones.py --revisar
      Lee docs/urls-a-revisar.txt (una ruta por línea), consulta cada una siguiendo redirecciones
      y escribe registro/urls-revision.csv (ruta, código inicial, código final, URL final, saltos).

  python scripts/redirecciones.py --aplicar
      Asegura que el plugin Redirection esté instalado y activo, crea el grupo
      "Publi2.0 remediación" y da de alta cada fila de docs/redirecciones.csv (origen, destino, motivo)
      que no exista ya. Todas son 301. Registro en registro/redirecciones.log.
"""
import argparse
import concurrent.futures as cf
import csv
import importlib.util
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
GRUPO = "Publi2.0 remediación"


def revisar():
    rutas = [l.strip() for l in (ROOT / "docs" / "urls-a-revisar.txt").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.startswith("#")]
    s = requests.Session()
    s.headers["User-Agent"] = "publi20-revision/1.0"

    def uno(ruta):
        url = ruta if ruta.startswith("http") else BASE + ruta
        # Parámetro aleatorio para saltar la caché de páginas del sitio (Redirection ignora la query).
        url += ("&" if "?" in url else "?") + f"nc={random.randint(1, 10**9)}"
        try:
            r = s.get(url, timeout=25, allow_redirects=True, headers={"Cache-Control": "no-cache"})
            first = r.history[0].status_code if r.history else r.status_code
            final = re.sub(r"[?&]nc=\d+$", "", r.url.replace(BASE, ""))
            return [ruta, first, r.status_code, final, len(r.history)]
        except Exception as e:  # noqa: BLE001
            return [ruta, "error", "error", str(e)[:80], 0]

    with cf.ThreadPoolExecutor(8) as ex:
        filas = list(ex.map(uno, rutas))
    out = ROOT / "registro" / "urls-revision.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ruta", "codigo_inicial", "codigo_final", "url_final", "saltos"])
        w.writerows(filas)
    malos = sum(1 for f in filas if f[2] != 200)
    print(f"Revisadas {len(filas)} rutas; {malos} no terminan en 200")


def asegurar_plugin(wp, log):
    plugins = wp.req("GET", "plugins")
    red = [p for p in plugins if p["plugin"].startswith("redirection/")]
    if not red:
        p = wp.req("POST", "plugins", json={"slug": "redirection", "status": "active"})
        log(f"Plugin Redirection instalado y activado ({p.get('version')})")
    elif red[0]["status"] != "active":
        wp.req("POST", f"plugins/{red[0]['plugin']}", json={"status": "active"})
        log("Plugin Redirection activado")
    else:
        log(f"Plugin Redirection ya activo ({red[0].get('version')})")


def red(wp, method, path, **kw):
    r = wp.s.request(method, f"{wp.api.replace('/wp/v2', '')}/redirection/v1/{path}", timeout=60, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def aplicar():
    logf = ROOT / "registro" / "redirecciones.log"
    lines = []

    def log(m):
        print(m, flush=True)
        lines.append(m)

    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    errores = 0
    try:
        asegurar_plugin(wp, log)
        ajustes = red(wp, "GET", "setting")
        log(f"Redirection instalado: {ajustes.get('installed', '?')}")
        grupos = red(wp, "GET", "group", params={"per_page": 200}).get("items", [])
        g = next((x for x in grupos if x["name"] == GRUPO), None)
        if not g:
            res = red(wp, "POST", "group", json={"name": GRUPO, "moduleId": 1, "enabled": True})
            g = next(x for x in res.get("items", []) if x["name"] == GRUPO)
            log(f"Grupo creado: {GRUPO} (id {g['id']})")
        existentes = set()
        page = 0
        while True:
            res = red(wp, "GET", "redirect", params={"per_page": 200, "page": page})
            items = res.get("items", [])
            existentes |= {i["url"] for i in items}
            if len(items) < 200:
                break
            page += 1
        filas = list(csv.DictReader((ROOT / "docs" / "redirecciones.csv").open(encoding="utf-8")))
        nuevas = 0
        for f in filas:
            origen, destino = f["origen"].strip(), f["destino"].strip()
            if not origen or origen in existentes or origen == destino:
                continue
            body = {"status": "enabled", "position": 0, "url": origen, "regex": False, "match_type": "url",
                    "match_data": {"source": {"flag_query": "ignore", "flag_case": True, "flag_trailing": True,
                                              "flag_regex": False}},
                    "title": f.get("motivo", "")[:50], "group_id": g["id"], "action_type": "url",
                    "action_code": 301, "action_data": {"url": destino}}
            try:
                red(wp, "POST", "redirect", json=body)
                existentes.add(origen)
                nuevas += 1
            except Exception as e:  # noqa: BLE001
                errores += 1
                log(f"ERROR {origen}: {str(e)[:200]}")
        log(f"Redirecciones nuevas: {nuevas}; ya existían u omitidas: {len(filas) - nuevas - errores}; errores: {errores}")
    except Exception as e:  # noqa: BLE001
        errores += 1
        log(f"ERROR general: {e}")
    logf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revisar", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    if a.revisar:
        revisar()
    if a.aplicar:
        aplicar()
