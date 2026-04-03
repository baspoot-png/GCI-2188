# ============================================================
# flash_sales_utils.py — Shared functions for Flash Sales
# A/A testing and corrected evaluation
# ============================================================
#
# Usage (Colab):
#   from google.colab import drive
#   drive.mount('/content/drive')
#   import sys
#   sys.path.insert(0, '/content/drive/MyDrive/aa_test')
#   import flash_sales_utils as fsu
# ============================================================

import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import gc


# ----------------------------------------------------------
# 1. City Features (MAVERICK)
# ----------------------------------------------------------

def get_city_features(client, country, ref_date):
    """Query city-level features for MAVERICK KNN matching.

    Replicates the MAVERICK control city finder logic:
    population, order volume, active customers, partner supply.
    """
    query = f"""
    WITH active AS (
        SELECT dr.city, SUM(fo.nroforders) AS total_ov,
            COUNT(DISTINCT fo.customerid) AS unique_customers
        FROM `just-data-warehouse.dwh.fact_order` AS fo
        INNER JOIN `just-data-warehouse.dwh.dim_restaurant` AS dr ON fo.restaurantid=dr.restaurantid
        WHERE dr.country='{country}'
          AND DATE(fo.orderdatetime) >= DATE_SUB(DATE('{ref_date}'), INTERVAL 90 DAY)
          AND DATE(fo.orderdatetime) < DATE('{ref_date}')
        GROUP BY 1
    ),
    population AS (
        SELECT dz.city, SUM(pop_addressable) AS pop_15plus
        FROM `just-data-warehouse.cma_mbr_population.mbr_population` AS pop
        INNER JOIN `just-data-warehouse.dwh.dim_zipcode` AS dz ON pop.tableau_map_zipcode=dz.zipcode
        WHERE pop.country='{country}' AND dz.country='{country}'
          AND year=(SELECT MAX(year) FROM `just-data-warehouse.cma_mbr_population.mbr_population`)
        GROUP BY 1
    ),
    supply AS (
        SELECT dr.city, COUNT(dr.restaurantid) AS online_partners,
            SUM(CASE WHEN dr.chain='(Not available)' THEN 1 ELSE 0 END) AS smb_partners,
            SUM(CASE WHEN dr.chain!='(Not available)' THEN 1 ELSE 0 END) AS chain_partners
        FROM `just-data-warehouse.dwh.dim_restaurant` AS dr
        WHERE dr.country='{country}'
          AND dr.onlinestatus IN ('Online (temporarily closed)','Online (with Menu)')
        GROUP BY 1
    )
    SELECT a.city, COALESCE(p.pop_15plus,0) AS pop_15plus,
        a.total_ov, a.unique_customers,
        COALESCE(s.online_partners,0) AS online_partners,
        COALESCE(s.smb_partners,0) AS smb_partners,
        COALESCE(s.chain_partners,0) AS chain_partners,
        SAFE_DIVIDE(a.total_ov, p.pop_15plus) AS ov_per_capita
    FROM active a
    LEFT JOIN population p ON a.city=p.city
    LEFT JOIN supply s ON a.city=s.city
    WHERE a.total_ov > 0
    """
    return client.query(query).to_dataframe()


# ----------------------------------------------------------
# 2. Control City Selection (KNN)
# ----------------------------------------------------------

def find_control_cities(df_cities, treatment_city, n_neighbors=25):
    """Find closest cities via KNN on city features."""
    if treatment_city not in df_cities['city'].values:
        print(f'  WARNING: {treatment_city} not found in city features')
        return []
    num_cols = df_cities.select_dtypes(include=['number']).columns.tolist()
    scaler = StandardScaler()
    scaled = scaler.fit_transform(df_cities[num_cols].fillna(0))
    target_idx = df_cities[df_cities['city'] == treatment_city].index[0]
    target_pos = list(df_cities.index).index(target_idx)
    n = min(n_neighbors + 1, len(df_cities))
    knn = NearestNeighbors(n_neighbors=n, algorithm='auto')
    knn.fit(scaled)
    _, indices = knn.kneighbors(scaled[target_pos].reshape(1, -1))
    return [df_cities.iloc[i]['city'] for i in indices.flatten()
            if df_cities.iloc[i]['city'] != treatment_city][:n_neighbors]


# ----------------------------------------------------------
# 3. Hourly Order Data
# ----------------------------------------------------------

def get_hourly_orders(client, country, cities, start, end,
                      hour_start=16, hour_end=22):
    """Query hourly order totals per city, filtered to Flash Sales hours.

    Returns one row per city per hour within [hour_start, hour_end).
    """
    city_list = ','.join([f"'{c}'" for c in cities])
    query = f"""
    SELECT
        TIMESTAMP_TRUNC(fo.orderdatetime, HOUR) AS order_hour,
        dr.city,
        SUM(fo.nroforders) AS totalorders
    FROM `just-data-warehouse.dwh.fact_order` AS fo
    INNER JOIN `just-data-warehouse.dwh.dim_restaurant` AS dr
        ON fo.restaurantid = dr.restaurantid
    WHERE dr.country = '{country}'
        AND dr.city IN ({city_list})
        AND DATE(fo.orderdatetime) >= DATE('{start}')
        AND DATE(fo.orderdatetime) <= DATE('{end}')
        AND EXTRACT(HOUR FROM fo.orderdatetime) >= {hour_start}
        AND EXTRACT(HOUR FROM fo.orderdatetime) < {hour_end}
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    return client.query(query).to_dataframe()


def get_daily_orders(client, country, cities, start, end):
    """Query daily order totals per city (no hour filter)."""
    city_list = ','.join([f"'{c}'" for c in cities])
    query = f"""
    SELECT DATE(fo.orderdatetime) AS orderdate, dr.city,
        SUM(fo.nroforders) AS totalorders
    FROM `just-data-warehouse.dwh.fact_order` AS fo
    INNER JOIN `just-data-warehouse.dwh.dim_restaurant` AS dr
        ON fo.restaurantid = dr.restaurantid
    WHERE dr.country = '{country}'
        AND dr.city IN ({city_list})
        AND DATE(fo.orderdatetime) >= DATE('{start}')
        AND DATE(fo.orderdatetime) <= DATE('{end}')
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    return client.query(query).to_dataframe()


# ----------------------------------------------------------
# 4. Correlation Filter
# ----------------------------------------------------------

def apply_correlation_filter(df_orders, treatment_city, controls,
                             threshold=0.8, time_col='order_hour'):
    """Filter control cities by weekly order correlation with treatment.

    Works with both hourly and daily data. Hourly data is aggregated
    to daily, then to weekly before computing correlation.
    """
    all_cities = [treatment_city] + controls
    pivot = df_orders[df_orders['city'].isin(all_cities)].pivot_table(
        index=time_col, columns='city', values='totalorders'
    ).fillna(0)
    pivot.index = pd.to_datetime(pivot.index)

    # Aggregate to weekly regardless of input granularity
    weekly = pivot.resample('W-MON').sum()

    if treatment_city not in weekly.columns:
        return []
    corr = weekly.corr()[treatment_city]
    passed = corr[(corr >= threshold) & (corr.index != treatment_city)]
    print(f'  Correlation: {len(passed)}/{len(controls)} pass '
          f'(>={threshold})')
    return passed.index.tolist()


# ----------------------------------------------------------
# 5. Contamination Check
# ----------------------------------------------------------

def check_control_contamination(client, country, cities, start, end):
    """Check for active OMT campaigns in control cities during a period.

    Returns DataFrame of (city, campaign_id) pairs found.
    """
    city_list = ','.join([f"'{c}'" for c in cities])
    query = f"""
    SELECT DISTINCT dr.city, dro.offer_source_campaign_id
    FROM `just-data-warehouse.dwh.fact_offer` AS fof
    INNER JOIN `just-data-warehouse.dwh.dim_restaurant_offers` AS dro
        ON fof.offerid = dro.offerid AND fof.restaurantid = dro.restaurantid
    INNER JOIN `just-data-warehouse.dwh.dim_restaurant` AS dr
        ON fof.restaurantid = dr.restaurantid
    WHERE dr.country = '{country}'
        AND dr.city IN ({city_list})
        AND DATE(fof.orderdatetimeutc) >= DATE('{start}')
        AND DATE(fof.orderdatetimeutc) <= DATE('{end}')
        AND dro.offer_source_campaign_id IS NOT NULL
    """
    df = client.query(query).to_dataframe()
    if len(df) > 0:
        n_cities = df['city'].nunique()
        print(f'  WARNING: {n_cities} control cities have active campaigns:')
        for _, row in df.drop_duplicates('city').iterrows():
            print(f'    {row["city"]}: {row["offer_source_campaign_id"]}')
    else:
        print('  No campaign contamination detected in control cities.')
    return df


# ----------------------------------------------------------
# 6. Hourly Data Flattening
# ----------------------------------------------------------

def flatten_hourly_to_sequential(pivot_df):
    """Convert hourly pivot table to sequential hourly DatetimeIndex.

    CausalImpact expects a regularly-spaced time series with a
    DatetimeIndex. Hourly data within Flash Sales hours (e.g.,
    16:00-21:00) has overnight gaps. This function replaces the
    original timestamps with a synthetic contiguous hourly index
    starting from an arbitrary date, preserving the order.
    """
    df = pivot_df.copy()
    df.index = pd.date_range(
        start='2020-01-01', periods=len(df), freq='h')
    return df


def build_hourly_pivot(df_orders, treatment_city, controls,
                       pre_start, pre_end, post_start, post_end):
    """Build a pivoted hourly time series for CausalImpact.

    Returns (pivot_df, pre_period, post_period) where periods
    are integer index ranges for the flattened sequential series.
    """
    all_cities = [treatment_city] + controls
    df = df_orders[df_orders['city'].isin(all_cities)].copy()
    df['order_hour'] = pd.to_datetime(df['order_hour'])

    pivot = df.pivot_table(
        index='order_hour', columns='city', values='totalorders'
    ).fillna(0).sort_index()

    # Reorder columns: treatment first, then controls
    cols = [treatment_city] + [c for c in pivot.columns
                                if c != treatment_city]
    pivot = pivot[cols]

    # Split into pre and post by timestamp
    pre_mask = (pivot.index >= pd.to_datetime(pre_start)) & \
               (pivot.index <= pd.to_datetime(post_start) - pd.Timedelta(hours=1))
    post_mask = (pivot.index >= pd.to_datetime(post_start)) & \
                (pivot.index <= pd.to_datetime(post_end) + pd.Timedelta(hours=23))

    n_pre = pre_mask.sum()
    n_post = post_mask.sum()

    # Keep only pre + post rows (exclude any gap)
    pivot = pivot[pre_mask | post_mask]

    # Flatten to sequential hourly DatetimeIndex
    pivot = flatten_hourly_to_sequential(pivot)

    pre_period = [pivot.index[0], pivot.index[n_pre - 1]]
    post_period = [pivot.index[n_pre], pivot.index[n_pre + n_post - 1]]

    print(f'  Hourly pivot: {n_pre} pre + {n_post} post = '
          f'{len(pivot)} total observations')
    return pivot, pre_period, post_period


# ----------------------------------------------------------
# 7. CausalImpact Runner
# ----------------------------------------------------------

def run_causal_impact(pivot_df, pre_period, post_period):
    """Run CausalImpact on a prepared pivot table.

    pivot_df: columns = [treatment_city, control1, control2, ...]
    pre_period: [start_idx, end_idx]
    post_period: [start_idx, end_idx]
    """
    import tensorflow as tf
    from causalimpact import CausalImpact

    try:
        ci = CausalImpact(pivot_df, pre_period, post_period)
        summary = ci.summary_data
        actual = summary.loc['actual', 'cumulative']
        predicted = summary.loc['predicted', 'cumulative']
        uplift = (actual / predicted - 1) if predicted > 0 else np.nan

        # Extract CI bounds if available
        ci_lower = summary.loc['predicted_lower', 'cumulative'] \
            if 'predicted_lower' in summary.index else np.nan
        ci_upper = summary.loc['predicted_upper', 'cumulative'] \
            if 'predicted_upper' in summary.index else np.nan

        result = {
            'actual_orders': actual,
            'predicted_orders': predicted,
            'uplift': uplift,
            'ci_lower_predicted': ci_lower,
            'ci_upper_predicted': ci_upper,
            'p_value': ci.p_value if hasattr(ci, 'p_value') else np.nan,
        }
    except Exception as e:
        print(f'  CausalImpact error: {e}')
        result = None
    finally:
        tf.keras.backend.clear_session()
        gc.collect()
    return result


# ----------------------------------------------------------
# 8. MDE Calculation
# ----------------------------------------------------------

def compute_mde(aa_uplifts, alpha=0.05, power=0.80):
    """Compute Minimum Detectable Effect from A/A uplift distribution.

    MDE = (z_alpha + z_power) * std(uplifts)
    For alpha=0.05 two-sided and power=0.80: factor ≈ 2.8
    """
    from scipy import stats
    z_alpha = stats.norm.ppf(1 - alpha / 2)  # 1.96
    z_power = stats.norm.ppf(power)           # 0.84
    factor = z_alpha + z_power                # ~2.80
    std = np.std(aa_uplifts, ddof=1)
    mde = factor * std
    print(f'  MDE at {int(power*100)}% power: {mde:.4f} ({mde*100:.1f}%)')
    print(f'  A/A uplift std: {std:.4f} ({std*100:.1f}%)')
    return mde


# ----------------------------------------------------------
# 9. Results Writer
# ----------------------------------------------------------

# ----------------------------------------------------------
# 9b. Maverick Campaign Calendar
# ----------------------------------------------------------

# Structured from MAVERICK TESTS spreadsheet.
# Each entry: (program, segment, cities, start, end, status)
MAVERICK_CAMPAIGNS = [
    ('SVP 2 (5x€10)',              'New, Reactivated',              ['Dresden','Dortmund','Essen'], '2026-02-17', '2026-03-31', 'Live'),
    ('TFD 2 (Free Delivery)',      'All',                           ['Dresden','Dortmund','Essen'], '2026-02-04', '2026-05-03', 'Live'),
    ('Prospect €15 off',           'Prospect',                      ['Dresden','Dortmund','Essen'], '2026-02-09', '2026-03-20', 'Delivered'),
    ('Win Back Wave 3 (€12)',      'Churned, Dormant, Lapsing',     ['Dresden','Dortmund','Essen'], '2026-03-04', '2026-03-31', 'Live'),
    ('Smart Growth Wave 6 (2x€7)', 'Engaged',                       ['Dresden','Dortmund','Essen'], '2026-03-19', '2026-03-30', 'Live'),
    ('Rapid Reward €10',           'Engaged',                       ['Dresden','Dortmund','Essen'], '2026-02-13', '2026-02-27', 'Delivered'),
    ('Offline vouchering (2x€20)', 'All',                           ['Dresden','Dortmund','Essen'], '2026-03-02', '2026-03-23', 'Delivered'),
    ('Refer a friend',             'New, Engaged',                  ['Dresden','Dortmund','Essen'], '2026-03-09', '2026-03-31', 'Live'),
    ('Sales Enablement (partner)', 'All',                           ['Dresden','Dortmund','Essen'], '2026-02-27', '2026-03-31', 'Live'),
    ('Inactive vouchering (2x€15)','Churned',                       ['Dresden','Dortmund','Essen'], '2026-01-14', '2026-02-22', 'Delivered'),
    ('Lapsing €7 off',             'Lapsing',                       ['Dortmund','Essen'],           '2026-02-19', '2026-02-25', 'Delivered'),
    ('BL Chain Voucher (€5/€7)',   'All',                           ['Dortmund','Essen'],           '2026-02-28', '2026-02-28', 'Delivered'),
]

MAVERICK_FLASH_SALES = [
    ('Flash 60%/30%',     'New, React, Engaged',          ['Essen','Dortmund'],           '2026-02-21', '2026-02-22', 'dinner'),
    ('Flash 50% lunch',   'Engaged',                      ['Dresden','Dortmund','Essen'], '2026-02-24', '2026-02-24', 'lunch'),
    ('Flash 30-50%',      'New, Eng, React, Early',       ['Essen','Dortmund'],           '2026-02-25', '2026-02-26', 'dinner'),
    ('Essen dinner Flash','All',                          ['Dresden','Dortmund','Essen'], '2026-02-27', '2026-02-28', 'dinner'),
    ('Flash lunch 50%',   'Eng, New, Early, React',       ['Dresden','Dortmund','Essen'], '2026-03-02', '2026-03-05', 'lunch'),
    ('Flash weekday 40-60%','All',                        ['Dortmund','Essen'],           '2026-03-04', '2026-03-04', 'dinner'),
    ('Flash lunch test',  'Engaged',                      ['Dortmund','Essen','Dresden'], '2026-03-06', '2026-03-06', 'lunch'),
    ('Flash weekend 30-80%','New, Early, Eng, React',     ['Dortmund','Essen'],           '2026-03-06', '2026-03-08', 'dinner'),
    ('Flash weekday Mon/Tues','New, Early, Engaged',      ['Dresden','Dortmund','Essen'], '2026-03-30', '2026-03-31', 'dinner'),
    ('Weekend lunch 30-60%','New, Early, Engaged',        ['Dortmund','Essen'],           '2026-03-27', '2026-03-28', 'lunch'),
]


def get_concurrent_campaigns(city, date_str):
    """Return list of campaigns active in a city on a given date."""
    d = pd.to_datetime(date_str).date()
    active = []
    for name, segment, cities, start, end, status in MAVERICK_CAMPAIGNS:
        if city in cities:
            s = pd.to_datetime(start).date()
            e = pd.to_datetime(end).date()
            if s <= d <= e:
                active.append({'campaign': name, 'segment': segment,
                               'start': start, 'end': end})
    return active


def plot_campaign_timeline(city, date_range_start='2026-01-01',
                           date_range_end='2026-04-01',
                           highlight_dates=None):
    """Plot Gantt-style timeline of all Maverick campaigns for a city.

    highlight_dates: list of (start, end) tuples to highlight
    (e.g., Flash Sales dates being evaluated).
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from datetime import datetime

    fig, ax = plt.subplots(figsize=(16, 8))

    # Background campaigns
    y = 0
    labels = []
    for name, segment, cities, start, end, status in MAVERICK_CAMPAIGNS:
        if city not in cities:
            continue
        s = pd.to_datetime(start)
        e = pd.to_datetime(end)
        ax.barh(y, (e - s).days + 1, left=s, height=0.6,
                color='steelblue', alpha=0.6, edgecolor='black',
                linewidth=0.5)
        labels.append(f'{name}\n({segment})')
        y += 1

    # Flash Sales
    for name, segment, cities, start, end, slot in MAVERICK_FLASH_SALES:
        if city not in cities:
            continue
        s = pd.to_datetime(start)
        e = pd.to_datetime(end)
        ax.barh(y, (e - s).days + 1, left=s, height=0.6,
                color='tomato', alpha=0.8, edgecolor='black',
                linewidth=0.5)
        labels.append(f'FS: {name}\n({slot})')
        y += 1

    # Highlight evaluation window
    if highlight_dates:
        for hs, he in highlight_dates:
            hs = pd.to_datetime(hs)
            he = pd.to_datetime(he)
            ax.axvspan(hs, he, alpha=0.15, color='gold',
                       label='Evaluation window')

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(pd.to_datetime(date_range_start),
                pd.to_datetime(date_range_end))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    plt.xticks(rotation=45)
    ax.set_title(f'Maverick Campaign Timeline: {city}', fontsize=14)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    return fig


# ----------------------------------------------------------
# 9c. Difference-in-Differences (within-city)
# ----------------------------------------------------------

def get_hourly_orders_single_city(client, country, city, start, end,
                                   hour_start=16, hour_end=22):
    """Query hourly orders for a single city (treatment only, no controls)."""
    query = f"""
    SELECT
        DATE(fo.orderdatetime) AS orderdate,
        EXTRACT(HOUR FROM fo.orderdatetime) AS hour,
        SUM(fo.nroforders) AS totalorders
    FROM `just-data-warehouse.dwh.fact_order` AS fo
    INNER JOIN `just-data-warehouse.dwh.dim_restaurant` AS dr
        ON fo.restaurantid = dr.restaurantid
    WHERE dr.country = '{country}'
        AND dr.city = '{city}'
        AND DATE(fo.orderdatetime) >= DATE('{start}')
        AND DATE(fo.orderdatetime) <= DATE('{end}')
        AND EXTRACT(HOUR FROM fo.orderdatetime) >= {hour_start}
        AND EXTRACT(HOUR FROM fo.orderdatetime) < {hour_end}
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    return client.query(query).to_dataframe()


def run_did_analysis(df_orders, flash_dates, pre_dates,
                     confidence=0.95):
    """Run within-city Difference-in-Differences.

    Compares Flash Sales days to adjacent non-Flash-Sales days
    within the same city.

    Args:
        df_orders: DataFrame with (orderdate, hour, totalorders)
        flash_dates: list of dates (str) that are Flash Sales days
        pre_dates: list of dates (str) that are comparison days
                   (same weekday pattern, no Flash Sales, but other
                   campaigns still running)
        confidence: CI level

    Returns: dict with DiD results
    """
    from scipy import stats

    flash_set = set(pd.to_datetime(d).date() for d in flash_dates)
    pre_set = set(pd.to_datetime(d).date() for d in pre_dates)

    df = df_orders.copy()
    df['orderdate'] = pd.to_datetime(df['orderdate']).dt.date

    # Daily totals (sum across hours)
    daily = df.groupby('orderdate')['totalorders'].sum().reset_index()

    flash_orders = daily[daily['orderdate'].isin(flash_set)]['totalorders']
    pre_orders = daily[daily['orderdate'].isin(pre_set)]['totalorders']

    if len(flash_orders) == 0 or len(pre_orders) == 0:
        print('  ERROR: No data for flash or pre dates')
        return None

    flash_mean = flash_orders.mean()
    pre_mean = pre_orders.mean()
    diff = flash_mean - pre_mean
    pct_diff = diff / pre_mean if pre_mean > 0 else np.nan

    # Welch's t-test (unequal variances)
    if len(flash_orders) > 1 and len(pre_orders) > 1:
        t_stat, p_value = stats.ttest_ind(flash_orders, pre_orders,
                                           equal_var=False)
        # CI on the difference
        pooled_se = np.sqrt(flash_orders.var() / len(flash_orders) +
                            pre_orders.var() / len(pre_orders))
        df_dof = len(flash_orders) + len(pre_orders) - 2
        t_crit = stats.t.ppf((1 + confidence) / 2, df_dof)
        ci_lower = diff - t_crit * pooled_se
        ci_upper = diff + t_crit * pooled_se
    else:
        t_stat, p_value = np.nan, np.nan
        ci_lower, ci_upper = np.nan, np.nan

    result = {
        'flash_dates': list(flash_dates),
        'pre_dates': list(pre_dates),
        'flash_mean_orders': flash_mean,
        'pre_mean_orders': pre_mean,
        'diff_orders': diff,
        'pct_diff': pct_diff,
        't_stat': t_stat,
        'p_value': p_value,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
    }
    return result


# ----------------------------------------------------------
# 10. Results Writer
# ----------------------------------------------------------

def write_flash_sales_result(client, row_dict, table_id):
    """Write a single Flash Sales result to the AA results table."""
    from google.cloud import bigquery

    df = pd.DataFrame([row_dict])
    schema = [
        bigquery.SchemaField('technique', 'STRING'),
        bigquery.SchemaField('country', 'STRING'),
        bigquery.SchemaField('window_start', 'STRING'),
        bigquery.SchemaField('window_end', 'STRING'),
        bigquery.SchemaField('seed', 'INTEGER'),
        bigquery.SchemaField('treatment_city', 'STRING'),
        bigquery.SchemaField('base_segment', 'STRING'),
        bigquery.SchemaField('n_units', 'INTEGER'),
        bigquery.SchemaField('n_controls', 'INTEGER'),
        bigquery.SchemaField('exact_match_pct', 'FLOAT'),
        bigquery.SchemaField('pre_period_uplift', 'FLOAT'),
        bigquery.SchemaField('campaign_period_uplift', 'FLOAT'),
        bigquery.SchemaField('post_period_uplift', 'FLOAT'),
        bigquery.SchemaField('campaign_incr_orders', 'FLOAT'),
        bigquery.SchemaField('post_incr_orders', 'FLOAT'),
        bigquery.SchemaField('run_timestamp', 'TIMESTAMP'),
    ]
    select_cols = [s.name for s in schema]
    job = client.load_table_from_dataframe(
        df[select_cols], table_id,
        job_config=bigquery.LoadJobConfig(
            schema=schema, write_disposition='WRITE_APPEND'))
    job.result()
