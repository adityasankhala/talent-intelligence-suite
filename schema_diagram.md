# Database Schema Diagram

## talent_analytics.db

```mermaid
erDiagram
    candidates {
        INTEGER id PK
        TEXT name
        TEXT email
        TEXT phone
        TEXT department
        TEXT role
        TEXT location
        TEXT source
        INTEGER experience_years
        TEXT skills
        INTEGER quality_score
        TEXT current_stage
        TEXT applied_date
        TEXT last_stage_date
        INTEGER time_in_pipeline_days
    }

    stage_transitions {
        INTEGER id PK
        INTEGER candidate_id FK
        TEXT stage_name
        INTEGER stage_order
        TEXT entered_date
    }

    github_profiles {
        TEXT username PK
        TEXT name
        TEXT bio
        INTEGER public_repos
        INTEGER followers
        INTEGER following
        TEXT created_at
        TEXT location
        TEXT company
    }

    github_repos {
        INTEGER id PK
        TEXT username FK
        TEXT repo_name
        TEXT description
        TEXT language
        INTEGER stars
        INTEGER forks
        INTEGER open_issues
        INTEGER size_kb
        TEXT created_at
        TEXT updated_at
        TEXT pushed_at
    }

    github_languages {
        INTEGER id PK
        TEXT username FK
        TEXT repo_name
        TEXT language
        INTEGER bytes
        REAL percentage
    }

    github_scores {
        TEXT username PK
        INTEGER activity_score
        INTEGER diversity_score
        INTEGER overall_score
        TEXT computed_at
    }

    candidates ||--o{ stage_transitions : "has stages"
    github_profiles ||--o{ github_repos : "owns"
    github_profiles ||--o{ github_languages : "uses"
    github_profiles ||--|| github_scores : "scored"
```

## Table Descriptions

| Table | Records | Purpose |
|-------|---------|---------|
| `candidates` | 3,000 | Applicant profiles with department, source, quality score, and funnel stage |
| `stage_transitions` | ~10,400 | Every stage a candidate entered, with timestamps for bottleneck analysis |
| `github_profiles` | Variable | GitHub user metadata fetched via REST API |
| `github_repos` | Variable | Non-fork repositories per user with stars, forks, and language |
| `github_languages` | Variable | Per-repo language byte distribution for diversity scoring |
| `github_scores` | Variable | Computed activity and diversity scores (1-100 scale) |
