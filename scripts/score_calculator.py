import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "talent_analytics.db")


def compute_activity_score(conn, username):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM github_repos WHERE username = ?
    """, (username,))
    repo_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT
            SUM(stars) as total_stars,
            SUM(forks) as total_forks,
            MAX(pushed_at) as last_push
        FROM github_repos
        WHERE username = ?
    """, (username,))
    row = cursor.fetchone()
    total_stars = row[0] or 0
    total_forks = row[1] or 0
    last_push = row[2]

    recency_score = 0
    if last_push:
        try:
            last_dt = datetime.strptime(last_push[:10], "%Y-%m-%d")
            days_since = (datetime.now() - last_dt).days
            if days_since <= 30:
                recency_score = 30
            elif days_since <= 90:
                recency_score = 20
            elif days_since <= 365:
                recency_score = 10
            else:
                recency_score = 3
        except ValueError:
            recency_score = 5

    repo_score = min(repo_count * 2, 25)
    star_score = min(total_stars * 0.5, 25)
    fork_score = min(total_forks * 1, 20)

    activity = min(round(repo_score + star_score + fork_score + recency_score), 100)
    return activity


def compute_diversity_score(conn, username):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT language, SUM(bytes) as total_bytes
        FROM github_languages
        WHERE username = ?
        GROUP BY language
        ORDER BY total_bytes DESC
    """, (username,))
    rows = cursor.fetchall()

    if not rows:
        return 0

    lang_count = len(rows)
    total_bytes = sum(r[1] for r in rows)

    if total_bytes == 0:
        return 0

    proportions = [r[1] / total_bytes for r in rows]
    import math
    entropy = -sum(p * math.log2(p) for p in proportions if p > 0)
    max_entropy = math.log2(lang_count) if lang_count > 1 else 1

    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

    count_score = min(lang_count * 5, 40)
    entropy_score = round(normalized_entropy * 60)

    diversity = min(count_score + entropy_score, 100)
    return diversity


def ensure_scores_table(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS github_scores")
    cursor.execute("""
        CREATE TABLE github_scores (
            username TEXT PRIMARY KEY,
            activity_score INTEGER,
            diversity_score INTEGER,
            overall_score INTEGER,
            computed_at TEXT,
            FOREIGN KEY (username) REFERENCES github_profiles (username)
        )
    """)
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT username FROM github_profiles")
    usernames = [row[0] for row in cursor.fetchall()]

    if not usernames:
        print("No GitHub profiles found in database.")
        print("Run github_fetcher.py first to populate profiles.")
        conn.close()
        return

    ensure_scores_table(conn)

    print(f"Computing scores for {len(usernames)} profiles...\n")
    print(f"{'Username':<20} {'Activity':>10} {'Diversity':>10} {'Overall':>10}")
    print(f"{'-' * 52}")

    for username in usernames:
        activity = compute_activity_score(conn, username)
        diversity = compute_diversity_score(conn, username)
        overall = round(activity * 0.6 + diversity * 0.4)

        conn.execute("""
            INSERT OR REPLACE INTO github_scores
                (username, activity_score, diversity_score, overall_score, computed_at)
            VALUES (?, ?, ?, ?, ?)
        """, (username, activity, diversity, overall, datetime.now().isoformat()))

        print(f"{username:<20} {activity:>10} {diversity:>10} {overall:>10}")

    conn.commit()
    conn.close()
    print(f"\nScores persisted to github_scores table in {DB_PATH}")


if __name__ == "__main__":
    main()
