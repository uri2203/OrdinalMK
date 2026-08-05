"""
Scheduler — Cron-based automation for all marketing engine tasks.
Manages task execution, logging, and error handling.
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import init_db, get_connection
from config.projects import load_config, get_all_project_ids
from content.engine import ContentEngine
from seo.monitor import SEOMonitor
from email.automation import EmailAutomation
from analytics.tracker import AnalyticsTracker
from reports.generator import ReportGenerator


class MarketingScheduler:
    """Orchestrates all marketing automation tasks."""
    
    def __init__(self):
        self.config = load_config()
        self.engine_config = self.config.get('engine', {})
        self.log_dir = Path(__file__).parent.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)
    
    def run_all_tasks(self):
        """Run all scheduled tasks for all projects."""
        project_ids = get_all_project_ids()
        
        print(f"\n{'='*60}")
        print(f"[*] Marketing Engine — Task Runner")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Projects: {', '.join(project_ids)}")
        print(f"{'='*60}\n")
        
        results = []
        
        for project_id in project_ids:
            project_config = self.config.get('projects', {}).get(project_id, {})
            
            print(f"\n[B] Processing: {project_config.get('name', project_id)}")
            print(f"   {'-'*40}")
            
            # 1. Analytics sync
            result = self._run_task('analytics_sync', project_id, 
                                   self._sync_analytics, project_id, project_config)
            results.append(result)
            
            # 2. SEO health check
            result = self._run_task('seo_health_check', project_id,
                                   self._check_seo_health, project_id, project_config)
            results.append(result)
            
            # 3. Content review
            result = self._run_task('content_review', project_id,
                                   self._review_content, project_id, project_config)
            results.append(result)
            
            # 4. Email campaign check
            result = self._run_task('email_check', project_id,
                                   self._check_email_campaigns, project_id, project_config)
            results.append(result)
        
        # Summary
        completed = sum(1 for r in results if r['status'] == 'completed')
        failed = sum(1 for r in results if r['status'] == 'failed')
        
        print(f"\n{'='*60}")
        print(f"[OK] Tasks completed: {completed}/{len(results)}")
        if failed:
            print(f"[X] Tasks failed: {failed}/{len(results)}")
        print(f"{'='*60}\n")
        
        return results
    
    def _run_task(self, task_type: str, project_id: str, func, *args) -> dict:
        """Run a single task with logging and error handling."""
        start_time = time.time()
        
        try:
            result = func(*args)
            duration = round(time.time() - start_time, 2)
            
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO task_log (task_type, project_id, status, result, completed_at)
                    VALUES (?, ?, 'completed', ?, datetime('now'))
                """, (task_type, project_id, json.dumps(result, default=str)))
            
            print(f"   [OK] {task_type}: {duration}s")
            return {'task': task_type, 'project': project_id, 'status': 'completed', 
                    'duration': duration, 'result': result}
        
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO task_log (task_type, project_id, status, error, completed_at)
                    VALUES (?, ?, 'failed', ?, datetime('now'))
                """, (task_type, project_id, error_msg))
            
            print(f"   [X] {task_type}: {error_msg[:100]}...")
            return {'task': task_type, 'project': project_id, 'status': 'failed',
                    'duration': duration, 'error': str(e)}
    
    def _sync_analytics(self, project_id: str, config: dict) -> dict:
        """Sync analytics data from Plausible."""
        plausible_config = config.get('sources', {}).get('plausible', {})
        site_id = plausible_config.get('site_id')
        
        if not site_id:
            return {'status': 'skipped', 'reason': 'No Plausible site_id'}
        
        tracker = AnalyticsTracker(project_id, site_id)
        result = tracker.sync_plausible_data()
        return result
    
    def _check_seo_health(self, project_id: str, config: dict) -> dict:
        """Check SEO health and rankings."""
        seo = SEOMonitor(project_id)
        health = seo.get_seo_health()
        return health
    
    def _review_content(self, project_id: str, config: dict) -> dict:
        """Review content status and stats."""
        content = ContentEngine(project_id)
        stats = content.get_stats()
        return stats
    
    def _check_email_campaigns(self, project_id: str, config: dict) -> dict:
        """Check email campaign performance."""
        email = EmailAutomation(project_id)
        metrics = email.get_campaign_metrics()
        return metrics
    
    def generate_daily_report(self, project_id: str = None) -> dict:
        """Generate daily reports for one or all projects."""
        project_ids = [project_id] if project_id else get_all_project_ids()
        results = []
        
        for pid in project_ids:
            config = self.config.get('projects', {}).get(pid, {})
            generator = ReportGenerator(pid, config)
            
            # Generate CSV export
            csv_path = generator.generate_csv_export('analytics', 7)
            
            results.append({
                'project': pid,
                'csv': csv_path
            })
        
        return results
    
    def generate_monthly_reports(self) -> list:
        """Generate monthly reports for all projects."""
        project_ids = get_all_project_ids()
        results = []
        
        for pid in project_ids:
            config = self.config.get('projects', {}).get(pid, {})
            generator = ReportGenerator(pid, config)
            result = generator.generate_monthly_report()
            results.append(result)
        
        return results


def main():
    """CLI entry point for the scheduler."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Marketing Engine Scheduler')
    parser.add_argument('command', choices=['run', 'daily', 'monthly', 'status'],
                       help='Command to execute')
    parser.add_argument('--project', '-p', help='Specific project ID')
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    scheduler = MarketingScheduler()
    
    if args.command == 'run':
        scheduler.run_all_tasks()
    
    elif args.command == 'daily':
        results = scheduler.generate_daily_report(args.project)
        print(f"\n[#] Daily reports generated:")
        for r in results:
            print(f"   {r['project']}: {r['csv']}")
    
    elif args.command == 'monthly':
        results = scheduler.generate_monthly_reports()
        print(f"\n📄 Monthly reports generated:")
        for r in results:
            print(f"   {r['period']}: {r['file']}")
    
    elif args.command == 'status':
        with get_connection() as conn:
            recent = conn.execute("""
                SELECT task_type, project_id, status, started_at, completed_at
                FROM task_log 
                ORDER BY started_at DESC LIMIT 20
            """).fetchall()
            
            print(f"\n[L] Recent Tasks:")
            for task in recent:
                status_icon = '[OK]' if task['status'] == 'completed' else '[X]'
                print(f"   {status_icon} {task['task_type']} ({task['project_id']}) — {task['started_at']}")


if __name__ == "__main__":
    main()
