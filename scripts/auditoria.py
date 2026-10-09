#!/usr/bin/env python3
"""Auditoría de publi20.com: redirecciones (plugin Redirection) y salud de las entradas publicadas.

Uso: python scripts/auditoria.py [--corregir]

Redirecciones (todas las activas, de todos los grupos). Para cada una sigue la cadena real, sin caché:
  ok          un salto y el destino responde 200
  cadena      dos o más saltos hasta un 200          -> corrige: apunta directo al destino final
  bucle       la cadena regresa a una URL ya vista   -> corrige: desactiva la regla
  destino_mal el destino final no responde 200       -> corrige: reapunta al archivo del pilar o desactiva
  secuestro   el origen es la URL viva de una entrada -> corrige: desactiva (taparía contenido publicado)
  basura      origen o destino sin sentido (/old_url) -> corrige: desactiva
  no_aplica   el origen no redirige (regla inactiva en la práctica o regex) -> solo se reporta

Entradas publicadas: código HTTP, imagen destacada, comentarios cerrados, autor y canónica.
Resultados: registro/auditoria-redirecciones.csv, registro/auditoria-entradas.csv, registro/auditoria.log
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
S = requests.Session()
S.headers.update({"User-Agent": "publi20-auditoria/1.0", "Cache-Control": "no-cache"})
LOG = []


def log(m):
    print(m, flush=True)
    LOG.append(m)


def red(wp, method, path, **kw):
    r = wp.s.request(method, f"{wp.api.replace('/wp/v2', '')}/redirection/v1/{path}", timeout=60, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def norm(u):
    u = (u or "").replace("http://", "https://").replace("https://publi20.com", BASE)
    u = u.replace(BASE, "")
    u = re.sub(r"[?&]nc=\d+", "", u)
    return u or "/"


def cadena(path, max_hops=10):
    url = BASE + path
    url += ("&" if "?" in url else "?") + f"nc={random.randint(1, 10**9)}"
    vistos, saltos = [], []
    for _ in range(max_hops):
        try:
            r = S.get(url, timeout=25, allow_redirects=False)
        except Exception as e:  # noqa: BLE001
            return saltos, "error", str(e)[:60]
        actual = norm(url)
        if actual in vistos:
            return saltos, "bucle", actual
        vistos.append(actual)
        if r.status_code in (301, 302, 307, 308) and r.headers.get("location"):
            loc = r.headers["location"]
            saltos.append((r.status_code, norm(loc), r.headers.get("x-redirect-by", "-")))
            url = loc if loc.startswith("http") else BASE + loc
            if "nc=" not in url:
                url += ("&" if "?" in url else "?") + f"nc={random.randint(1, 10**9)}"
            continue
        return saltos, r.status_code, actual
    return saltos, "bucle", norm(url)


def todas(wp):
    items, page = [], 0
    while True:
        res = red(wp, "GET", "redirect", params={"per_page": 200, "page": page})
        lote = res.get("items", [])
        items += lote
        if len(lote) < 200:
            break
        page += 1
    return items


def pilar(path):
    if path.startswith("/publicidad-negocios-mexico/"):
        return "/emprendimiento/"
    if path.startswith("/uncategorised/"):
        return "/"
    if re.search(r"investigacion-de-mercados|marketing-digital|inbound|mercadotecnia|desarrollo-web", path):
        return "/mercadotecnia/"
    return "/publicidad/"


def actualizar(wp, it, destino):
    body = {"url": it["url"], "match_type": it.get("match_type", "url"), "action_type": it.get("action_type", "url"),
            "action_code": it.get("action_code", 301), "action_data": {"url": destino}, "group_id": it["group_id"],
            "regex": it.get("regex", False), "title": it.get("title", ""), "position": it.get("position", 0),
            "match_data": {"source": {"flag_query": "ignore", "flag_case": True,
                                      "flag_trailing": True, "flag_regex": bool(it.get("regex"))}}}
    red(wp, "POST", f"redirect/{it['id']}", json=body)


def desactivar(wp, ids):
    for k in range(0, len(ids), 100):
        red(wp, "POST", "bulk/redirect/disable", json={"items": ids[k:k + 100]})


def entradas(wp):
    posts, page = [], 1
    while True:
        r = wp.s.get(f"{wp.api}/posts", timeout=60, params={"status": "publish", "per_page": 100, "page": page,
                     "context": "edit", "_fields": "id,link,slug,featured_media,comment_status,ping_status,author"})
        if r.status_code == 400:
            break
        r.raise_for_status()
        posts += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    return posts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corregir", action="store_true")
    a = ap.parse_args()
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    wp.whoami()
    out = ROOT / "registro"

    # --- Entradas publicadas
    posts = entradas(wp)
    vivas = {norm(p["link"]) for p in posts}
    log(f"Entradas publicadas: {len(posts)}")

    def chequeo(p):
        saltos, final, url = cadena(norm(p["link"]))
        canon = ""
        if final == 200:
            try:
                html = S.get(BASE + url + "?nc=" + str(random.randint(1, 10**9)), timeout=25).text
                m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
                canon = norm(m.group(1)) if m else "(sin canónica)"
            except Exception:  # noqa: BLE001
                canon = "?"
        return [p["id"], norm(p["link"]), final, len(saltos), url, canon, p["featured_media"] or 0,
                p["comment_status"], p["ping_status"], p["author"]]

    with cf.ThreadPoolExecutor(8) as ex:
        filas_e = list(ex.map(chequeo, posts))
    with (out / "auditoria-entradas.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "url", "codigo", "saltos", "url_final", "canonica", "imagen", "comentarios", "pings", "autor"])
        w.writerows(filas_e)
    log(f"  no responden 200: {sum(1 for x in filas_e if x[2] != 200)}")
    log(f"  canónica distinta a la URL: {sum(1 for x in filas_e if x[2] == 200 and x[5] not in (x[4], '?'))}")
    log(f"  sin imagen destacada: {sum(1 for x in filas_e if not x[6])}")
    log(f"  comentarios o pings abiertos: {sum(1 for x in filas_e if x[7] != 'closed' or x[8] != 'closed')}")
    log(f"  autores distintos: {sorted({x[9] for x in filas_e})}")

    # --- Redirecciones
    items = [i for i in todas(wp) if i.get("enabled", True)]
    grupos = {g["id"]: g["name"] for g in red(wp, "GET", "group", params={"per_page": 200}).get("items", [])}
    log(f"Redirecciones activas: {len(items)}")

    def evalua(it):
        src = it["url"]
        dest = it.get("action_data", {}).get("url", "") if isinstance(it.get("action_data"), dict) else ""
        if it.get("regex"):
            return it, "no_aplica", [], "regex", dest
        if not src.startswith("/") or src in ("/old_url",) or not dest or dest == "new_url":
            return it, "basura", [], "", dest
        if norm(src).rstrip("/") + "/" in vivas or norm(src) in vivas:
            return it, "secuestro", [], "", dest
        saltos, final, url = cadena(src)
        if not saltos and final != 200:
            # La regla no se dispara con el parámetro anti-caché (compara la query exacta).
            # Se evalúa su destino: a dónde llegaría un visitante.
            d = norm(dest)
            if not d.startswith("/"):
                return it, "basura", [], "", dest
            s2, f2, u2 = cadena(d)
            if f2 == 200 and not s2:
                return it, "ok_query", [], d, dest
            if f2 == 200:
                return it, "cadena", s2, u2, dest
            return it, "destino_mal", s2, f"{f2} {u2}", dest
        if final == "bucle":
            return it, "bucle", saltos, url, dest
        if not saltos:
            return it, "no_aplica", saltos, f"{final}", dest
        if final != 200:
            return it, "destino_mal", saltos, f"{final} {url}", dest
        if len(saltos) > 1:
            return it, "cadena", saltos, url, dest
        return it, "ok", saltos, url, dest

    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(evalua, items))

    from collections import Counter
    log("Resultado: " + ", ".join(f"{k}={v}" for k, v in Counter(r[1] for r in res).most_common()))
    plan_desact, plan_update = [], []
    for it, estado, saltos, info, dest in res:
        if estado in ("bucle", "basura", "secuestro"):
            plan_desact.append(it["id"])
        elif estado == "cadena":
            plan_update.append((it, info))
        elif estado == "destino_mal":
            nuevo = pilar(it["url"])
            plan_update.append((it, nuevo))
        elif estado == "ok_query":
            plan_update.append((it, info))
    with (out / "auditoria-redirecciones.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "grupo", "estado", "origen", "destino_regla", "saltos", "detalle", "accion"])
        for it, estado, saltos, info, dest in res:
            accion = {"bucle": "desactivar", "basura": "desactivar", "secuestro": "desactivar",
                      "cadena": f"reapuntar a {info}", "destino_mal": f"reapuntar a {pilar(it['url'])}",
                      "ok_query": "ignorar parámetros de la URL"}.get(estado, "")
            w.writerow([it["id"], grupos.get(it["group_id"], it["group_id"]), estado, it["url"], dest,
                        " > ".join(f"{c}:{u}" for c, u, _ in saltos), info, accion])

    if a.corregir:
        hechos = errores = 0
        try:
            if plan_desact:
                desactivar(wp, plan_desact)
                hechos += len(plan_desact)
        except Exception as e:  # noqa: BLE001
            errores += 1
            log(f"ERROR al desactivar: {e}")
        for it, destino in plan_update:
            try:
                actualizar(wp, it, destino)
                hechos += 1
            except Exception as e:  # noqa: BLE001
                errores += 1
                if errores < 5:
                    log(f"ERROR al actualizar {it['id']}: {str(e)[:200]}")
        log(f"Correcciones: {len(plan_desact)} desactivadas, {len(plan_update)} reapuntadas; errores: {errores}")
    (out / "auditoria.log").write_text("\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
    sys.exit(0)
