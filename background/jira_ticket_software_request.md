# Software Installation / Admin Rights Request

**Project:** Targeted Value CPiO Alignment — Automated Campaign Evaluation Pipeline
**Type:** Task
**Priority:** High
**Labels:** `infrastructure`, `dev-environment`, `data-engineering`

---

## Summary

Request for local development tooling to build the automated campaign evaluation pipeline that will replace manual Colab-based analysis across DE, NL, and UK markets.

---

## Business Justification

### Problem

Campaign incrementality measurement is currently performed manually using Google Colab notebooks, scattered Google Sheets, and market-specific ad hoc processes. This creates:

- **Measurement risk:** Synthetic control methods (City Lookalike, Customer Lookalike) have demonstrated bias gaps of up to 94% vs. ground truth A/B tests, and there is no automated validation in place.
- **Operational inefficiency:** Each campaign evaluation cycle requires a data scientist to manually run notebooks, copy data between systems, and update spreadsheets — taking days per campaign across 3 markets.
- **No single source of truth:** Results are spread across local folders, individual Colab environments, and disconnected Tableau/Looker dashboards.

### What we are building

A three-phase automated pipeline (see project overview) that:

1. **Phase 1 — Accuracy Benchmarking:** Runs A/A tests and historical simulations to quantify the bias in each synthetic control method. Requires local Python development to refactor and validate the existing Colab scripts.
2. **Phase 2 — Matching Optimization:** Improves KNN and BSTS matching algorithms with geographical, density, and cuisine constraints. Requires iterative local development with BigQuery access.
3. **Phase 3 — Automation:** Productionises the pipeline using Airflow, dbt, and Looker with automated validation scorecards.

### Why local development (not Colab)

- Colab is unsuitable for version-controlled, collaborative, production-grade development.
- The existing scripts already have a "running locally" code path — this project formalises that.
- Local development enables proper Git workflows, code review, testing, and CI/CD — required for production deployment.
- Docker containerisation (for Cloud Run / Vertex AI deployment) requires a local build environment.

---

## Software Required

### 1. IDE & Editor

| Software | Version | Purpose |
|----------|---------|---------|
| **Visual Studio Code** | Latest stable | Primary IDE for Python, SQL (dbt), YAML (Airflow DAGs), and LookML development. Required extensions: Python, Jupyter, dbt Power User, BigQuery Runner, Docker, GitLens. |

### 2. Python Runtime & Package Management

| Software | Version | Purpose |
|----------|---------|---------|
| **Python** | 3.10+ (recommend 3.11) | Runtime for all evaluation scripts. The existing codebase uses pandas, numpy, scikit-learn, and google-cloud-bigquery. |
| **pip** | Latest (bundled with Python) | Package installer. |
| **venv** (built-in) | — | Virtual environment isolation per project. |

**Required Python packages** (installed via pip into a virtual environment):

| Package | Purpose | Used in |
|---------|---------|---------|
| `pandas` | Data manipulation and analysis | Customer & Partner Lookalike scripts |
| `numpy` | Numerical computation | Customer & Partner Lookalike scripts |
| `scikit-learn` | KNN matching (`NearestNeighbors`) and feature scaling (`MinMaxScaler`) | Core matching algorithms |
| `google-cloud-bigquery` | BigQuery client — read/write campaign data | All scripts; connects to `just-data-warehouse` |
| `google-auth` | GCP authentication (replaces `google.colab.auth`) | All scripts |
| `db-dtypes` | BigQuery data type support for pandas | BigQuery result handling |
| `pyarrow` | Efficient BigQuery data transfer | BigQuery pandas integration |
| `scipy` | Statistical testing (significance, p-values) | Uplift and incrementality calculations |
| `matplotlib` / `seaborn` | Visualisation for validation scorecards and bias gap analysis | A/A test analysis, reporting |
| `jupyter` / `jupyterlab` | Notebook interface for exploratory analysis | Prototyping, interactive data exploration |
| `dbt-bigquery` | dbt adapter for BigQuery — builds the Silver/Gold transformation layers | Phase 3 pipeline (medallion architecture) |
| `apache-airflow` | Local Airflow development and DAG testing | Phase 3 pipeline orchestration |
| `pyfixest` / `causalimpact` | BSTS (Bayesian Structural Time Series) for City Lookalike | City Lookalike evaluation |
| `pytest` | Unit and integration testing | All phases |

### 3. Google Cloud SDK & CLI

| Software | Version | Purpose |
|----------|---------|---------|
| **Google Cloud SDK** (`gcloud` CLI) | Latest | Authentication (`gcloud auth application-default login`), project switching, and BigQuery CLI access. Already used in the existing Partner Lookalike script. |
| **bq** CLI (bundled with gcloud) | — | Ad hoc BigQuery queries and table inspection. |

**GCP project access required:** `just-data-gci-dev` (development) — read/write to `just-data-warehouse.crm_adhoc.*` and `just-data-warehouse.customer_intelligence.*` datasets.

### 4. Containerisation & Deployment

| Software | Version | Purpose |
|----------|---------|---------|
| **Docker Desktop** | Latest stable | Containerise Python evaluation scripts for deployment to Google Cloud Run / Vertex AI. Required for Phase 3 productionisation. |

### 5. Version Control

| Software | Version | Purpose |
|----------|---------|---------|
| **Git** | Latest | Version control. The project is hosted in GitBox. |

### 6. Terminal / Shell

| Software | Version | Purpose |
|----------|---------|---------|
| **zsh** (macOS default) | Built-in | Shell for running CLI tools. No additional installation needed. |
| **Homebrew** (macOS) | Latest | Package manager for installing Python, gcloud SDK, and Docker if not available through corporate software distribution. |

---

## Permissions Required

| Permission | Scope | Reason |
|------------|-------|--------|
| Local admin / install rights | Developer workstation | Install Python, VS Code, Docker, gcloud SDK |
| GCP IAM: BigQuery Data Viewer | `just-data-gci-dev` | Read campaign treatment/control tables |
| GCP IAM: BigQuery Data Editor | `just-data-gci-dev` | Write evaluation outputs and audience tables |
| GCP IAM: BigQuery Job User | `just-data-gci-dev` | Execute queries |
| GCP IAM: Cloud Run Developer | `just-data-gci-dev` | Deploy containerised evaluation scripts (Phase 3) |
| Docker Hub access | Public registry | Pull base Python images for containerisation |

---

## Use Cases

### UC-1: A/A Test Development (Phase 1)
> As a data scientist, I need to run historical simulations locally against BigQuery to validate that our synthetic control methods show zero bias during non-campaign periods. This requires Python + scikit-learn + google-cloud-bigquery running in VS Code.

### UC-2: Matching Algorithm Optimization (Phase 2)
> As a data scientist, I need to iteratively modify the KNN matching parameters in the Customer and Partner Lookalike scripts, run them against BigQuery, and compare results to A/B test ground truth. This requires a local Python environment with fast iteration cycles that Colab cannot provide.

### UC-3: dbt Model Development (Phase 3)
> As a data engineer, I need to develop and test dbt models locally (Bronze/Silver/Gold layers) that transform raw campaign data into validated, dashboard-ready aggregates. This requires dbt-bigquery and VS Code with the dbt Power User extension.

### UC-4: Airflow DAG Development (Phase 3)
> As a data engineer, I need to develop and test Airflow DAGs locally that orchestrate the full pipeline: Google Sheet ingestion, Python evaluation triggers, dbt runs, and Slack alerting. This requires a local Airflow installation.

### UC-5: Containerisation for Production (Phase 3)
> As a data engineer, I need to package the validated Python scripts into Docker containers for deployment to Cloud Run / Vertex AI. This requires Docker Desktop.

---

## Acceptance Criteria

- [ ] VS Code installed with Python, Jupyter, dbt, and Docker extensions
- [ ] Python 3.10+ installed and accessible from terminal
- [ ] Virtual environment created with all listed packages installable via `pip install -r requirements.txt`
- [ ] `gcloud auth application-default login` succeeds and BigQuery queries execute against `just-data-gci-dev`
- [ ] Docker Desktop installed and able to build/run containers
- [ ] Git configured and able to push to GitBox
- [ ] Existing Customer Lookalike script runs successfully from VS Code against BigQuery (replacing the Colab auth path)

---

## Timeline & Impact

- **Blocking:** All three project phases depend on this local development setup. Phase 1 (Accuracy Benchmarking) has a target start of Apr 8, 2026.
- **Risk if delayed:** Continued reliance on manual Colab processes, which have already produced measurement errors of up to 94% bias in campaign evaluation — directly impacting CPiO reporting accuracy and marketing budget allocation decisions across DE, NL, and UK.
