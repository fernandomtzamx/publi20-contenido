# Cómo se escribe un ranking de Publi2.0

Lee antes `docs/guia-de-estilo.md` (voz business casual, reglas duras). Esto agrega lo propio de los rankings.

## Principio

Un ranking de Publi2.0 es una **selección curada con metodología pública**. Nadie paga por aparecer. Cada empresa que aparece existe, sigue operando en octubre de 2026 y cada dato que se dice de ella se puede verificar con un enlace: su sitio oficial, un premio publicado por el organizador (Effie México, Cannes Lions, El Ojo de Iberoamérica, Círculo Creativo, Premios Ídolo, IAB México, Clio, etc.), un ranking de terceros con fuente (Scopen, Merca2.0, Expansión, AdLatina, Campaign) o prensa reconocida.

- **Prohibido inventar:** ni cifras, ni clientes, ni premios, ni años de fundación, ni número de empleados. Si no encuentras la fuente, no lo escribas.
- **Una empresa sin sitio web activo o sin rastro verificable no entra**, aunque la gente la busque.
- **Clientes:** solo los que la propia empresa muestra en su sitio o los que aparecen en un premio o nota de prensa, con enlace.
- **Nada de opiniones disfrazadas de hecho.** "Ideal para" se basa en la especialidad que la empresa declara.
- **Orden:** agrupa por tipo (por ejemplo: grupos internacionales, independientes, boutiques) y, dentro de cada grupo, en orden alfabético. Dilo en la metodología: "el orden dentro de cada grupo es alfabético; no es una calificación". No inventes puntuaciones.
- Entre 8 y 15 empresas por ranking (los rankings por ciudad pueden tener de 5 a 10). Si hay empresas que la gente busca (lista "empresas buscadas" del brief) y se pueden verificar, inclúyelas: son búsquedas reales que llegan al sitio.

## Formato del archivo

`content/rankings/<slug>.md`:

```markdown
---
title: "..."                 # 60 a 75 caracteres, palabra clave al inicio, con el año 2026 si cabe
slug: <slug>
type: post
status: draft
excerpt: "..."               # 140 a 160 caracteres, con la palabra clave, sin repetir el título
categories: [rankings]
tags: [...]                  # 4 a 6
palabra_clave: "..."         # la consulta principal del brief, tal cual la busca la gente
portada: plantilla
featured_image: images/<slug>-portada.png
featured_alt: "..."
portada_kicker: "RANKING 2026"
portada_stat: "12"           # número de empresas del ranking
portada_stat_label: "agencias verificadas"
---
```

Cuerpo, en este orden:

1. **Gancho** (2 a 4 párrafos cortos): el problema real de quien busca este proveedor.
2. Bloque `<div class="p20-tldr" markdown="1">` con "**Si solo tienes 30 segundos:**" y 3 o 4 viñetas.
3. `[TOC]`
4. `## Cómo armamos este ranking`: criterios, fuentes consultadas, fecha de corte (**octubre de 2026**), que nadie pagó por aparecer y que el orden dentro de cada grupo es alfabético. Invita a las empresas a escribir si un dato cambió.
5. Una `## ` por grupo, y dentro cada empresa como `### Nombre de la empresa` con:
   - Un párrafo de 2 a 4 frases: qué hace y por qué está aquí, con los enlaces de las fuentes en el texto.
   - Una lista corta: `- **Sede:** ...`, `- **Especialidad:** ...`, `- **Ideal para:** ...`, `- **Sitio:** [dominio](https://...)`.
6. `## Cómo elegir ...`: preguntas para la primera reunión, señales de alerta, qué pedir en la cotización. Sin precios inventados; si das rangos, con fuente.
7. Una tabla resumen (Empresa | Tipo | Sede | Especialidad).
8. `## Preguntas frecuentes`: 3 a 5 preguntas reales de búsqueda (usa las consultas del brief) como `### ¿...?` con respuesta breve.
9. Cierre de 1 o 2 frases y la línea `<p class="p20-credito">Fecha de corte: octubre de 2026. ¿Tu empresa debería estar aquí o cambió un dato? Escríbenos con la fuente y lo revisamos.</p>`

## Reglas de forma

- **Nunca uses guion largo (—) ni guion medio (–).** Usa dos puntos, comas o paréntesis.
- Español de México, de tú, párrafos de 1 a 3 frases.
- Extensión: 1,800 a 2,500 palabras.
- Enlaces externos con formato Markdown normal `[texto](https://...)`: el publicador les pone nofollow.
- Enlaces internos solo a notas ya publicadas del repo, con formato `/slug/` (el lint lo valida).
- Nada de logotipos ni imágenes de terceros.
- Revisa con `python scripts/lint.py content/rankings/<slug>.md` (debe dar `ok`; ignora el aviso de fecha y el error "falta la portada de plantilla": la portada se genera después).
