# OrdinalMK — Sync Engine (PowerShell)
# Pulls real data from Stripe, Resend, Supabase
# Run: powershell -File sync.ps1

$ErrorActionPreference = "Stop"

# Load .env
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#=]+)=(.+)$") {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

$STRIPE_KEY = $env:STRIPE_SECRET_KEY
$RESEND_KEY = $env:RESEND_API_KEY
$SUPABASE_URL = $env:SUPABASE_URL
$SUPABASE_KEY = $env:SUPABASE_ANON_KEY
$DATA_DIR = Join-Path $PSScriptRoot "docs\data"

Write-Host "=" * 50
Write-Host "OrdinalMK — Sync Engine"
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "=" * 50

# ─── STRIPE ──────────────────────────────────────
$stripeData = @{}
if ($STRIPE_KEY) {
    Write-Host "`n[*] Syncing Stripe..." -ForegroundColor Cyan
    try {
        $headers = @{ "Authorization" = "Bearer $STRIPE_KEY" }
        
        # Balance
        $balance = Invoke-RestMethod -Uri "https://api.stripe.com/v1/balance" -Headers $headers
        $avail = ($balance.available | Select-Object -First 1).amount / 100
        $pend = ($balance.pending | Select-Object -First 1).amount / 100
        
        # Subscriptions
        $subs = Invoke-RestMethod -Uri "https://api.stripe.com/v1/subscriptions?limit=100&status=active" -Headers $headers
        $subCount = $subs.data.Count
        $mrr = 0
        $planCounts = @{}
        foreach ($sub in $subs.data) {
            $plan = $sub.items.data[0].plan
            $amount = $plan.amount / 100
            if ($plan.interval -eq "year") { $amount /= 12 }
            $mrr += $amount
            $planName = $plan.nickname
            if (-not $planName) { $planName = "Plan" }
            if ($planCounts.ContainsKey($planName)) { $planCounts[$planName]++ } else { $planCounts[$planName] = 1 }
        }
        
        # Charges (last 30 days)
        $since = [int][double]::Parse((Get-Date).AddDays(-30).Subtract([datetime]"1970-01-01").TotalSeconds.ToString())
        $charges = Invoke-RestMethod -Uri "https://api.stripe.com/v1/charges?limit=100&created[gte]=$since" -Headers $headers
        
        $daily = @{}
        $totalRev = 0
        $totalTxns = 0
        foreach ($c in $charges.data) {
            if (-not $c.paid -or $c.refunded) { continue }
            $date = [DateTimeOffset]::FromUnixTimeSeconds($c.created).ToOffset([TimeSpan]::FromHours(-6)).ToString("yyyy-MM-dd")
            $amount = $c.amount / 100
            $totalRev += $amount
            $totalTxns++
            if ($daily.ContainsKey($date)) {
                $daily[$date].revenue += $amount
                $daily[$date].txns++
            } else {
                $daily[$date] = @{ revenue = $amount; txns = 1 }
            }
        }
        
        # Build daily array
        $dailyArray = @()
        for ($i = 30; $i -ge 1; $i--) {
            $date = (Get-Date).AddDays(-$i).ToString("yyyy-MM-dd")
            if ($daily.ContainsKey($date)) {
                $dailyArray += @{ date = $date; revenue_mxn = [math]::Round($daily[$date].revenue, 2); transactions = $daily[$date].txns; mrr = [math]::Round($mrr, 2) }
            } else {
                $dailyArray += @{ date = $date; revenue_mxn = 0; transactions = 0; mrr = [math]::Round($mrr, 2) }
            }
        }
        
        $stripeData = @{
            balance_available = $avail
            balance_pending = $pend
            mrr = [math]::Round($mrr, 2)
            arr = [math]::Round($mrr * 12, 2)
            active_subscriptions = $subCount
            by_plan = $planCounts
            month_revenue_mxn = [math]::Round($totalRev, 2)
            month_transactions = $totalTxns
            daily = $dailyArray
        }
        
        Write-Host "    MRR: `$$($stripeData.mrr)" -ForegroundColor Green
        Write-Host "    Active subs: $($stripeData.active_subscriptions)" -ForegroundColor Green
        Write-Host "    Month revenue: `$$($stripeData.month_revenue_mxn)" -ForegroundColor Green
        Write-Host "    Balance: `$$($stripeData.balance_available) available" -ForegroundColor Green
    } catch {
        Write-Host "    [!] Stripe error: $_" -ForegroundColor Red
    }
} else {
    Write-Host "`n[!] No STRIPE_SECRET_KEY" -ForegroundColor Yellow
}

# ─── RESEND ──────────────────────────────────────
$emailData = @{ stats = @{}; campaigns = @(); subscriber_growth = @() }
if ($RESEND_KEY) {
    Write-Host "`n[*] Syncing Resend..." -ForegroundColor Cyan
    try {
        $headers = @{ "Authorization" = "Bearer $RESEND_KEY" }
        $emails = Invoke-RestMethod -Uri "https://api.resend.com/emails?limit=100" -Headers $headers
        
        $total = $emails.data.Count
        $delivered = ($emails.data | Where-Object { $_.last_event -eq "delivered" }).Count
        $opened = ($emails.data | Where-Object { $_.last_event -eq "opened" }).Count
        $clicked = ($emails.data | Where-Object { $_.last_event -eq "clicked" }).Count
        $bounced = ($emails.data | Where-Object { $_.last_event -eq "bounce" }).Count
        
        $emailData.stats = @{
            total_sent = $total
            total_delivered = $delivered
            total_opened = $opened
            total_clicked = $clicked
            total_bounced = $bounced
            delivery_rate = [math]::Round($delivered / [math]::Max($total, 1) * 100, 1)
            open_rate = [math]::Round($opened / [math]::Max($delivered, 1) * 100, 1)
            click_rate = [math]::Round($clicked / [math]::Max($delivered, 1) * 100, 1)
            bounce_rate = [math]::Round($bounced / [math]::Max($total, 1) * 100, 1)
        }
        
        Write-Host "    Sent: $total" -ForegroundColor Green
        Write-Host "    Open rate: $($emailData.stats.open_rate)%" -ForegroundColor Green
        Write-Host "    Click rate: $($emailData.stats.click_rate)%" -ForegroundColor Green
    } catch {
        Write-Host "    [!] Resend error: $_" -ForegroundColor Red
    }
} else {
    Write-Host "`n[!] No RESEND_API_KEY" -ForegroundColor Yellow
}

# ─── SUPABASE ────────────────────────────────────
$supabaseData = @{}
if ($SUPABASE_URL -and $SUPABASE_KEY) {
    Write-Host "`n[*] Syncing Supabase..." -ForegroundColor Cyan
    try {
        $headers = @{ "apikey" = $SUPABASE_KEY; "Authorization" = "Bearer $SUPABASE_KEY" }
        
        $users = Invoke-RestMethod -Uri "$SUPABASE_URL/rest/v1/users?select=id" -Headers $headers
        $products = Invoke-RestMethod -Uri "$SUPABASE_URL/rest/v1/yayika_products?select=id" -Headers $headers
        $subscribers = Invoke-RestMethod -Uri "$SUPABASE_URL/rest/v1/yayika_subscribers?select=id&status=eq.active" -Headers $headers
        
        $supabaseData = @{
            users = $users.Count
            products = $products.Count
            subscribers = $subscribers.Count
        }
        
        Write-Host "    Users: $($supabaseData.users)" -ForegroundColor Green
        Write-Host "    Products: $($supabaseData.products)" -ForegroundColor Green
    } catch {
        Write-Host "    [!] Supabase error: $_" -ForegroundColor Red
    }
} else {
    Write-Host "`n[!] No SUPABASE config" -ForegroundColor Yellow
}

# ─── GENERATE JSON ───────────────────────────────
Write-Host "`n[*] Generating dashboard JSON..." -ForegroundColor Cyan

if (-not (Test-Path $DATA_DIR)) { New-Item -ItemType Directory -Path $DATA_DIR -Force | Out-Null }

# Overview
$overview = @{
    generated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
    today_visitors = 0
    yesterday_visitors = 0
    today_pageviews = 0
    total_subscribers = if ($supabaseData.ContainsKey('subscribers')) { $supabaseData.subscribers } else { $stripeData.active_subscriptions }
    total_articles = 10
    month_revenue_mxn = $stripeData.month_revenue_mxn
    mrr = $stripeData.mrr
    arr = $stripeData.arr
    active_subscriptions = $stripeData.active_subscriptions
}
$overview | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $DATA_DIR "overview.json") -Encoding UTF8
Write-Host "    Written: overview.json" -ForegroundColor Gray

# Revenue
if ($stripeData.daily) {
    $stripeData.daily | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $DATA_DIR "revenue.json") -Encoding UTF8
    Write-Host "    Written: revenue.json" -ForegroundColor Gray
}

# Email
$emailData | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $DATA_DIR "email.json") -Encoding UTF8
Write-Host "    Written: email.json" -ForegroundColor Gray

Write-Host "`n[OK] Dashboard updated!" -ForegroundColor Green
Write-Host "     Next: git add docs/data/ && git commit -m 'sync: real data' && git push" -ForegroundColor Gray
