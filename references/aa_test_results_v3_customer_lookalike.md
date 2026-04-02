# A/A Test Results: V3 Customer Lookalike

## Date: 2026-03-31

---

## 1. What is the V3 Customer Lookalike?

The V3 Customer Lookalike is a retrospective synthetic control method used to estimate campaign incrementality when A/B tests are not feasible. For each customer who received a campaign (treatment), the method finds a "twin" — a non-treated customer with the most similar ordering behaviour — and compares their outcomes.

### How it works

**Step 1 — Feature extraction.** For every customer in the audience, behavioural features are computed from `fact_order` over rolling lookback windows:

| Feature | Window |
|---|---|
| `L7D_orders` through `L730D_orders` | 7 to 730 days before campaign start |
| `L365D_AOV` | Average order value over prior year |
| `L365D_AOV_cat` | NTILE(3) bucket of AOV |
| `optin` | Email opt-in status |
| `L30D_promo_orders` | Promo orders in prior 30 days |

**Step 2 — Outlier exclusion.** Customers are excluded if they exceed plausible order thresholds (e.g., >365 orders in 365 days) or have any promo orders in the prior 30 days. This is intended to remove bots and heavy promo users.

**Step 3 — Exact match.** Treatment and lookalike pools are joined on a configurable set of exact-match conditions:
- `country`, `optin`, `campaign_start_date`
- `L14D_orders`, `L30D_orders`, `L90D_orders`, `L365D_orders`

Each treatment customer is matched to all lookalike customers with identical values on these conditions. Outcome metrics (campaign-period orders, post-period orders) are averaged across all matched lookalikes per treatment customer.

**Step 4 — KNN fallback.** Treatment customers with no exact match are matched to their single nearest neighbour (k=1) in the lookalike pool using KNN on MinMax-scaled features.

**Step 5 — Uplift calculation.**

```
Incremental orders = SUM(treatment_orders) - SUM(lookalike_orders)
Uplift = SUM(treatment_orders) / SUM(lookalike_orders) - 1
```

### V3-specific: Promo correction factor

V3 adds a correction for the fact that treatment customers receive promotional offers while lookalikes do not:

```
correction_factor = promo_share_lookalike / promo_share_treatment
corrected_uplift = raw_uplift / (1 - correction_factor)
```

### Production accuracy benchmark

In the Smart Growth Wave 1 (DE) comparison against a true A/B test (8,100 incremental orders):

| Method | Incremental Orders | Delta vs. A/B | Notes |
|---|---|---|---|
| A/B Test (ground truth) | 8,100 | — | Full 96k audience |
| Customer Lookalike (raw) | ~5,200 | **-36%** | On filtered 40k high-risk audience |
| Customer Lookalike (with 1.5x multiplier) | ~7,800 | -4% | Multiplier was calibrated against the A/B result — **not independent validation** |
| City Lookalike V2 | 447 | -94% | Signal drowned by organic noise |

**Caveat:** The ~7,800 / -4% figure was produced by applying a manually chosen 1.5x contamination multiplier to the raw ~5,200 result. The multiplier was selected to bring the estimate in line with the A/B ground truth. This is circular validation and should not be cited as evidence of accuracy. Independent validation requires A/A testing and RCT calibration without post-hoc parameter tuning.

---

## 2. A/A Test Methodology

### Purpose

An A/A test runs the exact same matching methodology against a period where **no campaign was active**. The expected result is **zero uplift** — any non-zero result quantifies the methodology's inherent measurement bias.

### Design

**Audience construction.** For each pre-campaign window, all customers in the market with at least 1 order in the prior 365 days were selected from `fact_order`. Customer segments were assigned point-in-time by joining `dim_unique_customer_history` to `fact_segmentation_scv_key` using the canonical snapshot-aligned join path.

**Random split.** Customers were randomly assigned to treatment (50%) or lookalike (50%), stratified by `base_segment` to ensure balanced segment representation. No actual campaign treatment was applied — both groups are identical in expectation.

**Matching.** The production V3 matching logic was run identically:
- Feature extraction via BigQuery (L7D through L730D orders, AOV, promo orders)
- Exact match on `country`, `optin`, `campaign_start_date`, `L14D_orders`, `L30D_orders`, `L90D_orders`, `L365D_orders`
- KNN fallback (k=1, MinMaxScaler) for unmatched treatment customers
- Outlier exclusion (same thresholds as production)

**Pre-campaign windows.** A/A windows were derived from the actual campaign calendar. For each real campaign evaluated with V3 in production, a same-duration window was placed immediately before the campaign start date. This ensures the A/A test operates in the same seasonal context and customer composition that the production evaluation faced.

Windows were filtered to 7-45 day campaigns, deduplicated where >50% of the window overlapped, and capped at 10 per country to ensure broad temporal coverage without excessive runtime.

**Overlap note.** Background campaigns (gift cards, partner promotions, concurrent Smart Growth waves) were present in many A/A windows. This is intentional — the A/A test measures methodology bias in the real operating environment, not in an artificial campaign-free vacuum.

### Configuration

| Parameter | Value |
|---|---|
| Markets | DE, NL |
| Time windows | 10 (DE), 6 (NL) — derived from campaign calendar |
| Seeds per window | 5 |
| Total runs | 80 (50 DE + 30 NL) |
| Audience size | 200,000 per run (sampled from full customer base) |
| Treatment share | 50% |
| Country codes | DE: `('DE', 'DEL')`, NL: `('NL')` |

### Pass/Fail criteria

| Verdict | Condition |
|---|---|
| **PASS** | \|mean uplift\| <= 2% AND 95% CI contains zero |
| **WARNING** | \|mean uplift\| > 2% OR 95% CI excludes zero |
| **HARD FAIL** | \|mean uplift\| > 5% |

---

## 3. Results

### Summary table

| Segment | N Runs | Mean Uplift | Exact Match % | Verdict |
|---|---|---|---|---|
| **total** | 159 | **+1.1%** | 53.1% | **PASS** |
| **engaged** | 154 | **+0.4%** | 48.3% | **PASS** |
| **early** | 154 | **+0.5%** | 52.7% | **PASS** |
| **dormant** | 154 | **-4.0%** | 62.8% | WARNING |
| **reactivated** | 154 | **-5.1%** | 55.2% | HARD FAIL |
| **lapsing** | 154 | **+10.6%** | 54.1% | HARD FAIL |
| **new** | 108 | **+11.8%** | 97.5% | HARD FAIL |
| **churned** | 108 | **+51.2%** | 61.1% | HARD FAIL |
| **prospect** | 6 | **+92.4%** | 83.3% | HARD FAIL |
| **unknown** | 156 | **+12.7%** | 54.5% | HARD FAIL |

### Matching quality

- **89% exact match rate** at the total level (89K of ~100K treatment customers per run)
- **~6% KNN fallback** (~5,500 unmatched customers per run)
- **~5% excluded as outliers** (promo orders or extreme order counts)

### Observations

**Total-level bias is low (+1.1%) but misleading.** The total aggregation masks opposing segment biases that cancel out: lapsing and new are biased positive (V3 overstates treatment), while dormant and reactivated are biased negative (V3 understates treatment). The +1.1% total is an artefact of averaging, not a sign of methodological accuracy.

**Sparse segments show extreme bias.** Churned (+51%), prospect (+92%), and new (+12%) customers have very few orders in the lookback period. Their behavioural features (L14D_orders, L30D_orders, etc.) are all near-zero, which means:
- Exact matching groups together everyone with zero orders — the match is trivially perfect but uninformative
- The matched pairs have identical pre-period behaviour but wildly different post-period outcomes
- Small absolute differences produce extreme percentage uplifts due to near-zero denominators

**High exact match rate for "new" (97.5%) is a red flag, not a strength.** Nearly all new customers have the same feature profile (1-2 orders across all windows), so they all match each other. The match is statistically valid but causally empty — matching on zeros tells you nothing about future behaviour.

**Lapsing bias (+10.6%) indicates asymmetric mean reversion.** Lapsing customers are at an inflection point — some will recover and order again, others will churn. A random 50/50 split should produce balanced groups, but the matching step reintroduces imbalance because it matches on *past* behaviour while the *future* trajectory is what matters. Treatment lapsing customers who happen to recover are matched with lookalikes who didn't — producing false uplift.

---

## 4. Conclusions

### V3 is reliable for engaged and early segments

For customers with substantial order history (engaged: regular orderers, early: building habit), the matching methodology produces less than 1% bias. The A/A test shows these segments PASS with:
- Mean uplift well within the +/-2% threshold
- Sufficient statistical power (154 runs)
- Reasonable exact match coverage (~50%, indicating meaningful feature variation)

**Recommendation:** V3 can be used with confidence for campaigns targeting engaged and early customers. Results for these segments should be reported without adjustment.

### V3 is unreliable for sparse segments

For churned, prospect, new, lapsing, and reactivated customers, V3 produces systematic bias exceeding 5% — often exceeding 10-50%. The fundamental issue is that customers with little or no order history cannot be meaningfully distinguished through behavioural matching.

**Recommendation:** V3 results for these segments should either:
1. **Not be reported** — exclude from campaign evaluation entirely
2. **Be flagged with a bias correction** — subtract the A/A-measured bias from production results (e.g., if A/A shows +10.6% for lapsing, subtract that from any measured campaign uplift for lapsing)
3. **Be replaced with a different technique** — City Lookalike (BSTS) or Clustered Geo-Experiment, which operate at city level and do not require individual customer history

### The total-level number should not be used in isolation

The +1.1% total bias is low, but it conceals segment-level biases of 5-92% that cancel out in aggregation. Any campaign evaluation that reports only total-level uplift using V3 is masking unreliable segment-level estimates. Production evaluations should always report per-segment breakdowns with the A/A bias context.

### Segment-level bias correction table

If V3 must be used for all segments (e.g., no alternative technique is available), apply the following A/A-measured bias as an adjustment:

| Segment | A/A Bias | Correction | Example |
|---|---|---|---|
| engaged | +0.4% | Subtract 0.4% | If V3 measures +5% uplift, adjusted = +4.6% |
| early | +0.5% | Subtract 0.5% | |
| dormant | -4.0% | Add 4.0% | If V3 measures +3% uplift, adjusted = +7.0% |
| reactivated | -5.1% | Add 5.1% | |
| lapsing | +10.6% | Subtract 10.6% | If V3 measures +15% uplift, adjusted = +4.4% |
| new | +11.8% | Subtract 11.8% | |
| churned | +51.2% | Subtract 51.2% | **Correction larger than typical effect — do not use** |
| prospect | +92.4% | — | **Insufficient data and extreme bias — do not use** |

**Caveat:** Bias corrections assume the A/A bias is stable across campaigns, time periods, and markets. This is a simplification — bias may vary with campaign duration, customer pool size, and seasonal effects. The corrections above are averages across 80 runs and should be treated as indicative, not definitive.

---

## 5. Next Steps

1. **Run City Lookalike A/A test** — determine whether BSTS handles sparse segments better than customer-level matching
2. **Run comparison notebook** (`aa_comparison.ipynb`) — cross-technique scorecard when City Lookalike results are available
3. **Investigate bias reduction** — test whether adding geographical constraints (restrict lookalike pool to similar cities) reduces bias for lapsing and dormant segments
4. **Align with markets** — share these findings with DE and NL analytical teams to agree on per-segment technique recommendations
