# Flujo semanal del agente editor de Publi2.0

Este documento describe lo que hace la tarea programada "Publi2.0: publicación 3 por semana" en cada corrida. La fuente de verdad de fechas y piezas es `docs/calendario.yml`. Las reglas de redacción están en `docs/guia-de-estilo.md` y, para rankings, en `docs/rankings-instrucciones.md`. Nunca uses guion largo ni guion medio.

## Ritmo

- **Lunes 08:00:** ranking (nuevo o actualización anual de uno existente).
- **Miércoles 08:00:** artículo de publicidad y mercadotecnia alineado a la temporada.
- **Viernes 08:00:** noticia escrita a partir de un comunicado de la carpeta `@Prensa` de Gmail.
- Pausa navideña: no se publica del 24 de diciembre al 3 de enero. Las piezas de esas fechas se recorren a la siguiente semana hábil manteniendo el orden.

## Qué hace cada corrida (lunes a viernes, 06:15 de Ciudad de México)

1. **Verificar la publicación de hoy** (si hoy es lunes, miércoles o viernes): consulta `https://www.publi20.com/wp-json/wp/v2/posts?slug=SLUG&_fields=status,link,title&nocache=FECHAHORA`. Si la entrada está `publish`, cambia su estado en el calendario a `publicado`. Si está `future` o no existe, dispara el publicador (`gh api -X POST repos/fernandomtzamx/publi20-contenido/actions/workflows/publish.yml/dispatches -f ref=main -f 'inputs[mode]=all'`), espera 3 minutos, `git pull`, lee `registro/ultima-publicacion.log` y vuelve a verificar. Si sigue sin salir, avisa al usuario con el error del registro.
2. **Escribir la siguiente pieza**: la primera entrada del calendario con `estado: por-escribir` y fecha posterior a hoy (normalmente la de dentro de dos días: el lunes se escribe la del miércoles, el miércoles la del viernes, el viernes la del lunes). Martes y jueves solo verifican y, si hay una pieza atrasada o con `estado: detener`, lo reportan.
3. **Publicar como programada**: el frontmatter lleva `status: publish` y `date` con la fecha del calendario a las 08:00. El publicador la deja en WordPress como `future` (programada). Así el usuario tiene dos días para revisarla en wp-admin o pedir cambios antes de que salga.
4. **Registrar**: cambia el `estado` de la pieza en `docs/calendario.yml` a `programado`, haz commit (con la línea `Co-Authored-By: Claude <noreply@anthropic.com>` al final del mensaje), `git pull --rebase` y `git push`. Espera 3 minutos, `git pull`, confirma en `registro/ultima-publicacion.log` que la entrada quedó `future` con su enlace.
5. **Avisar**: un solo mensaje al usuario con título, enlace de vista previa (`https://www.publi20.com/?p=ID&preview=true`) y dos líneas de resumen. Si no hay nada que escribir ni verificar, no mandes mensaje.

## Cómo se escribe cada pilar

### Ranking (lunes)

Sigue `docs/rankings-instrucciones.md` al pie de la letra: entre 8 y 15 empresas verificables (5 a 10 en rankings locales), agrupadas por tipo y en orden alfabético dentro de cada grupo, metodología pública, fecha de corte del mes en curso, nadie paga por aparecer. Portada con `python3 scripts/cover.py --out images/SLUG-portada.png --kicker "RANKING 2027" --title "..." --stat N --stat-label "empresas verificadas"`.

Si la entrada del calendario dice **ACTUALIZACIÓN**, reescribe el archivo existente conservando el slug: nueva fecha de corte, premios y cambios del último año, título con el año nuevo, y cambia el nombre de la portada (`-portada-2027.png`).

### Artículo (miércoles)

Guía o análisis de 1,200 a 1,800 palabras con la estructura de `docs/guia-de-estilo.md`: gancho, bloque `p20-tldr`, `[TOC]`, H2 conversacionales, preguntas frecuentes, cierre con acción concreta. Investiga con WebSearch y WebFetch; cada cifra con enlace a su fuente. Portada con Gemini: escribe `image_prompt` en inglés (escena concreta, sin texto ni marcas). Si el calendario dice **Reescritura** o **Actualización**, trabaja sobre el archivo existente y conserva el slug. Enlaza a los rankings publicados cuando el tema lo permita.

### Noticia de prensa (viernes)

1. Busca en Gmail con `label:@Prensa newer_than:21d` y lee el hilo completo del comunicado indicado en el calendario (campo `fuente`). Si el calendario dice "elegir en la carpeta @Prensa", elige el comunicado más reciente que sea relevante para publicidad, marketing, negocios o emprendimiento en México; actualiza en el calendario el título, el slug y el archivo de esa línea.
2. Escribe una noticia de 600 a 900 palabras en `content/noticias/SLUG.md`, categoría `noticias`: qué se anunció, por qué importa a quien hace publicidad o negocios en México, datos clave del comunicado y contexto con una o dos fuentes externas. No copies el comunicado: reescribe. Una cita textual como máximo, de menos de 15 palabras, atribuida a quien la dice.
3. Atribución obligatoria: el primer párrafo o el segundo dice que la información proviene de un comunicado de la empresa (por ejemplo: "según un comunicado de Palladium Hotel Group enviado a Publi2.0"). Nada de cifras que no vengan del comunicado o de una fuente enlazada.
4. Portada con Gemini (`image_prompt`): escena relacionada con el tema, sin logos ni texto. No uses las imágenes del comunicado.
5. Si el comunicado es publicidad disfrazada sin ningún dato de interés, elige otro y anótalo en el calendario.
6. **Correo a quien envió el comunicado, el mismo viernes y solo después de confirmar que la nota está `publish` en WordPress.** Responde en el hilo original de Gmail (herramienta `reply` del conector de Gmail, para que conserve el asunto y llegue al remitente real, normalmente la agencia de relaciones públicas). Si el comunicado llegó en varios hilos repetidos, responde solo al más reciente. Registra en el calendario `correo: enviado AAAA-MM-DD` en esa línea. Nunca mandes el correo si la nota no está publicada ni lo repitas si ya está registrado.

   Plantilla (ajusta nombre, marca y enlace; sin guiones largos ni medios; firma siempre igual):

   > Asunto: el del hilo (respuesta)
   >
   > Hola, [nombre si aparece en el correo; si no, "equipo de prensa"]:
   >
   > Gracias por el comunicado sobre [tema o marca]. Ya está publicado en Publi2.0: [URL de la nota].
   >
   > Un par de cosas que pueden servirles:
   >
   > 1. Si tienen notas exclusivas, datos propios o entrevistas con directivos de [marca], las priorizamos sobre el resto de comunicados. Basta con enviarlas a contacto@publi20.com con "Exclusiva" en el asunto.
   > 2. Publicamos rankings de proveedores de publicidad y marketing en México con metodología pública (agencias, casas productoras, medios, publicidad exterior y más): https://www.publi20.com/rankings/. Nadie paga por aparecer; si alguno de sus clientes debería estar en uno, escríbannos con la fuente y lo revisamos.
   >
   > Si hay alguna corrección a la nota, con gusto la hacemos.
   >
   > Saludos,
   > Fernando Martínez
   > Editor, Publi2.0
   > contacto@publi20.com

## Reglas que nunca se rompen

- Nada inventado: ni cifras, ni clientes, ni premios, ni citas. Sin fuente, no se publica.
- `python3 scripts/lint.py ARCHIVO` debe dar `ok` antes del commit (ignora el aviso de portada pendiente en rankings).
- Una pieza con `estado: detener` en el calendario no se escribe ni se publica; si ya estaba programada en WordPress, cámbiala a `draft` con el publicador (status: draft en el frontmatter) y avisa.
- Si algo bloquea la publicación (credenciales, error del publicador, fuente inexistente), no lo fuerces: explica el problema al usuario en el mensaje.
