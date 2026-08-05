"""
SEO Monitor — Tracks keyword rankings, backlinks, and site health.
Integrates with Plausible for traffic data.
"""

import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from config.database import get_connection


class SEOMonitor:
    """Monitors SEO metrics for a project."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    def record_ranking(self, keyword: str, position: int, url: str = '',
                       language: str = 'es', search_engine: str = 'google') -> dict:
        """Record a keyword ranking."""
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO seo_rankings 
                (project_id, keyword, language, position, url, search_engine)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (self.project_id, keyword, language, position, url, search_engine))
            
            conn.execute("""
                INSERT INTO task_log (task_type, project_id, status, result)
                VALUES ('seo_ranking_check', ?, 'completed', ?)
            """, (self.project_id, json.dumps({
                'keyword': keyword,
                'position': position,
                'language': language
            })))
        
        return {'keyword': keyword, 'position': position, 'language': language}
    
    def record_backlink(self, source_url: str, target_url: str,
                        anchor_text: str = '', domain_authority: int = 0) -> dict:
        """Record a discovered backlink."""
        with get_connection() as conn:
            # Check if already exists
            existing = conn.execute("""
                SELECT id FROM seo_backlinks 
                WHERE project_id = ? AND source_url = ? AND target_url = ?
            """, (self.project_id, source_url, target_url)).fetchone()
            
            if existing:
                return {'status': 'already_exists', 'id': existing['id']}
            
            cursor = conn.execute("""
                INSERT INTO seo_backlinks 
                (project_id, source_url, target_url, anchor_text, domain_authority)
                VALUES (?, ?, ?, ?, ?)
            """, (self.project_id, source_url, target_url, anchor_text, domain_authority))
        
        return {'status': 'new', 'id': cursor.lastrowid}
    
    def get_latest_rankings(self, language: str = None) -> list:
        """Get latest ranking for each keyword."""
        with get_connection() as conn:
            if language:
                rows = conn.execute("""
                    SELECT keyword, language, position, url, search_engine, checked_at
                    FROM seo_rankings 
                    WHERE project_id = ? AND language = ?
                    AND id IN (
                        SELECT MAX(id) FROM seo_rankings 
                        WHERE project_id = ? AND language = ?
                        GROUP BY keyword
                    )
                    ORDER BY position ASC
                """, (self.project_id, language, self.project_id, language)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT keyword, language, position, url, search_engine, checked_at
                    FROM seo_rankings 
                    WHERE project_id = ?
                    AND id IN (
                        SELECT MAX(id) FROM seo_rankings 
                        WHERE project_id = ?
                        GROUP BY keyword, language
                    )
                    ORDER BY position ASC
                """, (self.project_id, self.project_id)).fetchall()
        
        return [dict(r) for r in rows]
    
    def get_ranking_history(self, keyword: str, language: str = 'es', days: int = 30) -> list:
        """Get ranking history for a specific keyword."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT keyword, position, checked_at
                FROM seo_rankings 
                WHERE project_id = ? AND keyword = ? AND language = ?
                AND checked_at >= ?
                ORDER BY checked_at ASC
            """, (self.project_id, keyword, language, since)).fetchall()
        
        return [dict(r) for r in rows]
    
    def get_backlinks(self, limit: int = 50) -> list:
        """Get all backlinks for the project."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT source_url, target_url, anchor_text, 
                       domain_authority, discovered_at
                FROM seo_backlinks 
                WHERE project_id = ?
                ORDER BY domain_authority DESC LIMIT ?
            """, (self.project_id, limit)).fetchall()
        
        return [dict(r) for r in rows]
    
    def get_backlink_stats(self) -> dict:
        """Get backlink statistics."""
        with get_connection() as conn:
            total = conn.execute("""
                SELECT COUNT(*) as count FROM seo_backlinks 
                WHERE project_id = ?
            """, (self.project_id,)).fetchone()
            
            by_da = conn.execute("""
                SELECT 
                    CASE 
                        WHEN domain_authority >= 80 THEN 'high'
                        WHEN domain_authority >= 50 THEN 'medium'
                        ELSE 'low'
                    END as tier,
                    COUNT(*) as count
                FROM seo_backlinks 
                WHERE project_id = ?
                GROUP BY tier
            """, (self.project_id,)).fetchall()
            
            unique_domains = conn.execute("""
                SELECT COUNT(DISTINCT source_url) as count FROM seo_backlinks 
                WHERE project_id = ?
            """, (self.project_id,)).fetchone()
        
        return {
            'total_backlinks': total['count'] if total else 0,
            'unique_domains': unique_domains['count'] if unique_domains else 0,
            'by_authority': {r['tier']: r['count'] for r in by_da}
        }
    
    def get_seo_health(self) -> dict:
        """Calculate overall SEO health score."""
        rankings = self.get_latest_rankings()
        backlinks = self.get_backlink_stats()
        
        # Score components
        ranking_score = 0
        if rankings:
            top_10 = sum(1 for r in rankings if r['position'] <= 10)
            top_20 = sum(1 for r in rankings if r['position'] <= 20)
            ranking_score = min(40, (top_10 * 8) + (top_20 * 3))
        
        backlink_score = min(30, backlinks['total_backlinks'] * 2)
        
        # Content score (from articles)
        with get_connection() as conn:
            articles = conn.execute("""
                SELECT COUNT(*) as count FROM content_articles 
                WHERE project_id = ? AND status = 'published'
            """, (self.project_id,)).fetchone()
        
        content_score = min(30, (articles['count'] if articles else 0) * 3)
        
        total_score = ranking_score + backlink_score + content_score
        
        # Determine grade
        if total_score >= 80:
            grade = 'A'
        elif total_score >= 60:
            grade = 'B'
        elif total_score >= 40:
            grade = 'C'
        elif total_score >= 20:
            grade = 'D'
        else:
            grade = 'F'
        
        return {
            'total_score': total_score,
            'grade': grade,
            'components': {
                'rankings': ranking_score,
                'backlinks': backlink_score,
                'content': content_score
            },
            'rankings_count': len(rankings),
            'top_10_count': sum(1 for r in rankings if r['position'] <= 10),
            'backlinks_total': backlinks['total_backlinks']
        }


if __name__ == "__main__":
    # Test SEO monitor
    monitor = SEOMonitor('yayika')
    health = monitor.get_seo_health()
    print(f"[?] SEO Health for Yayika: {json.dumps(health, indent=2)}")
