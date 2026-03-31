Here is a comprehensive architecture document and implementation plan for your automated A/B testing and campaign evaluation pipeline.
This design leverages your existing Google Cloud and modern data stack (Cloud Composer/Airflow, BigQuery, dbt, and Looker) to create a highly maintainable, fault-tolerant system.
Architecture & Implementation Plan: Automated Campaign Evaluation
1. Executive Summary
The goal is to transition from a decentralized, highly manual process (relying on local Colab notebooks and scattered Google Sheets) into a robust, automated daily batch pipeline. This pipeline will centralize A/B testing and synthetic control outputs into BigQuery, transform the data using dbt to apply standardized (yet flexible) business logic, and serve the results via Looker for executive reporting and deep-dive analytics.
2. Target Architecture
A. Orchestration Layer (Google Cloud Composer / Airflow)
Airflow will act as the "brain" of the entire operation. It will run on a daily schedule (e.g., 6:00 AM UTC) to ensure data is fresh for morning reporting.
Tasks: Triggering Python scripts, polling for completion, triggering dbt models, and running data quality checks.
B. Ingestion & Compute (Python & Manual Inputs)
Productionizing Colab: The current Colab notebooks (for synthetic controls and look-alikes) will be refactored into modular Python scripts, packaged into Docker containers, and run via Google Cloud Run Jobs or Vertex AI Custom Training Jobs. Airflow will trigger these containers, pass dynamic parameters (like execution_date), and wait for them to write their output directly to BigQuery raw tables.
Google Sheets Ingestion: The Campaign_Details sheet will be ingested daily into a BigQuery raw dataset. This can be done natively via BigQuery External Connections (Federated Queries) or a lightweight Airflow PythonOperator.
C. Storage & Transformation (BigQuery + dbt)
We will implement a standard Medallion architecture managed by dbt (data build tool):
Bronze Layer (Raw): Exact 1:1 copies of the raw tables (crm_control_group_automation, Python outputs, and the raw Google Sheet data).
Silver Layer (Cleansing & Fault Tolerance): * Fault-Tolerant Parsing: dbt will parse the Campaign_Details data. We will implement strict SQL logic: COALESCE(vouchername, voucherdescription). If both are null, or if campaign_name is missing, dbt will filter these rows out into a campaign_details_dead_letter table and trigger a Slack alert via Airflow. The main pipeline will continue running using only the valid rows.
Regex/String Extraction: Extracting metadata from the concatenated voucherdescription string (e.g., extracting "FR" or "CRM" tags) will happen here.
Gold Layer (Business Logic & Aggregation): * Joins the cleaned campaign inputs with the control/treatment data.
Calculates statistical significance (p-values), incremental orders, ROI, and CPiO.
Handling Multiple Definitions: Because different teams may view logic differently, dbt will calculate explicitly named columns (e.g., incr_orders_standard, incr_orders_adjusted_v2). This allows teams to have their own distinct metrics without arguing over a single "true" column, while forcing everyone to use the central dbt repository to define them.
D. Presentation Layer (Looker)
Looker is the ideal choice here because of its strong semantic layer (LookML).
Integration: LookML will map directly to the dbt Gold tables.
Deep Dives: Users can drill down by country, frequency bucket, or base segment natively in Looker without requiring custom SQL.
Alerting: Looker can send scheduled reports or threshold alerts (e.g., "Campaign X reached statistical significance").
3. Addressing Your Specific Challenges
Fault Tolerance for Manual Inputs: By using a "Dead-Letter Queue" pattern in dbt, a campaign manager forgetting to input a voucher name won't crash the pipeline. The bad row is simply quarantined, an alert is sent to the responsible team, and the rest of the dashboard updates successfully.
Scattered Business Logic: Moving calculation logic out of Tableau/Looker and into dbt ensures version control. Any changes to how "Synthetic Control Scaling" is calculated must go through a GitHub Pull Request, providing an audit trail and forcing team alignment.
Future-Proofing & Evolution: Because the Python models (formerly Colab) are decoupled from the SQL transformations, Data Science can update the synthetic control Docker image to a better algorithm (e.g., v2.0) without breaking the downstream BI dashboards, as long as the output schema matches the data contract.
4. Implementation Plan & Roadmap
Phase 1: Foundation & Ingestion (Weeks 1-3)
Goal: Get all raw data flowing reliably into BigQuery without manual intervention.
Tasks:
Set up the Google Cloud Composer (Airflow) environment.
Create a robust ingestion job for the Campaign_Details Google Sheet.
Data Science Task: Refactor the primary Colab notebook into a Python script, containerize it, and deploy it to Cloud Run/Vertex AI. Build the Airflow DAG to trigger it.
Phase 2: Transformation & Fault Tolerance (Weeks 4-6)
Goal: Build the dbt project and implement the "Silver" and "Gold" layers.
Tasks:
Connect dbt to BigQuery.
Build the stg_campaign_details model with the fault-tolerance logic (quarantining rows missing required fields).
Build the primary fct_campaign_results table joining the Treatment/Control splits with the campaign metadata.
Define the various business logic metrics (Uplift, CPiO, Incremental Orders).
Implement dbt tests (e.g., not_null, unique) on the Gold tables.
Phase 3: Presentation & Pilot Rollout (Weeks 7-9)
Goal: Connect the BI layer and validate the numbers against the old manual process.
Tasks:
Connect Looker to the Gold dataset and define the LookML project.
Build the primary "Campaign Evaluation Dashboard" featuring the Executive Overview and Deep-Dive tabs.
Pilot: Run one specific historical campaign (e.g., a recent "Smart Growth Wave") through the new pipeline and compare the automated Looker output against the manual Campaign Results_old.csv. Address any discrepancies.
Phase 4: CI/CD, Alerting, & Handoff (Weeks 10-12)
Goal: Make the system bulletproof and transition ownership.
Tasks:
Set up Slack alerting in Airflow for pipeline failures or quarantined manual inputs.
Document the entire lineage in dbt Docs.
Host a workshop with Campaign Managers to explain the new automated SLA (e.g., "Input details by 5 PM, see results tomorrow at 8 AM").
Questions Before Moving Forward:
Does this architecture align with the technical capabilities of your current engineering and analytics teams? If you are satisfied with this blueprint, we can begin detailing the specific Airflow DAG structure or writing the dbt SQL logic for the fault-tolerant staging layer.
