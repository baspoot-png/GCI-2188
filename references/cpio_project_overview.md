# Targeted Value CPiO Alignment — Project Overview

## 1. Business Problem

Campaign performance is currently measured using a patchwork of disparate data sources, local Colab notebooks, scattered Google Sheets, and market-specific evaluation techniques. There is no single, automated dashboard that consolidates incrementality and performance results across all markets (DE, NL, UK).

The core challenge: **none of the synthetic control methodologies currently produce results reliable enough to replace A/B tests**, yet A/B tests are not always feasible. The project aims to systematically quantify this gap, improve the synthetic techniques, and then automate the entire evaluation pipeline.

### Campaigns in scope

| Campaign Type     | Audience Segments                  | Current Test Method   |
|-------------------|------------------------------------|-----------------------|
| Smart Growth      | Early, Engaged, Dormant, Churned, Lapsed | Voucher Control       |
| Winback           | Lapsed                             | Voucher Control       |
| SVP (Sequential)  | Various                            | Voucher Control       |
| Reactivation      | Churned/Lapsed                     | City Lookalike        |
| Local Heroes      | Prospects                          | Voucher Control       |

### Key data sources (BigQuery)

- **Ad hoc campaigns (Treatment/Control):** `just-data-warehouse.crm_adhoc.crm_control_group_automation_scv`, `crm_control_group_automation`
- **Winback:** `crm_adhoc.mlc_log_comebackvoucher`
- **SVP / Reactivation:** `crm_adhoc.reactivated_customer_control_group`, `crm_adhoc.welcome_control_group`
- **Lookalike outputs:** stored in various BQ tables (Customer, Customer-Promo, Partner) and locally (folder-based)
- **Campaign metadata:** Google Sheet with start/end dates, voucher details

### KPIs

Uplift, incremental orders (iOV), cost, CPiO (cost per incremental order), % incremental vouchers, with deep-dives by city, base segment, and frequency bucket.

---

## 2. Evaluation Methodologies

### 2.1 A/B Test (Ground Truth)

- **Treatment:** Customers that received email/push in focus cities.
- **Control:** Unbiased hold-out group of customers in the same cities.
- **Strengths:** No selection bias — the golden standard for causal measurement.
- **Limitations:** Not always possible to set up (requires SERP interruptor / OMT connected to Braze and SFMC/Hightouch, which is not yet enabled).

### 2.2 City Lookalike (Synthetic Control)

- **Treatment:** All customers of the targeted segment in focus cities.
- **Control:** Cities most similar to focus cities, selected using KNN/BSTS over the prior 12 months.
- **Method:** Bayesian Structural Time Series (BSTS) compares entire city daily sales trends against other cities to predict a counterfactual baseline.
- **Known issues:**
  - Control cities are fixed before the campaign period and may diverge over time.
  - Significance and incrementality change across runs due to Bayesian uncertainty.
  - V1 (Monte Carlo, unlocked audience) massively over-reported — captured 750K+ extra untargeted users, leading to "hallucinated uplift."
  - V2 (audience-locked) found only 447 incremental orders vs. 8.1K ground truth (6% accuracy) — signal drowned by organic noise from untargeted users.
  - More usable at total order level, less at segment level.

### 2.3 Customer Lookalike (1:1 Matching)

- **Treatment:** Customers that received email/push in focus cities.
- **Control:** For each treatment customer, a matched "twin" found outside focus cities using KNN on behavioural features over the prior 12 months.
- **Method:** KNN matching on individual behavioural similarity (not time-series).
- **Known issues:**
  - Overlap and double-counting with other concurrent campaigns.
  - Look-alikes may come from cities with completely different dynamics (geographical bias).
  - Not possible for customers without order history (new, reactivated, churned).
  - Uses a contamination multiplier (1.5x) to correct for treatment spillover — without it, results under-report by ~33%.
- **Strengths:** When filtered to high-risk customers (>35% churn probability), captured 96% of uplift in only 40% of the audience — suggesting most low-risk voucher recipients order organically anyway ("Voucher Waste" discovery).

### 2.4 Partner Lookalike

- **Treatment:** All partners in focus cities.
- **Control:** For each partner in a focus city, matched partners outside focus cities over the prior 12 months.
- **Known issues:**
  - Partners from different cuisine types, price points, and competitive environments can be incorrectly matched.
  - Needs geographical + density + cuisine matching conditions.
- **Status:** Still to be validated against ground truth.

### 2.5 Accuracy comparison (Smart Growth Wave 1 — DE)

| Method                          | Incr. Orders | Delta vs. A/B | Notes |
|---------------------------------|-------------:|:-------------:|-------|
| **A/B Test (Ground Truth)**     |        8,100 |       —       | Full 96k audience |
| City Lookalike V1 (Monte Carlo) |       ~8,900 (Dormant segment alone) | Massive over-report | No audience lock |
| City Lookalike V2 (Locked)      |          447 |      -94%     | Signal drowned by organic noise |
| Customer Lookalike (Locked, raw)|       ~5,200 |      -36%     | On filtered 40k high-risk audience |
| Customer Lookalike (Locked, with 1.5x multiplier) | ~7,800 | -4% | **Multiplier was tuned to match the A/B result — circular validation** |

Key takeaway: The commonly cited -4% accuracy for Customer Lookalike was achieved by (a) filtering to 40k high-risk customers and (b) applying a manually chosen 1.5x contamination multiplier calibrated against the A/B result. The raw output was -36%. This is not independent validation. Unbiased accuracy measurement requires A/A testing and RCT calibration without post-hoc tuning.

---

## 3. Phased Roadmap

### Phase 1: Accuracy Benchmarking (target: ~Apr 8, 2026)

**Goal:** Quantify exactly how wrong each synthetic technique is, and under what conditions.

- **A/A Testing:** Run historical simulations for each evaluation technique during non-testing periods to confirm zero bias. Any technique that shows uplift during a period with no campaign is fundamentally flawed.
- **RCT Calibration:** Map all previous A/B tests (Smart Growth Wave 1 & 2 DE, Winback UK) to their synthetic counterparts (City Lookalike, Customer Lookalike, Partner Lookalike) to measure the "Bias Gap" for each technique per segment.
- **Cross-market alignment:** Discuss findings with DE, NL, UK analytical teams.

**Exit criteria:** A quantified bias gap for each technique, per segment, per market.

### Phase 2: Matching Optimization & Technique Selection (target: ~Apr 22, 2026)

**Goal:** Improve synthetic techniques to minimise the bias gap, and select the best technique per segment.

Optimisation directions:
- **Geographical constraint:** Restrict customer and partner matching to cities from the City Lookalike output, limiting geographical bias.
- **Predictive matching:** Match customers on predicted future orders (not just historical behaviour).
- **Condition testing:** Systematically test different matching conditions and measure impact on accuracy.
- **Partner matching:** Add geographical + density + cuisine matching conditions.

Outputs:
- Per-segment recommendation: can we evaluate (yes/no), which technique, aligned across markets.
- Validation scorecard: Pre-Period Bias, A/A Placebo Error.

**Decision tree (recommendation):**
- Existing customer with history → **Customer Lookalike (1:1 Matching)**
- New prospect without history → **City Lookalike** or no evaluation

### Phase 3: Experimentation Logic Upgrade & Automation (target: TBD)

**Goal:** Productionise the chosen techniques into an automated, self-validating pipeline.

- **Automated evaluation pipelines** with built-in checks on unbiased pre-period.
- **Hard rejection** of any match where pre-period bias exceeds a variance threshold.
- **Campaign input from Google Sheets** — campaign managers enter start/end dates, voucher details.
- **Global Dashboard** displaying all campaign results from the Google Sheet input.
- **Validation scorecard** applied automatically to every evaluation run.

This phase connects to the [technical architecture](architecture.md) (Airflow orchestration, dbt medallion layers, Looker dashboards) for the implementation details.

---

## 4. Long-term Vision

The only way to measure campaign impact with full accuracy is **end-to-end experimentation** — connecting SERP interruptor and OMT to Braze and SFMC/Hightouch. Until that is enabled, this project develops a rigorous "second best" through the phased process above.

---

## 5. Existing Assets

| Asset | Location |
|-------|----------|
| Challenge brief | [background/challenge.md](challenge.md) |
| Methodology presentation | [background/260324 Campaign evaluation methodologies comparison.txt](260324%20Campaign%20evaluation%20methodologies%20comparison.txt) |
| Technical architecture | [background/architecture.md](architecture.md) |
| Customer Lookalike script | [notebooks/copy_of_customer_look_alike_evaluation_v3_with_promo_orders_bilal.py](../notebooks/copy_of_customer_look_alike_evaluation_v3_with_promo_orders_bilal.py) |
| Partner Lookalike script | [notebooks/partner_look_alike_evaluation_parallel (1).py](<../notebooks/partner_look_alike_evaluation_parallel (1).py>) |