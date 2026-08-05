"""
Content Engine — Generates and manages SEO-optimized articles.
Supports multilingual content generation and publishing workflows.
"""

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path

from config.database import get_connection


class ContentEngine:
    """Manages content creation, optimization, and publishing."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    def create_article(self, title: str, body: str, language: str = 'es',
                       meta_description: str = '', keywords: list = None,
                       source: str = 'generated') -> dict:
        """Create a new article."""
        slug = self._generate_slug(title)
        word_count = len(body.split())
        reading_time = max(1, word_count // 200)
        
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO content_articles 
                (project_id, title, slug, language, body, meta_description, 
                 keywords, word_count, reading_time_min, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.project_id, title, slug, language, body,
                meta_description, json.dumps(keywords or []),
                word_count, reading_time, source
            ))
            
            article_id = cursor.lastrowid
            
            # Log the task
            conn.execute("""
                INSERT INTO task_log (task_type, project_id, status, result)
                VALUES ('content_create', ?, 'completed', ?)
            """, (self.project_id, json.dumps({
                'article_id': article_id,
                'title': title,
                'language': language
            })))
        
        return {
            'id': article_id,
            'title': title,
            'slug': slug,
            'language': language,
            'word_count': word_count,
            'reading_time_min': reading_time
        }
    
    def publish_article(self, article_id: int) -> bool:
        """Mark article as published."""
        with get_connection() as conn:
            conn.execute("""
                UPDATE content_articles 
                SET status = 'published', published_at = datetime('now')
                WHERE id = ? AND project_id = ?
            """, (article_id, self.project_id))
        return True
    
    def get_drafts(self, limit: int = 20) -> list:
        """Get unpublished drafts."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM content_articles 
                WHERE project_id = ? AND status = 'draft'
                ORDER BY created_at DESC LIMIT ?
            """, (self.project_id, limit)).fetchall()
        return [dict(r) for r in rows]
    
    def get_published(self, language: str = None, limit: int = 50) -> list:
        """Get published articles, optionally filtered by language."""
        with get_connection() as conn:
            if language:
                rows = conn.execute("""
                    SELECT * FROM content_articles 
                    WHERE project_id = ? AND status = 'published' AND language = ?
                    ORDER BY published_at DESC LIMIT ?
                """, (self.project_id, language, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM content_articles 
                    WHERE project_id = ? AND status = 'published'
                    ORDER BY published_at DESC LIMIT ?
                """, (self.project_id, limit)).fetchall()
        return [dict(r) for r in rows]
    
    def get_stats(self) -> dict:
        """Get content statistics for the project."""
        with get_connection() as conn:
            total = conn.execute("""
                SELECT COUNT(*) as count FROM content_articles 
                WHERE project_id = ?
            """, (self.project_id,)).fetchone()
            
            by_status = conn.execute("""
                SELECT status, COUNT(*) as count FROM content_articles 
                WHERE project_id = ?
                GROUP BY status
            """, (self.project_id,)).fetchall()
            
            by_language = conn.execute("""
                SELECT language, COUNT(*) as count FROM content_articles 
                WHERE project_id = ?
                GROUP BY language
            """, (self.project_id,)).fetchall()
            
            avg_words = conn.execute("""
                SELECT AVG(word_count) as avg_words, 
                       AVG(reading_time_min) as avg_reading_time
                FROM content_articles 
                WHERE project_id = ? AND status = 'published'
            """, (self.project_id,)).fetchone()
        
        return {
            'total': total['count'] if total else 0,
            'by_status': {r['status']: r['count'] for r in by_status},
            'by_language': {r['language']: r['count'] for r in by_language},
            'avg_word_count': round(avg_words['avg_words'] or 0, 0) if avg_words else 0,
            'avg_reading_time': round(avg_words['avg_reading_time'] or 0, 1) if avg_words else 0
        }
    
    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug from title."""
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = slug.strip('-')
        
        # Add hash for uniqueness
        hash_suffix = hashlib.md5(title.encode()).hexdigest()[:6]
        return f"{slug}-{hash_suffix}"


# ──────────────────────────────────────────────────
# Content Templates (SEO-optimized)
# ──────────────────────────────────────────────────

CONTENT_TEMPLATES = {
    'blog_post': {
        'structure': [
            'title_with_keyword',
            'hook_paragraph',
            'problem_statement',
            'solution_with_product',
            'benefits_list',
            'testimonial_or_data',
            'call_to_action',
            'faq_section'
        ],
        'seo_rules': {
            'title_length': (50, 60),
            'meta_description_length': (150, 160),
            'keyword_density_pct': (1.0, 2.5),
            'min_words': 1500,
            'headings_required': True,
            'internal_links_min': 2,
            'external_links_min': 1,
            'image_alt_required': True
        }
    },
    'product_page': {
        'structure': [
            'product_title',
            'benefits_headline',
            'features_list',
            'pricing_table',
            'faq',
            'cta_button'
        ],
        'seo_rules': {
            'title_length': (50, 60),
            'meta_description_length': (150, 160),
            'min_words': 800
        }
    },
    'landing_page': {
        'structure': [
            'hero_section',
            'social_proof',
            'problem_agitation',
            'solution',
            'features_grid',
            'pricing',
            'testimonials',
            'guarantee',
            'final_cta',
            'faq'
        ],
        'seo_rules': {
            'title_length': (40, 55),
            'min_words': 1200
        }
    }
}


def generate_content_brief(project_config: dict, topic: str, language: str = 'es') -> dict:
    """Generate a content brief based on project config and topic."""
    keywords = project_config.get('seo', {}).get('target_keywords', {}).get(language, [])
    
    return {
        'topic': topic,
        'language': language,
        'target_keywords': keywords[:5],
        'suggested_title': f"{topic.title()} - Guía Completa {datetime.now().year}",
        'meta_description': f"Descubre todo sobre {topic}. Guía práctica con tips, herramientas y recomendaciones para {project_config.get('name', '')}.",
        'content_type': 'blog_post',
        'template': CONTENT_TEMPLATES['blog_post'],
        'competitor_research': f"Analyzing top 10 results for: {topic}",
        'internal_links': [],
        'estimated_reading_time': '8-10 min'
    }


if __name__ == "__main__":
    # Test content engine
    engine = ContentEngine('yayika')
    stats = engine.get_stats()
    print(f"[#] Content Stats for Yayika: {json.dumps(stats, indent=2)}")
