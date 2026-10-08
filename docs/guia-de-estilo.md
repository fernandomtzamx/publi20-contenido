# Guía de estilo de Publi2.0

Todo agente que escriba para Publi2.0 lee esta guía antes de empezar. Los contenidos se redactan con IA, los revisa una persona antes de publicarse y todos salen firmados por **Fernando Martínez**.

## Voz: business casual

El modelo es el blog de [Business Casual Copywriting](https://businesscasualcopywriting.com/blog/), adaptado al español de México.

- **Cercano y directo.** De tú, como alguien que sabe del tema y te lo explica tomando un café. Autoridad sin solemnidad.
- **Primera persona del autor, segunda hacia el lector.** "Te lo digo porque lo he visto en tres pitches seguidos."
- **Humor ligero y autoironía** cuando aclaran el punto. Nunca para rellenar.
- **Párrafos de una a tres frases.** Frases cortas. Ritmo. Alguna exclamación, sin abusar.
- **Arranque con gancho:** una situación que el lector reconoce, un dato o una contradicción. Nunca "En el mundo actual del marketing...".
- **Cierre breve y cálido**, con una acción concreta: qué hacer mañana con lo que acabas de leer.
- **Cero relleno corporativo:** nada de "soluciones integrales", "potenciar", "sinergia" o "transformación digital", salvo para burlarte de ellas con un propósito.
- **Honestidad comercial:** decir para qué sirve algo y para qué no ("Contrátala si / Piénsalo dos veces si").

Si está disponible, el agente carga la skill `business-casual-conversion-copy` antes de redactar.

## Reglas duras

1. **Autor:** Fernando Martínez en todas las entradas. El publicador lo asigna; no lo escribas en el texto.
2. **Enlaces externos:** todos salen con `rel="nofollow noopener"`. El publicador lo agrega solo.
3. **Comentarios:** cerrados en todas las entradas y páginas. El publicador los cierra en cada publicación.
4. **Nunca uses guion largo ni guion medio.** Usa dos puntos, comas, punto y seguido o paréntesis. El lint lo marca como error.
5. **Ningún dato sin fuente.** Cada cifra, premio, fecha o afirmación verificable lleva enlace a su fuente original. Si no hay fuente, se elimina.
6. **Nada inventado:** ni testimonios, ni casos, ni porcentajes "de ejemplo" presentados como reales.
7. **Citas textuales:** máximo una por fuente y de menos de 15 palabras. Lo demás se parafrasea.
8. **Rankings:** cada uno publica su metodología, sus fuentes y su fecha de corte. Ninguna empresa real aparece con datos que no se puedan verificar en su sitio, en premios o en prensa. Nadie paga por aparecer.
9. **Revisión humana** antes de cambiar `status` a `publish`. Mientras tanto, todo va como `draft`.

## Identidad visual de Publi2.0

Todo lo visual sigue el logo de Publi2.0 (`brand/logo-publi20.png`): **negro #000000, rojo #EA3322 y blanco**, con grises neutros de apoyo. Nada de colores, clases ni estilos de otros sitios.

- **Portada de cada nota:** la genera Gemini como fotografía editorial, sin texto, sin logos y sin marca de agua visible. Se escribe la escena en `image_prompt` (en inglés, una o dos frases concretas: lugar, objetos, luz, ambiente). El prompt base de `docs/sitio.yml` agrega el estilo y las prohibiciones. Nada de personas famosas, marcas, letreros ni pantallas con texto.
- **Rankings:** usan la plantilla de Publi2.0 (`scripts/cover.py`, con logo y paleta negro, rojo #EA3322 y blanco) y no pasan por Gemini. Se marca con `portada: plantilla` o basta con la categoría `rankings`.
- **Nombre del archivo:** Gemini guarda en `images/<slug>-portada.jpg` y la plantilla en `images/<slug>-portada.png`. Si rehaces una portada, cambia el nombre en `featured_image` (por ejemplo `-portada-v2`), porque el publicador reutiliza la imagen que ya existe con el mismo nombre.
- **Revisión:** la portada generada queda en el repositorio después de publicar; si no convence, se cambia `image_prompt` y el nombre del archivo y se vuelve a publicar.
- **Estilos dentro de la nota:** solo las clases de `scripts/article.css` con prefijo `p20-` (`p20-tldr`, `p20-def`, `p20-video`).

## Videos

Cuando la nota hable de un comercial, una campaña o un evento que tenga video, búscalo e insértalo.

1. **Primero el canal oficial** [@Publi20](https://www.youtube.com/@Publi20). Si ahí está, se usa ese.
2. Si no está, usa el canal oficial de la marca o de un medio reconocido. Evita resubidas de cuentas anónimas.
3. Para buscar: agrega los términos a `docs/busquedas-video.txt` y haz push; los resultados (id, título, canal y duración) quedan en `registro/videos.log`.
4. Insértalo en su propia línea, justo después del párrafo que lo menciona:

```markdown
[youtube ID_O_URL "Qué muestra el video. Video: nombre del canal en YouTube."]
```

El publicador lo convierte en un bloque de inserción de YouTube de WordPress. El pie siempre dice de qué canal es el video.

## Estructura de un artículo

```markdown
---
title: "..."                # 60 a 75 caracteres, palabra clave al inicio
slug: palabra-clave-corta
type: post
status: draft               # pasa a publish solo después de la revisión humana
date: 2026-10-27 08:00      # hora de Ciudad de México
excerpt: "..."              # 140 a 160 caracteres, meta descripción
categories: [creatividad]   # la subsección; su pilar padre define la URL
image_prompt: "..."         # escena para la portada de Gemini (no aplica en rankings)
tags: [...]
---

Gancho (2 a 4 párrafos cortos)

<div class="p20-tldr" markdown="1">
**Si solo tienes 30 segundos:**
- ...
</div>

[TOC]

## Secciones H2 con títulos conversacionales

## Preguntas frecuentes   (3 a 5 preguntas reales de búsqueda)
```

- Extensión: guías y artículos de 1,200 a 1,800 palabras; rankings de 1,800 a 2,500.
- Enlaces internos con el formato `/slug/` y solo a piezas ya publicadas.

## Categorías

| Pilar | Subsecciones |
| --- | --- |
| publicidad | creatividad, medios, guias |
| mercadotecnia | marketing-digital, investigacion-de-mercados |
| negocios | automotriz, comercio-electronico |
| emprendimiento | productividad, liderazgo, pymes, ventas |
| rankings | (sin subsecciones) |
| noticias | (sin subsecciones) |
