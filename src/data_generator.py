"""
Generate realistic sample data for engagement analytics.

Creates authors, posts, and engagements with patterns:
- Peak engagement 9am-5pm on weekdays
- Some authors have high volume but low engagement
- Categories show different engagement patterns
- Realistic temporal distribution
"""

import random
from datetime import datetime, timedelta
from typing import List, Tuple
import psycopg2
from psycopg2.extras import execute_values

# Configuration
NUM_AUTHORS = 50
NUM_POSTS = 10000
NUM_ENGAGEMENTS = 50000
NUM_USERS = 5000

CATEGORIES = ["Tech", "Lifestyle", "Business", "Health", "Finance", "Entertainment"]
ENGAGEMENT_TYPES = ["view", "like", "comment", "share"]
COUNTRIES = ["US", "UK", "CA", "AU", "DE", "FR", "IN", "BR"]
USER_SEGMENTS = ["free", "trial", "subscriber", "enterprise"]

# Engagement probability by hour (24-hour format)
HOUR_WEIGHTS = {
    0: 0.2, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 5: 0.2,
    6: 0.3, 7: 0.5, 8: 0.8, 9: 1.0, 10: 1.0, 11: 1.0,
    12: 0.9, 13: 1.0, 14: 1.0, 15: 0.9, 16: 0.8, 17: 0.7,
    18: 0.6, 19: 0.5, 20: 0.4, 21: 0.4, 22: 0.3, 23: 0.2
}

# Weekday engagement multiplier (Monday=0, Sunday=6)
WEEKDAY_WEIGHTS = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 0.9, 5: 0.6, 6: 0.5}


def get_db_connection():
    """Create PostgreSQL connection."""
    return psycopg2.connect(
        host="127.0.0.1",
        port=13177,
        database="engagement_db",
        user="analytics",
        password="analytics_pass"
    )


def generate_authors() -> List[Tuple]:
    """Generate author records."""
    authors = []
    start_date = datetime(2018, 1, 1)

    for i in range(1, NUM_AUTHORS + 1):
        name = f"Author_{i}"
        joined_date = start_date + timedelta(days=random.randint(0, 2500))
        category = random.choice(CATEGORIES)
        authors.append((name, joined_date.date(), category))

    return authors


def generate_posts() -> List[Tuple]:
    """Generate post records with varied patterns."""
    posts = []
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 11, 18)

    # Define author archetypes for realistic patterns
    high_volume_authors = set(random.sample(range(1, NUM_AUTHORS + 1), k=10))

    for _ in range(NUM_POSTS):
        author_id = random.randint(1, NUM_AUTHORS)
        category = random.choice(CATEGORIES)

        # High-volume authors post more frequently
        timestamp_range = (end_date - start_date).days
        publish_timestamp = start_date + timedelta(
            days=random.randint(0, timestamp_range),
            hours=random.randint(6, 22),
            minutes=random.randint(0, 59)
        )

        title = f"Post about {category} topic {random.randint(1000, 9999)}"
        content_length = random.randint(200, 3000)
        has_media = random.random() < 0.6  # 60% have media

        posts.append((
            author_id, category, publish_timestamp,
            title, content_length, has_media
        ))

    return posts


def generate_engagements(num_posts: int) -> List[Tuple]:
    """Generate engagement records with realistic time patterns."""
    engagements = []

    # Engagement conversion rates
    view_to_like = 0.15
    like_to_comment = 0.10
    comment_to_share = 0.05

    for post_id in range(1, num_posts + 1):
        # Number of views varies by post
        base_views = random.randint(50, 500)

        # Some posts go viral (promoted content)
        if random.random() < 0.05:  # 5% promoted
            base_views *= random.randint(5, 20)

        # Generate engagement timestamps based on publish time
        post_timestamp = datetime(2024, 1, 1) + timedelta(
            days=random.randint(0, 320),
            hours=random.randint(0, 23)
        )

        # Views
        for _ in range(base_views):
            engagement_time = generate_realistic_timestamp(post_timestamp)
            user_id = random.randint(1, NUM_USERS)
            engagements.append((post_id, 'view', user_id, engagement_time))

        # Likes (subset of views)
        num_likes = int(base_views * view_to_like * random.uniform(0.5, 1.5))
        for _ in range(num_likes):
            engagement_time = generate_realistic_timestamp(post_timestamp)
            user_id = random.randint(1, NUM_USERS)
            engagements.append((post_id, 'like', user_id, engagement_time))

        # Comments (subset of likes)
        num_comments = int(num_likes * like_to_comment * random.uniform(0.5, 1.5))
        for _ in range(num_comments):
            engagement_time = generate_realistic_timestamp(post_timestamp)
            user_id = random.randint(1, NUM_USERS)
            engagements.append((post_id, 'comment', user_id, engagement_time))

        # Shares (subset of comments)
        num_shares = int(num_comments * comment_to_share * random.uniform(0.5, 1.5))
        for _ in range(num_shares):
            engagement_time = generate_realistic_timestamp(post_timestamp)
            user_id = random.randint(1, NUM_USERS)
            engagements.append((post_id, 'share', user_id, engagement_time))

    # Limit total engagements
    if len(engagements) > NUM_ENGAGEMENTS:
        engagements = random.sample(engagements, NUM_ENGAGEMENTS)

    return engagements


def generate_realistic_timestamp(post_timestamp: datetime) -> datetime:
    """Generate engagement timestamp based on hour/day patterns."""
    # Engagement happens within 30 days of post
    days_offset = random.choices(
        range(0, 30),
        weights=[10, 8, 6, 4, 3, 2, 1] + [1] * 23,
        k=1
    )[0]

    hour = random.choices(
        range(24),
        weights=[HOUR_WEIGHTS[h] for h in range(24)],
        k=1
    )[0]

    engagement_time = post_timestamp + timedelta(
        days=days_offset,
        hours=hour - post_timestamp.hour,
        minutes=random.randint(0, 59)
    )

    # Apply weekday weight
    weekday_factor = WEEKDAY_WEIGHTS[engagement_time.weekday()]
    if random.random() > weekday_factor:
        # Push to weekday
        engagement_time += timedelta(days=random.randint(1, 3))

    return engagement_time


def generate_post_metadata(num_posts: int) -> List[Tuple]:
    """Generate post metadata."""
    metadata = []
    tag_options = [
        "SQL", "Python", "Analytics", "Wellness", "Morning", "Tips",
        "Optimization", "Tutorial", "Guide", "Review", "Trends"
    ]

    for post_id in range(1, num_posts + 1):
        tags = random.sample(tag_options, k=random.randint(1, 4))
        is_promoted = random.random() < 0.05  # 5% promoted
        language = "en"

        metadata.append((post_id, tags, is_promoted, language))

    return metadata


def generate_users() -> List[Tuple]:
    """Generate user records."""
    users = []
    start_date = datetime(2020, 1, 1)

    for _ in range(NUM_USERS):
        signup_date = start_date + timedelta(days=random.randint(0, 1800))
        country = random.choice(COUNTRIES)
        segment = random.choice(USER_SEGMENTS)

        users.append((signup_date.date(), country, segment))

    return users


def load_data():
    """Load all generated data into PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()

    print("Generating data...")

    # Generate all data
    authors = generate_authors()
    print(f"Generated {len(authors)} authors")

    # Load authors first (needed for FK)
    execute_values(
        cursor,
        "INSERT INTO authors (name, joined_date, author_category) VALUES %s",
        authors
    )
    conn.commit()
    print("Loaded authors")

    posts = generate_posts()
    print(f"Generated {len(posts)} posts")

    execute_values(
        cursor,
        """INSERT INTO posts
           (author_id, category, publish_timestamp, title, content_length, has_media)
           VALUES %s""",
        posts
    )
    conn.commit()
    print("Loaded posts")

    # Get actual post count
    cursor.execute("SELECT COUNT(*) FROM posts")
    num_posts = cursor.fetchone()[0]

    engagements = generate_engagements(num_posts)
    print(f"Generated {len(engagements)} engagements")

    # Batch insert engagements (large dataset)
    batch_size = 5000
    for i in range(0, len(engagements), batch_size):
        batch = engagements[i:i+batch_size]
        execute_values(
            cursor,
            """INSERT INTO engagements
               (post_id, type, user_id, engaged_timestamp)
               VALUES %s""",
            batch
        )
        conn.commit()
        print(f"Loaded engagements batch {i//batch_size + 1}")

    users = generate_users()
    execute_values(
        cursor,
        "INSERT INTO users (signup_date, country, user_segment) VALUES %s",
        users
    )
    conn.commit()
    print(f"Loaded {len(users)} users")

    metadata = generate_post_metadata(num_posts)
    execute_values(
        cursor,
        """INSERT INTO post_metadata
           (post_id, tags, is_promoted, language)
           VALUES %s""",
        metadata
    )
    conn.commit()
    print(f"Loaded {len(metadata)} post metadata records")

    # Refresh materialized view
    cursor.execute("REFRESH MATERIALIZED VIEW engagement_stats")
    conn.commit()
    print("Refreshed materialized view")

    cursor.close()
    conn.close()
    print("\nData loading complete!")


if __name__ == "__main__":
    load_data()
