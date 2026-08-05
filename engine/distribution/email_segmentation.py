"""
OrdinalMK — Email Segmentation Engine
Sends localized emails based on subscriber's language and region.
"""

import os
import json
import requests
from datetime import datetime
from typing import Optional
from .regional import RegionalDistributor, REGIONS


class EmailSegmentation:
    """Segment and send emails by language/region."""
    
    def __init__(self, project_id: str, languages: list):
        self.project_id = project_id
        self.languages = languages
        self.distributor = RegionalDistributor(project_id, languages)
        self.resend_api_key = os.getenv('RESEND_API_KEY', '')
        self.resend_base = 'https://api.resend.com'
    
    # ──────────────────────────────────────────────
    # SUBSCRIBER SEGMENTATION
    # ──────────────────────────────────────────────
    
    def segment_subscriber(self, email: str, country_code: str = None, 
                          browser_lang: str = None) -> dict:
        """Determine subscriber's segment based on available data."""
        # Priority: country > browser language > default
        detected_lang = 'es'
        
        if country_code:
            for lang, region in REGIONS.items():
                if country_code.upper() in region['countries']:
                    detected_lang = lang
                    break
        elif browser_lang:
            detected_lang = browser_lang.split('-')[0]
            if detected_lang not in self.languages:
                detected_lang = 'es'
        
        region = REGIONS.get(detected_lang, REGIONS['es'])
        
        return {
            'email': email,
            'language': detected_lang,
            'country': country_code,
            'locale': region['locales'][0],
            'currency': region['currency'],
            'google_domain': region['google_domain'],
            'payment_methods': region['payment_methods'],
            'social_platforms': region['social_platforms'],
            'email_tone': region['email_tone'],
            'tags': [f'lang:{detected_lang}'],
            'segment': f'{detected_lang}_{country_code or "unknown"}'
        }
    
    # ──────────────────────────────────────────────
    # EMAIL CAMPAIGNS BY LANGUAGE
    # ──────────────────────────────────────────────
    
    def create_campaign(self, campaign_type: str, custom_content: dict = None) -> dict:
        """Create a multi-language email campaign."""
        campaigns = {}
        
        for lang in self.languages:
            template = self.distributor.get_localized_email_template(campaign_type, lang)
            
            campaigns[lang] = {
                'type': campaign_type,
                'language': lang,
                'subject': template.get('subject', ''),
                'greeting': template.get('greeting', ''),
                'body': template.get('body', ''),
                'region': REGIONS.get(lang, {}),
                'content': custom_content.get(lang, {}) if custom_content else {}
            }
        
        return campaigns
    
    def send_segmented_email(self, to_email: str, campaign_type: str, 
                            country_code: str = None, custom_subject: str = None,
                            custom_body: str = None) -> dict:
        """Send a localized email to a subscriber."""
        if not self.resend_api_key:
            return {'success': False, 'error': 'RESEND_API_KEY not set'}
        
        # Segment subscriber
        segment = self.segment_subscriber(to_email, country_code)
        lang = segment['language']
        
        # Get localized template
        template = self.distributor.get_localized_email_template(campaign_type, lang)
        
        subject = custom_subject or template.get('subject', '')
        body = custom_body or template.get('body', '')
        
        # Build HTML email
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #0f1117; color: #e4e6f0;">
    <div style="background: linear-gradient(135deg, #1a1d27, #232733); border-radius: 12px; padding: 32px; border: 1px solid #2d3140;">
        <h1 style="color: #6366f1; font-size: 24px; margin-bottom: 16px;">{subject}</h1>
        <p style="font-size: 16px; line-height: 1.6; color: #8b8fa3;">{template.get('greeting', '')}</p>
        <p style="font-size: 16px; line-height: 1.6; color: #8b8fa3;">{body}</p>
        <div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid #2d3140;">
            <p style="font-size: 12px; color: #4a4e5c;">
                {self.project_id.title()} | 
                <a href="https://{self.project_id}.com/{lang}/unsubscribe?email={to_email}" style="color: #6366f1;">Unsubscribe</a>
            </p>
        </div>
    </div>
</body>
</html>"""
        
        # Send via Resend
        try:
            response = requests.post(
                f'{self.resend_base}/emails',
                headers={
                    'Authorization': f'Bearer {self.resend_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'from': f'{self.project_id.title()} <onboarding@resend.dev>',
                    'to': [to_email],
                    'subject': subject,
                    'html': html,
                    'tags': [
                        {'name': 'language', 'value': lang},
                        {'name': 'campaign', 'value': campaign_type},
                        {'name': 'project', 'value': self.project_id}
                    ]
                }
            )
            
            return {
                'success': response.status_code == 200,
                'id': response.json().get('id'),
                'language': lang,
                'segment': segment['segment'],
                'subject': subject
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ──────────────────────────────────────────────
    # BULK SEND BY LANGUAGE
    # ──────────────────────────────────────────────
    
    def send_bulk_by_language(self, subscribers: list, campaign_type: str,
                             language_filter: str = None) -> dict:
        """Send bulk emails segmented by language."""
        results = {'sent': 0, 'failed': 0, 'by_language': {}}
        
        for sub in subscribers:
            email = sub.get('email')
            country = sub.get('country')
            
            # Segment
            segment = self.segment_subscriber(email, country)
            sub_lang = segment['language']
            
            # Filter by language if specified
            if language_filter and sub_lang != language_filter:
                continue
            
            # Send
            result = self.send_segmented_email(email, campaign_type, country)
            
            if result['success']:
                results['sent'] += 1
                results['by_language'][sub_lang] = results['by_language'].get(sub_lang, 0) + 1
            else:
                results['failed'] += 1
        
        return results
    
    # ──────────────────────────────────────────────
    # WELCOME SEQUENCE BY LANGUAGE
    # ──────────────────────────────────────────────
    
    def send_welcome_sequence(self, email: str, country_code: str = None) -> dict:
        """Send welcome sequence in subscriber's language."""
        segment = self.segment_subscriber(email, country_code)
        lang = segment['language']
        
        sequence = []
        
        # Day 0: Welcome
        result1 = self.send_segmented_email(email, 'welcome', country_code)
        sequence.append(('welcome', result1))
        
        # Day 1: Nurture
        result2 = self.send_segmented_email(email, 'nurture', country_code)
        sequence.append(('nurture', result2))
        
        # Day 3: Upsell
        result3 = self.send_segmented_email(email, 'upsell', country_code)
        sequence.append(('upsell', result3))
        
        return {
            'email': email,
            'language': lang,
            'sequence': sequence,
            'total_sent': sum(1 for _, r in sequence if r['success'])
        }
    
    # ──────────────────────────────────────────────
    # CAMPAIGN REPORT
    # ──────────────────────────────────────────────
    
    def get_segmentation_report(self) -> dict:
        """Get report of email segmentation status."""
        report = {
            'project': self.project_id,
            'languages': self.languages,
            'campaigns': {},
            'generated_at': datetime.now().isoformat()
        }
        
        for lang in self.languages:
            region = REGIONS.get(lang, {})
            templates = {}
            
            for campaign_type in ['welcome', 'nurture', 'upsell']:
                template = self.distributor.get_localized_email_template(campaign_type, lang)
                templates[campaign_type] = template
            
            report['campaigns'][lang] = {
                'name': region.get('name', lang),
                'locale': region.get('locales', [lang])[0],
                'currency': region.get('currency', 'USD'),
                'templates': templates,
                'social_platforms': region.get('social_platforms', []),
                'payment_methods': region.get('payment_methods', [])
            }
        
        return report


if __name__ == "__main__":
    engine = EmailSegmentation('yayika', ['es', 'en', 'pt', 'fr', 'de'])
    
    # Test segmentation
    test_subscribers = [
        {'email': 'maria@gmail.com', 'country': 'MX'},
        {'email': 'john@gmail.com', 'country': 'US'},
        {'email': 'ana@gmail.com', 'country': 'BR'},
        {'email': 'jean@gmail.com', 'country': 'FR'},
        {'email': 'hans@gmail.com', 'country': 'DE'}
    ]
    
    for sub in test_subscribers:
        segment = engine.segment_subscriber(sub['email'], sub['country'])
        print(f"{sub['email']} -> {segment['language']} ({segment['segment']})")
    
    # Generate report
    report = engine.get_segmentation_report()
    print(f"\nCampaign Report:")
    for lang, data in report['campaigns'].items():
        print(f"  {data['name']}: {len(data['templates'])} templates")
