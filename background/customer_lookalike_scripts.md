# Customer Lookalike Evaluation Scripts

This document describes the two production Customer Lookalike evaluation scripts used to measure campaign incrementality via 1:1 statistical matching.

---

## Overview

Both scripts follow the same core approach:

1. **Audience ingestion** — Read treatment and potential lookalike customers from a BigQuery audience table for a given campaign.
2. **Feature engineering** — Calculate historical order features (L7D, L14D, L30D, L90D, etc.) per customer from `fact_order`.
3. **Outlier removal** — Exclude customers with implausibly high order counts.
4. **Exact matching** — Match treatment customers to lookalikes with identical values on a set of discrete conditions.
5. **KNN fallback** — For unmatched treatment customers, find the nearest lookalike using `sklearn.NearestNeighbors` (k=1) on MinMax-scaled features.
6. **Result aggregation** — Combine exact-match and KNN results, write to a BigQuery results table.
7. **Uplift calculation** — Query the results table to compute pre-period uplift, campaign-period uplift, and incremental orders.

The scripts differ in which features they match on, which audience table they read from, and what outcome metrics they track.

---

## V2: With City Type

**File:** `notebooks/customer_look_alike_evaluation_v2_with_city_type.py`
**Colab:** `https://colab.research.google.com/drive/1uyjelowiGuE19KZmfwLrXSOeCzZOCc3Q`

### Purpose

Extends the base Customer Lookalike methodology by adding `city_type` as a matching dimension. This constrains matches to customers in the same type of city (e.g. urban vs. suburban), reducing geographical bias.

### Configuration

| Setting | Value |
|---------|-------|
| Campaign | `pfo_customer_uplift_DENLGBES_1yearnopromo_fixed` |
| Market filter | `NL` only, from `2024-09-22` onwards |
| Audience table | `customer_intelligence.customer_lookalike_evaluation_audience_citytype` |
| Results table | `customer_intelligence.customer_lookalike_evaluation_results_gmv2` |

### Matching conditions (exact match)

```
country, city_type, optin, campaign_start_date,
L14D_orders, L30D_orders, L90D_orders, L365D_orders, L365D_AOV_cat
```

### KNN features (fallback)

```
optin, L14D_orders, L30D_orders, L90D_orders, L180D_orders, L365D_orders, L365D_AOV_cat
```

### Outcome metrics tracked

- `campaign_period_orders` — orders during campaign window
- `campaign_period_discount` — total discount amount during campaign
- `campaign_period_food_total` — total food revenue during campaign
- `L30D_GMV` — 30-day GMV (pre-period baseline)

### Key differences from V3

- **Includes `city_type`** in both the query and exact-match conditions, adding a geographical constraint.
- **Includes `L365D_AOV_cat`** (AOV tercile) as both an exact-match and KNN feature.
- **Does not filter on promo orders** — no `L30D_promo_orders == 0` filter.
- **Tracks GMV and discount** metrics alongside order counts.
- **Does not include `L730D_orders`** in outlier filtering or KNN.
- **Iterates per country x date x city_type** combination (triple loop).
- **Processes one country/date/city_type at a time** and writes to BQ after each iteration (no batching).

### Outlier filters

```python
L7D_orders  <= 7
L14D_orders <= 14
L30D_orders <= 30
L90D_orders <= 90
L180D_orders <= 180
L365D_orders <= 365
L365D_orders > 0     # must have at least 1 order in past year
treatment == 1 (or 0)
```

---

## V3: With Promo Orders Correction

**File:** `notebooks/customer_look_alike_evaluation_v3_with_promo_orders_bilal.py`
**Colab:** `https://colab.research.google.com/drive/1M5TASzG7iar22Zoe6Ue-8oSIp_kmI2io`

### Purpose

The current production evaluation script. Adds a promo-order correction factor that adjusts for the fact that treatment customers receive promotional vouchers while lookalikes do not — without this, raw uplift understates true incrementality by mixing organic and promo-driven orders.

### Configuration

| Setting | Value |
|---------|-------|
| Campaign | `SmartGrowth_Jan26_Wave1_20260319` |
| Market filter | `AT, BE, BG, CH, DE` |
| Audience table | `customer_intelligence.customer_lookalike_evaluation_audience` |
| Results table | `customer_intelligence.customer_lookalike_evaluation_results_promo_orders` |

### Matching conditions (exact match)

```
country, optin, campaign_start_date,
L14D_orders, L30D_orders, L90D_orders, L365D_orders
```

### KNN features (fallback)

```
optin, L14D_orders, L30D_orders, L90D_orders, L180D_orders, L365D_orders, L730D_orders
```

### Outcome metrics tracked

- `campaign_period_orders` — total orders during campaign
- `campaign_period_promo_orders` — orders with `restaurant_discount > 0` during campaign

### Key differences from V2

- **No `city_type`** — matches across all cities in a country.
- **No `L365D_AOV_cat`** in matching — fewer exact-match conditions, so higher exact-match rate.
- **Promo order filtering** — excludes customers with `L30D_promo_orders > 0` from both treatment and lookalike pools, ensuring pre-campaign promo activity doesn't confound results.
- **Includes `L730D_orders`** (2-year history) in outlier filtering and KNN features.
- **Batched writes** — collects all country/date results in memory and writes once to BQ at the end.
- **Promo correction in results query** — the final SQL calculates:
  - `incr_correction_factor`: ratio of promo-order share (lookalike / treatment)
  - `corrected_incr_on_repeat_orders`: incremental orders adjusted for the promo imbalance
  - `corrected_order_uplift`: uplift adjusted for promo contamination
  - `first_order_uplift`: first-order incrementality estimate
  - `total_incr_orders`: combined repeat + first-order incrementality

### Outlier filters

```python
L7D_orders   <= 7
L14D_orders  <= 14
L30D_orders  <= 30
L90D_orders  <= 90
L180D_orders <= 180
L365D_orders <= 365
L730D_orders <= 730
L30D_promo_orders == 0   # NEW: exclude recent promo users
treatment == 1 (or 0)
```

Note: unlike V2, V3 does **not** require `L365D_orders > 0`, so zero-order customers are included.

---

## Side-by-Side Comparison

| Dimension | V2 (City Type) | V3 (Promo Correction) |
|-----------|-----------------|------------------------|
| City-type matching | Yes | No |
| AOV-category matching | Yes | No |
| Promo-order exclusion | No | Yes (`L30D_promo_orders == 0`) |
| Promo correction factor | No | Yes (in results query) |
| L730D (2-year) features | No | Yes |
| Min order requirement | `L365D_orders > 0` | None |
| GMV / discount tracking | Yes | No |
| BQ write strategy | Per iteration | Batched at end |
| Audience table | `..._audience_citytype` | `..._audience` |
| Results table | `..._results_gmv2` | `..._results_promo_orders` |

---

## Shared Limitations

Both scripts share the structural limitations identified in the A/A test validation:

1. **Low exact-match coverage (~20%)** — Most treatment customers fall through to KNN, which can introduce systematic bias.
2. **No match-quality threshold** — KNN always returns the nearest neighbour regardless of distance. Poor matches are never rejected.
3. **No pre-period validation built in** — Neither script checks whether the matched pairs have similar pre-campaign ordering before accepting the match. The pre-period uplift check only happens downstream in the results query.
4. **Single-neighbour matching** — `n_neighbors=1` means each unmatched treatment customer maps to exactly one lookalike. Averaging over multiple neighbours could reduce variance.
5. **Campaign overlap** — Neither script validates that lookalike customers weren't exposed to other concurrent campaigns.

---

## Data Flow

```
Audience table (BQ)
    │
    ▼
Query: join with fact_order to get order features
    │
    ▼
Split into treatment / lookalike DataFrames
    │
    ▼
Remove outliers
    │
    ├──► Exact match on discrete conditions
    │        │
    │        ▼
    │    grouped_df (matched treatment customers)
    │
    └──► Unmatched treatment customers
             │
             ▼
         MinMaxScaler → KNN (k=1) → nearest_neighbors_df
             │
             ▼
         Concatenate exact + KNN results → final_df
             │
             ▼
         Write to BQ results table
             │
             ▼
         Results query: compute uplift, incremental orders (+ promo correction in V3)
```
