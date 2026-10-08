# Publi2.0: contenido y pipeline de publicación

Repositorio fuente de [publi20.com](https://www.publi20.com). Cada archivo Markdown en `content/` se publica en WordPress por la API REST cuando llega a `main`.

## Reglas que aplica el publicador

- **Autor:** todas las entradas salen a nombre de Fernando Martínez (`docs/sitio.yml`).
- **Enlaces externos:** se marcan con `rel="nofollow noopener"` de forma automática.
- **Comentarios:** cada entrada y página se publica con comentarios y pingbacks cerrados. El modo `setup` también los cierra en todo el contenido existente.
- **Estado:** todo entra como `draft` hasta que pasa la revisión humana.

## Cómo funciona

1. Se escribe o actualiza `content/<pilar>/<slug>.md` siguiendo `docs/guia-de-estilo.md` y `docs/calendario.yml`.
2. `python scripts/lint.py content/.../archivo.md` revisa el frontmatter, la extensión, las fuentes y los guiones.
3. Al hacer push a `main`, la GitHub Action `Publicar en WordPress` publica solo los archivos nuevos o modificados.
4. Si ya existe una entrada con el mismo `slug`, se actualiza; nunca se duplica.

## Configuración inicial (una sola vez)

1. **Usuario y contraseña de aplicación.** En wp-admin de publi20.com: Usuarios > Fernando Martínez > Contraseñas de aplicación > nombre "github-publi20" > Añadir. Copia la contraseña.
   Si prefieres un usuario técnico con rol Editor, crea la contraseña en ese usuario y pon el id de Fernando en `autor.id` de `docs/sitio.yml`.
2. **Secretos en GitHub** (Settings > Secrets and variables > Actions):

   | Secreto | Valor |
   | --- | --- |
   | `WP_URL` | `https://www.publi20.com` |
   | `WP_USER` | usuario de WordPress de Fernando Martínez |
   | `WP_APP_PASSWORD` | la contraseña de aplicación del paso 1 |

3. **Enlaces permanentes.** Ajustes > Enlaces permanentes > Estructura personalizada: `/%category%/%postname%/`. Así las URLs quedan como `/publicidad/creatividad/slug/` y `/rankings/slug/`.
4. **Plugin de autenticación (solo si hace falta).** Si `check` dice que el encabezado Authorization no llega, sube `wordpress/mu-plugins/publi20-auth.php` a `wp-content/mu-plugins/`.
5. **Probar.** Actions > Publicar en WordPress > Run workflow > `check`. Debe responder "Conectado como Fernando Martínez" y el id del autor.
6. **Aplicar la estructura.** Run workflow > `setup`: crea las categorías y cierra los comentarios en todo el sitio.

## Uso local

```bash
pip install -r requirements.txt
export WP_URL=... WP_USER=... WP_APP_PASSWORD=...
python scripts/publish.py --check
python scripts/publish.py content/publicidad/comerciales-prohibidos-censurados.md
```
