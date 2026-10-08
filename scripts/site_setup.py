#!/usr/bin/env python3
"""Aplica docs/sitio.yml en publi20.com: categorías (con jerarquía), cierre de comentarios y ajustes.

Qué hace, en orden:
  0. Si docs/sitio.yml trae autor.perfil, actualiza el nombre público del usuario conectado.
  1. Crea o actualiza las categorías de los pilares y sus subsecciones.
  2. Cierra comentarios y pingbacks en todas las entradas y páginas que los tengan abiertos.
  3. Si el usuario conectado es administrador, desactiva los comentarios por defecto del sitio.
     Si no lo es, avisa qué hacer a mano en Ajustes > Comentarios.
"""
import importlib.util
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("publish", ROOT / "scripts" / "publish.py")
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)


def categorias(wp, cats):
    errors = 0
    for c in cats:
        try:
            payload = {"name": c["name"], "description": c.get("description", "")}
            if c.get("parent"):
                parent = wp.req("GET", "categories", params={"slug": c["parent"]})
                if not parent:
                    raise RuntimeError(f"no existe la categoría padre '{c['parent']}'")
                payload["parent"] = parent[0]["id"]
            found = wp.req("GET", "categories", params={"slug": c["slug"]})
            if found:
                wp.req("POST", f"categories/{found[0]['id']}", json=payload)
                print(f"Categoría actualizada: {c['slug']} -> {c['name']}")
            else:
                wp.req("POST", "categories", json={**payload, "slug": c["slug"]})
                print(f"Categoría creada: {c['slug']} -> {c['name']}")
        except Exception as e:  # noqa: BLE001
            errors += 1
            print(f"ERROR categoría {c.get('slug')}: {e}")
    return errors


def cerrar_comentarios(wp):
    errors = closed = 0
    for endpoint in ("posts", "pages"):
        page = 1
        while True:
            r = wp.s.get(f"{wp.api}/{endpoint}", timeout=30, params={
                "status": "publish,future,draft,pending,private", "per_page": 100, "page": page,
                "context": "edit", "_fields": "id,comment_status,ping_status"})
            if r.status_code == 400:
                break
            if r.status_code >= 400:
                print(f"ERROR al listar {endpoint}: {r.status_code} {r.text[:200]}")
                errors += 1
                break
            items = r.json()
            for it in items:
                if it.get("comment_status") == "closed" and it.get("ping_status") == "closed":
                    continue
                try:
                    wp.req("POST", f"{endpoint}/{it['id']}", json={"comment_status": "closed", "ping_status": "closed"})
                    closed += 1
                except Exception as e:  # noqa: BLE001
                    errors += 1
                    print(f"ERROR al cerrar comentarios en {endpoint}/{it['id']}: {e}")
            if page >= int(r.headers.get("X-WP-TotalPages", 1)):
                break
            page += 1
    print(f"Comentarios cerrados en {closed} entradas o páginas")
    return errors


def ajustes(wp):
    try:
        wp.req("POST", "settings", json={"default_comment_status": "closed", "default_ping_status": "closed"})
        print("Ajustes del sitio: comentarios y pingbacks desactivados por defecto")
        return 0
    except Exception as e:  # noqa: BLE001
        print("AVISO: este usuario no puede cambiar los ajustes del sitio "
              f"({str(e)[:80]}). Hazlo a mano: Ajustes > Comentarios > desmarca "
              "'Permitir comentarios en las entradas nuevas' y 'Permitir avisos de enlaces'.")
        return 0


def main():
    cfg = yaml.safe_load((ROOT / "docs" / "sitio.yml").read_text(encoding="utf-8")) or {}
    wp = pub.WP(pub.env("WP_URL"), pub.env("WP_USER"), pub.env("WP_APP_PASSWORD"))
    me = wp.whoami()
    print(f"Conectado como {me.get('name')} (roles: {', '.join(me.get('roles', []))})")
    errors = 0
    perfil = (cfg.get("autor") or {}).get("perfil")
    if perfil:
        try:
            me = wp.req("POST", "users/me", json=perfil)
            print(f"Perfil del usuario conectado: nombre público '{me.get('name')}'")
        except Exception as e:  # noqa: BLE001
            errors += 1
            print(f"ERROR perfil: {e}")
    errors += categorias(wp, cfg.get("categorias") or [])
    if cfg.get("cerrar_comentarios", True):
        errors += cerrar_comentarios(wp)
        errors += ajustes(wp)
    if errors:
        sys.exit(f"{errors} error(es)")


if __name__ == "__main__":
    main()
