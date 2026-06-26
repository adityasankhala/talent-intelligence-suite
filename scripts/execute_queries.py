import sqlite3
import csv
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "talent_analytics.db")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

QUERIES = {
    "01_funnel_conversion_rates": """
        SELECT
            stage_name,
            COUNT(DISTINCT candidate_id) AS candidates_at_stage,
            ROUND(
                COUNT(DISTINCT candidate_id) * 100.0 /
                (SELECT COUNT(*) FROM candidates),
                1
            ) AS pct_of_total
        FROM stage_transitions
        GROUP BY stage_name
        ORDER BY MIN(stage_order)
    """,

    "02_avg_time_to_hire_by_department": """
        SELECT
            c.department,
            COUNT(c.id) AS hired_count,
            ROUND(AVG(c.time_in_pipeline_days), 1) AS avg_days_to_hire,
            MIN(c.time_in_pipeline_days) AS fastest_hire,
            MAX(c.time_in_pipeline_days) AS slowest_hire
        FROM candidates c
        WHERE c.current_stage = 'Hired'
        GROUP BY c.department
        ORDER BY avg_days_to_hire DESC
    """,

    "03_source_roi_analysis": """
        SELECT
            c.source,
            COUNT(c.id) AS total_applicants,
            SUM(CASE WHEN c.current_stage = 'Hired' THEN 1 ELSE 0 END) AS total_hired,
            ROUND(
                SUM(CASE WHEN c.current_stage = 'Hired' THEN 1 ELSE 0 END) * 100.0 /
                COUNT(c.id),
                1
            ) AS hire_conversion_pct,
            ROUND(AVG(c.quality_score), 1) AS avg_quality_score,
            ROUND(
                AVG(CASE WHEN c.current_stage = 'Hired' THEN c.quality_score END),
                1
            ) AS avg_hired_quality
        FROM candidates c
        GROUP BY c.source
        ORDER BY hire_conversion_pct DESC
    """,

    "04_stage_bottleneck_duration": """
        SELECT
            t1.stage_name AS from_stage,
            t2.stage_name AS to_stage,
            COUNT(*) AS transitions,
            ROUND(AVG(
                JULIANDAY(t2.entered_date) - JULIANDAY(t1.entered_date)
            ), 1) AS avg_days_in_stage,
            MAX(
                CAST(JULIANDAY(t2.entered_date) - JULIANDAY(t1.entered_date) AS INTEGER)
            ) AS max_days_in_stage
        FROM stage_transitions t1
        JOIN stage_transitions t2
            ON t1.candidate_id = t2.candidate_id
            AND t2.stage_order = t1.stage_order + 1
        GROUP BY t1.stage_name, t2.stage_name
        ORDER BY t1.stage_order
    """,

    "05_offer_acceptance_rate_by_dept": """
        SELECT
            c.department,
            SUM(CASE WHEN c.current_stage IN ('Offered', 'Hired') THEN 1 ELSE 0 END) AS total_offered,
            SUM(CASE WHEN c.current_stage = 'Hired' THEN 1 ELSE 0 END) AS total_accepted,
            ROUND(
                SUM(CASE WHEN c.current_stage = 'Hired' THEN 1 ELSE 0 END) * 100.0 /
                NULLIF(SUM(CASE WHEN c.current_stage IN ('Offered', 'Hired') THEN 1 ELSE 0 END), 0),
                1
            ) AS acceptance_rate_pct
        FROM candidates c
        GROUP BY c.department
        ORDER BY acceptance_rate_pct DESC
    """,

    "06_quality_score_vs_outcome": """
        SELECT
            CASE
                WHEN c.quality_score >= 80 THEN 'High (80-100)'
                WHEN c.quality_score >= 60 THEN 'Medium (60-79)'
                ELSE 'Low (40-59)'
            END AS quality_tier,
            COUNT(c.id) AS total_candidates,
            SUM(CASE WHEN c.current_stage = 'Hired' THEN 1 ELSE 0 END) AS hired,
            ROUND(
                SUM(CASE WHEN c.current_stage = 'Hired' THEN 1 ELSE 0 END) * 100.0 /
                COUNT(c.id),
                1
            ) AS hire_rate_pct,
            ROUND(AVG(c.time_in_pipeline_days), 1) AS avg_pipeline_days
        FROM candidates c
        GROUP BY quality_tier
        ORDER BY quality_tier
    """,

    "07_department_stage_heatmap": """
        SELECT
            c.department,
            st.stage_name,
            COUNT(DISTINCT c.id) AS candidate_count
        FROM candidates c
        JOIN stage_transitions st ON c.id = st.candidate_id
        GROUP BY c.department, st.stage_name
        ORDER BY c.department, st.stage_order
    """,

    "08_monthly_application_trend": """
        SELECT
            STRFTIME('%Y-%m', c.applied_date) AS month,
            COUNT(c.id) AS applications,
            SUM(CASE WHEN c.current_stage = 'Hired' THEN 1 ELSE 0 END) AS hires,
            ROUND(AVG(c.quality_score), 1) AS avg_quality
        FROM candidates c
        GROUP BY month
        ORDER BY month
    """,
}


def export_query(conn, name, sql, output_dir):
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    headers = [desc[0] for desc in cursor.description]

    filepath = os.path.join(output_dir, f"{name}.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    return headers, rows


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    for name, sql in QUERIES.items():
        headers, rows = export_query(conn, name, sql, REPORTS_DIR)
        print(f"\n{'=' * 70}")
        print(f"  {name.replace('_', ' ').upper()}")
        print(f"{'=' * 70}")

        col_widths = []
        for i, h in enumerate(headers):
            max_w = len(str(h))
            for row in rows:
                max_w = max(max_w, len(str(row[i])))
            col_widths.append(min(max_w, 25))

        header_line = " | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
        print(f"  {header_line}")
        print(f"  {'-' * len(header_line)}")
        for row in rows[:15]:
            row_line = " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(headers)))
            print(f"  {row_line}")
        if len(rows) > 15:
            print(f"  ... and {len(rows) - 15} more rows")
        print(f"  Exported to: reports/{name}.csv")

    conn.close()
    print(f"\nAll {len(QUERIES)} query reports exported to {REPORTS_DIR}/")


if __name__ == "__main__":
    main()
