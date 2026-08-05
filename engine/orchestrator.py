"""
OrdinalMK — Marketing Orchestrator
Runs all marketing automation tasks in sequence.
This is the main entry point for the daily marketing workflow.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.publishers.content_publisher import ContentPublisher
from engine.publishers.email_automation import EmailAutomation
from engine.publishers.landing_page import LandingPageGenerator
from engine.publishers.seo_optimizer import SEOOptimizer


class MarketingOrchestrator:
    """Orchestrates all marketing automation tasks."""
    
    def __init__(self, project_id: str, config: dict):
        self.project_id = project_id
        self.config = config
        self.domain = config.get('domain', 'yayika.com')
        self.log = []
        
        # Initialize modules
        self.publisher = ContentPublisher(project_id)
        self.email = EmailAutomation()
        self.landing = LandingPageGenerator(project_id)
        self.seo = SEOOptimizer(project_id, self.domain)
    
    def run_all(self) -> dict:
        """Execute all marketing tasks."""
        print(f"\n{'='*60}")
        print(f"OrdinalMK — Marketing Orchestrator")
        print(f"  Project: {self.project_id}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        results = {}
        
        # 1. Content Publishing
        print("[1/5] Content Publishing...")
        results['content'] = self._run_content()
        
        # 2. SEO Optimization
        print("[2/5] SEO Optimization...")
        results['seo'] = self._run_seo()
        
        # 3. Landing Pages
        print("[3/5] Landing Pages...")
        results['landing'] = self._run_landing()
        
        # 4. Email Campaigns
        print("[4/5] Email Campaigns...")
        results['email'] = self._run_email()
        
        # 5. Generate Reports
        print("[5/5] Reports...")
        results['reports'] = self._run_reports()
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for task, result in results.items():
            status = "OK" if result.get('status') == 'ok' else "PARTIAL"
            print(f"  [{status}] {task}: {result.get('message', '')}")
        
        # Save log
        self._save_log(results)
        
        return results
    
    def _run_content(self) -> dict:
        """Publish content to the project."""
        try:
            # Get content calendar
            calendar = self.publisher.get_content_calendar(7)
            
            published = 0
            for item in calendar[:2]:  # Publish 2 articles per run
                article = self.publisher.generate_article(item['topic'], item['language'])
                result = self.publisher.publish_article(article)
                if result['status'] == 'published':
                    published += 1
                    print(f"  Published: {result['slug']} ({result['language']}) SEO:{result['seo_score']}")
            
            return {'status': 'ok', 'message': f'{published} articles published', 'count': published}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _run_seo(self) -> dict:
        """Generate SEO assets."""
        try:
            # Generate sitemap
            pages = [
                {'slug': '', 'url': f'https://{self.domain}/', 'priority': '1.0', 'changefreq': 'daily'},
                {'slug': 'tienda', 'url': f'https://{self.domain}/tienda', 'priority': '0.9'},
                {'slug': 'comunidad', 'url': f'https://{self.domain}/comunidad', 'priority': '0.8'},
                {'slug': 'blog', 'url': f'https://{self.domain}/blog', 'priority': '0.7'},
            ]
            
            sitemap = self.seo.generate_sitemap(pages)
            robots = self.seo.generate_robots_txt()
            
            print(f"  Sitemap: {sitemap}")
            print(f"  Robots: {robots}")
            
            return {'status': 'ok', 'message': 'SEO assets generated'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _run_landing(self) -> dict:
        """Create landing pages."""
        try:
            # Main landing page
            result = self.landing.create_landing_page({
                'title': 'Yayika - Plataforma para Mujeres Emprendedoras',
                'headline': 'Transforma tu vida con Yayika',
                'subtitle': 'La plataforma #1 para mujeres emprendedoras en Latinoamerica',
                'language': 'es',
                'price': '$179 MXN/mes',
                'price_name': 'Plan Semilla',
                'stripe_link': 'https://buy.stripe.com/00wcN502q0xY2481elgA80f',
                'meta_description': 'Yayika es la plataforma #1 para mujeres emprendedoras. Productos digitales, comunidad y mentoring.'
            })
            
            print(f"  Landing: {result['slug']}")
            
            return {'status': 'ok', 'message': 'Landing pages created'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _run_email(self) -> dict:
        """Send email campaigns."""
        try:
            sequences = self.email.get_sequences()
            print(f"  Available sequences: {', '.join(s['name'] for s in sequences)}")
            
            # Don't send emails automatically - just prepare them
            # Emails are sent when users subscribe via the website
            return {'status': 'ok', 'message': f'{len(sequences)} email sequences ready'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _run_reports(self) -> dict:
        """Generate marketing reports."""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'project': self.project_id,
                'tasks': {
                    'content_published': True,
                    'seo_optimized': True,
                    'landing_created': True,
                    'email_ready': True
                }
            }
            
            report_path = Path(__file__).parent.parent / "docs" / "data" / "marketing_report.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            
            print(f"  Report: {report_path}")
            
            return {'status': 'ok', 'message': 'Report generated'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _save_log(self, results: dict):
        """Save execution log."""
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'project': self.project_id,
            'results': results
        }
        
        log_file = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_entry, f, indent=2, default=str)


# ──────────────────────────────────────────────────
# PROJECT CONFIGS
# ──────────────────────────────────────────────────
PROJECTS = {
    'yayika': {
        'name': 'Yayika',
        'domain': 'yayika.com',
        'languages': ['es', 'en', 'pt', 'fr', 'de']
    },
    'lastmile': {
        'name': 'LastMile Platform',
        'domain': 'lastmile-platform.com',
        'languages': ['es', 'en']
    },
    'tuialista': {
        'name': 'TuIAlista',
        'domain': 'tuialista.com',
        'languages': ['es', 'en']
    }
}


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else 'yayika'
    
    if project not in PROJECTS:
        print(f"Unknown project: {project}")
        print(f"Available: {', '.join(PROJECTS.keys())}")
        sys.exit(1)
    
    orchestrator = MarketingOrchestrator(project, PROJECTS[project])
    results = orchestrator.run_all()
