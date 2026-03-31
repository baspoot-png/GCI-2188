----------- To evaluate the performance of an OMT campaign ------------------------------

        WITH omt_orders AS (
        SELECT
          CASE WHEN s.base_segment IS NULL THEN 'unknown' ELSE s.base_segment END AS base_segment,
          dr.city,
          SUM(fo.nroforders)                                                        AS omt_orders,
          ROUND(SUM(fof.applied_discount_amount),0)                                 AS omt_total_costs,
          ROUND(SAFE_DIVIDE(SUM(fo.gtv),SUM(fo.nroforders)),2)                      AS omt_GTV_per_order,
          ROUND(SAFE_DIVIDE(SUM(fof.applied_discount_amount),SUM(fo.nroforders)),2) AS omt_cost_per_order,
          COUNT(DISTINCT s.scv_key)                                                 AS omt_unique_buyer

        FROM `just-data-warehouse.dwh.fact_order`                               AS fo
        INNER JOIN `just-data-warehouse.dwh.fact_offer`                         AS fof  ON      fo.orderid               = fof.orderid
        INNER JOIN `just-data-warehouse.core_dwh.dim_order`                     AS dor  ON      fo.orderid               = dor.orderid
        INNER JOIN `just-data-warehouse.dwh.dim_restaurant_offers`              AS dro  ON      fof.offerid              = dro.offerid
                                                                                                AND fof.restaurantid         = dro.restaurantid
        INNER JOIN `just-data-warehouse.dwh.dim_restaurant`                     AS dr   ON      fo.restaurantid          = dr.restaurantid

        LEFT JOIN `just-data-warehouse.core_dwh.dim_unique_customer_history`    AS ch   ON      fo.customerid = ch.customer_id
                                                                                                AND DATE_SUB(ch.snapshot_date, INTERVAL 1 DAY) = DATE(fo.orderdatetime)
                                                                                                AND ch.snapshot_date >= '2026-01-15'
        LEFT JOIN `just-data-warehouse.dwh.fact_segmentation_scv_key`           AS s    ON      ch.scv_key = s.scv_key
                                                                                                AND DATE_SUB(DATE(fo.orderdatetime), INTERVAL 1 DAY) = s.snapshot_date
                                                                                                AND s.snapshot_date >= '2026-01-14'

        WHERE
            DATE(fo.orderdatetime)                  = '2026-03-04'    --> needs to match OMT period!
        --    AND DATE(fo.orderdatetime)              <= '2026-02-28'    --> needs to match OMT period!
            AND EXTRACT(HOUR FROM fo.orderdatetime) >= 16            --> adjust if Lunch or Dinner Flash Sales
            AND EXTRACT(HOUR FROM fo.orderdatetime) < 22                    --> needs to match OMT period!
            AND DATE(fof.orderdatetimeutc)          >= '2026-01-15'   --> do not touch
            AND DATE(dor.orderday)                  >= '2026-01-15'   --> do not touch

            AND dro.offer_source_campaign_id        LIKE 'MaverickDinnerFlashS_04Mar2026%'     --> OMT campaign ID

            AND dr.city IN ('Dortmund', 'Essen', 'Dresden')
        GROUP BY ALL
        ),

        all_orders AS (
        SELECT
          CASE WHEN s.base_segment IS NULL THEN 'unknown' ELSE s.base_segment END AS base_segment,
          dr.city,
          SUM(fo.nroforders)                                                        AS all_orders,
          ROUND(SAFE_DIVIDE(SUM(fo.gtv),SUM(fo.nroforders)),2)                      AS all_GTV_per_order,
          COUNT(DISTINCT s.scv_key)                                                 AS all_unique_buyer

        FROM `just-data-warehouse.dwh.fact_order`                               AS fo
        INNER JOIN `just-data-warehouse.dwh.dim_restaurant`                     AS dr   ON      fo.restaurantid          = dr.restaurantid

        LEFT JOIN `just-data-warehouse.core_dwh.dim_unique_customer_history`    AS ch   ON      fo.customerid = ch.customer_id
                                                                                                AND DATE_SUB(ch.snapshot_date, INTERVAL 1 DAY) = DATE(fo.orderdatetime)
                                                                                                AND ch.snapshot_date >= '2026-01-15'
        LEFT JOIN `just-data-warehouse.dwh.fact_segmentation_scv_key`           AS s    ON      ch.scv_key = s.scv_key
                                                                                                AND DATE_SUB(DATE(fo.orderdatetime), INTERVAL 1 DAY) = s.snapshot_date
                                                                                                AND s.snapshot_date >= '2026-01-14'

        WHERE
            DATE(fo.orderdatetime)                  = '2026-03-04'         --> needs to match OMT period!
   --         AND DATE(fo.orderdatetime)              <= '2026-02-28'         --> needs to match OMT period!
            AND EXTRACT(HOUR FROM fo.orderdatetime) >= 16                   --> needs to match OMT period!
            AND EXTRACT(HOUR FROM fo.orderdatetime) < 22                    --> needs to match OMT period!
            AND dr.city IN ('Dortmund', 'Essen', 'Dresden')

        GROUP BY ALL
        )

        SELECT omt.city,
               omt.base_segment,
               CONCAT(omt.city,omt.base_segment)                                AS key,  --- for VLOOKUP in Google Sheet
               ao.all_unique_buyer                                              AS total_ordering_customers,
               omt.omt_unique_buyer                                             AS customers_with_offer,
               ROUND(SAFE_DIVIDE(omt.omt_unique_buyer,ao.all_unique_buyer),2)   AS offer_customer_share,
               omt.omt_orders,
               ROUND(SAFE_DIVIDE(omt.omt_orders,omt.omt_unique_buyer),2)        AS offers_orders_per_ordering_customer,
               ao.all_orders,
               ROUND(SAFE_DIVIDE(omt.omt_orders,ao.all_orders),2)               AS offer_order_share,
               omt.omt_GTV_per_order,
               omt.omt_cost_per_order,
               omt.omt_total_costs,
               ao.all_GTV_per_order

        FROM        all_orders AS ao
        LEFT JOIN   omt_orders AS omt ON      ao.city           = omt.city
                                         AND  ao.base_segment   = omt.base_segment;
