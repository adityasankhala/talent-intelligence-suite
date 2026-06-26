import requests
import sqlite3
import time
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "talent_analytics.db")
API_BASE = "https://api.github.com"
MAX_RETRIES = 3
PER_PAGE = 100


def get_headers(token=None):
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def handle_rate_limit(response):
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    if remaining == 0:
        reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
        sleep_secs = max(reset_ts - int(time.time()), 1) + 5
        print(f"Rate limit hit. Sleeping for {sleep_secs} seconds...")
        time.sleep(sleep_secs)


def api_get(url, headers, params=None):
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 403:
                handle_rate_limit(response)
                continue

            if response.status_code == 404:
                return None

            response.raise_for_status()
            handle_rate_limit(response)
            return response.json()

        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1}/{MAX_RETRIES} for {url}")
            time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError:
            print(f"Connection error on attempt {attempt + 1}/{MAX_RETRIES}")
            time.sleep(2 ** attempt)
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                raise

    return None


def fetch_paginated(url, headers, params=None, max_pages=5):
    all_items = []
    params = params or {}
    params["per_page"] = PER_PAGE

    for page in range(1, max_pages + 1):
        params["page"] = page
        data = api_get(url, headers, params)

        if not data or len(data) == 0:
            break

        all_items.extend(data)

        if len(data) < PER_PAGE:
            break

    return all_items


def fetch_user_profile(username, headers):
    data = api_get(f"{API_BASE}/users/{username}", headers)
    if not data:
        return None

    return {
        "username": data.get("login"),
        "name": data.get("name"),
        "bio": data.get("bio"),
        "public_repos": data.get("public_repos", 0),
        "followers": data.get("followers", 0),
        "following": data.get("following", 0),
        "created_at": data.get("created_at"),
        "location": data.get("location"),
        "company": data.get("company"),
    }


def fetch_user_repos(username, headers):
    raw_repos = fetch_paginated(
        f"{API_BASE}/users/{username}/repos",
        headers,
        params={"sort": "updated", "type": "owner"},
        max_pages=3,
    )

    repos = []
    for r in raw_repos:
        if r.get("fork"):
            continue
        repos.append({
            "username": username,
            "repo_name": r.get("name"),
            "description": (r.get("description") or "")[:200],
            "language": r.get("language"),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "size_kb": r.get("size", 0),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "pushed_at": r.get("pushed_at"),
        })

    return repos


def fetch_repo_languages(username, repo_name, headers):
    data = api_get(f"{API_BASE}/repos/{username}/{repo_name}/languages", headers)
    if not data:
        return []

    total_bytes = sum(data.values()) or 1
    return [
        {
            "username": username,
            "repo_name": repo_name,
            "language": lang,
            "bytes": byte_count,
            "percentage": round(byte_count * 100.0 / total_bytes, 1),
        }
        for lang, byte_count in data.items()
    ]


def create_github_schema(conn):
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS github_languages")
    cursor.execute("DROP TABLE IF EXISTS github_repos")
    cursor.execute("DROP TABLE IF EXISTS github_profiles")

    cursor.execute("""
        CREATE TABLE github_profiles (
            username TEXT PRIMARY KEY,
            name TEXT,
            bio TEXT,
            public_repos INTEGER,
            followers INTEGER,
            following INTEGER,
            created_at TEXT,
            location TEXT,
            company TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE github_repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            description TEXT,
            language TEXT,
            stars INTEGER,
            forks INTEGER,
            open_issues INTEGER,
            size_kb INTEGER,
            created_at TEXT,
            updated_at TEXT,
            pushed_at TEXT,
            FOREIGN KEY (username) REFERENCES github_profiles (username)
        )
    """)

    cursor.execute("""
        CREATE TABLE github_languages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            language TEXT NOT NULL,
            bytes INTEGER,
            percentage REAL,
            FOREIGN KEY (username) REFERENCES github_profiles (username)
        )
    """)

    conn.commit()


def save_profile(conn, profile):
    conn.execute("""
        INSERT OR REPLACE INTO github_profiles
            (username, name, bio, public_repos, followers, following, created_at, location, company)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        profile["username"], profile["name"], profile["bio"],
        profile["public_repos"], profile["followers"], profile["following"],
        profile["created_at"], profile["location"], profile["company"],
    ))
    conn.commit()


def save_repos(conn, repos):
    conn.executemany("""
        INSERT INTO github_repos
            (username, repo_name, description, language, stars, forks, open_issues,
             size_kb, created_at, updated_at, pushed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (r["username"], r["repo_name"], r["description"], r["language"],
         r["stars"], r["forks"], r["open_issues"], r["size_kb"],
         r["created_at"], r["updated_at"], r["pushed_at"])
        for r in repos
    ])
    conn.commit()


def save_languages(conn, languages):
    conn.executemany("""
        INSERT INTO github_languages
            (username, repo_name, language, bytes, percentage)
        VALUES (?, ?, ?, ?, ?)
    """, [
        (l["username"], l["repo_name"], l["language"], l["bytes"], l["percentage"])
        for l in languages
    ])
    conn.commit()


def fetch_and_store(usernames, token=None):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    headers = get_headers(token)
    conn = sqlite3.connect(DB_PATH)
    create_github_schema(conn)

    for username in usernames:
        print(f"\nFetching profile: {username}")
        profile = fetch_user_profile(username, headers)
        if not profile:
            print(f"  Skipped (not found or API error)")
            continue

        save_profile(conn, profile)
        print(f"  Profile saved: {profile['public_repos']} repos, {profile['followers']} followers")

        repos = fetch_user_repos(username, headers)
        save_repos(conn, repos)
        print(f"  Repos saved: {len(repos)} non-fork repositories")

        all_langs = []
        for repo in repos[:10]:
            langs = fetch_repo_languages(username, repo["repo_name"], headers)
            all_langs.extend(langs)

        save_languages(conn, all_langs)
        print(f"  Languages indexed: {len(all_langs)} entries across repos")

    conn.close()
    print(f"\nGitHub data stored in: {DB_PATH}")


def main():
    token = os.environ.get("GITHUB_TOKEN")

    if len(sys.argv) > 1:
        usernames = sys.argv[1:]
    else:
        usernames = ["torvalds", "gvanrossum", "yyx990803"]
        print("No usernames provided. Using defaults for demo.")
        print("Usage: python github_fetcher.py <username1> <username2> ...")

    if not token:
        print("Warning: No GITHUB_TOKEN env var set. Rate limits will be very low (60/hr).")
        print("Set it with: export GITHUB_TOKEN=ghp_your_token_here\n")

    fetch_and_store(usernames, token)


if __name__ == "__main__":
    main()
