"""
Report Generator — Creates marketing reports in multiple formats.
Supports JSON, CSV, and basic HTML reports.
"""

import json
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.database import get_connection
from analytics.tracker import AnalyticsTracker
from mailer.automation import EmailAutomation
from seo.monitor import SEOMonitor
from content.engine import ContentEngine


class ReportGenerator:
    """Generates comprehensive marketing reports."""
    
    def __init__(self, project_id: str, project_config: dict):
        self.project_id = project_id
        self.config = project_config
        self.reports_dir = Path(__file__).parent.parent / "reports"
        self.reports_dir.mkdir(exist_ok=True)
    
    def generate_monthly_report(self, month: int = None, year: int = None) -> dict:
        """Generate a comprehensive monthly marketing report."""
        now = datetime.now()
        month = month or now.month
        year = year or now.year
        
        # Calculate date range
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year+1}-01-01"
        else:
            end_date = f"{year}-{month+1:02d}-01"
        
        # Gather data from all modules
        tracker = AnalyticsTracker(self.project_id, self.config.get('sources', {}).get('plausible', {}).get('site_id'))
        email = EmailAutomation(self.project_id)
        seo = SEOMonitor(self.project_id)
        content = ContentEngine(self.project_id)
        
        # Compile report data
        report_data = {
            'project': self.project_id,
            'period': f"{year}-{month:02d}",
            'generated_at': now.isoformat(),
            'sections': {
                'traffic': tracker.get_traffic_summary(30),
                'revenue': tracker.get_revenue_summary(30),
                'email': email.get_campaign_metrics(),
                'email_subscribers': email.get_subscriber_stats(),
                'seo_health': seo.get_seo_health(),
                'seo_rankings': seo.get_latest_rankings(),
                'backlinks': seo.get_backlink_stats(),
                'content': content.get_stats(),
                'tasks': self._get_task_summary(start_date, end_date)
            }
        }
        
        # Save report
        report_filename = f"monthly_{self.project_id}_{year}_{month:02d}.json"
        report_path = self.reports_dir / report_filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        
        # Also save to database
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO reports (project_id, report_type, title, data, file_path)
                VALUES (?, 'monthly', ?, ?, ?)
            """, (
                self.project_id,
                f"Reporte Mensual {self.config.get('name', self.project_id)} - {year}/{month:02d}",
                json.dumps(report_data, default=str),
                str(report_path)
            ))
        
        return {
            'status': 'generated',
            'file': str(report_path),
            'period': report_data['period'],
            'summary': self._get_summary_text(report_data)
        }
    
    def generate_csv_export(self, data_type: str = 'analytics', days: int = 30) -> str:
        """Export data as CSV."""
        now = datetime.now()
        filename = f"export_{self.project_id}_{data_type}_{now.strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = self.reports_dir / filename
        
        tracker = AnalyticsTracker(self.project_id)
        
        if data_type == 'analytics':
            data = tracker.get_daily_analytics(days)
            headers = ['date', 'visitors', 'pageviews', 'bounce_rate', 'visit_duration']
        elif data_type == 'revenue':
            data = tracker.get_revenue_summary(days)['daily_data']
            headers = ['date', 'revenue_mxn', 'transactions', 'mrr']
        else:
            return ''
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
        
        return str(filepath)
    
    def _get_task_summary(self, start_date: str, end_date: str) -> dict:
        """Get task execution summary for a period."""
        with get_connection() as conn:
            tasks = conn.execute("""
                SELECT task_type, status, COUNT(*) as count
                FROM task_log 
                WHERE started_at >= ? AND started_at < ?
                GROUP BY task_type, status
            """, (start_date, end_date)).fetchall()
        
        summary = {}
        for task in tasks:
            ttype = task['task_type']
            if ttype not in summary:
                summary[ttype] = {'completed': 0, 'failed': 0, 'running': 0}
            summary[ttype][task['status']] = task['count']
        
        return summary
    
    def _get_summary_text(self, report_data: dict) -> str:
        """Generate a human-readable summary."""
        sections = report_data['sections']
        traffic = sections.get('traffic', {})
        revenue = sections.get('revenue', {})
        email = sections.get('email', {})
        seo = sections.get('seo_health', {})
        content = sections.get('content', {})
        
        lines = [
            f"# Resumen Marketing — {report_data['period']}",
            f"Proyecto: {self.config.get('name', self.project_id)}",
            "",
            f"## Tráfico",
            f"- Visitantes: {traffic.get('total_visitors', 0):,}",
            f"- Pageviews: {traffic.get('total_pageviews', 0):,}",
            f"- Bounce Rate: {traffic.get('avg_bounce_rate', 0)}%",
            f"- Tendencia: {traffic.get('visitor_trend_pct', 0)}%",
            "",
            f"## Revenue",
            f"- Total: ${revenue.get('total_revenue_mxn', 0):,.2f} MXN",
            f"- Transacciones: {revenue.get('total_transactions', 0)}",
            f"- MRR: ${revenue.get('avg_mrr', 0):,.2f}",
            "",
            f"## Email",
            f"- Campañas: {email.get('total_campaigns', 0)}",
            f"- Open Rate: {email.get('open_rate', 0)}%",
            f"- Click Rate: {email.get('click_rate', 0)}%",
            "",
            f"## SEO",
            f"- Score: {seo.get('total_score', 0)}/100 ({seo.get('grade', 'N/A')})",
            f"- Top 10: {seo.get('top_10_count', 0)} keywords",
            f"- Backlinks: {seo.get('backlinks_total', 0)}",
            "",
            f"## Contenido",
            f"- Artículos publicados: {content.get('by_status', {}).get('published', 0)}",
            f"- Palabras promedio: {content.get('avg_word_count', 0):.0f}",
        ]
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Test report generation
    from config.projects import get_project_config
    
    config = get_project_config('yayika')
    generator = ReportGenerator('yayika', config)
    
    result = generator.generate_monthly_report()
    print(f"📄 Report Generated: {result['file']}")
    print(f"\n{result['summary']}")
