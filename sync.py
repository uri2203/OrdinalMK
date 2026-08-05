"""
OrdinalMK — Sync Engine (stdlib only, no external deps)
Pulls real data from Stripe, Resend, Supabase and generates JSON for the dashboard.
Run: python sync.py
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

# ──────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────
def load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()

load_env()

STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')

DATA_DIR = Path(__file__).parent / "docs" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def api_get(url: str, headers: dict = None, params: dict = None) -> dict:
    """Generic GET request using urllib."""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    
    req = urllib.request.Request(url)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"    [!] HTTP {e.code}: {e.read().decode()[:200]}")
        return {}
    except Exception as e:
        print(f"    [!] Error: {e}")
        return {}


# ──────────────────────────────────────────────────
# STRIPE CONNECTOR
# ──────────────────────────────────────────────────
class StripeConnector:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base = "https://api.stripe.com/v1"
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    def _get(self, endpoint, params=None):
        return api_get(f"{self.base}{endpoint}", self.headers, params)
    
    def get_balance(self):
        return self._get("/balance")
    
    def get_subscriptions(self):
        data = self._get("/subscriptions", {"limit": "100", "status": "active"})
        return data.get('data', [])
    
    def get_charges(self, days=30):
        since = int((datetime.now() - timedelta(days=days)).timestamp())
        data = self._get("/charges", {"limit": "100", "created[gte]": str(since)})
        return data.get('data', [])
    
    def get_daily_revenue(self, days=30):
        charges = self.get_charges(days)
        daily = {}
        for c in charges:
            if not c.get('paid') or c.get('refunded'):
                continue
            date = datetime.fromtimestamp(c['created']).strftime('%Y-%m-%d')
            amount = c['amount'] / 100
            if date not in daily:
                daily[date] = {'revenue_mxn': 0, 'transactions': 0}
            daily[date]['revenue_mxn'] += amount
            daily[date]['transactions'] += 1
        
        result = []
        for i in range(days, 0, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            if date in daily:
                result.append({'date': date, 'revenue_mxn': round(daily[date]['revenue_mxn'], 2), 'transactions': daily[date]['transactions']})
            else:
                result.append({'date': date, 'revenue_mxn': 0, 'transactions': 0})
        return result
    
    def get_mrr(self):
        subs = self.get_subscriptions()
        mrr = 0
        plan_counts = {}
        for sub in subs:
            items = sub.get('items', {}).get('data', [])
            if items:
                plan = items[0].get('plan', {})
                amount = plan.get('amount', 0) / 100
                interval = plan.get('interval', 'month')
                name = plan.get('nickname', 'Unknown')
                if interval == 'year':
                    amount /= 12
                mrr += amount
                plan_counts[name] = plan_counts.get(name, 0) + 1
        return {'mrr': round(mrr, 2), 'arr': round(mrr * 12, 2), 'active': len(subs), 'by_plan': plan_counts}
    
    def get_summary(self):
        balance = self.get_balance()
        mrr_data = self.get_mrr()
        daily = self.get_daily_revenue(30)
        total_rev = sum(d['revenue_mxn'] for d in daily)
        total_txns = sum(d['transactions'] for d in daily)
        return {
            'balance_available': balance.get('available', [{}])[0].get('amount', 0) / 100,
            'balance_pending': balance.get('pending', [{}])[0].get('amount', 0) / 100,
            'mrr': mrr_data['mrr'],
            'arr': mrr_data['arr'],
            'active_subscriptions': mrr_data['active'],
            'by_plan': mrr_data['by_plan'],
            'month_revenue_mxn': round(total_rev, 2),
            'month_transactions': total_txns,
            'daily': daily
        }


# ──────────────────────────────────────────────────
# RESEND CONNECTOR
# ──────────────────────────────────────────────────
class ResendConnector:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base = "https://api.resend.com"
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    def get_emails(self, limit=100):
        data = api_get(f"{self.base}/emails?limit={limit}", self.headers)
        return data.get('data', [])
    
    def get_metrics(self):
        emails = self.get_emails()
        total = len(emails)
        delivered = sum(1 for e in emails if e.get('last_event') == 'delivered')
        opened = sum(1 for e in emails if e.get('last_event') == 'opened')
        clicked = sum(1 for e in emails if e.get('last_event') == 'clicked')
        bounced = sum(1 for e in emails if e.get('last_event') == 'bounce')
        return {
            'total_sent': total,
            'total_delivered': delivered,
            'total_opened': opened,
            'total_clicked': clicked,
            'total_bounced': bounced,
            'delivery_rate': round(delivered / max(total, 1) * 100, 1),
            'open_rate': round(opened / max(delivered, 1) * 100, 1),
            'click_rate': round(clicked / max(delivered, 1) * 100, 1),
            'bounce_rate': round(bounced / max(total, 1) * 100, 1)
        }


# ──────────────────────────────────────────────────
# SUPABASE CONNECTOR
# ──────────────────────────────────────────────────
class SupabaseConnector:
    def __init__(self, url, anon_key):
        self.url = url
        self.headers = {"apikey": anon_key, "Authorization": f"Bearer {anon_key}"}
    
    def _get(self, table, params=None):
        query = f"{self.url}/rest/v1/{table}"
        if params:
            query += "?" + urllib.parse.urlencode(params)
        return api_get(query, self.headers)
    
    def get_users_count(self):
        data = self._get("users", {"select": "id"})
        return len(data) if isinstance(data, list) else 0
    
    def get_products_count(self):
        data = self._get("yayika_products", {"select": "id"})
        return len(data) if isinstance(data, list) else 0
    
    def get_subscribers_count(self):
        data = self._get("yayika_subscribers", {"select": "id", "status": "eq.active"})
        return len(data) if isinstance(data, list) else 0


# ──────────────────────────────────────────────────
# SYNC
# ──────────────────────────────────────────────────
def sync_all():
    print("=" * 50)
    print("OrdinalMK — Sync Engine")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Stripe
    stripe_data = {}
    if STRIPE_SECRET_KEY:
        print("\n[*] Syncing Stripe...")
        try:
            stripe = StripeConnector(STRIPE_SECRET_KEY)
            stripe_data = stripe.get_summary()
            print(f"    MRR: ${stripe_data['mrr']:,.2f}")
            print(f"    Active subs: {stripe_data['active_subscriptions']}")
            print(f"    Month revenue: ${stripe_data['month_revenue_mxn']:,.2f}")
            print(f"    Balance available: ${stripe_data['balance_available']:,.2f}")
        except Exception as e:
            print(f"    [!] Error: {e}")
    else:
        print("\n[!] No STRIPE_SECRET_KEY")
    
    # Resend
    email_data = {'stats': {}, 'campaigns': [], 'subscriber_growth': []}
    if RESEND_API_KEY:
        print("\n[*] Syncing Resend...")
        try:
            resend = ResendConnector(RESEND_API_KEY)
            email_data['stats'] = resend.get_metrics()
            print(f"    Sent: {email_data['stats']['total_sent']}")
            print(f"    Open rate: {email_data['stats']['open_rate']}%")
            print(f"    Click rate: {email_data['stats']['click_rate']}%")
        except Exception as e:
            print(f"    [!] Error: {e}")
    else:
        print("\n[!] No RESEND_API_KEY")
    
    # Supabase
    supabase_data = {}
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        print("\n[*] Syncing Supabase...")
        try:
            sb = SupabaseConnector(SUPABASE_URL, SUPABASE_ANON_KEY)
            supabase_data = {
                'users': sb.get_users_count(),
                'products': sb.get_products_count(),
                'subscribers': sb.get_subscribers_count()
            }
            print(f"    Users: {supabase_data['users']}")
            print(f"    Products: {supabase_data['products']}")
        except Exception as e:
            print(f"    [!] Error: {e}")
    else:
        print("\n[!] No SUPABASE config")
    
    # Generate JSON
    print("\n[*] Generating dashboard JSON...")
    
    overview = {
        'generated_at': datetime.now().isoformat(),
        'today_visitors': 0,
        'yesterday_visitors': 0,
        'today_pageviews': 0,
        'total_subscribers': supabase_data.get('subscribers', stripe_data.get('active_subscriptions', 0)),
        'total_articles': 10,
        'month_revenue_mxn': stripe_data.get('month_revenue_mxn', 0),
        'mrr': stripe_data.get('mrr', 0),
        'arr': stripe_data.get('arr', 0),
        'active_subscriptions': stripe_data.get('active_subscriptions', 0),
        'tasks_total_24h': 0,
        'tasks_completed_24h': 0
    }
    _write_json('overview.json', overview)
    
    revenue = stripe_data.get('daily', [])
    if revenue:
        mrr = stripe_data.get('mrr', 0)
        for r in revenue:
            r['mrr'] = mrr
        _write_json('revenue.json', revenue)
    
    _write_json('email.json', email_data)
    
    print(f"\n[OK] Dashboard updated at {DATA_DIR}")
    print(f"     Next: git add docs/data/ && git commit -m 'sync: real data' && git push")
    
    return {'stripe': stripe_data, 'email': email_data, 'supabase': supabase_data}


def _write_json(filename, data):
    filepath = DATA_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"    Written: {filename}")


if __name__ == "__main__":
    sync_all()
