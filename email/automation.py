"""
Email Automation — Manages email campaigns, sequences, and subscriber analytics.
Integrates with Resend API for sending.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

from config.database import get_connection


class EmailAutomation:
    """Manages email campaigns and subscriber analytics."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.api_key = os.environ.get('RESEND_API_KEY', '')
        self.from_email = os.environ.get('EMAIL_FROM', 'marketing@yayika.com')
    
    def add_subscriber(self, email: str, name: str = '',
                       source: str = 'web', tags: list = None) -> dict:
        """Add a new subscriber."""
        with get_connection() as conn:
            try:
                cursor = conn.execute("""
                    INSERT INTO email_subscribers 
                    (project_id, email, name, source, tags)
                    VALUES (?, ?, ?, ?, ?)
                """, (self.project_id, email, name, source, json.dumps(tags or [])))
                
                conn.execute("""
                    INSERT INTO task_log (task_type, project_id, status, result)
                    VALUES ('email_subscribe', ?, 'completed', ?)
                """, (self.project_id, json.dumps({'email': email, 'source': source})))
                
                return {'status': 'subscribed', 'id': cursor.lastrowid}
            except Exception as e:
                if 'UNIQUE' in str(e):
                    return {'status': 'already_subscribed'}
                raise
    
    def unsubscribe(self, email: str) -> dict:
        """Unsubscribe an email."""
        with get_connection() as conn:
            conn.execute("""
                UPDATE email_subscribers 
                SET status = 'unsubscribed', unsubscribed_at = datetime('now')
                WHERE project_id = ? AND email = ?
            """, (self.project_id, email))
        
        return {'status': 'unsubscribed', 'email': email}
    
    def create_campaign(self, name: str, subject: str, body_html: str,
                        sequence: str = 'general') -> dict:
        """Create an email campaign."""
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO email_campaigns 
                (project_id, name, sequence, subject, body_html)
                VALUES (?, ?, ?, ?, ?)
            """, (self.project_id, name, sequence, subject, body_html))
        
        return {'id': cursor.lastrowid, 'name': name, 'status': 'draft'}
    
    def send_campaign(self, campaign_id: int) -> dict:
        """Send a campaign to all active subscribers."""
        with get_connection() as conn:
            # Get campaign
            campaign = conn.execute("""
                SELECT * FROM email_campaigns 
                WHERE id = ? AND project_id = ?
            """, (campaign_id, self.project_id)).fetchone()
            
            if not campaign:
                return {'error': 'Campaign not found'}
            
            # Get active subscribers
            subscribers = conn.execute("""
                SELECT email, name FROM email_subscribers 
                WHERE project_id = ? AND status = 'active'
            """, (self.project_id,)).fetchall()
            
            # Update campaign status
            conn.execute("""
                UPDATE email_campaigns 
                SET status = 'sent', sent_at = datetime('now'), recipient_count = ?
                WHERE id = ?
            """, (len(subscribers), campaign_id))
            
            # Log the send
            conn.execute("""
                INSERT INTO task_log (task_type, project_id, status, result)
                VALUES ('email_send', ?, 'completed', ?)
            """, (self.project_id, json.dumps({
                'campaign_id': campaign_id,
                'recipients': len(subscribers)
            })))
        
        return {
            'status': 'sent',
            'recipients': len(subscribers),
            'campaign_id': campaign_id
        }
    
    def get_campaigns(self, limit: int = 20) -> list:
        """Get recent campaigns."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM email_campaigns 
                WHERE project_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (self.project_id, limit)).fetchall()
        
        return [dict(r) for r in rows]
    
    def get_subscribers(self, status: str = 'active') -> list:
        """Get subscribers by status."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM email_subscribers 
                WHERE project_id = ? AND status = ?
                ORDER BY subscribed_at DESC
            """, (self.project_id, status)).fetchall()
        
        return [dict(r) for r in rows]
    
    def get_subscriber_stats(self) -> dict:
        """Get subscriber statistics."""
        with get_connection() as conn:
            total = conn.execute("""
                SELECT COUNT(*) as count FROM email_subscribers 
                WHERE project_id = ?
            """, (self.project_id,)).fetchone()
            
            active = conn.execute("""
                SELECT COUNT(*) as count FROM email_subscribers 
                WHERE project_id = ? AND status = 'active'
            """, (self.project_id,)).fetchone()
            
            # Growth last 30 days
            growth = conn.execute("""
                SELECT DATE(subscribed_at) as date, COUNT(*) as count
                FROM email_subscribers 
                WHERE project_id = ? 
                AND subscribed_at >= datetime('now', '-30 days')
                GROUP BY DATE(subscribed_at)
                ORDER BY date ASC
            """, (self.project_id,)).fetchall()
            
            # By source
            by_source = conn.execute("""
                SELECT source, COUNT(*) as count 
                FROM email_subscribers 
                WHERE project_id = ?
                GROUP BY source
            """, (self.project_id,)).fetchall()
        
        return {
            'total': total['count'] if total else 0,
            'active': active['count'] if active else 0,
            'growth': [dict(r) for r in growth],
            'by_source': {r['source']: r['count'] for r in by_source}
        }
    
    def get_campaign_metrics(self) -> dict:
        """Get aggregated email metrics."""
        with get_connection() as conn:
            totals = conn.execute("""
                SELECT 
                    COUNT(*) as total_campaigns,
                    SUM(recipient_count) as total_recipients,
                    SUM(open_count) as total_opens,
                    SUM(click_count) as total_clicks,
                    SUM(bounce_count) as total_bounces
                FROM email_campaigns 
                WHERE project_id = ? AND status = 'sent'
            """, (self.project_id,)).fetchone()
        
        recipients = totals['total_recipients'] or 1  # Avoid division by zero
        
        return {
            'total_campaigns': totals['total_campaigns'] or 0,
            'total_recipients': totals['total_recipients'] or 0,
            'total_opens': totals['total_opens'] or 0,
            'total_clicks': totals['total_clicks'] or 0,
            'total_bounces': totals['total_bounces'] or 0,
            'open_rate': round((totals['total_opens'] or 0) / recipients * 100, 1),
            'click_rate': round((totals['total_clicks'] or 0) / recipients * 100, 1),
            'bounce_rate': round((totals['total_bounces'] or 0) / recipients * 100, 1)
        }


# Email sequence templates
EMAIL_SEQUENCES = {
    'welcome': {
        'name': 'Bienvenida',
        'emails': [
            {'delay_hours': 0, 'subject_key': 'welcome_1'},
            {'delay_hours': 24, 'subject_key': 'welcome_2'},
            {'delay_hours': 72, 'subject_key': 'welcome_3'}
        ]
    },
    'nurture': {
        'name': 'Nutrición',
        'emails': [
            {'delay_hours': 48, 'subject_key': 'nurture_1'},
            {'delay_hours': 120, 'subject_key': 'nurture_2'},
            {'delay_hours': 240, 'subject_key': 'nurture_3'}
        ]
    },
    'upsell': {
        'name': 'Conversión',
        'emails': [
            {'delay_hours': 168, 'subject_key': 'upsell_1'},
            {'delay_hours': 336, 'subject_key': 'upsell_2'}
        ]
    }
}


if __name__ == "__main__":
    # Test email automation
    automation = EmailAutomation('yayika')
    stats = automation.get_subscriber_stats()
    print(f"[@] Email Stats for Yayika: {json.dumps(stats, indent=2)}")
