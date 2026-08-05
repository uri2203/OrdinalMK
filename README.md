# OrdinalMK

**Multi-project marketing automation engine with visual dashboard.**

Motor de marketing automatizado multi-proyecto con dashboard visual, monitoreo SEO, automatización de emails, y reportes automatizados. Parte del ecosistema Ordinal.

## Features

- **📊 Dashboard Visual** — Chart.js + Flask, métricas en tiempo real
- **🌐 Multi-Proyecto** — Un solo motor para gestionar múltiples proyectos
- **📝 Content Engine** — Generación y gestión de artículos SEO multilingüe
- **🔍 SEO Monitor** — Rankings, backlinks, health score
- **📧 Email Automation** — Campañas, secuencias, métricas de engagement
- **📈 Analytics Tracker** — Integración con Plausible, métricas de tráfico
- **📋 Report Generator** — Reportes mensuales automáticos (JSON, CSV)
- **⏰ Scheduler** — Automatización basada en cron

## Architecture

```
marketing-engine/
├── config/              # Configuración multi-proyecto
│   ├── projects.yaml    # Definición de proyectos
│   ├── database.py      # SQLite database
│   └── projects.py      # Config loader
├── content/             # Content Engine
│   └── engine.py        # Generación de artículos
├── seo/                 # SEO Monitor
│   └── monitor.py       # Rankings & backlinks
├── email/               # Email Automation
│   └── automation.py    # Campañas & suscriptores
├── analytics/           # Analytics Tracker
│   └── tracker.py       # Plausible integration
├── reports/             # Report Generator
│   └── generator.py     # Monthly reports
├── scheduler/           # Task Scheduler
│   └── runner.py        # Cron automation
├── templates/           # Dashboard HTML
│   ├── dashboard.html   # Main dashboard
│   └── project.html     # Project detail view
├── static/              # Static assets
├── data/                # SQLite database (gitignored)
├── logs/                # Task logs (gitignored)
├── reports/             # Generated reports (gitignored)
├── app.py               # Flask application
├── requirements.txt     # Python dependencies
└── .env.example         # Environment template
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/uri2203/yayika-marketing-engine.git
cd yayika-marketing-engine

# 2. Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Initialize database
python -m config.database

# 6. Run dashboard
python app.py
```

Dashboard available at: `http://localhost:5000`

## Configuration

Edit `config/projects.yaml` to add/remove projects:

```yaml
projects:
  yayika:
    name: "Yayika"
    domain: "yayika.com"
    languages: ["es", "en", "pt", "fr", "de"]
    sources:
      plausible:
        site_id: "yayika.com"
    goals:
      monthly_unique_visitors: 10000
      monthly_revenue_mxn: 50000
```

## Scheduler (Cron)

Add to crontab for automated tasks:

```bash
# Daily analytics sync (3am)
0 3 * * * cd /path/to/marketing-engine && python -m scheduler.runner run

# Weekly reports (Monday 8am)
0 8 * * 1 cd /path/to/marketing-engine && python -m scheduler.runner daily

# Monthly reports (1st of month, 9am)
0 9 1 * * cd /path/to/marketing-engine && python -m scheduler.runner monthly
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard |
| `GET /project/<id>` | Project detail |
| `GET /api/overview` | Aggregated stats |
| `GET /api/project/<id>/analytics` | Daily analytics |
| `GET /api/project/<id>/revenue` | Revenue data |
| `GET /api/project/<id>/content` | Content articles |
| `GET /api/project/<id>/seo` | SEO rankings |
| `GET /api/project/<id>/email` | Email campaigns |
| `GET /api/tasks` | Task execution log |
| `GET /api/health` | Health check |

## Tech Stack

- **Backend**: Python 3.11+, Flask
- **Database**: SQLite (WAL mode)
- **Frontend**: Chart.js 4, Vanilla JS
- **Analytics**: Plausible API
- **Email**: Resend API
- **Payments**: Stripe
- **Hosting**: GitHub Pages (static) + any Python host (dashboard)

## License

Private — © 2026 Edgar Apolonio Aguilera
