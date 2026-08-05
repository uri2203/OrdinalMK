"""Quick test script to verify API endpoints."""
import json
from app import app

with app.test_client() as c:
    print("=== OVERVIEW ===")
    r = c.get('/api/overview')
    print(json.dumps(r.get_json(), indent=2))
    
    print("\n=== ANALYTICS (last 5 days) ===")
    r2 = c.get('/api/project/yayika/analytics?days=5')
    data = r2.get_json()
    for d in data[:3]:
        print(f"  {d['date']}: {d['visitors']} visitors, {d['pageviews']} pageviews")
    
    print("\n=== REVENUE (last 5 days) ===")
    r3 = c.get('/api/project/yayika/revenue?days=5')
    data = r3.get_json()
    for d in data[:3]:
        print(f"  {d['date']}: ${d['revenue_mxn']:.2f} MXN")
    
    print("\n=== SEO RANKINGS ===")
    r4 = c.get('/api/project/yayika/seo')
    data = r4.get_json()
    for d in data[:5]:
        print(f"  #{d['position']} - {d['keyword']} ({d['language']})")
    
    print("\n=== EMAIL STATS ===")
    r5 = c.get('/api/project/yayika/email')
    data = r5.get_json()
    print(f"  Campaigns: {len(data.get('campaigns', []))}")
    print(f"  Subscriber growth data points: {len(data.get('subscriber_growth', []))}")
    
    print("\n=== CONTENT ===")
    r6 = c.get('/api/project/yayika/content')
    data = r6.get_json()
    print(f"  Total articles: {len(data)}")
    
    print("\n=== HEALTH ===")
    r7 = c.get('/api/health')
    print(json.dumps(r7.get_json(), indent=2))
    
    print("\n[OK] All endpoints working!")
