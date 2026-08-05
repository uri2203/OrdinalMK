"""
Seed Script — Populates database with realistic test data.
Run once to populate the dashboard with sample data.
"""

import sys
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.database import init_db, get_connection, seed_projects
from config.projects import load_config


def seed_analytics(project_id: str, days: int = 30):
    """Seed realistic daily analytics data."""
    base_visitors = random.randint(80, 200)
    base_pageviews = base_visitors * random.uniform(1.5, 3.0)
    
    with get_connection() as conn:
        for i in range(days, 0, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            
            # Simulate growth trend
            growth_factor = 1 + (days - i) * 0.008
            weekday = (datetime.now() - timedelta(days=i)).weekday()
            # Weekends have less traffic
            weekend_factor = 0.6 if weekday >= 5 else 1.0
            
            visitors = int(base_visitors * growth_factor * weekend_factor * random.uniform(0.8, 1.2))
            pageviews = int(visitors * random.uniform(1.8, 3.2))
            bounce_rate = random.uniform(35, 65)
            visit_duration = random.uniform(120, 400)
            
            # Language distribution
            traffic_by_language = json.dumps({
                'es': int(visitors * 0.45),
                'en': int(visitors * 0.25),
                'pt': int(visitors * 0.15),
                'fr': int(visitors * 0.10),
                'de': int(visitors * 0.05)
            })
            
            traffic_by_country = json.dumps({
                'MX': int(visitors * 0.40),
                'US': int(visitors * 0.20),
                'CO': int(visitors * 0.10),
                'AR': int(visitors * 0.08),
                'ES': int(visitors * 0.07),
                'BR': int(visitors * 0.08),
                'OTHER': int(visitors * 0.07)
            })
            
            top_pages = json.dumps([
                {'page': '/', 'views': int(pageviews * 0.25)},
                {'page': '/tienda', 'views': int(pageviews * 0.15)},
                {'page': '/cuenta/mi-ciclo', 'views': int(pageviews * 0.12)},
                {'page': '/comunidad', 'views': int(pageviews * 0.10)},
                {'page': '/blog/ tracker-ciclo-menstrual', 'views': int(pageviews * 0.08)}
            ])
            
            conn.execute("""
                INSERT OR REPLACE INTO analytics_daily 
                (project_id, date, visitors, pageviews, bounce_rate, 
                 visit_duration_avg, top_pages, traffic_by_language, traffic_by_country)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (project_id, date, visitors, pageviews, bounce_rate,
                  visit_duration, top_pages, traffic_by_language, traffic_by_country))


def seed_revenue(project_id: str, days: int = 30):
    """Seed realistic daily revenue data."""
    plans = [
        {'name': 'Semilla', 'price': 179, 'weight': 0.5},
        {'name': 'Guerrera', 'price': 349, 'weight': 0.35},
        {'name': 'Diamante', 'price': 549, 'weight': 0.15}
    ]
    
    base_daily_revenue = random.uniform(800, 2000)
    base_subs = 25
    
    with get_connection() as conn:
        for i in range(days, 0, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            
            # Growth trend
            growth = 1 + (days - i) * 0.01
            
            # Simulate daily revenue
            daily_revenue = base_daily_revenue * growth * random.uniform(0.7, 1.3)
            
            # Random transactions
            transactions = random.randint(1, 5)
            new_subs = random.randint(0, 3)
            churned = random.randint(0, 1)
            
            base_subs += new_subs - churned
            mrr = base_subs * 250  # Average plan
            arr = mrr * 12
            
            conn.execute("""
                INSERT OR REPLACE INTO revenue_daily 
                (project_id, date, revenue_mxn, transactions, 
                 new_subscribers, churned_subscribers, mrr, arr)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (project_id, date, round(daily_revenue, 2), transactions,
                  new_subs, churned, mrr, arr))


def seed_content(project_id: str):
    """Seed sample content articles."""
    articles = [
        {'title': 'Guia Completa del Ciclo Menstrual para Principiantes', 'lang': 'es', 'status': 'published', 'words': 2500},
        {'title': 'Como Usar el Planner de Yayika para Organizar tu Vida', 'lang': 'es', 'status': 'published', 'words': 1800},
        {'title': '5 Beneficios de Trackear tu Ciclo Menstrual', 'lang': 'es', 'status': 'published', 'words': 1500},
        {'title': 'Menstrual Cycle Tracking: A Complete Guide', 'lang': 'en', 'status': 'published', 'words': 2200},
        {'title': 'Digital Products for Women: Why They Matter', 'lang': 'en', 'status': 'published', 'words': 1600},
        {'title': 'Guia do Ciclo Menstrual para Iniciantes', 'lang': 'pt', 'status': 'published', 'words': 2000},
        {'title': 'Guide Complet du Cycle Menstruel', 'lang': 'fr', 'status': 'published', 'words': 1900},
        {'title': 'Kompletter Leitfaden fur den Menstruationszyklus', 'lang': 'de', 'status': 'published', 'words': 2100},
        {'title': 'Planificador para Mujeres Emprendedoras: Tips y Tricks', 'lang': 'es', 'status': 'draft', 'words': 1200},
        {'title': 'Community Building for Women: Best Practices', 'lang': 'en', 'status': 'draft', 'words': 900},
    ]
    
    import hashlib
    import re
    
    with get_connection() as conn:
        for a in articles:
            slug = re.sub(r'[^\w\s-]', '', a['title'].lower())
            slug = re.sub(r'[\s_]+', '-', slug).strip('-')
            hash_suffix = hashlib.md5(a['title'].encode()).hexdigest()[:6]
            slug = f"{slug}-{hash_suffix}"
            
            published_at = datetime.now().isoformat() if a['status'] == 'published' else None
            
            conn.execute("""
                INSERT INTO content_articles 
                (project_id, title, slug, language, word_count, reading_time_min, 
                 status, meta_description, keywords, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, a['title'], slug, a['lang'], a['words'],
                max(1, a['words'] // 200), a['status'],
                f"Descubre todo sobre {a['title'].lower()}. Guia practica con tips y recomendaciones.",
                json.dumps(['ciclo menstrual', 'mujeres', 'productos digitales']),
                published_at
            ))


def seed_seo(project_id: str):
    """Seed SEO rankings and backlinks."""
    rankings = [
        {'keyword': 'tracker ciclo menstrual', 'lang': 'es', 'pos': 3},
        {'keyword': 'planificador mujeres', 'lang': 'es', 'pos': 7},
        {'keyword': 'productos digitales mujeres', 'lang': 'es', 'pos': 12},
        {'keyword': 'comunidad mujeres emprendedoras', 'lang': 'es', 'pos': 5},
        {'keyword': 'menstrual cycle tracker', 'lang': 'en', 'pos': 15},
        {'keyword': 'women planner digital', 'lang': 'en', 'pos': 22},
        {'keyword': 'digital products women', 'lang': 'en', 'pos': 18},
        {'keyword': 'rastreador ciclo menstrual', 'lang': 'pt', 'pos': 8},
        {'keyword': 'suivi cycle menstruel', 'lang': 'fr', 'pos': 25},
        {'keyword': 'zyklus tracking frauen', 'lang': 'de', 'pos': 30},
    ]
    
    backlinks = [
        {'source': 'https://blog-mujeres.com/ciclo-menstrual', 'anchor': 'tracker menstrual', 'da': 45},
        {'source': 'https://emprendedoras.com/productos-digitales', 'anchor': 'Yayika', 'da': 52},
        {'source': 'https://health-women.org/menstrual-tracking', 'anchor': 'menstrual cycle tracker', 'da': 38},
        {'source': 'https://tech-women.co/digital-tools', 'anchor': 'digital products for women', 'da': 41},
    ]
    
    with get_connection() as conn:
        for r in rankings:
            conn.execute("""
                INSERT INTO seo_rankings (project_id, keyword, language, position, url, search_engine)
                VALUES (?, ?, ?, ?, ?, 'google')
            """, (project_id, r['keyword'], r['lang'], r['pos'], f"https://yayika.com"))
        
        for b in backlinks:
            conn.execute("""
                INSERT INTO seo_backlinks (project_id, source_url, target_url, anchor_text, domain_authority)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, b['source'], 'https://yayika.com', b['anchor'], b['da']))


def seed_email(project_id: str):
    """Seed email subscribers and campaigns."""
    subscribers = [
        {'email': 'maria@example.com', 'name': 'Maria', 'source': 'web'},
        {'email': 'laura@example.com', 'name': 'Laura', 'source': 'web'},
        {'email': 'ana@example.com', 'name': 'Ana', 'source': 'web'},
        {'email': 'sophia@example.com', 'name': 'Sophia', 'source': 'import'},
        {'email': 'julia@example.com', 'name': 'Julia', 'source': 'web'},
        {'email': 'camila@example.com', 'name': 'Camila', 'source': 'api'},
        {'email': 'valentina@example.com', 'name': 'Valentina', 'source': 'web'},
        {'email': 'isabella@example.com', 'name': 'Isabella', 'source': 'web'},
    ]
    
    campaigns = [
        {'name': 'Welcome Series #1', 'seq': 'welcome', 'subject': 'Bienvenida a Yayika!', 'status': 'sent', 'recipients': 8, 'opens': 7, 'clicks': 5},
        {'name': 'Nurture Tips', 'seq': 'nurture', 'subject': '5 Tips para tu Ciclo', 'status': 'sent', 'recipients': 8, 'opens': 6, 'clicks': 3},
        {'name': 'Upsell Plan Guerrera', 'seq': 'upsell', 'subject': 'Desbloquea tu Potencial', 'status': 'sent', 'recipients': 8, 'opens': 5, 'clicks': 2},
    ]
    
    with get_connection() as conn:
        for s in subscribers:
            try:
                conn.execute("""
                    INSERT INTO email_subscribers (project_id, email, name, source)
                    VALUES (?, ?, ?, ?)
                """, (project_id, s['email'], s['name'], s['source']))
            except Exception:
                pass
        
        for c in campaigns:
            conn.execute("""
                INSERT INTO email_campaigns 
                (project_id, name, sequence, subject, status, recipient_count, 
                 open_count, click_count, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (project_id, c['name'], c['seq'], c['subject'], c['status'],
                  c['recipients'], c['opens'], c['clicks']))


def seed_tasks(project_id: str):
    """Seed recent task log."""
    tasks = [
        {'type': 'analytics_sync', 'status': 'completed'},
        {'type': 'seo_health_check', 'status': 'completed'},
        {'type': 'content_review', 'status': 'completed'},
        {'type': 'email_check', 'status': 'completed'},
        {'type': 'analytics_sync', 'status': 'completed'},
        {'type': 'seo_ranking_check', 'status': 'completed'},
    ]
    
    with get_connection() as conn:
        for i, t in enumerate(tasks):
            started = (datetime.now() - timedelta(hours=i*2)).isoformat()
            completed = (datetime.now() - timedelta(hours=i*2) + timedelta(seconds=random.randint(1, 15))).isoformat()
            
            conn.execute("""
                INSERT INTO task_log (task_type, project_id, status, started_at, completed_at, result)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (t['type'], project_id, t['status'], started, completed, 
                  json.dumps({'test': True})))


def main():
    """Run all seed functions."""
    print("[*] Initializing database...")
    init_db()
    
    print("[*] Seeding projects...")
    config_path = Path(__file__).parent / "config" / "projects.yaml"
    seed_projects(str(config_path))
    
    project_id = 'yayika'
    print(f"[*] Seeding data for: {project_id}")
    
    print("   [*] Analytics (30 days)...")
    seed_analytics(project_id, 30)
    
    print("   [*] Revenue (30 days)...")
    seed_revenue(project_id, 30)
    
    print("   [*] Content articles...")
    seed_content(project_id)
    
    print("   [*] SEO rankings & backlinks...")
    seed_seo(project_id)
    
    print("   [*] Email subscribers & campaigns...")
    seed_email(project_id)
    
    print("   [*] Task log...")
    seed_tasks(project_id)
    
    print("\n[OK] Database seeded successfully!")
    print("[*] Run 'python app.py' to see the dashboard.")


if __name__ == "__main__":
    main()
