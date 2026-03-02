# Retail Analytics Reference — DSR|RIECT / ClickHouse

## Project Context

- **Project**: DSR|RIECT (Retail Intelligence Execution Control Tower)
- **Local path**: `/Users/dsr-ai-lab/DSR|RIECT/`
- **DB**: ClickHouse — `vmart_sales.pos_transactional_data`, `vmart_product.inventory_current`
- **Latest sales date**: ~2026-02-28, FY2025-26 Week 48, days_elapsed_fy=334
- **FY**: Indian Financial Year — April 1 to March 31

## Core KPIs

| KPI | Formula | Target | Priority |
|---|---|---|---|
| SPSF | Revenue / Store sqft | 1,000 INR | P1 |
| Sell-Thru % | Units Sold / (Units Sold + Closing Stock) × 100 | 95% | P1 |
| DOI | (Closing Stock / Avg Daily Sales) | Minimise | P1 |
| ATV | Net Revenue / Transaction Count | — | P2 |
| UPT | Units Sold / Transaction Count | — | P2 |
| Discount Rate | Discount / MRP × 100 | — | P2 |
| Gross Margin % | (Revenue - COGS) / Revenue × 100 | — | P2 |
| Mobile Pct | Mobile Transactions / Total × 100 | — | P3 |
| Bill Integrity | Valid Bills / Total Bills × 100 | — | P3 |
| GIT Coverage | GIT / SOH × 100 | — | P3 |

## Date Intelligence (FY-Aware)

```python
# FY starts April 1
import datetime

def fy_start(date: datetime.date) -> datetime.date:
    return datetime.date(date.year if date.month >= 4 else date.year - 1, 4, 1)

def fy_end(date: datetime.date) -> datetime.date:
    return datetime.date(date.year + 1 if date.month >= 4 else date.year, 3, 31)

def fy_week(date: datetime.date) -> int:
    delta = (date - fy_start(date)).days
    return (delta // 7) + 1

def ytd_range(as_of: datetime.date):
    return fy_start(as_of), as_of

def mtd_range(as_of: datetime.date):
    return as_of.replace(day=1), as_of

def qtd_range(as_of: datetime.date):
    month = as_of.month
    fy_s  = fy_start(as_of)
    q_starts = [fy_s, fy_s.replace(month=(fy_s.month + 3) % 12 or 12),
                fy_s.replace(month=(fy_s.month + 6) % 12 or 12),
                fy_s.replace(month=(fy_s.month + 9) % 12 or 12)]
    for qs in reversed(q_starts):
        if as_of >= qs:
            return qs, as_of
    return fy_s, as_of

def wtd_range(as_of: datetime.date):
    # Week starts Monday
    week_start = as_of - datetime.timedelta(days=as_of.weekday())
    return week_start, as_of

def ltl_range(as_of: datetime.date):
    """Like-for-Like: same week/period prior FY."""
    prior_fy_same_day = as_of.replace(year=as_of.year - 1)
    prior_week_start  = prior_fy_same_day - datetime.timedelta(days=prior_fy_same_day.weekday())
    return prior_week_start, prior_week_start + datetime.timedelta(days=6)
```

## ClickHouse SQL Patterns

### YTD Revenue (FY-aware)
```sql
SELECT
    store_id,
    store_name,
    SUM(net_revenue) AS ytd_revenue,
    COUNT(DISTINCT bill_no) AS ytd_transactions
FROM vmart_sales.pos_transactional_data
WHERE
    sale_date BETWEEN toDate('2025-04-01') AND toDate('2026-02-28')
    AND is_cancelled = 0
GROUP BY store_id, store_name
ORDER BY ytd_revenue DESC;
```

### SPSF Calculation
```sql
SELECT
    p.store_id,
    p.store_name,
    SUM(p.net_revenue)       AS revenue,
    s.floor_sqft,
    SUM(p.net_revenue) / s.floor_sqft AS spsf
FROM vmart_sales.pos_transactional_data p
JOIN store_sqft s ON p.store_id = s.store_id
WHERE p.sale_date BETWEEN {start_date} AND {end_date}
  AND p.is_cancelled = 0
GROUP BY p.store_id, p.store_name, s.floor_sqft
HAVING spsf < 1000   -- below target
ORDER BY spsf ASC;
```

### Sell-Through %
```sql
SELECT
    sku_code,
    category,
    SUM(units_sold)  AS sold,
    SUM(closing_stock) AS stock,
    SUM(units_sold) / (SUM(units_sold) + SUM(closing_stock)) * 100 AS sell_thru_pct
FROM vmart_product.inventory_current i
JOIN vmart_sales.pos_transactional_data s USING (sku_code)
WHERE s.sale_date BETWEEN {start_date} AND {end_date}
GROUP BY sku_code, category
HAVING sell_thru_pct < 95   -- below target
ORDER BY sell_thru_pct ASC;
```

### LTL (Like-for-Like) — Dual Date Range in One Query
```sql
SELECT
    store_id,
    sumIf(net_revenue, sale_date BETWEEN {curr_start} AND {curr_end}) AS current_revenue,
    sumIf(net_revenue, sale_date BETWEEN {prior_start} AND {prior_end}) AS prior_revenue,
    (current_revenue - prior_revenue) / prior_revenue * 100 AS ltl_growth_pct
FROM vmart_sales.pos_transactional_data
WHERE sale_date BETWEEN {prior_start} AND {curr_end}
  AND is_cancelled = 0
GROUP BY store_id
ORDER BY ltl_growth_pct ASC;
```

### DOI Calculation
```sql
SELECT
    category,
    SUM(closing_stock) AS total_stock,
    AVG(avg_daily_sales) AS avg_daily_sales,
    SUM(closing_stock) / AVG(avg_daily_sales) AS doi
FROM vmart_product.inventory_current
GROUP BY category
ORDER BY doi DESC;
```

## Alert Thresholds (config.py)

```python
THRESHOLDS = {
    "SPSF":              {"target": 1000,  "critical": 700,   "warning": 850},
    "SELL_THRU":         {"target": 95.0,  "critical": 80.0,  "warning": 88.0},
    "DOI":               {"target": 30,    "critical": 60,    "warning": 45},
    "ATV":               {"target": None,  "critical": None,  "warning": None},  # dynamic
    "DISCOUNT_RATE":     {"target": 15.0,  "critical": 35.0,  "warning": 25.0},
    "NON_PROMO_DISC":    {"target": 5.0,   "critical": 15.0,  "warning": 10.0},
    "GROSS_MARGIN":      {"target": 40.0,  "critical": 25.0,  "warning": 32.0},
    "MOBILE_PENETRATION":{"target": 60.0,  "critical": 30.0,  "warning": 45.0},
    "BILL_INTEGRITY":    {"target": 99.0,  "critical": 95.0,  "warning": 97.0},
}
```

## Exception Priority Model

```
P1 — SPSF, Sell-Thru, DOI breaches         → Immediate action
P2 — ATV, UPT, Discount Rate deviations     → Action within 24h
P3 — Mobile Pct, Bill Integrity, GIT         → Review this week
P4 — Informational                            → Monitor
```

## RIECT Roadmap

```
Phase 1 (current): Alert/Exception Engine → /api/alerts + UI panel
Phase 2:           Control Tower Dashboard (KPI tiles + chat dual-pane)
Phase 3:           Real-time signal ingestion (watched folder, scheduled pull)
Phase 4:           Execution loop (playbooks, escalation, outcome tracking)
```

## Backend Pipeline Files

```
app/backend/pipeline/
├── query_normalizer.py   — normalise natural language to structured query
├── orchestrator.py       — main pipeline orchestrator + sqft enrichment
├── sql_generator.py      — generate ClickHouse SQL from structured query
├── prompt_builder.py     — build LLM prompt with KPI sections
└── date_engine.py        — FY-aware date intelligence (YTD/MTD/WTD/QTD/LTL)

app/backend/riect/kpi_engine/
├── kpi_controller.py     — orchestrates all KPI engines
├── extended_kpi_engine.py — ATV, UPT, Discount Rate, Gross Margin, etc.
└── anomaly_engine.py     — detects KPI anomalies with severity scoring
```
