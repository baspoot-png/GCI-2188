# Customer Strategy Experiment Design
**Version 1.0 — Planning Document**
**Status: Draft for Review**

---

## 1. Executive Summary

This document outlines the experimental design for a phased customer strategy investment programme across 140 cities, covering three customer lifecycle objectives: acquiring and habituating new customers (Strategy A), re-engaging lapsing customers (Strategy B), and building order frequency among newer customers (Strategy C). The experiment uses geo-level causal inference via Bayesian Structural Time Series (BSTS) with Hamiltonian Monte Carlo (HMC) to measure incrementality, with cities grouped into treatment clusters and a control holdout.

---

## 2. Business Objectives

| Strategy | Target Segment | Goal |
|---|---|---|
| A — Acquire & Habituate | New customers | Drive first and repeat orders |
| B — Re-engage | Lapsing / lapsed customers | Reactivate dormant demand |
| C — Build Frequency | Newer habituated customers | Increase order cadence |

Strategies are launched sequentially: A launches first, B layers on top of A the following month, and C follows thereafter. The measurement approach treats each new layer as **portfolio incrementality** — i.e. does adding B on top of A lift re-engagement above what A alone would predict — rather than attempting to isolate each strategy in a vacuum.

---

## 3. City Universe

### 3.1 Scope
- **140 cities** representing 70%+ of total company order volume
- Cities are defined by **store-based delivery polygons**, not customer residence
- Cities are pre-classified into two strategic positions:

| Position | Count | Description |
|---|---|---|
| Attack | 45 | Growth-priority markets |
| Defend | 85 | Retention-priority markets |

### 3.2 London
London is currently represented by **one borough** in the 140-city list, with further boroughs planned for inclusion next quarter.

**Design decision:** London is designated as a **mandatory treatment city** in this experiment. It must not be assigned to the control holdout. The rationale is:

- High customer mobility between boroughs makes London uniquely susceptible to control contamination
- If London is in control, treated customers who also order from London stores will pollute the control baseline (Scenario 2 spillover — see Section 6)
- The business has confirmed London cannot be excluded

**Future quarter note:** When additional London boroughs are added, a dedicated design review is required before inclusion. Options include collapsing all London boroughs into a single city unit or running a London-specific sub-experiment. This is a documented **design debt item**.

---

## 4. Cluster Design

### 4.1 Structure
- **12 treatment clusters** + **1 control holdout**
- **6 distinct treatment arms**, each replicated across 2 clusters
- Approximately 9–10 cities per cluster; 18–20 cities per treatment arm
- Replication across clusters allows cross-validation: if the same treatment shows consistent lift in 2 independent clusters, confidence in the result is materially higher

> **Why not 12 different treatments?** With ~10 cities per cluster, each arm would have insufficient statistical power to reliably detect a 1–2% effect. Replication solves this while also protecting against a single cluster being an outlier.

### 4.2 Treatment Arms
Treatment arms test combinations of offer mechanics across the two offer types:

- **Discounts / promo codes**
- **Bundled offers**

The specific arm definitions (e.g. discount depth, bundle structure) are to be confirmed by the commercial team prior to cluster assignment.

### 4.3 Attack / Defend Balance
Each cluster must maintain a representative ratio of attack and defend cities, proportional to the overall universe (approximately 1:2 attack-to-defend). This is enforced as a constraint in the clustering algorithm.

### 4.4 Control Holdout
The control holdout is **not** a residual — it is actively selected using the same stratified random process as the treatment clusters. It should resemble a 13th cluster that receives no intervention.

- Target size: **15–20 cities**
- Must not contain cities geographically adjacent to treatment cities (see Section 6)
- Must maintain attack/defend balance consistent with the overall universe

---

## 5. Stratification Variables

Cities are matched and balanced across clusters using the following variables:

| Variable | Type | Notes |
|---|---|---|
| Daily Order volume | trended | Primary size signal |
| Daily Order YoY | trended | Primary size signal |
| Customer count | Static snapshot | Overall market size |
| Supply quality score | Static snapshot | Restaurant/store quality metric |
| Market share | Static snapshot | Competitive position |
| Multiple Indices of Deprivation (MIOD) | Static snapshot | ONS socioeconomic proxy; directly relevant to price sensitivity |
| Attack / defend classification | Categorical | Balanced ratio per cluster |

> **Important:** The inclusion of a trend variable (order volume growth rate) alongside the static snapshot is critical. Two cities with the same 90-day average but diverging trajectories will produce poor BSTS pre-period fit, undermining the reliability of causal estimates. This variable must be included even if it requires additional data preparation.

---

## 6. Spillover Risk & Mitigations

Spillover — where a treatment in one city affects outcomes in another — is the primary experimental risk. There are two distinct scenarios with different severities:

### Scenario 1: Treatment vs Treatment
A customer orders from City A (discount arm) and City B (bundle arm). They are exposed to both treatments.

**Severity: Acceptable.** Customer migration toward a preferred offer type is itself a behavioural signal worth observing. This is sometimes referred to as interference as information.

### Scenario 2: Treatment vs Control
A customer orders from City A (treatment) and City B (control). The control city receives treated customers.

**Severity: High.** This deflates the measured treatment effect because the control baseline is being artificially lifted or cannibalised from. This is the scenario to actively mitigate.

### 6.1 Geographic Adjacency Constraint
The clustering algorithm enforces the following rule: **no two geographically adjacent cities may be assigned to different clusters where one is control.** Adjacent cities may be in different treatment clusters (Scenario 1), but neither may be control if the other is treated.

Adjacency is defined using a dual-layer check:

1. **Distance-based:** Cities within X km of each other are flagged as potentially adjacent (threshold to be calibrated against delivery polygon data)
2. **Behavioural adjacency:** Cities where a material proportion of customers order from stores in both cities are flagged as functionally adjacent, regardless of physical distance

The behavioural adjacency check is the more reliable signal for this use case, as it reflects actual customer cross-city ordering patterns rather than assumed geographic proximity.

### 6.2 Targeted Offer Mechanics
Offers are delivered via targeted channels (push notifications, in-app targeted messaging) to specific customer segments — they are not publicly visible to all users in a city. This significantly reduces the spillover radius compared to public in-app banners, as customers must be in the target segment to receive the offer. This is a meaningful mitigant and should be preserved in the operational design.

### 6.3 Cross-City Customer Ordering
Since city membership is store-based and not residence-based, individual customers may technically belong to multiple cities. Given targeted offer delivery, the practical exposure risk is lower than it would be with broadcast offers. This is documented as a **known, accepted risk** with the following mitigant: cross-city customers are flagged in the data and used as a **sensitivity check** in the BSTS model — results are reported both including and excluding this cohort.

---

## 7. Wave Rollout & Measurement Design

### 7.1 Deployment Waves
Due to operational constraints, clusters are deployed in 4 weekly waves of 3 clusters each:

| Wave | Week | Clusters |
|---|---|---|
| Wave 1 | Week 1 | Clusters 1, 2, 3 |
| Wave 2 | Week 2 | Clusters 4, 5, 6 |
| Wave 3 | Week 3 | Clusters 7, 8, 9 |
| Wave 4 | Week 4 | Clusters 10, 11, 12 |

### 7.2 Time Confounding Risk — Open Item 🔴
**This is a material, unresolved risk.**

Because clusters launch in different calendar weeks, they are measured across different time windows. External factors — competitor promotions, seasonal events, supply disruptions — that occur during weeks 5–8 affect late-wave clusters but not early-wave clusters. BSTS synthetic controls adjust for city-level structural differences but cannot retroactively place two clusters in the same calendar window.

**Recommended mitigation (under discussion):** Define a single shared measurement start date from when the final cluster goes live (Week 4). All clusters would then share an identical 4-week measurement window. Early-wave clusters accumulate additional pre-period data, which strengthens their BSTS synthetic control fit.

**Current status:** The business is unable to consolidate to a simultaneous launch due to operational constraints. Time confounding is therefore a **documented, accepted risk** pending further discussion on the shared measurement window approach. This item must be resolved before experiment launch.

### 7.3 Washout Windows
A **2–4 week observation period** (no new interventions) is defined between strategy waves:

- Between Strategy A launch and Strategy B layer-on
- Between Strategy B and Strategy C layer-on

This prevents Strategy B's BSTS pre-period from being contaminated by the launch noise of Strategy A, and ensures the new baseline is stable before the next layer is measured.

---

## 8. Measurement Framework

### 8.1 Method
**Bayesian Structural Time Series (BSTS)** with Hamiltonian Monte Carlo (HMC) sampling, implemented via the `tfcausal_impact` library in Python.

BSTS constructs a synthetic counterfactual for each treatment city-cluster by identifying control cities that co-moved with it during the pre-period. The post-period divergence between actual and synthetic counterfactual is the estimated treatment effect.

### 8.2 Pre-Period
- Minimum 12 months of weekly or daily city-level time series data is available and will be used
- Pre-period must be clean of prior interventions where possible
- A fresh pre-period baseline is defined at each strategy wave launch

### 8.3 Primary Metrics
- Order volume (city-level, weekly)
- Customer counts by segment (new, lapsing, frequency)
- Order frequency per customer

### 8.4 Minimum Detectable Effect (MDE)
- Target MDE: **1–2% uplift in orders**
- This is at the edge of what is reliably detectable with ~10 cities per cluster over a 4-week window
- The A/A test (see Section 9) will empirically validate whether this MDE is achievable given actual city-level variance
- If A/A results show synthetic controls cannot track cities within 1–2% during the pre-period, the MDE target must be revised upward or the cluster size increased

### 8.5 Sensitivity Analysis
All primary results are accompanied by a sensitivity analysis that:
- Excludes cross-city customers (Scenario 2 spillover check)
- Excludes London
- Tests alternative pre-period lengths

---

## 9. A/A Testing

Before any treatment is deployed, an A/A test is conducted across the proposed clusters using historical data. This validates that:

1. The synthetic controls can accurately track treatment cities during a known period with no intervention
2. Pre-period fit is within acceptable tolerance (target: synthetic control tracks within 1–2% of actuals)
3. Cluster balance is confirmed across all 10 stratification variables

**The A/A test is not a formality.** If fit quality is poor for certain cities or clusters, the clustering must be revised before go-live. Results of the A/A test should be documented and signed off by the data science team prior to Wave 1 launch.

---

## 10. Open Risks & Design Decisions

| # | Risk | Severity | Status |
|---|---|---|---|
| 1 | Wave rollout time confounding | 🔴 High | Open — shared measurement window under discussion |
| 2 | Static-only stratification (mitigated by adding trend variable) | 🔴 High | Resolved — growth rate variable added |
| 3 | Control holdout adjacency to treatment cities | 🔴 High | Resolved — dual-layer adjacency constraint |
| 4 | London borough scaling (next quarter) | 🟡 Medium | Documented design debt — review required before Q+1 |
| 5 | 1–2% MDE vs cluster size | 🟡 Medium | Pending A/A test validation |
| 6 | Strategy stacking causal attribution | 🟡 Medium | Resolved — portfolio framing + washout windows |
| 7 | Inaccurate polygon data | 🟢 Low | Mitigated — behavioural adjacency as primary signal |
| 8 | Cross-city customer ordering | 🟢 Low | Mitigated — targeted offers + sensitivity analysis |

---

## 11. Build Plan (Next Steps)

The following components are to be built in Python in sequence:

**Stage 1 — City feature matrix**
Compile all 10 stratification variables per city into a single dataframe, including the trend variable (90-day order volume growth rate).

**Stage 2 — Behavioural adjacency matrix**
For each city pair, calculate the proportion of customers who order from stores in both cities. Flag pairs above a defined threshold as functionally adjacent.

**Stage 3 — Constrained clustering algorithm**
Stratified random clustering with:
- Attack/defend ratio constraint
- Geographic and behavioural adjacency constraint (no treatment-control adjacent pairs)
- London as mandatory treatment city
- Balance validation across all 10 stratification variables

**Stage 4 — Cluster balance validation**
Statistical checks (standardised mean differences, variance ratios) confirming clusters are balanced before go-live. Visual diagnostic outputs per variable.

**Stage 5 — A/A test**
Retrospective BSTS fit quality assessment across all clusters using historical data. Sign-off gate before Wave 1 launch.

---

## 12. Glossary

| Term | Definition |
|---|---|
| BSTS | Bayesian Structural Time Series — a method for constructing synthetic counterfactuals using a set of control time series |
| HMC | Hamiltonian Monte Carlo — a sampling method used to fit the BSTS model |
| MDE | Minimum Detectable Effect — the smallest true effect size the experiment is powered to detect |
| Attack city | A growth-priority market where the strategic objective is to gain share |
| Defend city | A retention-priority market where the strategic objective is to protect existing share |
| MIOD | Multiple Indices of Deprivation (ONS) — a socioeconomic classification used here as a proxy for customer price sensitivity |
| Spillover | A situation where a treatment applied to one city affects outcomes in another city |
| A/A test | A retrospective test using historical data to validate that the experimental design would have produced reliable results in the absence of any intervention |
| Washout window | A pause period between strategy waves during which no new interventions are introduced, allowing baselines to stabilise |
| Portfolio incrementality | The combined incremental lift of all active strategies together, rather than the isolated effect of any single strategy |