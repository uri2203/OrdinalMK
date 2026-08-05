"""
Analytics Tracker — Syncs data from Plausible Analytics and other sources.
Provides unified analytics across all projects.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

import requests

from config.database import get_connection


class AnalyticsTracker:
    """Tracks and syncs analytics data from multiple sources."""
    
    def __init__(self, project_id: str, plausible_site_id: str = None):
        self.project_id = project_id
        self.plausible_site_id = plausible_site_id
        self.plausible_api_url = "https://plausible.io/api"
        self.plausible_api_key = os.environ.get('PLAUSIBLE_API_KEY', '')
    
    def sync_plausible_data(self, date: str = None) -> dict:
        """Sync daily analytics from Plausible."""
        if not self.plausible_site_id:
            return {'error': 'No Plausible site_id configured'}
        
        if not self.plausible_api_key:
            return {'error': 'No PLAUSIBLE_API_KEY set'}
        
        target_date = date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        headers = {
            'Authorization': f'Bearer {self.plausible_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Get main stats
        stats_url = f"{self.plausible_api_url}/v1/stats/aggregate"
        stats_payload = {
            'site_id': self.plausible_site_id,
            'period': 'day',
            'date': target_date,
            'metrics': ['visitors', 'pageviews', 'bounce_rate', 'visit_duration']
        }
        
        try:
            stats_resp = requests.post(stats_url, json=stats_payload, headers=headers, timeout=30)
            stats_resp.raise_for_status()
            stats_data = stats_resp.json().get('results', {})
        except Exception as e:
            return {'error': f'Stats API error: {str(e)}'}
        
        # Get top pages
        pages_url = f"{self.plausible_api_url}/v1/stats/breakdown"
        pages_payload = {
            'site_id': self.plausible_site_id,
            'period': 'day',
            'date': target_date,
            'property': 'page',
            'metrics': ['pageviews', 'visitors'],
            'limit': 10
        }
        
        try:
            pages_resp = requests.post(pages_url, json=pages_payload, headers=headers, timeout=30)
            pages_resp.raise_for_status()
            top_pages = pages_resp.json().get('results', [])
        except Exception:
            top_pages = []
        
        # Get traffic by country
        countries_payload = {
            'site_id': self.plausible_site_id,
            'period': 'day',
            'date': target_date,
            'property': 'visit:country',
            'metrics': ['visitors'],
            'limit': 20
        }
        
        try:
            countries_resp = requests.post(pages_url, json=countries_payload, headers=headers, timeout=30)
            countries_resp.raise_for_status()
            countries = {r['visit:country']: r['visitors'] for r in countries_resp.json().get('results', [])}
        except Exception:
            countries = {}
        
        # Store in database
        visitors = stats_data.get('visitors', {}).get('value', 0)
        pageviews = stats_data.get('pageviews', {}).get('value', 0)
        bounce_rate = stats_data.get('bounce_rate', {}).get('value', 0)
        visit_duration = stats_data.get('visit_duration', {}).get('value', 0)
        
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO analytics_daily 
                (project_id, date, visitors, pageviews, bounce_rate, 
                 visit_duration_avg, top_pages, traffic_by_country)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.project_id, target_date, visitors, pageviews,
                bounce_rate, visit_duration,
                json.dumps([{'page': p.get('page', ''), 'views': p.get('pageviews', 0)} for p in top_pages[:10]]),
                json.dumps(countries)
            ))
            
            conn.execute("""
                INSERT INTO task_log (task_type, project_id, status, result)
                VALUES ('analytics_sync', ?, 'completed', ?)
            """, (self.project_id, json.dumps({
                'date': target_date,
                'visitors': visitors,
                'pageviews': pageviews
            })))
        
        return {
            'date': target_date,
            'visitors': visitors,
            'pageviews': pageviews,
            'bounce_rate': bounce_rate,
            'visit_duration': visit_duration,
            'top_pages_count': len(top_pages),
            'countries_count': len(countries)
        }
    
    def get_daily_analytics(self, days: int = 30) -> list:
        """Get daily analytics for the project."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT date, visitors, pageviews, bounce_rate,
                       visit_duration_avg, top_pages, traffic_by_country
                FROM analytics_daily 
                WHERE project_id = ?
                ORDER BY date DESC LIMIT ?
            """, (self.project_id, days)).fetchall()
        
        return [dict(r) for r in rows]
    
    def get_traffic_summary(self, days: int = 7) -> dict:
        """Get traffic summary for last N days."""
        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with get_connection() as conn:
            totals = conn.execute("""
                SELECT 
                    SUM(visitors) as total_visitors,
                    SUM(pageviews) as total_pageviews,
                    AVG(bounce_rate) as avg_bounce_rate,
                    AVG(visit_duration_avg) as avg_visit_duration
                FROM analytics_daily 
                WHERE project_id = ? AND date >= ?
            """, (self.project_id, since)).fetchone()
            
            daily = conn.execute("""
                SELECT date, visitors, pageviews
                FROM analytics_daily 
                WHERE project_id = ? AND date >= ?
                ORDER BY date ASC
            """, (self.project_id, since)).fetchall()
            
            # Trend (compare with previous period)
            prev_since = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
            prev_until = since
            
            prev_totals = conn.execute("""
                SELECT SUM(visitors) as total_visitors, SUM(pageviews) as total_pageviews
                FROM analytics_daily 
                WHERE project_id = ? AND date >= ? AND date < ?
            """, (self.project_id, prev_since, prev_until)).fetchone()
        
        current_visitors = totals['total_visitors'] or 0
        prev_visitors = prev_totals['total_visitors'] or 1
        visitor_trend = ((current_visitors - prev_visitors) / prev_visitors * 100) if prev_visitors else 0
        
        return {
            'period_days': days,
            'total_visitors': current_visitors,
            'total_pageviews': totals['total_pageviews'] or 0,
            'avg_bounce_rate': round(totals['avg_bounce_rate'] or 0, 1),
            'avg_visit_duration': round(totals['avg_visit_duration'] or 0, 0),
            'visitor_trend_pct': round(visitor_trend, 1),
            'daily_data': [dict(r) for r in daily]
        }
    
    def record_revenue(self, date: str, revenue_mxn: float = 0,
                       transactions: int = 0, new_subscribers: int = 0,
                       churned_subscribers: int = 0) -> dict:
        """Record daily revenue data."""
        with get_connection() as conn:
            # Get current MRR
            active_subs = conn.execute("""
                SELECT COUNT(*) as count FROM email_subscribers 
                WHERE project_id = ? AND status = 'active'
            """, (self.project_id,)).fetchone()
            
            # Simple MRR calculation (would be more complex with Stripe data)
            mrr = (active_subs['count'] or 0) * 179  # Average plan price
            arr = mrr * 12
            
            conn.execute("""
                INSERT OR REPLACE INTO revenue_daily 
                (project_id, date, revenue_mxn, transactions, 
                 new_subscribers, churned_subscribers, mrr, arr)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.project_id, date, revenue_mxn, transactions,
                  new_subscribers, churned_subscribers, mrr, arr))
        
        return {'date': date, 'revenue_mxn': revenue_mxn, 'mrr': mrr}
    
    def get_revenue_summary(self, days: int = 30) -> dict:
        """Get revenue summary."""
        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with get_connection() as conn:
            totals = conn.execute("""
                SELECT 
                    SUM(revenue_mxn) as total_revenue,
                    SUM(transactions) as total_transactions,
                    SUM(new_subscribers) as total_new_subs,
                    SUM(churned_subscribers) as total_churned,
                    AVG(mrr) as avg_mrr
                FROM revenue_daily 
                WHERE project_id = ? AND date >= ?
            """, (self.project_id, since)).fetchone()
            
            daily = conn.execute("""
                SELECT date, revenue_mxn, transactions, mrr
                FROM revenue_daily 
                WHERE project_id = ? AND date >= ?
                ORDER BY date ASC
            """, (self.project_id, since)).fetchall()
        
        return {
            'period_days': days,
            'total_revenue_mxn': round(totals['total_revenue'] or 0, 2),
            'total_transactions': totals['total_transactions'] or 0,
            'total_new_subscribers': totals['total_new_subs'] or 0,
            'total_churned': totals['total_churned'] or 0,
            'avg_mrr': round(totals['avg_mrr'] or 0, 2),
            'daily_data': [dict(r) for r in daily]
        }


if __name__ == "__main__":
    tracker = AnalyticsTracker('yayika', 'yayika.com')
    summary = tracker.get_traffic_summary(7)
    print(f"[#] Traffic Summary for Yayika (7 days):")
    print(f"   Visitors: {summary['total_visitors']}")
    print(f"   Pageviews: {summary['total_pageviews']}")
    print(f"   Bounce Rate: {summary['avg_bounce_rate']}%")
    print(f"   Trend: {summary['visitor_trend_pct']}%")
