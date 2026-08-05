"""
OrdinalMK — Multi-Project Orchestrator
Manages marketing automation for ALL projects from one engine.
Each project gets its own content, emails, landing pages, and deploy.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from engine.publishers.content_publisher import ContentPublisher
from engine.publishers.email_automation import EmailAutomation
from engine.publishers.landing_page import LandingPageGenerator
from engine.publishers.seo_optimizer import SEOOptimizer


class MultiProjectOrchestrator:
    """Orchestrates marketing for ALL projects."""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "projects.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.projects = self.config.get('projects', {})
        self.engine_config = self.config.get('engine', {})
        self.results = {}
    
    def run_all_projects(self) -> dict:
        """Run marketing automation for ALL projects."""
        print(f"\n{'='*60}")
        print(f"OrdinalMK — Multi-Project Marketing Engine")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Projects: {', '.join(self.projects.keys())}")
        print(f"{'='*60}\n")
        
        for project_id, project_config in self.projects.items():
            print(f"\n{'-'*60}")
            print(f"  PROJECT: {project_config['name']}")
            print(f"  {project_config['concept']}")
            print(f"{'-'*60}")
            
            result = self._run_project(project_id, project_config)
            self.results[project_id] = result
        
        # Summary
        self._print_summary()
        
        # Save results
        self._save_results()
        
        return self.results
    
    def run_project(self, project_id: str) -> dict:
        """Run marketing for a single project."""
        if project_id not in self.projects:
            return {'error': f'Project {project_id} not found'}
        
        return self._run_project(project_id, self.projects[project_id])
    
    def _run_project(self, project_id: str, config: dict) -> dict:
        """Run all marketing tasks for one project."""
        result = {
            'project': project_id,
            'name': config['name'],
            'started_at': datetime.now().isoformat(),
            'tasks': {}
        }
        
        # 1. Content
        print(f"\n  [1/4] Generating content...")
        result['tasks']['content'] = self._generate_content(project_id, config)
        
        # 2. Landing Pages
        print(f"  [2/4] Creating landing pages...")
        result['tasks']['landing'] = self._create_landing(project_id, config)
        
        # 3. SEO
        print(f"  [3/4] Optimizing SEO...")
        result['tasks']['seo'] = self._optimize_seo(project_id, config)
        
        # 4. Deploy (push to GitHub)
        print(f"  [4/4] Deploying to GitHub...")
        result['tasks']['deploy'] = self._deploy(project_id, config)
        
        result['completed_at'] = datetime.now().isoformat()
        result['status'] = 'completed'
        
        return result
    
    def _generate_content(self, project_id: str, config: dict) -> dict:
        """Generate content for a project."""
        try:
            publisher = ContentPublisher(project_id)
            
            # Override topics from config
            publisher.topics = config.get('content', {}).get('topics', {})
            
            # Generate calendar
            calendar = publisher.get_content_calendar(7)
            
            # Publish 2 articles
            published = 0
            for item in calendar[:2]:
                article = publisher.generate_article(item['topic'], item['language'])
                result = publisher.publish_article(article)
                if result['status'] == 'published':
                    published += 1
                    print(f"    Published: {result['slug'][:50]}... ({result['language']}) SEO:{result['seo_score']}")
            
            return {'status': 'ok', 'count': published}
        except Exception as e:
            print(f"    Error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _create_landing(self, project_id: str, config: dict) -> dict:
        """Create landing pages for a project."""
        try:
            landing_gen = LandingPageGenerator(project_id)
            
            created = 0
            for lp_config in config.get('landing_pages', []):
                products = config.get('products', [{}])
                main_product = products[0] if products else {}
                
                result = landing_gen.create_landing_page({
                    'title': f"{config['name']} - {lp_config.get('headline', '')}",
                    'headline': lp_config.get('headline', config.get('tagline', '')),
                    'subtitle': lp_config.get('subtitle', config.get('concept', '')),
                    'language': config.get('primary_language', 'es'),
                    'price': f"${main_product.get('price', 0)} {main_product.get('currency', 'USD')}/mo" if main_product.get('price', 0) > 0 else "Gratis",
                    'price_name': main_product.get('name', ''),
                    'stripe_link': main_product.get('stripe_link', '#'),
                    'meta_description': f"{config['name']} - {config['concept']}"
                })
                
                if result['status'] == 'created':
                    created += 1
                    print(f"    Landing: {lp_config['name']}")
            
            return {'status': 'ok', 'count': created}
        except Exception as e:
            print(f"    Error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _optimize_seo(self, project_id: str, config: dict) -> dict:
        """Generate SEO assets for a project."""
        try:
            seo = SEOOptimizer(project_id, config['domain'])
            
            # Generate sitemap
            pages = [{'slug': '', 'url': f"https://{config['domain']}/", 'priority': '1.0'}]
            for lp in config.get('landing_pages', []):
                pages.append({
                    'slug': lp.get('slug', '').lstrip('/'),
                    'url': f"https://{config['domain']}{lp.get('slug', '')}",
                    'priority': '0.8'
                })
            
            sitemap = seo.generate_sitemap(pages)
            robots = seo.generate_robots_txt()
            
            print(f"    Sitemap: {sitemap}")
            print(f"    Robots: {robots}")
            
            return {'status': 'ok'}
        except Exception as e:
            print(f"    Error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _deploy(self, project_id: str, config: dict) -> dict:
        """Deploy content to GitHub Pages."""
        try:
            deploy_config = config.get('deploy', {})
            repo = deploy_config.get('repo', '')
            branch = deploy_config.get('branch', 'main')
            
            if not repo:
                return {'status': 'skipped', 'message': 'No repo configured'}
            
            # Copy published content to docs/ for GitHub Pages
            published_dir = Path(__file__).parent.parent / "published" / project_id
            docs_dir = Path(__file__).parent.parent / "docs" / "projects" / project_id
            
            if published_dir.exists():
                import shutil
                docs_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy content
                for item in published_dir.rglob('*'):
                    if item.is_file():
                        rel = item.relative_to(published_dir)
                        dest = docs_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)
                
                print(f"    Copied to docs/projects/{project_id}/")
            
            return {'status': 'ok', 'repo': repo, 'branch': branch}
        except Exception as e:
            print(f"    Error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _print_summary(self):
        """Print execution summary."""
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        
        for project_id, result in self.results.items():
            status = result.get('status', 'unknown')
            tasks = result.get('tasks', {})
            
            content_count = tasks.get('content', {}).get('count', 0)
            landing_count = tasks.get('landing', {}).get('count', 0)
            
            print(f"\n  {result['name']}:")
            print(f"    Status: {status}")
            print(f"    Articles: {content_count}")
            print(f"    Landing pages: {landing_count}")
            print(f"    SEO: {tasks.get('seo', {}).get('status', 'N/A')}")
            print(f"    Deploy: {tasks.get('deploy', {}).get('status', 'N/A')}")
    
    def _save_results(self):
        """Save results to file."""
        output_dir = Path(__file__).parent.parent / "docs" / "data"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / "marketing_report.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'projects': self.results
            }, f, indent=2, default=str)
        
        print(f"\n  Report: {filepath}")
    
    def list_projects(self) -> list:
        """List all configured projects."""
        return [
            {
                'id': pid,
                'name': p['name'],
                'concept': p['concept'],
                'domain': p['domain'],
                'languages': p.get('languages', []),
                'content_topics': len(p.get('content', {}).get('topics', {}).get(p.get('primary_language', 'es'), []))
            }
            for pid, p in self.projects.items()
        ]


# --------------------------------------------------
# CLI
# --------------------------------------------------
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='OrdinalMK Multi-Project Orchestrator')
    parser.add_argument('command', choices=['run', 'run-project', 'list'],
                       help='Command to execute')
    parser.add_argument('--project', '-p', help='Project ID (for run-project)')
    parser.add_argument('--config', '-c', help='Config file path')
    
    args = parser.parse_args()
    
    orchestrator = MultiProjectOrchestrator(args.config)
    
    if args.command == 'run':
        orchestrator.run_all_projects()
    
    elif args.command == 'run-project':
        if not args.project:
            print("Error: --project required")
            sys.exit(1)
        orchestrator.run_project(args.project)
    
    elif args.command == 'list':
        projects = orchestrator.list_projects()
        print(f"\nOrdinalMK — {len(projects)} Projects Configured:\n")
        for p in projects:
            print(f"  {p['id']}:")
            print(f"    Name: {p['name']}")
            print(f"    Concept: {p['concept']}")
            print(f"    Domain: {p['domain']}")
            print(f"    Languages: {', '.join(p['languages'])}")
            print(f"    Content topics: {p['content_topics']}")
            print()
