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
from engine.distribution.regional import RegionalDistributor
from engine.distribution.email_segmentation import EmailSegmentation
from engine.distribution.multilang_landing import MultilangLandingPageGenerator


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
        
        languages = config.get('languages', ['es', 'en'])
        
        # 1. Content
        print(f"\n  [1/6] Generating content...")
        result['tasks']['content'] = self._generate_content(project_id, config)
        
        # 2. Landing Pages (multi-lang)
        print(f"  [2/6] Creating multi-language landing pages...")
        result['tasks']['landing'] = self._create_multilang_landing(project_id, config)
        
        # 3. SEO (multi-lang)
        print(f"  [3/6] Optimizing SEO (multi-language)...")
        result['tasks']['seo'] = self._optimize_seo_multilang(project_id, config)
        
        # 4. Email Segmentation
        print(f"  [4/6] Setting up email segmentation...")
        result['tasks']['email'] = self._setup_email_segmentation(project_id, config)
        
        # 5. Distribution Report
        print(f"  [5/6] Generating distribution report...")
        result['tasks']['distribution'] = self._generate_distribution_report(project_id, config)
        
        # 6. Deploy (push to GitHub)
        print(f"  [6/6] Deploying to GitHub...")
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
    
    def _create_multilang_landing(self, project_id: str, config: dict) -> dict:
        """Create multi-language landing pages with hreflang."""
        try:
            languages = config.get('languages', ['es', 'en'])
            landing_gen = MultilangLandingPageGenerator(
                project_id, languages,
                domain=config.get('domain'),
                brand=config.get('name'),
                theme=config.get('theme'),
                og_image=config.get('og_image'),
            )
            
            created = 0
            
            # Generate main landing in all languages
            # El contenido de la landing viene del bloque `landing:` por idioma en
            # projects.yaml. `concept` puede ser un string (descripción corta), no
            # sirve como contenido multi-idioma; por eso NO se usa aquí.
            _landing = config.get('landing')
            concept = _landing if isinstance(_landing, dict) else {}
            pricing = config.get('pricing', {})
            testimonials = config.get('testimonials', [])
            
            results = landing_gen.generate_multilang_landing(
                slug='index',
                content=concept,
                pricing=pricing,
                testimonials=testimonials
            )
            
            created = len(results)
            for lang, path in results.items():
                print(f"    Landing [{lang}]: {path}")
            
            return {'status': 'ok', 'count': created, 'languages': list(results.keys())}
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
    
    def _optimize_seo_multilang(self, project_id: str, config: dict) -> dict:
        """Generate multi-language SEO assets with hreflang."""
        try:
            languages = config.get('languages', ['es', 'en'])
            distributor = RegionalDistributor(project_id, languages, domain=config.get('domain'))
            
            # Generate sitemaps per language
            sitemaps = distributor.generate_sitemap_per_language()
            
            for lang, sitemap_path in sitemaps.items():
                print(f"    Sitemap [{lang}]: {sitemap_path}")
            
            # Generate robots.txt
            robots_content = f"""User-agent: *
Allow: /

Sitemap: https://{config['domain']}/sitemap_index.xml

# OrdinalMK — Multi-language SEO
# Languages: {', '.join(languages)}
"""
            robots_path = Path(__file__).parent.parent / "published" / project_id / "robots.txt"
            robots_path.parent.mkdir(parents=True, exist_ok=True)
            with open(robots_path, 'w', encoding='utf-8') as f:
                f.write(robots_content)
            
            print(f"    Robots: {robots_path}")
            
            return {'status': 'ok', 'sitemaps': list(sitemaps.keys())}
        except Exception as e:
            print(f"    Error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _setup_email_segmentation(self, project_id: str, config: dict) -> dict:
        """Set up email segmentation by language."""
        try:
            languages = config.get('languages', ['es', 'en'])
            email_engine = EmailSegmentation(project_id, languages)
            
            # Generate segmentation report
            report = email_engine.get_segmentation_report()
            
            for lang, data in report['campaigns'].items():
                print(f"    Email [{lang}]: {data['name']} - {len(data['templates'])} templates")
            
            # Save report
            output_dir = Path(__file__).parent.parent / "published" / project_id
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path = output_dir / "email_segmentation.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            
            return {'status': 'ok', 'languages': list(report['campaigns'].keys())}
        except Exception as e:
            print(f"    Error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _generate_distribution_report(self, project_id: str, config: dict) -> dict:
        """Generate comprehensive distribution report."""
        try:
            languages = config.get('languages', ['es', 'en'])
            distributor = RegionalDistributor(project_id, languages, domain=config.get('domain'))
            
            report = distributor.get_region_report()
            
            for lang, data in report['regions'].items():
                print(f"    Region [{lang}]: {data['name']} - {data['pages_published']} pages, {len(data['countries'])} countries")
            
            # Save report
            output_dir = Path(__file__).parent.parent / "published" / project_id
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path = output_dir / "distribution_report.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            
            return {'status': 'ok', 'regions': list(report['regions'].keys())}
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
            email_langs = tasks.get('email', {}).get('languages', [])
            seo_langs = tasks.get('seo', {}).get('sitemaps', [])
            dist_regions = tasks.get('distribution', {}).get('regions', [])
            
            print(f"\n  {result['name']}:")
            print(f"    Status: {status}")
            print(f"    Articles: {content_count}")
            print(f"    Landing pages: {landing_count} (multi-lang)")
            print(f"    Email: {', '.join(email_langs)}")
            print(f"    SEO: {', '.join(seo_langs)}")
            print(f"    Regions: {', '.join(dist_regions)}")
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
