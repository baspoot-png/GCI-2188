# Synthetic Control Techniques: Assessment & Comparison

## Context

When A/B tests are not feasible (no SERP interruptor / OMT connected to Braze and SFMC/Hightouch), campaign incrementality must be estimated using synthetic control methods. Three distinct techniques are currently in use or planned across DE, NL, and UK markets. This document compares them on methodology, assumptions, known issues, and suitability.

---

## Overview

| Dimension | 1. Customer Lookalike | 2. City Lookalike (MAVERICK + BSTS) | 3. Clustered Geo-Experiment (UK) |
|---|---|---|---|
| **Unit of analysis** | Individual customer | Entire city | Cluster of cities |
| **Control construction** | KNN matching on behavioural features | KNN on city features + BSTS time-series counterfactual | Stratified random clustering + BSTS |
| **Matching basis** | 12-month order history per customer | City-level supply, demand, demographics, competitive landscape | City-level order trends, demographics, market share, deprivation index |
| **Markets** | DE, NL (all markets) | DE (Flash Sales, Reactivation) | UK (planned) |
| **Scripts** | `customer_look_alike_evaluation_v3_with_promo_orders_bilal.py`, `customer_look_alike_evaluation_v2_with_city_type.py` | `maverick___control_city_finder.py`, `Flash Sales Causal Inference.sql`, `essen___flash_sales___27_28_02_26___inc_per_customer_segments.py` | `background/uk_plan.md` |
| **Campaign types** | Smart Growth, Winback, SVP | Flash Sales, Reactivation | Acquire & Habituate, Re-engage, Build Frequency |

---

## Technique 1: Customer Lookalike (1:1 Matching)

### How it works

For each treatment customer who received a campaign (email, push, voucher), find a "twin" — a non-treated customer with the most similar ordering behaviour — and compare their outcomes during and after the campaign.

**Step 1 — Feature extraction.** For every customer in the audience, compute behavioural features from `fact_order` over rolling lookback windows:

| Feature | Window |
|---|---|
| `L7D_orders` through `L730D_orders` | 7 to 730 days before campaign start |
| `L365D_AOV` | Average order value over prior year |
| `L365D_AOV_cat` | NTILE(3) bucket of AOV |
| `optin` | Email opt-in status |
| `L30D_promo_orders` | Promo orders in prior 30 days (V3 only) |

**Step 2 — Exact match.** Treatment and lookalike pools are merged on a configurable set of exact-match conditions (e.g., country, optin, campaign_start_date, L14D_orders, L30D_orders, L90D_orders, L365D_orders). Each treatment customer is matched to all lookalike customers with identical values on these conditions. Outcome metrics are averaged across all matched lookalikes per treatment customer.

**Step 3 — KNN fallback.** Treatment customers with no exact match are matched to their nearest neighbour in the lookalike pool using KNN (k=1) on MinMax-scaled features. Scaling is fit on the lookalike pool and applied to unmatched treatment customers.

**Step 4 — Uplift calculation.** Incremental orders = sum(treatment_orders) - sum(lookalike_orders). Uplift = treatment / lookalike - 1.

### Variants

| Variant | Difference | Script |
|---|---|---|
| **V3** (promo orders) | Adds `L30D_promo_orders` filter (excludes customers with recent promo orders) and `campaign_period_promo_orders` for a correction factor | `customer_look_alike_evaluation_v3_with_promo_orders_bilal.py` |
| **V2** (city_type) | Adds `city_type` as matching condition, stratifies by city type, tracks GMV and discount metrics | `customer_look_alike_evaluation_v2_with_city_type.py` |
| **Partner Lookalike** | Same method but applied to restaurants instead of customers; uses `L30D_promo_order_share_cat` and partner-level features | `partner_look_alike_evaluation_parallel.py` |

### Strengths

- **Closest to ground truth** when applied correctly. In the Smart Growth Wave 1 (DE) benchmark, Customer Lookalike estimated ~7,800 incremental orders vs. 8,100 from the A/B test (-4% error).
- **Works at individual level** — can produce per-customer, per-segment, per-city breakdowns.
- **Flexible matching conditions** — can be tuned per campaign type.
- **No time-series modelling** — simpler to implement and interpret than BSTS.

### Known Issues

| Issue | Severity | Detail |
|---|---|---|
| **Geographical bias** | High | Look-alikes can come from cities with completely different dynamics. A treatment customer in Dortmund may be matched with a lookalike in a rural area with no campaign activity — or in a city with its own active campaign. |
| **Not usable for customers without history** | High | Cannot match new, reactivated, or churned customers with zero order history. These segments are often the primary campaign target (Reactivation, Winback). |
| **Contamination from concurrent campaigns** | High | If a lookalike customer is in a city running another campaign, their orders are artificially inflated, understating the treatment effect. The V3 promo correction factor partially addresses this. |
| **Outlier exclusion is aggressive** | Medium | Customers with >365 orders in 365 days, or any promo orders in L30D (V3), are excluded. This may systematically remove heavy users who are precisely the ones campaigns target. |
| **Exact match bias** | Medium | Exact matching on integer order counts creates discrete buckets. A customer with 5 orders in L30D is matched only with lookalikes who also had exactly 5 — not 4 or 6. This reduces the pool and may force lower-quality KNN matches. |
| **MinMaxScaler sensitivity** | Low | MinMaxScaler is sensitive to outliers in the lookalike pool. A single customer with 350 orders in L365D compresses all others into a narrow band. |
| **No temporal validation** | Low | No check that treatment and lookalike customers have parallel pre-period trends. Matching on features assumes stationarity. |

### Promo Correction Factor (V3 only)

V3 introduces a correction for the fact that treatment customers receive promotional offers while lookalikes do not. The correction factor is:

```
correction = promo_share_lookalike / promo_share_treatment
corrected_uplift = raw_uplift / (1 - correction)
```

This adjusts for the proportion of orders that would have been promo orders even without the campaign. However, this assumes the promo propensity ratio is constant across segments — which is unlikely for heterogeneous audiences.

---

## Technique 2: City Lookalike (MAVERICK + BSTS)

### How it works

Instead of matching individual customers, this technique matches entire cities and compares aggregate order trends. It operates in two stages: city selection (MAVERICK) and causal estimation (CausalImpact/BSTS).

**Stage 1 — MAVERICK: Control city selection.** For each treatment city (e.g., Essen), find the most similar cities using KNN on city-level features.

Features used in MAVERICK KNN:

| Feature | Source |
|---|---|
| Population (15+) | `cma_mbr_population.mbr_population` |
| Age distribution (15-29, 30-44, 45-59, 60+) | Same |
| Online partners (total, SMB, chain) | `dim_restaurant` |
| Local Heroes partners | `sales_analytics_datamarts.dim_local_heroes` |
| Active customers, opt-in count | `fact_unique_active_customer` + `dim_customer` |
| Competitive penetration (JET, Uber, Wolt) | `sda.fact_competitor_place` + `dim_competitor_place` |
| Popular partner penetration | Competitor data filtered by Google review quality |
| Order volume (current month, prior month, prior year) | `fact_order` |
| OV year-on-year growth | Derived |
| Conversion rate (session-to-order) | `ubd_datamart.restaurant_funnel_serp_to_order` |
| SMB photo/description coverage | `core_dwh.fact_restaurant_daily_snapshot` |
| City tier | `country_analytics_hub.dim_reported_city` |
| Competitor logistics presence | `sda.dim_competitor_place` fulfillment type |

After KNN returns the top 25 candidate control cities, a **correlation filter** is applied: only cities whose weekly order time series correlates >= 0.8 with the treatment city are retained.

**Stage 2 — CausalImpact (BSTS).** Bayesian Structural Time Series builds a counterfactual: "what would the treatment city's orders have been without the campaign?" using the control cities' order time series as covariates.

The model learns the relationship between treatment and control cities during a pre-period (no campaign), then projects this relationship into the post-period (campaign active). The difference between actual and predicted is the estimated treatment effect.

### Current Implementation Issues

| Issue | Severity | Detail |
|---|---|---|
| **2-day post-period** | Critical | The Essen Flash Sales evaluation uses `post_period = ['2026-02-27', '2026-02-28']`. BSTS needs weeks of post-period data, not 2 days. Statistical power is near zero. |
| **2-month gap between pre and post** | Critical | Pre-period ends Dec 31, post starts Feb 27. Jan-Feb are invisible to the model. It extrapolates Dec patterns (including Christmas) to predict late Feb — invalid. |
| **Christmas/NYE in pre-period** | High | Oct 1 - Dec 31 includes holiday spikes. The model learns holiday patterns as "normal," then predicts a regular weekday using that distorted baseline. |
| **All controls aggregated into one bucket** | High | The Flash Sales SQL assigns all 22 control cities to a single `'X'` group. CausalImpact is designed to receive *individual* control time series as separate covariates, using spike-and-slab variable selection to weight the best controls. Aggregation defeats this entirely. |
| **Hour filtering commented out** | High | Flash Sales run during specific hours (16:00-22:00 for dinner), but the data query includes all 24 hours. The treatment effect is diluted by ~4x. |
| **No contamination check on controls** | High | Control cities (Frankfurt, Dusseldorf, Stuttgart) likely run their own campaigns. Active promotions in controls inflate the counterfactual, understating the treatment effect. |
| **No parallel trends validation** | Medium | No pre-period check that treatment and controls follow parallel trends — the fundamental assumption of the method. |
| **Copy-paste per segment, no multiple testing correction** | Medium | The same CausalImpact analysis is run 8 times (one per base_segment) with no Bonferroni or FDR correction. 8 tests at alpha=0.05 gives ~34% false positive rate. |

### Accuracy benchmark

In the Smart Growth Wave 1 (DE) comparison:

| Method | Incremental Orders | Delta vs. A/B |
|---|---|---|
| A/B Test (ground truth) | 8,100 | — |
| City Lookalike V1 (Monte Carlo, unlocked) | ~8,900 (Dormant alone) | Massive over-report |
| City Lookalike V2 (audience-locked) | 447 | **-94%** |
| Customer Lookalike (locked) | ~7,800 | -4% |

The City Lookalike captured only 6% of the true incremental effect. The signal was drowned by organic noise from untargeted users ordering in the same cities.

### Strengths (when implemented correctly)

- **Works for all customer segments** including new, churned, and prospect customers with no order history — unlike Customer Lookalike.
- **Captures spillover effects** — if a campaign drives additional orders from non-targeted customers in the same city, this is captured in city-level totals.
- **Natural counterfactual** — BSTS constructs a time-series counterfactual, which handles seasonality and trends more naturally than cross-sectional matching.

---

## Technique 3: Clustered Geo-Experiment with BSTS (UK Plan)

### How it works

This is a **prospective experimental design** — unlike Techniques 1 and 2 which are retrospective. Cities are assigned to treatment and control *before* the campaign launches, giving the design properties closer to a randomised controlled trial.

**Step 1 — City feature matrix.** Compile stratification variables for all 140 UK cities:

| Variable | Purpose |
|---|---|
| Daily order volume (trended) | Primary size signal |
| Daily order YoY growth | Trend signal — critical for BSTS pre-period fit |
| Customer count | Market size |
| Supply quality score | Restaurant quality |
| Market share | Competitive position |
| Multiple Indices of Deprivation (MIOD) | Socioeconomic proxy for price sensitivity |
| Attack / defend classification | Strategic position (growth vs. retention) |

**Step 2 — Behavioural adjacency matrix.** For each city pair, calculate the proportion of customers who order from stores in both cities. Pairs above a threshold are flagged as functionally adjacent. This is more reliable than geographic distance because it reflects actual customer cross-city ordering patterns.

**Step 3 — Constrained stratified clustering.** 140 cities are assigned to 12 treatment clusters + 1 control holdout. Constraints:
- Attack/defend ratio maintained proportionally in every cluster
- No treatment-control adjacent city pairs (prevents spillover)
- London is mandatory treatment (high cross-borough contamination risk)
- 6 distinct treatment arms, each replicated across 2 clusters for cross-validation
- ~15-20 cities in control holdout

**Step 4 — BSTS measurement.** Same CausalImpact/BSTS method as Technique 2, but with critical design advantages:
- Control cities are **prospectively assigned and protected** from treatment contamination
- Pre-period is clean and continuous (minimum 12 months)
- Measurement window is shared across clusters

### Key design features

| Feature | Why it matters |
|---|---|
| **Prospective randomisation** | Unlike retrospective techniques, treatment assignment is random before the campaign starts. This eliminates selection bias. |
| **Spillover mitigation via adjacency constraints** | Dual-layer check (geographic + behavioural) prevents the primary failure mode of city-level synthetic controls. |
| **Replication across clusters** | Each treatment arm is tested in 2 independent clusters. Consistent effects across both provide much stronger evidence than a single comparison. |
| **A/A pre-validation** | Required before launch — if BSTS cannot track cities within 1-2% during a non-campaign period, the design is revised. |
| **Portfolio incrementality framing** | When strategies stack (A, then A+B, then A+B+C), each layer is measured as marginal lift above the existing stack — not isolated. |
| **Washout windows** | 2-4 week pauses between strategy layers prevent launch noise from contaminating the next layer's BSTS pre-period. |

### Open risks

| Risk | Severity | Status |
|---|---|---|
| **Wave rollout time confounding** | High | Open — 4 weekly waves mean clusters experience different calendar windows. Recommended fix: shared measurement start date from Week 4. |
| **1-2% MDE vs. cluster size** | Medium | ~10 cities per cluster may be insufficient to detect 1-2% order uplift. Depends on A/A test validation. |
| **London scaling** | Medium | Currently one borough. When more boroughs are added, design review is required. |
| **Cross-city customer ordering** | Low | Mitigated by targeted (not broadcast) offers + sensitivity analysis excluding cross-city customers. |

---

## Head-to-Head Comparison

### Fundamental trade-offs

| Dimension | Customer Lookalike | City Lookalike (MAVERICK) | Clustered Geo (UK) |
|---|---|---|---|
| **Selection bias risk** | Medium — matching quality depends on feature set | High — city similarity may not hold during campaign period | Low — prospective randomisation |
| **Spillover risk** | High — lookalikes in treated cities are contaminated | High — control cities may run own campaigns | Low — adjacency constraints enforced |
| **Segments covered** | Only existing customers with history | All segments (new, churned, prospect) | All segments |
| **Granularity** | Per-customer | Per-city | Per-cluster (city aggregate) |
| **Scalability** | High — runs per campaign automatically | Low — requires manual city selection per campaign | Medium — upfront design cost, then reusable |
| **Statistical rigour** | Low — no time-series modelling, no CI | Medium — BSTS provides posterior intervals | High — BSTS + replication + A/A validation |
| **Operational cost** | Low — Colab notebook, ~2h per campaign | Medium — MAVERICK + CausalImpact, manual pipeline | High — clustering algorithm, adjacency matrix, multi-wave coordination |
| **Accuracy (vs. A/B)** | -4% (best case, DE) | -94% (DE, audience-locked) | Unknown — not yet tested |

### When to use which

| Scenario | Recommended technique | Rationale |
|---|---|---|
| Campaign targeting **existing customers** with order history (Smart Growth, Winback) | **Customer Lookalike V3** | Best accuracy for this segment. Add geographical constraint (Phase 2) to reduce bias. |
| Campaign targeting **all customers** including new/churned/prospect | **City Lookalike** or **Clustered Geo** | Customer Lookalike cannot match customers without history. |
| **Reactivation** campaigns (churned/lapsed customers) | **City Lookalike** (if retrospective) or **Clustered Geo** (if prospective) | Target segment has no recent order history. |
| **Flash Sales** or **OMT** campaigns (city-wide, time-limited) | **City Lookalike** with fixes (hour filter, individual controls, continuous pre-period) | City-level effect is the natural unit of analysis. |
| **New market** experiment with upfront design time | **Clustered Geo** | Most rigorous, but requires planning before campaign launch. |
| Quick retrospective evaluation with **no upfront design** | **Customer Lookalike V3** | Can be run after the fact on any campaign with audience data. |

---

## Required Improvements Before Production Use

### Customer Lookalike

1. **Add geographical constraint** — restrict lookalike pool to cities from the City Lookalike output, limiting cross-market matching bias.
2. **Validate with A/A test** — quantify inherent bias per segment. The unified A/A framework (`unified_aa_test_framework.ipynb`) is built for this purpose.
3. **Integrate segments** — join `fact_segmentation_scv_key` via `dim_unique_customer_history` to enable per-segment bias measurement.

### City Lookalike (MAVERICK + BSTS)

1. **Pass individual control city time series** to CausalImpact, not an aggregated bucket.
2. **Ensure continuous pre+post periods** — no gaps, no Christmas in the baseline for a February evaluation.
3. **Apply hour filtering** matching the actual campaign window (e.g., 16:00-22:00 for dinner Flash Sales).
4. **Check control city contamination** — query `fact_offer` + `dim_restaurant_offers` to verify no OMT campaigns are active in control cities.
5. **Add multiple testing correction** for per-segment analysis.
6. **Validate with A/A test** — run BSTS on non-campaign periods to quantify baseline drift.

### Clustered Geo (UK)

1. **Build the constrained clustering algorithm** with adjacency matrix.
2. **Resolve wave rollout time confounding** — agree on shared measurement window.
3. **Run A/A validation** before Wave 1 launch — this is a go/no-go gate.
4. **Define MDE empirically** from A/A results, not assumed.

---

## Key BigQuery Tables

| Table | Used by | Purpose |
|---|---|---|
| `dwh.fact_order` | All | Order data |
| `dwh.dim_customer` | Customer LA | Customer attributes, optin |
| `dwh.dim_restaurant` | MAVERICK | Partner supply features |
| `core_dwh.dim_unique_customer_history` | Segment join | `customerid` -> `scv_key` mapping (point-in-time) |
| `dwh.fact_segmentation_scv_key` | Segment join | `base_segment` at snapshot date |
| `customer_intelligence.customer_lookalike_evaluation_audience` | Customer LA V3 | Treatment/control audience |
| `customer_intelligence.customer_lookalike_evaluation_audience_citytype` | Customer LA V2 | Treatment/control with city_type |
| `cma_mbr_population.mbr_population` | MAVERICK | City population data |
| `sda.fact_competitor_place` / `dim_competitor_place` | MAVERICK | Competitive landscape |
| `dwh.fact_offer` / `dim_restaurant_offers` | OMT check | Campaign contamination detection |
| `customers.scv_key_base` | MAVERICK | Customer-to-city mapping |

---

## Summary

No single technique is universally best. Each has a clearly defined use case:

- **Customer Lookalike** is the workhorse for retrospective evaluation of campaigns targeting existing customers. It is the most accurate when applied to customers with order history, but fails completely for new/churned segments.

- **City Lookalike (MAVERICK + BSTS)** is the only option for campaigns that affect entire cities or target segments without order history. However, the current implementation has critical methodological flaws that must be fixed before results can be trusted.

- **Clustered Geo-Experiment** is the most rigorous approach, approaching A/B test quality through prospective randomisation and spillover controls. It requires significant upfront investment in design and coordination, making it suitable for large, planned programmes rather than ad-hoc evaluation.

The Phase 1 accuracy benchmarking (A/A tests + RCT calibration) will provide the quantitative evidence to select and improve techniques per segment and market. Until that is complete, no synthetic control result should be treated as ground truth.
