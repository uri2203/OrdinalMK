"""
Marketing Engine — Main Application (Flask Dashboard)
Multi-project marketing automation dashboard with real-time charts.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import init_db, get_connection, get_db_path
from config.projects import load_config

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'marketing-engine-dev-key-change-in-prod')

# Load config
CONFIG = load_config()
PROJECTS = CONFIG.get('projects', {})


# ──────────────────────────────────────────────────
# ROUTES: Dashboard Overview
# ──────────────────────────────────────────────────

@app.route('/')
def index():
    """Main dashboard — overview of all projects."""
    return render_template('dashboard.html', projects=PROJECTS)


@app.route('/project/<project_id>')
def project_detail(project_id):
    """Detail view for a specific project."""
    if project_id not in PROJECTS:
        return redirect(url_for('index'))
    
    project = PROJECTS[project_id]
    
    # Get latest analytics
    with get_connection() as conn:
        # Last 30 days of analytics
        analytics = conn.execute("""
            SELECT * FROM analytics_daily 
            WHERE project_id = ? 
            ORDER BY date DESC LIMIT 30
        """, (project_id,)).fetchall()
        
        # Latest revenue
        revenue = conn.execute("""
            SELECT * FROM revenue_daily 
            WHERE project_id = ? 
            ORDER BY date DESC LIMIT 30
        """, (project_id,)).fetchall()
        
        # Content stats
        content_stats = conn.execute("""
            SELECT status, COUNT(*) as count FROM content_articles 
            WHERE project_id = ? 
            GROUP BY status
        """, (project_id,)).fetchall()
        
        # Email stats
        email_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_campaigns,
                SUM(recipient_count) as total_recipients,
                SUM(open_count) as total_opens,
                SUM(click_count) as total_clicks
            FROM email_campaigns 
            WHERE project_id = ?
        """, (project_id,)).fetchone()
        
        # SEO rankings
        seo_latest = conn.execute("""
            SELECT keyword, language, position, url 
            FROM seo_rankings 
            WHERE project_id = ? 
            AND id IN (
                SELECT MAX(id) FROM seo_rankings 
                WHERE project_id = ? 
                GROUP BY keyword, language
            )
            ORDER BY position ASC
            LIMIT 20
        """, (project_id, project_id)).fetchall()
    
    return render_template('project.html', 
                         project_id=project_id,
                         project=project,
                         analytics=analytics,
                         revenue=revenue,
                         content_stats=content_stats,
                         email_stats=email_stats,
                         seo_latest=seo_latest)


# ──────────────────────────────────────────────────
# API: Data Endpoints (for charts)
# ──────────────────────────────────────────────────

@app.route('/api/overview')
def api_overview():
    """API: aggregated stats across all projects."""
    with get_connection() as conn:
        # Total visitors today
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        today_stats = conn.execute("""
            SELECT SUM(visitors) as visitors, SUM(pageviews) as pageviews
            FROM analytics_daily WHERE date = ?
        """, (today,)).fetchone()
        
        yesterday_stats = conn.execute("""
            SELECT SUM(visitors) as visitors, SUM(pageviews) as pageviews
            FROM analytics_daily WHERE date = ?
        """, (yesterday,)).fetchone()
        
        # Total subscribers
        total_subs = conn.execute("""
            SELECT COUNT(*) as count FROM email_subscribers 
            WHERE status = 'active'
        """).fetchone()
        
        # Total articles
        total_articles = conn.execute("""
            SELECT COUNT(*) as count FROM content_articles
        """).fetchone()
        
        # This month revenue
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        month_revenue = conn.execute("""
            SELECT SUM(revenue_mxn) as total FROM revenue_daily 
            WHERE date >= ?
        """, (month_start,)).fetchone()
        
        # Task success rate (last 24h)
        tasks_24h = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM task_log 
            WHERE started_at >= datetime('now', '-1 day')
        """).fetchone()
    
    return jsonify({
        'today_visitors': today_stats['visitors'] or 0 if today_stats else 0,
        'yesterday_visitors': yesterday_stats['visitors'] or 0 if yesterday_stats else 0,
        'today_pageviews': today_stats['pageviews'] or 0 if today_stats else 0,
        'total_subscribers': total_subs['count'] if total_subs else 0,
        'total_articles': total_articles['count'] if total_articles else 0,
        'month_revenue_mxn': month_revenue['total'] or 0 if month_revenue else 0,
        'tasks_total_24h': tasks_24h['total'] or 0 if tasks_24h else 0,
        'tasks_completed_24h': tasks_24h['completed'] or 0 if tasks_24h else 0,
    })


@app.route('/api/project/<project_id>/analytics')
def api_project_analytics(project_id):
    """API: daily analytics for a project (last 30 days)."""
    days = request.args.get('days', 30, type=int)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT date, visitors, pageviews, bounce_rate, 
                   visit_duration_avg, traffic_by_language, traffic_by_country
            FROM analytics_daily 
            WHERE project_id = ? 
            ORDER BY date DESC LIMIT ?
        """, (project_id, days)).fetchall()
    
    return jsonify([dict(r) for r in rows])


@app.route('/api/project/<project_id>/revenue')
def api_project_revenue(project_id):
    """API: daily revenue for a project (last 30 days)."""
    days = request.args.get('days', 30, type=int)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT date, revenue_mxn, transactions, new_subscribers, 
                   churned_subscribers, mrr
            FROM revenue_daily 
            WHERE project_id = ? 
            ORDER BY date DESC LIMIT ?
        """, (project_id, days)).fetchall()
    
    return jsonify([dict(r) for r in rows])


@app.route('/api/project/<project_id>/content')
def api_project_content(project_id):
    """API: content articles for a project."""
    status = request.args.get('status', None)
    with get_connection() as conn:
        query = "SELECT * FROM content_articles WHERE project_id = ?"
        params = [project_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT 50"
        rows = conn.execute(query, params).fetchall()
    
    return jsonify([dict(r) for r in rows])


@app.route('/api/project/<project_id>/seo')
def api_project_seo(project_id):
    """API: latest SEO rankings for a project."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT keyword, language, position, url, checked_at
            FROM seo_rankings 
            WHERE project_id = ?
            AND id IN (
                SELECT MAX(id) FROM seo_rankings 
                WHERE project_id = ? 
                GROUP BY keyword, language
            )
            ORDER BY position ASC
        """, (project_id, project_id)).fetchall()
    
    return jsonify([dict(r) for r in rows])


@app.route('/api/project/<project_id>/email')
def api_project_email(project_id):
    """API: email campaign stats for a project."""
    with get_connection() as conn:
        campaigns = conn.execute("""
            SELECT * FROM email_campaigns 
            WHERE project_id = ? 
            ORDER BY created_at DESC LIMIT 20
        """, (project_id,)).fetchall()
        
        subscribers = conn.execute("""
            SELECT 
                DATE(subscribed_at) as date,
                COUNT(*) as count
            FROM email_subscribers 
            WHERE project_id = ?
            GROUP BY DATE(subscribed_at)
            ORDER BY date DESC LIMIT 30
        """, (project_id,)).fetchall()
    
    return jsonify({
        'campaigns': [dict(r) for r in campaigns],
        'subscriber_growth': [dict(r) for r in subscribers]
    })


@app.route('/api/tasks')
def api_tasks():
    """API: recent task execution log."""
    limit = request.args.get('limit', 20, type=int)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM task_log 
            ORDER BY started_at DESC LIMIT ?
        """, (limit,)).fetchall()
    
    return jsonify([dict(r) for r in rows])


@app.route('/api/health')
def api_health():
    """API: health check."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'db_exists': get_db_path().exists(),
        'projects_count': len(PROJECTS),
        'projects': list(PROJECTS.keys())
    })


# ──────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────

if __name__ == '__main__':
    # Init database
    init_db()
    
    # Run dashboard
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    
    print(f"\n[*] Marketing Engine Dashboard")
    print(f"   http://localhost:{port}")
    print(f"   Projects: {', '.join(PROJECTS.keys())}")
    print(f"   Database: {get_db_path()}\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
