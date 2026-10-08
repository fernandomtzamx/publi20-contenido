#!/usr/bin/env python3
"""Exporta el contenido publicado de publi20.com a legacy/ para su remediación.

Genera:
  legacy/inventario.csv          una fila por entrada o página publicada
  legacy/posts/<id>.json         contenido crudo (raw) y metadatos de cada entrada
"""
import csv
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("publish", ROOT / "scripts" / "publish.py")
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)


def todos(wp, endpoint, **params):
    page, out = 1, []
    while True:
        r = wp.s.get(f"{wp.api}/{endpoint}", timeout=60,
                     params={"per_page": 100, "page": page, **params})
        if r.status_code == 400:
            break
        r.raise_for_status()
        out += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    return out


def main():
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    cats = {c["id"]: c["slug"] for c in todos(wp, "categories", _fields="id,slug")}
    tags = {t["id"]: t["name"] for t in todos(wp, "tags", _fields="id,name")}
    users = {u["id"]: u["name"] for u in todos(wp, "users", _fields="id,name", context="edit")}
    d = ROOT / "legacy" / "posts"
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for endpoint in ("posts", "pages"):
        for p in todos(wp, endpoint, status="publish", context="edit"):
            raw = p["content"]["raw"]
            rec = {
                "tipo": endpoint[:-1], "id": p["id"], "slug": p["slug"], "link": p["link"],
                "titulo": p["title"]["raw"], "fecha": p["date"], "modificado": p["modified"],
                "autor": users.get(p.get("author"), p.get("author")),
                "categorias": [cats.get(c, c) for c in p.get("categories", [])],
                "etiquetas": [tags.get(t, t) for t in p.get("tags", [])],
                "extracto": p.get("excerpt", {}).get("raw", ""),
                "imagen_destacada": p.get("featured_media", 0),
                "parent": p.get("parent", 0), "plantilla": p.get("template", ""),
                "contenido": raw,
            }
            (d / f"{p['id']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            text = pub.re.sub(r"<[^>]+>", " ", raw)
            rows.append({k: rec[k] for k in ("tipo", "id", "slug", "link", "titulo", "fecha", "modificado", "autor")}
                        | {"categorias": "|".join(rec["categorias"]), "etiquetas": "|".join(map(str, rec["etiquetas"])),
                           "palabras": len(text.split()), "imagen_destacada": rec["imagen_destacada"],
                           "enlaces": raw.count("<a "), "iframes": raw.count("<iframe"), "imagenes": raw.count("<img")})
    with open(ROOT / "legacy" / "inventario.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Exportadas {len(rows)} entradas y páginas publicadas")


if __name__ == "__main__":
    main()
