"""
Marketing Engine — Core Database Module
SQLite-backed storage for analytics, content, and campaign data.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "marketing_engine.db"


def get_db_path():
    return DB_PATH


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize all database tables."""
    with get_connection() as conn:
        conn.executescript("""
        -- Proyectos
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            domain TEXT,
            languages TEXT DEFAULT '["es","en"]',
            config TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Artículos de contenido generados
        CREATE TABLE IF NOT EXISTS content_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'es',
            body TEXT,
            meta_description TEXT,
            keywords TEXT DEFAULT '[]',
            status TEXT DEFAULT 'draft',  -- draft, published, archived
            source TEXT DEFAULT 'generated',  -- generated, imported, curated
            word_count INTEGER DEFAULT 0,
            reading_time_min INTEGER DEFAULT 0,
            published_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        -- SEO Rankings
        CREATE TABLE IF NOT EXISTS seo_rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            keyword TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'es',
            position INTEGER,
            url TEXT,
            search_engine TEXT DEFAULT 'google',
            checked_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        -- SEO Backlinks
        CREATE TABLE IF NOT EXISTS seo_backlinks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            source_url TEXT NOT NULL,
            target_url TEXT NOT NULL,
            anchor_text TEXT,
            domain_authority INTEGER,
            discovered_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        -- Email Campaigns
        CREATE TABLE IF NOT EXISTS email_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sequence TEXT NOT NULL,
            subject TEXT NOT NULL,
            body_html TEXT,
            status TEXT DEFAULT 'draft',  -- draft, scheduled, sent, failed
            scheduled_at TEXT,
            sent_at TEXT,
            recipient_count INTEGER DEFAULT 0,
            open_count INTEGER DEFAULT 0,
            click_count INTEGER DEFAULT 0,
            bounce_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        -- Email Subscribers
        CREATE TABLE IF NOT EXISTS email_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            email TEXT NOT NULL,
            name TEXT,
            status TEXT DEFAULT 'active',  -- active, unsubscribed, bounced
            source TEXT DEFAULT 'web',  -- web, import, api
            subscribed_at TEXT DEFAULT (datetime('now')),
            unsubscribed_at TEXT,
            tags TEXT DEFAULT '[]',
            FOREIGN KEY (project_id) REFERENCES projects(id),
            UNIQUE(project_id, email)
        );

        -- Analytics Daily Snapshots
        CREATE TABLE IF NOT EXISTS analytics_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            date TEXT NOT NULL,
            visitors INTEGER DEFAULT 0,
            pageviews INTEGER DEFAULT 0,
            bounce_rate REAL DEFAULT 0,
            visit_duration_avg REAL DEFAULT 0,
            top_pages TEXT DEFAULT '[]',
            top_referrers TEXT DEFAULT '[]',
            traffic_by_language TEXT DEFAULT '{}',
            traffic_by_country TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id),
            UNIQUE(project_id, date)
        );

        -- Revenue Tracking
        CREATE TABLE IF NOT EXISTS revenue_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            date TEXT NOT NULL,
            revenue_mxn REAL DEFAULT 0,
            revenue_usd REAL DEFAULT 0,
            transactions INTEGER DEFAULT 0,
            new_subscribers INTEGER DEFAULT 0,
            churned_subscribers INTEGER DEFAULT 0,
            mrr REAL DEFAULT 0,
            arr REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id),
            UNIQUE(project_id, date)
        );

        -- Competitor Tracking
        CREATE TABLE IF NOT EXISTS competitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            domain TEXT,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        -- Competitor Snapshots
        CREATE TABLE IF NOT EXISTS competitor_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competitor_id INTEGER NOT NULL,
            estimated_traffic INTEGER,
            domain_authority INTEGER,
            backlinks_count INTEGER,
            top_keywords TEXT DEFAULT '[]',
            snapshot_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (competitor_id) REFERENCES competitors(id)
        );

        -- Scheduled Reports
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            report_type TEXT NOT NULL,  -- daily, weekly, monthly
            title TEXT NOT NULL,
            data TEXT DEFAULT '{}',
            format TEXT DEFAULT 'json',  -- json, csv, pdf
            file_path TEXT,
            status TEXT DEFAULT 'generated',
            generated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        -- Tasks / Jobs log
        CREATE TABLE IF NOT EXISTS task_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            project_id TEXT,
            status TEXT DEFAULT 'running',  -- running, completed, failed
            result TEXT DEFAULT '{}',
            error TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );
        """)


def seed_projects(config_path: str):
    """Seed projects from YAML config into database."""
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    with get_connection() as conn:
        for pid, pconfig in config.get('projects', {}).items():
            conn.execute("""
                INSERT OR REPLACE INTO projects (id, name, domain, languages, config, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (
                pid,
                pconfig.get('name', pid),
                pconfig.get('domain', ''),
                json.dumps(pconfig.get('languages', ['es'])),
                json.dumps(pconfig, default=str)
            ))
    
    print(f"[OK] Seeded {len(config.get('projects', {}))} projects")


if __name__ == "__main__":
    init_db()
    print(f"[OK] Database initialized at {DB_PATH}")
    
    config_path = Path(__file__).parent / "projects.yaml"
    if config_path.exists():
        seed_projects(str(config_path))
