"""
FastAPI Engagement Trends Endpoint
Bonus deliverable for take-home assignment

Provides real-time access to engagement analytics via REST API.
"""

from datetime import datetime, timedelta
from typing import Optional
import psycopg2
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Engagement Analytics API",
    description="Real-time engagement trends and analytics",
    version="1.0.0"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
def get_db_connection():
    """Create PostgreSQL connection."""
    return psycopg2.connect(
        host="127.0.0.1",
        port=13177,
        database="engagement_db",
        user="analytics",
        password="analytics_pass"
    )


# Response models
class EngagementTrend(BaseModel):
    date: str
    views: int
    likes: int
    comments: int
    shares: int
    total_engagements: int


class PostEngagement(BaseModel):
    post_id: int
    title: str
    author_name: str
    category: str
    publish_date: str
    views: int
    likes: int
    comments: int
    shares: int
    total_engagements: int
    engagement_rate: float


class AuthorStats(BaseModel):
    author_id: int
    author_name: str
    category: str
    total_posts: int
    total_engagements: int
    avg_engagement_per_post: float
    trend_7d: float
    trend_30d: float


class CategoryRanking(BaseModel):
    category: str
    total_engagements: int
    total_posts: int
    avg_engagement_per_post: float
    top_author: str
    rank: int


@app.get("/")
def root():
    """API root endpoint."""
    return {
        "message": "Engagement Analytics API",
        "endpoints": [
            "/engagement/{post_id}",
            "/author/{author_id}/trends",
            "/categories/top"
        ],
        "docs": "/docs"
    }


@app.get("/engagement/{post_id}", response_model=PostEngagement)
def get_post_engagement(
    post_id: int,
    period: str = Query("7d", regex="^(7d|30d|90d|all)$")
):
    """
    Get engagement metrics for a specific post.

    Args:
        post_id: Post ID to query
        period: Time period (7d, 30d, 90d, all)

    Returns:
        Engagement metrics for the post
    """
    period_days = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "all": 36500  # 100 years (effectively all)
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
        SELECT
            p.post_id,
            p.title,
            a.name AS author_name,
            p.category,
            p.publish_timestamp::date AS publish_date,
            COUNT(CASE WHEN e.type = 'view' THEN 1 END) AS views,
            COUNT(CASE WHEN e.type = 'like' THEN 1 END) AS likes,
            COUNT(CASE WHEN e.type = 'comment' THEN 1 END) AS comments,
            COUNT(CASE WHEN e.type = 'share' THEN 1 END) AS shares,
            COUNT(e.engagement_id) AS total_engagements,
            CASE
                WHEN COUNT(CASE WHEN e.type = 'view' THEN 1 END) > 0
                THEN ROUND(100.0 * (
                    COUNT(CASE WHEN e.type IN ('like', 'comment', 'share') THEN 1 END)
                ) / COUNT(CASE WHEN e.type = 'view' THEN 1 END), 2)
                ELSE 0
            END AS engagement_rate
        FROM posts p
        JOIN authors a ON p.author_id = a.author_id
        LEFT JOIN engagements e ON p.post_id = e.post_id
            AND e.engaged_timestamp >= CURRENT_DATE - INTERVAL '%s days'
        WHERE p.post_id = %s
        GROUP BY p.post_id, p.title, a.name, p.category, p.publish_timestamp
        """

        cursor.execute(query, (period_days[period], post_id))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Post {post_id} not found")

        return PostEngagement(
            post_id=result[0],
            title=result[1],
            author_name=result[2],
            category=result[3],
            publish_date=str(result[4]),
            views=result[5],
            likes=result[6],
            comments=result[7],
            shares=result[8],
            total_engagements=result[9],
            engagement_rate=float(result[10])
        )

    finally:
        cursor.close()
        conn.close()


@app.get("/author/{author_id}/trends", response_model=AuthorStats)
def get_author_trends(author_id: int):
    """
    Get engagement trends for a specific author.

    Args:
        author_id: Author ID to query

    Returns:
        Author statistics and trends
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
        WITH author_engagement AS (
            SELECT
                a.author_id,
                a.name AS author_name,
                a.author_category,
                COUNT(DISTINCT p.post_id) AS total_posts,
                SUM(es.total_engagements) AS total_engagements,
                ROUND(AVG(es.total_engagements), 2) AS avg_engagement_per_post
            FROM authors a
            JOIN posts p ON a.author_id = p.author_id
            JOIN engagement_stats es ON p.post_id = es.post_id
            WHERE a.author_id = %s
            GROUP BY a.author_id, a.name, a.author_category
        ),
        trend_7d AS (
            SELECT
                AVG(es.total_engagements) AS avg_7d
            FROM posts p
            JOIN engagement_stats es ON p.post_id = es.post_id
            WHERE p.author_id = %s
                AND p.publish_timestamp >= CURRENT_DATE - INTERVAL '7 days'
        ),
        trend_30d AS (
            SELECT
                AVG(es.total_engagements) AS avg_30d
            FROM posts p
            JOIN engagement_stats es ON p.post_id = es.post_id
            WHERE p.author_id = %s
                AND p.publish_timestamp >= CURRENT_DATE - INTERVAL '30 days'
        )
        SELECT
            ae.author_id,
            ae.author_name,
            ae.author_category,
            ae.total_posts,
            ae.total_engagements,
            ae.avg_engagement_per_post,
            COALESCE(t7.avg_7d, 0) AS trend_7d,
            COALESCE(t30.avg_30d, 0) AS trend_30d
        FROM author_engagement ae
        CROSS JOIN trend_7d t7
        CROSS JOIN trend_30d t30
        """

        cursor.execute(query, (author_id, author_id, author_id))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Author {author_id} not found")

        return AuthorStats(
            author_id=result[0],
            author_name=result[1],
            category=result[2],
            total_posts=result[3],
            total_engagements=result[4],
            avg_engagement_per_post=float(result[5]),
            trend_7d=float(result[6]),
            trend_30d=float(result[7])
        )

    finally:
        cursor.close()
        conn.close()


@app.get("/categories/top", response_model=list[CategoryRanking])
def get_top_categories(
    metric: str = Query("engagement", regex="^(engagement|posts)$"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get top categories ranked by engagement or post count.

    Args:
        metric: Ranking metric (engagement or posts)
        limit: Number of categories to return

    Returns:
        Ranked list of categories
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        order_by = "total_engagements DESC" if metric == "engagement" else "total_posts DESC"

        query = f"""
        WITH category_stats AS (
            SELECT
                p.category,
                COUNT(DISTINCT p.post_id) AS total_posts,
                SUM(es.total_engagements) AS total_engagements,
                ROUND(AVG(es.total_engagements), 2) AS avg_engagement_per_post,
                (
                    SELECT a.name
                    FROM authors a
                    JOIN posts p2 ON a.author_id = p2.author_id
                    JOIN engagement_stats es2 ON p2.post_id = es2.post_id
                    WHERE p2.category = p.category
                    GROUP BY a.author_id, a.name
                    ORDER BY SUM(es2.total_engagements) DESC
                    LIMIT 1
                ) AS top_author
            FROM posts p
            JOIN engagement_stats es ON p.post_id = es.post_id
            GROUP BY p.category
        )
        SELECT
            category,
            total_engagements,
            total_posts,
            avg_engagement_per_post,
            top_author,
            ROW_NUMBER() OVER (ORDER BY {order_by}) AS rank
        FROM category_stats
        ORDER BY {order_by}
        LIMIT %s
        """

        cursor.execute(query, (limit,))
        results = cursor.fetchall()

        return [
            CategoryRanking(
                category=row[0],
                total_engagements=row[1],
                total_posts=row[2],
                avg_engagement_per_post=float(row[3]),
                top_author=row[4] or "Unknown",
                rank=row[5]
            )
            for row in results
        ]

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=13516)
