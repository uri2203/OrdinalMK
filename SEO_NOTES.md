# OrdinalMK — Notas de SEO y preparación para lanzamiento

Esta rama endurece el SEO del motor y lo deja **multi-proyecto de verdad**
(nada de marca/dominio/tema hardcodeado). Todo sale de `config/projects.yaml`.

## ✅ Arreglado en esta rama

**Bloqueadores (el motor no arrancaba / no generaba):**
- **`email/` → `mailer/`**: el paquete `email/` en la raíz **tapaba el módulo
  `email` de la stdlib** y rompía `requests`/`urllib3` al importar → el
  orquestador crasheaba antes de empezar. Renombrado + imports actualizados.
  *(Muy probablemente la causa de que el bot diario no commitee desde el 5-ago.)*
- **Bug de llaves anidadas** en `multilang_landing.py` (footer): `REGIONS.get(l, {{}})`
  se evaluaba como set-con-dict (unhashable) → crash. Extraído fuera del f-string.

**SEO (multi-proyecto):**
- **hreflang inválido**: usaba locale con guion bajo (`es_ES`), que Google
  **ignora**. Ahora usa el código de idioma correcto (`es`, `en`, …) + `x-default`.
- **Dominio hardcodeado** como `{project_id}.com` (mal para `lastmile-platform.com`).
  Ahora `domain` viene de config y se propaga a landings, hreflang y sitemaps.
- **Faltaban** `canonical`, `robots`, Twitter Cards y OG completo (`og:url`,
  `og:image`, `og:type`, `og:site_name`) → añadidos al generador activo.
- **Tema por marca**: colores/tipografía desde `theme:` de cada proyecto
  (tuialista naranja claro, yayika índigo, lastmile azul).
- **Título con relleno** ("Marca … — Marca") corregido en `landing_page.py`.
- **Sitemap**: prioridad 1.0 para `index`, URLs con el dominio real.
- **`landing_page.py`** reescrito: 100% dirigido por config; si un proyecto no
  aporta features/testimonios, la sección **se omite** (nunca datos de otra marca).

**Seguridad:**
- `noindex` en el dashboard (`docs/index.html` + `templates/dashboard.html`) y
  `docs/robots.txt` que bloquea `/data/` (métricas internas de ingresos).

## ⚠️ Pendiente (decisiones / trabajo mayor — no incluido aquí)

1. **Publicar en el dominio de marca.** Hoy el workflow solo commitea a `docs/`
   de OrdinalMK → las landings quedan en `github.io/OrdinalMK/…`, **huérfanas y
   fuera del dominio**. Cada proyecto ya tiene `github_repo` en config: el paso
   de deploy debe **empujar `published/<proyecto>/` al repo/dominio de la marca**
   (p. ej. `uri2203/tuialista-site`) para que Google indexe en `tuialista.com`.
   Mientras no se haga, el SEO de estas landings **no cuenta para la marca**.
2. **Esquema de contenido.** El generador multilang espera
   `content = {lang: {title, subtitle, description, cta_text, cta_link, features…}}`,
   pero `projects.yaml` define `concept` como string. Hay que estructurar el
   contenido por idioma (o adaptarlo en el orquestador) para que se generen las
   landings — hoy los sitemaps salen vacíos por esto.
3. **Dashboard interno.** `robots.txt`/`noindex` evitan el indexado, pero los
   JSON siguen siendo accesibles por URL. Lo ideal: **no** servir el dashboard de
   ingresos en Pages público (moverlo a un host privado / detrás de auth).
4. **Consolidar generadores.** Hay 3 rutas de landing (`landing_page.py`,
   `multilang_landing.py`, `regional.generate_multilang_page`). Conviene unificar
   en una sola (la multilang) para no mantener SEO por triplicado.

## ➕ Cómo agregar un proyecto nuevo (multi-proyecto)

Solo un bloque en `config/projects.yaml` — **cero cambios de código**:

```yaml
  miproyecto:
    name: MiProyecto
    domain: miproyecto.com
    github_repo: uri2203/miproyecto
    og_image: "https://miproyecto.com/og-image.png"
    theme: { primary: "#e8821e", primary_dark: "#c46a12" }
    languages: [es, en]
    primary_language: es
    # concept/products/pages/topics por idioma…
```
