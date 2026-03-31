            WITH base_table AS (
           SELECT
            DATE(fo.orderdatetime) AS orderdate,
            CASE
                  WHEN  dr.city = 'Essen'               THEN 'Y' --> as treatment
                        ELSE 'X'                                 -- as control
            END AS citygroup,
            s.base_segment,
            SUM(fo.nroforders) AS totalorders

          FROM `just-data-warehouse.dwh.fact_order`                                 AS fo
          INNER JOIN `just-data-warehouse.dwh.dim_restaurant`                       AS dr   ON fo.restaurantid = dr.restaurantid
          LEFT JOIN `just-data-warehouse.core_dwh.dim_unique_customer_history`      AS ch   ON fo.customerid = ch.customer_id
                                                                                                AND DATE_SUB(ch.snapshot_date, INTERVAL 1 DAY) = DATE(fo.orderdatetime)
                                                                                                AND ch.snapshot_date >= '2025-10-01'
          LEFT JOIN `just-data-warehouse.dwh.fact_segmentation_scv_key`             AS s    ON  ch.scv_key = s.scv_key
                                                                                                AND DATE_SUB(DATE(fo.orderdatetime), INTERVAL 1 DAY) = s.snapshot_date
                                                                                                AND s.snapshot_date >= '2025-09-30'
          WHERE
            dr.country = 'DE'
            AND dr.city IN (
                                        'Essen',   -- treatment
                                        'Hannover',
                                        'Nürnberg',
                                        'Leipzig',
                                        'Bremen',
                                        'Duisburg',
                                        'Stuttgart',
                                        'Düsseldorf',
                                        'Mannheim',
                                        'Bochum',
                                        'Bonn',
                                        'Wuppertal',
                                        'Karlsruhe',
                                        'Münster',
                                        'Wiesbaden',
                                        'Mönchengladbach',
                                        'Mainz',
                                        'Bielefeld',
                                        'Kassel',
                                        'Aachen',
                                        'Kiel',
                                        'Frankfurt am Main',
                                        'Krefeld')

            AND DATE(fo.orderdatetime) >= '2025-10-01'
            AND DATE(fo.orderdatetime) <= '2026-03-05'  ---> until the last campaign date
      --     AND EXTRACT(HOUR FROM fo.orderdatetime) >= 11 --> adjust if Lunch or Dinner Flash Sales
      --     AND EXTRACT(HOUR FROM fo.orderdatetime) < 14  --> adjust if Lunch or Dinner Flash Sales

           GROUP BY DATE(fo.orderdatetime), dr.city, s.base_segment
            )
           SELECT bt.orderdate                  AS date,
                  bt.citygroup,
                  bt.base_segment,
                  SUM(bt.totalorders)           AS totalorders
           FROM base_table AS bt
           GROUP BY ALL
