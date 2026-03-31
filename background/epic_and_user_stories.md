# Epic: Automated Campaign Evaluation Pipeline

## Epic Definition

| Field               | Value |
|---------------------|-------|
| **Epic Name**       | Automated Campaign Evaluation Pipeline — CPiO Alignment |
| **Epic Key**        | CPIO-EPIC-001 |
| **Owner**           | [TBD] |
| **Start Date**      | 2026-04-01 |
| **Target End Date** | 2026-06-30 |
| **Labels**          | `campaign-evaluation`, `data-engineering`, `data-science`, `automation` |
| **Markets**         | DE, NL, UK |

### Description

Build an end-to-end automated pipeline that replaces the current manual, Colab-based campaign evaluation process with a validated, self-service system. The pipeline will:

1. **Benchmark** each synthetic control methodology (City Lookalike, Customer Lookalike, Partner Lookalike) against A/B test ground truth to quantify measurement bias.
2. **Optimise** matching algorithms to minimise that bias, producing a per-segment methodology recommendation aligned across DE, NL, and UK.
3. **Automate** the entire flow — from Google Sheet campaign input through evaluation execution to a global Looker dashboard — with built-in statistical validation that rejects unreliable results.

### Business Value

- **Accuracy:** Current synthetic methods show bias gaps of up to 94% vs. ground truth. Inaccurate CPiO reporting leads to misallocated marketing budgets across three markets.
- **Speed:** Each campaign evaluation currently takes days of manual data scientist effort (running Colab notebooks, copying data, updating spreadsheets). The automated pipeline targets next-morning results.
- **Trust:** A validation scorecard and hard-rejection logic will give stakeholders confidence in the numbers — or an explicit warning when results cannot be trusted.
- **Scale:** The system must support 5 campaign types across 3 markets and multiple audience segments without additional manual effort per campaign.

### Success Metrics

| Metric | Current State | Target |
|--------|--------------|--------|
| Bias gap (Customer Lookalike vs. A/B) | ~4% | < 5% consistently |
| Bias gap (City Lookalike vs. A/B) | up to 94% | < 20% or hard rejection |
| Time from campaign end to results | 3-5 days (manual) | < 24 hours (automated) |
| Campaigns evaluated per quarter | Ad hoc | All active campaigns |
| Markets with aligned methodology | 0 (each uses own approach) | 3 (DE, NL, UK) |

### Scope

**In scope:**
- A/A testing and bias gap quantification for all synthetic methods
- Customer Lookalike and Partner Lookalike matching optimisation
- Refactoring Colab notebooks into production Python scripts
- Google Sheet ingestion pipeline
- dbt transformation layers (Bronze/Silver/Gold)
- Airflow orchestration
- Global Looker dashboard with validation scorecard
- Cross-market alignment on recommended methodology per segment

**Out of scope:**
- Enabling end-to-end A/B testing (SERP interruptor / OMT integration with Braze/SFMC) — this is the long-term vision, not this Epic
- New campaign type development
- Changes to campaign targeting or audience selection logic

### Dependencies

- GCP project access (`just-data-gci-dev`) with BigQuery read/write and Cloud Run permissions
- Local development environment approved (see CPIO-SW-001 software request)
- Access to historical A/B test results for Smart Growth Wave 1 & 2 (DE) and Winback (UK)
- Campaign details Google Sheet shared with service account

---

## User Stories

---

### CPIO-001: Refactor Customer Lookalike Colab into a local Python script

| Field | Value |
|-------|-------|
| **Phase** | Phase 1 (Foundation) |
| **Story Points** | 5 |
| **Priority** | Highest |
| **Dependencies** | Local dev environment approved |

**As a** data scientist,
**I want** the Customer Lookalike Colab notebook refactored into a standalone Python script that runs locally with `gcloud` auth,
**so that** I can version-control it in Git, iterate quickly, and eventually containerise it for production.

#### Acceptance Criteria

- [ ] `google.colab.auth` replaced with `google.auth.default()` / `gcloud auth application-default login`
- [ ] Duplicate import blocks (Colab vs. local) consolidated into a single code path
- [ ] Script accepts parameters via command-line arguments or a config file: `campaign_name`, `country`, `start_date`, `end_date`, `post_period_start`, `post_period_end`
- [ ] Script runs end-to-end locally against `just-data-gci-dev` and writes results to BigQuery
- [ ] Output schema documented (columns, types, descriptions)
- [ ] Existing logic preserved — no algorithmic changes in this story

---

### CPIO-002: Refactor Partner Lookalike Colab into a local Python script

| Field | Value |
|-------|-------|
| **Phase** | Phase 1 (Foundation) |
| **Story Points** | 5 |
| **Priority** | Highest |
| **Dependencies** | Local dev environment approved |

**As a** data scientist,
**I want** the Partner Lookalike Colab notebook refactored into a standalone Python script that runs locally,
**so that** I can iterate on matching conditions and version-control changes.

#### Acceptance Criteria

- [ ] `google.colab.auth` replaced with `gcloud` application-default credentials
- [ ] Duplicate import blocks consolidated
- [ ] Parameterised via CLI args or config: `campaign_name`, `country`, `start_date`, `end_date`, `post_period_start`, `post_period_end`
- [ ] Parallel execution (`ProcessPoolExecutor`) preserved and tested with multiple cores
- [ ] Script runs end-to-end locally and writes results to BigQuery
- [ ] Output schema documented

---

### CPIO-003: Build A/A test framework for Customer Lookalike

| Field | Value |
|-------|-------|
| **Phase** | Phase 1 (Accuracy Benchmarking) |
| **Story Points** | 8 |
| **Priority** | High |
| **Dependencies** | CPIO-001 |

**As a** data scientist,
**I want** a reusable A/A testing framework that runs the Customer Lookalike script against a "dummy" campaign period where no actual campaign was active,
**so that** I can measure the technique's inherent bias (any non-zero uplift = bias).

#### Acceptance Criteria

- [ ] Parameterised BigQuery SQL identifies the target audience during a confirmed non-campaign period
- [ ] Script excludes customers who received any actual campaign treatment during the dummy window
- [ ] Outputs incremental orders and uplift metrics in the same format as a real evaluation
- [ ] Logs a warning if `abs(uplift) > 2 * standard_error`
- [ ] Can be run across multiple historical windows by changing date parameters
- [ ] Results stored in a dedicated BigQuery table (`customer_lookalike_aa_results`) for comparison
- [ ] Tested against at least 2 non-overlapping dummy periods in DE

---

### CPIO-004: Build A/A test framework for City Lookalike

| Field | Value |
|-------|-------|
| **Phase** | Phase 1 (Accuracy Benchmarking) |
| **Story Points** | 8 |
| **Priority** | High |
| **Dependencies** | None (uses existing City Lookalike methodology) |

**As a** data scientist,
**I want** an A/A testing framework for the City Lookalike (BSTS) method,
**so that** I can confirm whether the Bayesian model returns zero bias when no campaign is running.

#### Acceptance Criteria

- [ ] Uses the same BSTS/Monte Carlo engine as the production City Lookalike
- [ ] Runs against a dummy period with no active campaigns in focus cities
- [ ] Supports both V1 (unlocked audience) and V2 (audience-locked) variants
- [ ] Outputs daily counterfactual predictions and cumulative uplift
- [ ] Logs a warning if absolute uplift deviates significantly from zero
- [ ] Results stored in `city_lookalike_aa_results` BigQuery table
- [ ] Tested against at least 2 dummy periods in DE

---

### CPIO-005: RCT Calibration — map A/B tests to synthetic counterparts

| Field | Value |
|-------|-------|
| **Phase** | Phase 1 (Accuracy Benchmarking) |
| **Story Points** | 8 |
| **Priority** | High |
| **Dependencies** | CPIO-001, CPIO-003, CPIO-004 |

**As a** data scientist,
**I want** to run all three synthetic methods (Customer Lookalike, City Lookalike V2, Partner Lookalike) against the same audiences and time periods as our existing A/B tests,
**so that** I can produce a definitive bias gap table per technique, per segment, per market.

#### Acceptance Criteria

- [ ] Executed against Smart Growth Wave 1 (DE), Smart Growth Wave 2 (DE), and Winback (UK)
- [ ] Each synthetic method uses the locked audience from the original A/B test (no dynamic re-selection)
- [ ] Bias gap calculated: `synthetic_iOV - AB_iOV` (absolute) and `(synthetic_iOV - AB_iOV) / AB_iOV` (percentage)
- [ ] Results broken down by segment: Early/Engaged vs. Dormant/Churned/Lapsed
- [ ] Summary table produced showing bias gap per method, per campaign, per segment
- [ ] Findings documented with recommendation on which techniques are viable for each segment
- [ ] Results shared with DE, NL, UK analytical teams for alignment

---

### CPIO-006: Add geographical constraints to Customer Lookalike matching

| Field | Value |
|-------|-------|
| **Phase** | Phase 2 (Matching Optimization) |
| **Story Points** | 5 |
| **Priority** | High |
| **Dependencies** | CPIO-001, CPIO-005 |

**As a** data scientist,
**I want** the Customer Lookalike script to restrict control candidate selection to cities identified by the City Lookalike output,
**so that** matched "twins" come from geographically and behaviourally similar cities rather than arbitrary non-focus cities.

#### Acceptance Criteria

- [ ] KNN matching pool filtered to customers in City Lookalike control cities only
- [ ] Configurable: can toggle geographical constraint on/off for comparison testing
- [ ] Re-run against Smart Growth Wave 1 (DE) with constraint enabled
- [ ] Bias gap compared to unconstrained version (from CPIO-005)
- [ ] Control pool size logged — flag if constraint reduces pool below statistical power threshold
- [ ] No degradation in runtime beyond 2x of unconstrained version

---

### CPIO-007: Add cuisine, density, and geo constraints to Partner Lookalike matching

| Field | Value |
|-------|-------|
| **Phase** | Phase 2 (Matching Optimization) |
| **Story Points** | 8 |
| **Priority** | High |
| **Dependencies** | CPIO-002, CPIO-005 |

**As a** data scientist,
**I want** the Partner Lookalike script to match partners on cuisine type, population density, and geographical proximity in addition to behavioural features,
**so that** a pizza restaurant in a dense urban area is not matched to a sushi restaurant in a suburban area.

#### Acceptance Criteria

- [ ] KNN feature set extended with: `cuisine_type` (categorical, one-hot encoded), `city_population_density`, `city_geo_cluster` (from City Lookalike output)
- [ ] Price point similarity added as a matching dimension
- [ ] Configurable feature weights so each dimension's influence can be tuned
- [ ] Re-run against an available A/B test period to measure bias gap improvement
- [ ] Results compared to unconstrained Partner Lookalike baseline
- [ ] Matching quality report: distribution of cuisine match rates, geo distance between matched pairs

---

### CPIO-008: Ingest Campaign Details Google Sheet into BigQuery

| Field | Value |
|-------|-------|
| **Phase** | Phase 3 (Automation) |
| **Story Points** | 3 |
| **Priority** | Medium |
| **Dependencies** | Google Sheet shared with service account |

**As a** data engineer,
**I want** the Campaign Details Google Sheet automatically ingested into a BigQuery raw table on a daily schedule,
**so that** campaign managers can define campaigns in a familiar spreadsheet and the pipeline picks them up without manual intervention.

#### Acceptance Criteria

- [ ] Google Sheet read via BigQuery External Connection (federated query) or Airflow `PythonOperator`
- [ ] Raw data lands in `crm_adhoc.raw_campaign_details` with an `ingested_at` timestamp
- [ ] Required fields validated: `campaign_name`, `country`, `start_date`, `end_date`, `voucher_name`
- [ ] Rows missing required fields routed to `crm_adhoc.campaign_details_dead_letter` with a reason column
- [ ] Valid rows available for downstream dbt models
- [ ] Ingestion runs daily at 05:00 UTC (before the main pipeline at 06:00 UTC)
- [ ] Slack alert sent when rows are quarantined to the dead-letter table

---

### CPIO-009: Build dbt transformation layers (Bronze/Silver/Gold)

| Field | Value |
|-------|-------|
| **Phase** | Phase 3 (Automation) |
| **Story Points** | 13 |
| **Priority** | Medium |
| **Dependencies** | CPIO-008, CPIO-001, CPIO-002 |

**As a** data engineer,
**I want** a dbt project with Bronze, Silver, and Gold layers that transform raw campaign and evaluation data into dashboard-ready aggregates,
**so that** business logic is version-controlled, testable, and consistent across all markets.

#### Acceptance Criteria

- [ ] **Bronze models:** 1:1 staging of `crm_control_group_automation`, `crm_control_group_automation_scv`, `mlc_log_comebackvoucher`, `reactivated_customer_control_group`, `welcome_control_group`, `raw_campaign_details`, and Python evaluation output tables
- [ ] **Silver models:**
  - [ ] `stg_campaign_details` — fault-tolerant parsing with `COALESCE(vouchername, voucherdescription)`, regex extraction of metadata tags, dead-letter routing
  - [ ] `stg_treatment_control` — unified treatment/control view across all campaign source tables
  - [ ] `stg_evaluation_results` — unified view of Customer/City/Partner Lookalike outputs
- [ ] **Gold models:**
  - [ ] `fct_campaign_results` — joins campaign metadata with treatment/control splits and evaluation outputs
  - [ ] Calculates: uplift, incremental orders (`incr_orders_standard`, `incr_orders_adjusted`), CPiO, cost, % incremental vouchers
  - [ ] Includes validation scorecard columns: `pre_period_bias`, `aa_placebo_error`, `bias_gap_pct`, `validation_status` (APPROVED / HARD_REJECTION / CONDITIONAL)
  - [ ] Hard rejection flag set when `pre_period_bias > variance_threshold`
- [ ] dbt tests: `not_null` on key columns, `unique` on primary keys, custom test for bias threshold
- [ ] `dbt docs generate` produces complete lineage documentation
- [ ] All models run successfully against `just-data-gci-dev`

---

### CPIO-010: Build Airflow DAG to orchestrate the full pipeline

| Field | Value |
|-------|-------|
| **Phase** | Phase 3 (Automation) |
| **Story Points** | 8 |
| **Priority** | Medium |
| **Dependencies** | CPIO-008, CPIO-009, CPIO-001, CPIO-002 |

**As a** data engineer,
**I want** an Airflow DAG that orchestrates the entire daily pipeline — from Google Sheet ingestion through Python evaluation to dbt transformation,
**so that** campaign results are refreshed automatically each morning without manual intervention.

#### Acceptance Criteria

- [ ] DAG schedule: daily at 06:00 UTC
- [ ] Task sequence:
  1. Sensor: confirm Google Sheet ingestion (from CPIO-008) has completed
  2. Operator: trigger Python evaluation scripts (Customer/City/Partner Lookalike) via Cloud Run or local execution, parameterised with active campaigns from `raw_campaign_details`
  3. Sensor: wait for evaluation scripts to complete and write to BigQuery
  4. Operator: `dbt run` on Silver and Gold models
  5. Operator: `dbt test` — validate Gold tables
  6. Branching: if dbt tests fail or hard rejection triggered, send Slack alert but do not block dashboard refresh for other campaigns
- [ ] Retries: 2 retries with exponential backoff for transient failures
- [ ] Slack alerts on: pipeline failure, dead-letter rows, hard rejection
- [ ] DAG viewable and testable in local Airflow (via `docker-compose` or standalone)
- [ ] Idempotent: re-running the DAG for the same date does not create duplicate results

---

## Story Map Summary

```
Phase 1: Accuracy Benchmarking (Apr 1–15)
├── CPIO-001  Refactor Customer Lookalike to local Python     [5 pts]
├── CPIO-002  Refactor Partner Lookalike to local Python      [5 pts]
├── CPIO-003  A/A test framework — Customer Lookalike         [8 pts]
├── CPIO-004  A/A test framework — City Lookalike             [8 pts]
└── CPIO-005  RCT Calibration — bias gap quantification       [8 pts]

Phase 2: Matching Optimization (Apr 15–30)
├── CPIO-006  Geographical constraints — Customer Lookalike   [5 pts]
└── CPIO-007  Cuisine/density/geo — Partner Lookalike         [8 pts]

Phase 3: Automation (May onward)
├── CPIO-008  Google Sheet ingestion to BigQuery              [3 pts]
├── CPIO-009  dbt transformation layers (Bronze/Silver/Gold)  [13 pts]
└── CPIO-010  Airflow DAG orchestration                       [8 pts]
                                                        Total: 71 pts
```

### Dependency Graph

```
CPIO-001 ──┬── CPIO-003 ──┬── CPIO-005 ──┬── CPIO-006
            │              │              │
CPIO-002 ──┤  CPIO-004 ───┘              ├── CPIO-007
            │                             │
            └─────────────────────────────┼── CPIO-009 ─── CPIO-010
                                          │
                              CPIO-008 ───┘
```
