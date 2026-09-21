# OrdinalMK — Panel de control

Un solo lugar para **evaluar y controlar** el marketing de todos los proyectos:
resumen por proyecto, revisión de contenido fiscal, prospectos (ver/aprobar/
enviar), lanzar corridas y ver reportes. Login server-side real.

## Probarlo en tu equipo (local)
```bash
pip install -r requirements.txt
ORDINALMK_PANEL_PASSWORD=tu-clave python panel.py
# abre http://localhost:5001  (usuario: no hay; solo contraseña)
```

## Ponerlo en línea 24/7 (Render)
1. Crea cuenta en render.com y conéctala al repo `uri2203/OrdinalMK`.
2. Render detecta `render.yaml` y crea el servicio **ordinalmk-panel**.
3. En **Environment**, pon los secrets:
   - `ORDINALMK_PANEL_PASSWORD` — contraseña del panel (fuerte).
   - `ANTHROPIC_API_KEY` — contenido con IA.
   - `GOOGLE_PLACES_API_KEY` — descubrir prospectos.
   - `RESEND_API_KEY` — enviar emails/outreach.
   - `GH_TOKEN` — publicar en los repos de marca.
   - `GSC_CREDENTIALS` — (opcional) medición.
4. Deploy. Tendrás una URL tipo `https://ordinalmk-panel.onrender.com`.

## Qué puedes hacer desde el panel
- **Resumen:** estado, prioridad, prospectos, ingreso y pendientes por proyecto.
- **Revisión:** aprobar/rechazar el contenido fiscal apartado (_held).
- **Prospectos:** descubrir, aprobar y enviar outreach por proyecto.
- **Lanzar corrida:** ejecuta el motor (contenido→publica→prospecta→mide) en 2º plano.
- **Reportes:** contenido, ingresos y recomendaciones por proyecto.

## Notas honestas
- **Persistencia:** el `render.yaml` incluye un disco de 1GB montado en `reports/`
  para que prospectos/held/reportes NO se pierdan al reiniciar. Sin disco, el
  filesystem de Render es efímero.
- **Login:** es una sola contraseña compartida (suficiente para un equipo chico).
  Para usuarios individuales/roles, se añade después.
- **La corrida real** necesita las llaves puestas; sin ellas usa fallbacks
  (plantilla / colas) y no gasta.
