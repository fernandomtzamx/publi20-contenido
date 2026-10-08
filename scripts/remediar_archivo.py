#!/usr/bin/env python3
"""Remediación del archivo de comunicados de prensa (legacy/posts/*.json -> content/archivo/*.md).

Qué hace con cada comunicado, sin despublicarlo ni cambiar su URL ni su fecha de publicación:
  - Limpia el HTML heredado: atributos de importación, párrafos y spans vacíos, códigos de Joomla,
    imágenes y logotipos enlazados desde servidores de terceros y líneas "Foto/Logo - URL".
  - Convierte los enlaces a YouTube del comunicado en videos insertados.
  - Agrega una nota de archivo con la fuente y la fecha original, y deja el enlace a la versión original.
  - Lo clasifica en Noticias + la subsección del pilar que corresponde, con extracto para buscadores.
El publicador agrega nofollow a los enlaces externos, cierra comentarios y actualiza la fecha de modificación.

Uso: python scripts/remediar_archivo.py   (regenera content/archivo/)
"""
import json
import pathlib
import re

import yaml
from bs4 import BeautifulSoup, Comment

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "legacy" / "posts"
OUT = ROOT / "content" / "archivo"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]

# Notas propias que se remedian a mano en su pilar (no son comunicados).
EDITORIALES = {4973, 5016, 5057, 5072, 5090, 5257, 5278, 5299, 5300, 5301, 5342, 5343, 5344, 5365,
               5386, 5387, 5408, 5409, 5410, 5411, 5412, 5413, 8371}

# Duplicados consolidados: quedan en borrador y su URL redirige a la versión de México (5227 y 5025).
DUPLICADOS = {5226, 5228, 5229, 5230, 5231, 5232, 5026, 5017}

REGLAS = [  # (patrón sobre el título, subsección); la primera que coincide gana
    (r"emprend|startup|jóvenes empresarios|joven emprendedor|franquici|pymes|premios verde|young talent|"
     r"women's forum|silicon valley", "pymes"),
    (r"isuzu|audi|michelin|neumátic|bridgestone|kiekert|nira dynamics|vehícul|automotri|nucor|"
     r"autobús|xcmg|mohawk", "automotriz"),
    (r"comercio electrónico|e-commerce|ecwid|cornershop|safetypay|boacompra|compran en internet|"
     r"pagos electrónicos|aplicación móvil|la curacao|best buy", "comercio-electronico"),
    (r"research now|focusvision|encuesta|índice revela|según los consumidores|"
     r"responsabilidades corporativas|qué compran|great place to work", "investigacion-de-mercados"),
    (r"marketing|redes sociales|navegg|impartner|prm|crm|lealtad|wyndham rewards|influenc|"
     r"red social|versy", "marketing-digital"),
    (r"campaña|\bcomercial\b|publicidad|ddb|omnicom|havas|rokkan|portadalat|identidad de marca|"
     r"lanza la iniciativa|equalizing music|gillette|pepsi|mountain dew|"
     r"martini|hennessy|smirnoff|make up for ever|magnum|tory burch", "creatividad"),
    (r"\btv\b|televisión|netflix|serie|revista|gq|vanity fair|radio|america tevé|américa tevé|"
     r"hola! tv|cortometrajes|cine|grupo expansión|medios|music|dugout", "medios"),
]


def subseccion(titulo):
    t = titulo.lower()
    for rx, sub in REGLAS:
        if re.search(rx, t):
            return sub
    return "negocios"


def youtube_ids(html):
    return list(dict.fromkeys(re.findall(r"(?:youtu\.be/|youtube\.com/watch\?v=|youtube\.com/embed/)([\w-]{11})", html)))


def limpiar(html):
    soup = BeautifulSoup(html, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup.find_all(True):
        for attr in ("readability", "border", "align", "style", "class", "id", "target", "title"):
            tag.attrs.pop(attr, None)
    # Imágenes enlazadas desde servidores de terceros (logotipos y fotos de agencias de noticias)
    for img in soup.find_all("img"):
        img.decompose()
    # Spans sin atributos: se quedan solo con su texto
    for span in soup.find_all("span"):
        span.unwrap()
    # Divs sin atributos: se desenvuelven
    for div in soup.find_all("div"):
        div.unwrap()
    fuente, original = "", ""
    for p in soup.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if re.match(r"^(\(?\s*)(Foto|Logo|Video|Fotografía|Imagen)\s*[-:]", txt, re.I) and len(txt) < 260:
            p.decompose()
            continue
        if re.match(r"^To view the original version on PR Newswire", txt, re.I):
            a = p.find("a")
            original = a.get("href", "") if a else ""
            p.decompose()
            continue
        m = re.match(r"^FUENTE\s+(.+)$", txt)
        if m:
            fuente = m.group(1).strip()
            p.decompose()
            continue
        if not txt and not p.find(["iframe", "a"]):
            p.decompose()
    out = str(soup)
    out = re.sub(r"\{loadmodule[^}]*\}|\{loadposition[^}]*\}|\[module-\d+\]", "", out)
    out = re.sub(r"\s*\n\s*\n+", "\n\n", out).strip()
    # Separar la línea de fecha del cuerpo: "CIUDAD, 23 de febrero de 2016 /PRNewswire/ -"
    # Regla editorial: sin guion largo ni medio.
    out = re.sub(r"(\d)\s*[\u2013\u2014]\s*(\d)", r"\1-\2", out)
    out = re.sub(r"\s*[\u2013\u2014]+\s*", ", ", out)
    out = re.sub(r",\s*([,.;:)])", r"\1", out)
    out = re.sub(r"(>)\s*,\s*", r"\1", out)
    out = re.sub(r"/\s*PRNewswire(?:-HISPANIC PR WIRE)?\s*/\s*[-–]?", "", out)
    return out, fuente, original


def extracto(html, titulo):
    txt = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    txt = re.sub(r"^[A-ZÁÉÍÓÚÑ ,.\-]+,\s+\d{1,2} de \w+ de \d{4}\s*[-–]?\s*", "", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) < 60:
        txt = titulo
    if len(txt) > 158:
        cut = txt[:158]
        txt = cut[:cut.rfind(" ")].rstrip(",;:") + "…"
    return txt


def fecha_larga(iso):
    y, m, d = iso[:10].split("-")
    return f"{int(d)} de {MESES[int(m) - 1]} de {y}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()
    n = 0
    for f in sorted(SRC.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d["tipo"] != "post" or d["id"] in EDITORIALES:
            continue
        yt = youtube_ids(d["contenido"])
        cuerpo, fuente, original = limpiar(d["contenido"])
        sub = subseccion(d["titulo"])
        nota = (f'<p class="p20-archivo"><strong>Archivo Publi2.0.</strong> Comunicado de prensa'
                f'{" de " + fuente if fuente else ""} publicado originalmente el {fecha_larga(d["fecha"])}. '
                'Lo conservamos como referencia; las cifras y los cargos corresponden a esa fecha.</p>')
        videos = "\n".join(f"[youtube {v}]" for v in yt)
        cierre = (f'<p class="p20-archivo-fuente">Fuente: {fuente or "comunicado de prensa"}'
                  + (f'. <a href="{original}">Versión original del comunicado</a>' if original else "")
                  + ".</p>")
        meta = {
            "id": d["id"], "title": d["titulo"].strip(), "slug": d["slug"], "type": "post",
            "status": "draft" if d["id"] in DUPLICADOS else "publish", "formato": "html", "legado": True, "portada": "ninguna",
            "excerpt": extracto(cuerpo, d["titulo"]),
            "categories": ["noticias"] + ([sub] if sub != "negocios" else ["negocios"]),
            "tags": ["comunicados de prensa", f"archivo {d['fecha'][:4]}"],
        }
        fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000)
        body = f"{nota}\n\n{cuerpo}\n\n{videos}\n\n{cierre}\n" if videos else f"{nota}\n\n{cuerpo}\n\n{cierre}\n"
        (OUT / f"{d['id']}-{d['slug'][:60]}.md").write_text(f"---\n{fm}---\n\n{body}", encoding="utf-8")
        n += 1
    print(f"{n} comunicados remediados en content/archivo/")


if __name__ == "__main__":
    main()
