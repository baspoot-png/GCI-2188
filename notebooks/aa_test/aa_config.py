# ============================================================
# aa_config.py — Shared A/A Test Configuration
# ============================================================
#
# Upload this file to Colab alongside any technique notebook:
#   from google.colab import files
#   files.upload()  # select aa_config.py
#   import aa_config as cfg
#
# Or mount Google Drive:
#   from google.colab import drive
#   drive.mount('/content/drive')
#   import sys
#   sys.path.insert(0, '/content/drive/MyDrive/aa_testing/')
#   import aa_config as cfg
# ============================================================

# --- GCP ---
PROJECT_ID = 'just-data-gci-dev'

# --- Markets ---
COUNTRIES = ['DE', 'NL']

# --- Country code mapping ---
# dim_country uses 'DEL' for Germany (logistics), not 'DE'.
# All other markets use a single code.
# Use country_codes(country) in SQL WHERE clauses.
COUNTRY_CODES = {
    'DE': ['DE', 'DEL'],
}

def country_codes_sql(country):
    """Return SQL IN clause for a market's country codes."""
    codes = COUNTRY_CODES.get(country, [country])
    return ', '.join(f"'{c}'" for c in codes)

# --- Customer-level A/A settings ---
N_SEEDS = 5
TREATMENT_SHARE = 0.5
MAX_AUDIENCE_SIZE = 200_000  # Random sample cap per window.
                             # Production campaigns are typically 100K-1.2M.
                             # 200K gives realistic scale while keeping
                             # BQ upload + exact match fast (~2 min per run).

# --- Bias thresholds ---
BIAS_THRESHOLD_HARD = 0.05   # |uplift| > 5% = HARD FAIL
BIAS_THRESHOLD_WARN = 0.02   # |uplift| > 2% = WARNING

# --- Campaign name prefixes ---
AA_PREFIX_V3 = 'AA_V3'
AA_PREFIX_V2 = 'AA_V2'
AA_PREFIX_CITY = 'AA_CITY'

# --- Pre-campaign A/A windows ---
# Generated from all campaigns in campaign_data.csv + Campaign Results.tsv.
# Each A/A window = same-duration period BEFORE the real campaign started.
# The "post" period = the real campaign period itself.
#
# Windows are built dynamically from CAMPAIGN_DATA_PATH at import time.
# Upload campaign_data.csv alongside aa_config.py to Colab.
#
# Overlapping background campaigns are intentional — they reflect the
# same environment the production evaluation operates in.
# The A/A test measures methodology bias, not environment purity.

import os as _os
from datetime import datetime as _dt, timedelta as _td

CAMPAIGN_DATA_PATH = 'campaign_data.csv'  # tab-separated, same dir as this file

# --- Window filters ---
MIN_WINDOW_DAYS = 7     # skip campaigns shorter than 7 days
MAX_WINDOW_DAYS = 45    # skip abnormally long campaigns (gift cards, Rewe)
MAX_WINDOWS_PER_COUNTRY = 10  # cap per market for manageable runtime
                              # (~10 windows x 5 seeds = 50 runs per country)


def _build_time_windows(csv_path):
    """Build pre-campaign A/A windows from campaign calendar data.

    Filters:
      - Duration between MIN_WINDOW_DAYS and MAX_WINDOW_DAYS
      - At most MAX_WINDOWS_PER_COUNTRY per market (evenly spread across time)
      - Deduplicates overlapping windows (keeps the one with the most
        common campaign duration for that market)
    """
    windows = {}
    if not _os.path.exists(csv_path):
        print(f'WARNING: {csv_path} not found — TIME_WINDOWS will be empty.')
        print('Upload campaign_data.csv alongside aa_config.py.')
        return windows
    import csv
    with open(csv_path) as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            country = row['country']
            name = row['campaign_name']
            try:
                c_start = _dt.strptime(row['earliest_start'], '%Y-%m-%d')
                c_end = _dt.strptime(row['campaign_end'], '%Y-%m-%d')
            except (ValueError, KeyError):
                continue

            days = (c_end - c_start).days
            if days < MIN_WINDOW_DAYS or days > MAX_WINDOW_DAYS:
                continue

            aa_end = c_start - _td(days=1)
            aa_start = aa_end - _td(days=days)

            if country not in windows:
                windows[country] = []
            windows[country].append({
                'start': aa_start.strftime('%Y-%m-%d'),
                'end': aa_end.strftime('%Y-%m-%d'),
                'post_start': c_start.strftime('%Y-%m-%d'),
                'post_end': c_end.strftime('%Y-%m-%d'),
                'days': days,
                'label': name,
            })

    # Per country: sort by date, deduplicate overlapping windows,
    # then evenly sample up to MAX_WINDOWS_PER_COUNTRY
    for country in windows:
        ws = sorted(windows[country], key=lambda w: w['start'])

        # Deduplicate: if two windows overlap >50%, keep the later one
        deduped = []
        for w in ws:
            w_start = _dt.strptime(w['start'], '%Y-%m-%d')
            w_end = _dt.strptime(w['end'], '%Y-%m-%d')
            skip = False
            for prev in deduped:
                p_start = _dt.strptime(prev['start'], '%Y-%m-%d')
                p_end = _dt.strptime(prev['end'], '%Y-%m-%d')
                overlap_start = max(w_start, p_start)
                overlap_end = min(w_end, p_end)
                overlap_days = max((overlap_end - overlap_start).days, 0)
                w_days = (w_end - w_start).days
                if w_days > 0 and overlap_days / w_days > 0.5:
                    skip = True
                    break
            if not skip:
                deduped.append(w)

        # Evenly sample if more than max
        if len(deduped) > MAX_WINDOWS_PER_COUNTRY:
            step = len(deduped) / MAX_WINDOWS_PER_COUNTRY
            indices = [int(i * step) for i in range(MAX_WINDOWS_PER_COUNTRY)]
            deduped = [deduped[i] for i in indices]

        windows[country] = deduped

    total = sum(len(v) for v in windows.values())
    print(f'Loaded {total} pre-campaign windows across '
          f'{len(windows)} markets from {csv_path}')
    print(f'  (filtered: {MIN_WINDOW_DAYS}-{MAX_WINDOW_DAYS} day campaigns, '
          f'max {MAX_WINDOWS_PER_COUNTRY} per country)')
    for c in sorted(windows):
        print(f'  {c}: {len(windows[c])} windows')
    return windows

TIME_WINDOWS = _build_time_windows(CAMPAIGN_DATA_PATH)

# --- V3 matching conditions ---
LOOK_ALIKE_CONDITIONS_V3 = [
    'country', 'optin', 'campaign_start_date',
    'L14D_orders', 'L30D_orders', 'L90D_orders', 'L365D_orders',
]

# --- V2 matching conditions ---
LOOK_ALIKE_CONDITIONS_V2 = [
    'country', 'city_type', 'optin', 'campaign_start_date',
    'L14D_orders', 'L30D_orders', 'L90D_orders', 'L365D_orders',
    'L365D_AOV_cat',
]

# --- City Lookalike config ---
CITY_TREATMENT_CANDIDATES = {
    'DE': ['Dortmund', 'Dresden', 'Essen'],
    'NL': ['Amsterdam', 'Eindhoven', 'Nijmegen'],
}
CITY_KNN_NEIGHBORS = 25  # Reduce from 25 to prevent OOM on Colab
CITY_CORRELATION_THRESHOLD = 0.8

# --- BQ tables ---
AA_AUDIENCE_TABLE = (
    'just-data-warehouse.customer_intelligence'
    '.customer_lookalike_aa_audience'
)
AA_RESULTS_TABLE = (
    'just-data-warehouse.customer_intelligence'
    '.aa_test_results'
)

# --- Segments (lowercase, matching fact_segmentation_scv_key) ---
BASE_SEGMENTS = [
    'new', 'reactivated', 'early', 'engaged',
    'lapsing', 'dormant', 'prospect', 'churned', 'unknown',
]

# ============================================================
# Flash Sales A/A Configuration
# ============================================================

FLASH_SALES_TREATMENT_CITIES = {
    'DE': ['Dortmund', 'Dresden', 'Essen'],
}

# Hour windows (Flash Sales run during specific time slots)
FLASH_SALES_HOUR_WINDOWS = {
    'dinner': (16, 22),   # 16:00-21:59
    'lunch':  (11, 14),   # 11:00-13:59
}
FLASH_SALES_DEFAULT_WINDOW = 'dinner'

# A/A test parameters
FLASH_SALES_POST_DAYS = 2          # typical Flash Sales duration
FLASH_SALES_PRE_WEEKS = 6          # 6 weeks pre-period at hourly resolution
FLASH_SALES_KNN_NEIGHBORS = 25
FLASH_SALES_CORRELATION_THRESHOLD = 0.8

# Technique name for BQ results table
FLASH_SALES_TECHNIQUE = 'FLASH_SALES_BSTS'

# German public holidays to exclude from A/A windows (2025)
FLASH_SALES_HOLIDAY_EXCLUSIONS = [
    # Christmas / NYE block
    ('2024-12-20', '2025-01-05'),
    # Easter 2025
    ('2025-04-18', '2025-04-21'),
    # Labour Day
    ('2025-05-01', '2025-05-01'),
    # Ascension Day
    ('2025-05-29', '2025-05-29'),
    # Whit Monday
    ('2025-06-09', '2025-06-09'),
    # German Unity Day
    ('2025-10-03', '2025-10-03'),
    # Christmas / NYE block 2025
    ('2025-12-20', '2026-01-05'),
]


def _build_flash_sales_aa_windows(
    n_windows=12,
    post_days=FLASH_SALES_POST_DAYS,
    pre_weeks=FLASH_SALES_PRE_WEEKS,
    holiday_exclusions=FLASH_SALES_HOLIDAY_EXCLUSIONS,
    min_gap_days=21,
):
    """Generate non-overlapping fake Flash Sales A/A windows.

    Picks dates evenly spread across Jan-Dec 2025, avoiding holidays
    and ensuring at least min_gap_days between windows.
    """
    from datetime import date, timedelta

    range_start = date(2025, 1, 15)
    range_end = date(2025, 11, 30)

    # Parse holiday ranges
    holidays = []
    for h_start, h_end in holiday_exclusions:
        holidays.append((
            _dt.strptime(h_start, '%Y-%m-%d').date(),
            _dt.strptime(h_end, '%Y-%m-%d').date(),
        ))

    def in_holiday(d):
        for h_start, h_end in holidays:
            if h_start <= d <= h_end:
                return True
        return False

    def pre_period_clean(post_start):
        """Check that the 6-week pre-period has no holidays."""
        pre_start = post_start - timedelta(days=pre_weeks * 7)
        pre_end = post_start - timedelta(days=1)
        d = pre_start
        while d <= pre_end:
            if in_holiday(d):
                return False
            d += timedelta(days=1)
        return True

    # Generate candidate dates (every day in range)
    candidates = []
    d = range_start
    while d <= range_end:
        post_end = d + timedelta(days=post_days - 1)
        if (not in_holiday(d) and not in_holiday(post_end)
                and pre_period_clean(d)):
            candidates.append(d)
        d += timedelta(days=1)

    if not candidates:
        print('WARNING: No valid Flash Sales A/A dates found.')
        return []

    # Evenly sample n_windows dates with minimum gap
    selected = []
    step = max(len(candidates) // n_windows, 1)
    for i in range(0, len(candidates), step):
        candidate = candidates[i]
        if selected and (candidate - selected[-1]).days < min_gap_days:
            continue
        selected.append(candidate)
        if len(selected) >= n_windows:
            break

    windows = []
    for post_start in selected:
        post_end = post_start + timedelta(days=post_days - 1)
        pre_end = post_start - timedelta(days=1)
        pre_start = post_start - timedelta(days=pre_weeks * 7)
        windows.append({
            'pre_start': pre_start.strftime('%Y-%m-%d'),
            'pre_end': pre_end.strftime('%Y-%m-%d'),
            'post_start': post_start.strftime('%Y-%m-%d'),
            'post_end': post_end.strftime('%Y-%m-%d'),
            'days': post_days,
        })

    print(f'Generated {len(windows)} Flash Sales A/A windows '
          f'({post_days}-day post, {pre_weeks}-week pre)')
    for w in windows:
        print(f'  {w["post_start"]} to {w["post_end"]} '
              f'(pre: {w["pre_start"]} to {w["pre_end"]})')
    return windows

FLASH_SALES_AA_WINDOWS = _build_flash_sales_aa_windows()
