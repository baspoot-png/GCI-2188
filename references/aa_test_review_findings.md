# A/A Test Review: Findings & Recommendations

## Date: 2026-03-30

## Scripts Reviewed

| Script | Technique | Unit | Market |
|--------|-----------|------|--------|
| `customer_look_alike_evaluation_v3_with_promo_orders_bilal.py` | Customer Lookalike V3 | Customer | All |
| `customer_look_alike_evaluation_v2_with_city_type.py` | Customer Lookalike V2 | Customer | All |
| `maverick___control_city_finder.py` | City Lookalike (MAVERICK) | City | DE |
| `Flash Sales Causal Inference.sql` | City Lookalike (CausalImpact data) | City | DE |
| `essen___flash_sales___27_28_02_26___inc_per_customer_segments.py` | City Lookalike (CausalImpact eval) | City | DE |
| `OMT Evaluation Script.sql` | Campaign measurement (not synthetic) | Order | DE |
| `customer_lookalike_aa_test_no_segment.ipynb` | A/A test for V3 | Customer | DE |
| `customer_lookalike_aa_test.ipynb` | A/A test for V3 (with segments) | Customer | DE |

---

## Key Discoveries

### 1. Canonical `scv_key` join path (confirmed across 3 scripts)

```sql
-- fact_order.customerid -> dim_unique_customer_history.customer_id -> fact_segmentation_scv_key.scv_key
LEFT JOIN `just-data-warehouse.core_dwh.dim_unique_customer_history` AS ch
    ON fo.customerid = ch.customer_id
    AND DATE_SUB(ch.snapshot_date, INTERVAL 1 DAY) = DATE(fo.orderdatetime)
LEFT JOIN `just-data-warehouse.dwh.fact_segmentation_scv_key` AS s
    ON ch.scv_key = s.scv_key
    AND DATE_SUB(DATE(fo.orderdatetime), INTERVAL 1 DAY) = s.snapshot_date
```

Confirmed in: `Flash Sales Causal Inference.sql`, `OMT Evaluation Script.sql`, `maverick___control_city_finder.py`.

Alternative path for current-state (not point-in-time): `dim_customer.customerhash = scv_key`.

### 2. Segment values are lowercase

`fact_segmentation_scv_key.base_segment` uses lowercase values: `new`, `reactivated`, `early`, `engaged`, `lapsing`, `dormant`, `prospect`, `churned`. The segmented A/A notebook uses title-case (`New`, `Reactivated`, etc.) — these will silently produce empty groups.

### 3. `fact_segmentation_scv_key` also contains `city`

The table includes a `city` column, which could be used to derive `city_type` for V2 matching or to assign customers to cities for City Lookalike analysis.

---

## Findings by Technique

### A. Customer Lookalike V3 (A/A test: `customer_lookalike_aa_test_no_segment.ipynb`)

**Status:** Architecturally sound, has critical bugs.

| Issue | Severity | Detail |
|-------|----------|--------|
| Missing `cleanup_aa_audience` function | CRITICAL | Called in `finally` block but never defined. Rows accumulate across seeds, potentially contaminating subsequent runs. |
| Only DE market | HIGH | `COUNTRIES = ['DE']` hardcoded. NL and EN/UK missing. |
| No segment integration | HIGH | Does not join `fact_segmentation_scv_key`. Cannot produce per-segment bias measurements. |
| Incomplete overlap check | MEDIUM | Only checks `customer_lookalike_evaluation_audience`. Misses OMT campaigns (`fact_offer`), Winback (`mlc_log_comebackvoucher`), and other campaign tables. |
| `run_matching_v3` truncated | MEDIUM | Cell 10 appears truncated mid-SQL in the no-segment notebook. Verify completeness. |
| No V2 support | HIGH | Cannot evaluate V2 technique. |

### B. Customer Lookalike V2

**Status:** Not testable in current A/A framework.

| Issue | Detail |
|-------|--------|
| `city_type` sourcing unknown | V2 production uses `customer_lookalike_evaluation_audience_citytype` table. For A/A, need to source city_type independently — either from `fact_segmentation_scv_key.city` mapped to a tier/type, or from `dim_reported_city.city_tier`. |
| Additional matching conditions | V2 uses `city_type` and `L365D_AOV_cat` beyond V3's conditions. |
| GMV metrics not in A/A | V2 tracks `L30D_GMV`, `campaign_period_food_total`, `campaign_period_discount` — none present in the A/A script. |

### C. City Lookalike — MAVERICK + CausalImpact (Flash Sales evaluation)

**Status:** Fundamentally flawed methodology as currently implemented.

| Flaw | Severity | Detail |
|------|----------|--------|
| **2-day post-period** | CRITICAL | `post_period = ['2026-02-27', '2026-02-28']`. CausalImpact/BSTS needs weeks of post-period data, not 2 days. Statistical power is near zero. |
| **2-month gap between pre and post** | CRITICAL | Pre-period ends 2025-12-31, post-period starts 2026-02-27. January and February are invisible. The model extrapolates Dec patterns to predict late Feb — invalid. |
| **Christmas/NYE in pre-period** | HIGH | Oct 1 - Dec 31 includes holiday spikes that distort the BSTS baseline. The model learns holiday patterns as "normal" then predicts a regular weekday in Feb. |
| **All control cities aggregated** | HIGH | Single `'X'` bucket for 22 control cities. CausalImpact is designed to use multiple individual control series as covariates with spike-and-slab variable selection. Aggregation loses this advantage. |
| **Hour filtering commented out** | HIGH | Flash Sales run during specific hours (e.g., 16:00-22:00), but the data query includes all 24 hours. Treatment effect is diluted by ~4x. |
| **No control city contamination check** | HIGH | Control cities (Frankfurt, Dusseldorf, Stuttgart) likely run their own campaigns. If controls have active promotions, the counterfactual is inflated and treatment effect understated. |
| **No parallel trends validation** | MEDIUM | No pre-period check that treatment and control cities follow parallel trends. |
| **8 segments, no multiple testing correction** | MEDIUM | Same analysis copy-pasted 8 times. At alpha=0.05, 34% chance of false positive across 8 tests. |

**Context:** This aligns with the project overview finding: City Lookalike V2 (audience-locked) found only 447 incremental orders vs. 8,100 ground truth (6% accuracy).

### D. OMT Evaluation Script

**Status:** Not a synthetic control — a descriptive campaign measurement. Relevant as a contamination source.

| Relevance | Detail |
|-----------|--------|
| Campaign contamination detection | OMT campaigns are tracked via `fact_offer` + `dim_restaurant_offers.offer_source_campaign_id`. The A/A overlap check must query these tables, not just lookalike audience tables. |
| Hour-specific campaigns | Flash Sales run during specific hours. A full-day analysis may not detect contamination from hour-specific promotions. |
| Confirmed segment join | Uses identical `dim_unique_customer_history` -> `fact_segmentation_scv_key` pattern. |

---

## A/A Framework Gaps Summary

| Requirement | V3 A/A | V2 A/A | City A/A |
|-------------|--------|--------|----------|
| Matching logic implemented | Partial (truncated) | No | No |
| Multi-market (DE, NL, EN) | No (DE only) | No | No |
| Segment integration | No | No | No |
| Campaign overlap check (comprehensive) | Partial (1 table) | N/A | N/A |
| `cleanup_aa_audience` function | Missing | N/A | N/A |
| Statistical validation | Yes | N/A | N/A |
| Pass/fail criteria | Yes | N/A | N/A |
| Visualizations | Yes | N/A | N/A |

---

## Recommendations

### Immediate (implemented in unified framework)

1. **Add `cleanup_aa_audience` function** — `DELETE FROM table WHERE campaign_name = ?`
2. **Integrate segments** via canonical `dim_unique_customer_history` -> `fact_segmentation_scv_key` join
3. **Fix segment case** — use lowercase values matching `fact_segmentation_scv_key`
4. **Expand overlap check** — include `fact_offer`, `crm_control_group_automation_scv`
5. **Support multi-market** — per-market time windows, per-market campaign calendars
6. **Add V2 matching module** — with `city_type` from `fact_segmentation_scv_key.city` (requires mapping validation)
7. **Add City Lookalike module** — MAVERICK KNN + CausalImpact with individual control series

### For City Lookalike specifically

- Use **individual control city time series** as CausalImpact covariates (not aggregated)
- Require **continuous pre+post periods** (no gaps)
- Exclude **holiday periods** from pre-period, or use longer pre-periods that span multiple seasons
- Apply **hour filtering** matching the actual campaign window
- Add **correlation filter** (>=0.8) as MAVERICK production does
- Add **multiple testing correction** for per-segment analysis

### Open questions (require user input)

1. Which column do markets use for segment targeting — `base_segment` or `lifecycle_segment`?
2. How is `city_type` derived for V2? Is there a mapping from city name to city_type?
3. What are the confirmed campaign-free windows for NL and EN/UK?
4. Should the A/A test for City Lookalike use the full MAVERICK feature set or a simplified version?
