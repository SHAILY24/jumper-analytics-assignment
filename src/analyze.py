"""
Simple engagement analysis script.

Generates key insights and exports summary statistics.
Alternative to full Jupyter notebook for quick analysis.
"""

import psycopg2
import pandas as pd
from datetime import datetime


def get_db_connection():
    """Create PostgreSQL connection."""
    return psycopg2.connect(
        host="127.0.0.1",
        port=13177,
        database="engagement_db",
        user="analytics",
        password="analytics_pass"
    )


def analyze_engagement_patterns():
    """Analyze time-based engagement patterns."""
    conn = get_db_connection()

    query = """
    SELECT
        EXTRACT(HOUR FROM engaged_timestamp) AS hour,
        EXTRACT(DOW FROM engaged_timestamp) AS dow,
        COUNT(*) AS engagement_count,
        type
    FROM engagements
    WHERE engaged_timestamp >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY hour, dow, type
    ORDER BY hour, dow
    """

    df = pd.read_sql(query, conn)
    conn.close()

    # Peak hours
    hourly = df.groupby('hour')['engagement_count'].sum().sort_values(ascending=False)
    print("\n=== TOP 5 ENGAGEMENT HOURS ===")
    print(hourly.head())

    # Best days
    daily = df.groupby('dow')['engagement_count'].sum().sort_values(ascending=False)
    print("\n=== ENGAGEMENT BY DAY OF WEEK ===")
    day_names = {0: 'Sun', 1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat'}
    for dow, count in daily.items():
        print(f"{day_names[dow]}: {count:,}")

    return df


def analyze_author_performance():
    """Identify high-volume, low-engagement authors."""
    conn = get_db_connection()

    query = """
    SELECT
        a.name,
        a.author_category,
        COUNT(DISTINCT p.post_id) AS posts,
        ROUND(AVG(es.total_engagements), 2) AS avg_engagement
    FROM authors a
    JOIN posts p ON a.author_id = p.author_id
    JOIN engagement_stats es ON p.post_id = es.post_id
    GROUP BY a.author_id, a.name, a.author_category
    HAVING COUNT(DISTINCT p.post_id) >= 5
    ORDER BY posts DESC, avg_engagement ASC
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print("\n=== HIGH-VOLUME AUTHORS (5+ POSTS) ===")
    print(df.head(10))

    # Calculate opportunity
    median_engagement = df['avg_engagement'].median()
    df['below_median'] = df['avg_engagement'] < median_engagement
    df['opportunity'] = (median_engagement - df['avg_engagement']) * df['posts']
    df['opportunity'] = df['opportunity'].clip(lower=0)

    print(f"\nMedian Engagement: {median_engagement:.2f}")
    print(f"Authors Below Median: {df['below_median'].sum()} of {len(df)}")
    print(f"\nTop Improvement Opportunities:")
    print(df.nlargest(5, 'opportunity')[['name', 'posts', 'avg_engagement', 'opportunity']])

    return df


def analyze_category_performance():
    """Compare engagement across categories."""
    conn = get_db_connection()

    query = """
    SELECT
        category,
        COUNT(DISTINCT post_id) AS total_posts,
        SUM(total_engagements) AS total_engagement,
        ROUND(AVG(total_engagements), 2) AS avg_engagement,
        ROUND(AVG(view_count), 2) AS avg_views,
        CASE
            WHEN SUM(view_count) > 0
            THEN ROUND(100.0 * SUM(like_count + comment_count + share_count) / SUM(view_count), 2)
            ELSE 0
        END AS engagement_rate_pct
    FROM engagement_stats
    GROUP BY category
    ORDER BY total_engagement DESC
    """

    df = pd.read_sql(query, conn)
    conn.close()

    print("\n=== CATEGORY PERFORMANCE ===")
    print(df.to_string(index=False))

    return df


def generate_summary_report():
    """Generate overall summary statistics."""
    conn = get_db_connection()

    queries = {
        "Total Posts": "SELECT COUNT(*) FROM posts",
        "Total Engagements": "SELECT COUNT(*) FROM engagements",
        "Total Authors": "SELECT COUNT(*) FROM authors",
        "Total Users": "SELECT COUNT(*) FROM users",
        "Avg Engagement/Post": "SELECT ROUND(AVG(total_engagements), 2) FROM engagement_stats",
        "Date Range": """
            SELECT
                MIN(publish_timestamp)::date || ' to ' || MAX(publish_timestamp)::date
            FROM posts
        """
    }

    print("\n" + "="*60)
    print("ENGAGEMENT ANALYTICS SUMMARY")
    print("="*60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    for label, query in queries.items():
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()[0]
        cursor.close()
        print(f"{label:25s}: {result}")

    conn.close()


if __name__ == "__main__":
    generate_summary_report()
    analyze_engagement_patterns()
    analyze_category_performance()
    analyze_author_performance()

    print("\n" + "="*60)
    print("Analysis complete. See RECOMMENDATIONS.md for actionable insights.")
    print("="*60)
