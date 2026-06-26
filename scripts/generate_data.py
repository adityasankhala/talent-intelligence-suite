import sqlite3
import os
import random
from datetime import datetime, timedelta

try:
    from faker import Faker
except ImportError:
    raise SystemExit("Faker is required. Run: pip install Faker")

fake = Faker()
Faker.seed(42)
random.seed(42)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "talent_analytics.db")

DEPARTMENTS = {
    "Engineering": {
        "roles": ["Software Engineer", "Backend Developer", "Frontend Developer", "DevOps Engineer", "QA Engineer"],
        "weight": 0.35,
        "screen_pass": 0.55,
        "tech1_pass": 0.60,
        "tech2_pass": 0.70,
        "mgr_pass": 0.80,
        "offer_accept": 0.75,
        "avg_days_per_stage": [3, 5, 5, 4, 3, 2],
    },
    "Data & Analytics": {
        "roles": ["Data Analyst", "Data Scientist", "BI Developer", "ML Engineer"],
        "weight": 0.20,
        "screen_pass": 0.50,
        "tech1_pass": 0.55,
        "tech2_pass": 0.65,
        "mgr_pass": 0.85,
        "offer_accept": 0.80,
        "avg_days_per_stage": [2, 6, 6, 5, 4, 2],
    },
    "Sales & Marketing": {
        "roles": ["Sales Executive", "Marketing Analyst", "Account Manager", "Growth Strategist"],
        "weight": 0.20,
        "screen_pass": 0.60,
        "tech1_pass": 0.70,
        "tech2_pass": 0.75,
        "mgr_pass": 0.75,
        "offer_accept": 0.70,
        "avg_days_per_stage": [2, 4, 3, 3, 3, 2],
    },
    "Talent Acquisition": {
        "roles": ["TA Specialist", "HR Coordinator", "Sourcing Analyst", "People Operations Associate"],
        "weight": 0.15,
        "screen_pass": 0.65,
        "tech1_pass": 0.72,
        "tech2_pass": 0.78,
        "mgr_pass": 0.90,
        "offer_accept": 0.85,
        "avg_days_per_stage": [1, 3, 3, 3, 2, 1],
    },
    "Product": {
        "roles": ["Product Manager", "Product Analyst", "Technical Product Manager"],
        "weight": 0.10,
        "screen_pass": 0.45,
        "tech1_pass": 0.50,
        "tech2_pass": 0.60,
        "mgr_pass": 0.82,
        "offer_accept": 0.78,
        "avg_days_per_stage": [3, 7, 7, 5, 4, 3],
    },
}

SOURCES = {
    "LinkedIn": 0.40,
    "Referral": 0.20,
    "Job Board": 0.18,
    "Career Site": 0.12,
    "Campus Drive": 0.07,
    "Agency": 0.03,
}

LOCATIONS = [
    "Gurgaon, India", "Bangalore, India", "Hyderabad, India",
    "Singapore", "Tokyo, Japan", "Sydney, Australia",
    "Hong Kong", "Beijing, China",
]

STAGES = ["Applied", "Screened", "Tech Round 1", "Tech Round 2", "Managerial", "Offered", "Hired"]

SKILL_POOL = {
    "Engineering": ["Python", "Java", "JavaScript", "Go", "SQL", "AWS", "Docker", "Kubernetes", "React", "Node.js", "Git", "CI/CD", "REST APIs", "Microservices"],
    "Data & Analytics": ["Python", "SQL", "R", "Power BI", "Tableau", "Excel", "Pandas", "NumPy", "PyTorch", "TensorFlow", "Spark", "ETL", "Statistics"],
    "Sales & Marketing": ["CRM", "Salesforce", "Excel", "Google Analytics", "HubSpot", "SEO", "Content Strategy", "Lead Generation", "Negotiation"],
    "Talent Acquisition": ["Sourcing", "Boolean Search", "Excel", "ATS", "LinkedIn Recruiter", "Workday", "Interview Scheduling", "Employer Branding"],
    "Product": ["Jira", "Agile", "SQL", "Wireframing", "Figma", "Product Strategy", "A/B Testing", "User Research", "PRD Writing", "Roadmapping"],
}


def pick_weighted(options_dict):
    items = list(options_dict.keys())
    weights = list(options_dict.values())
    return random.choices(items, weights=weights, k=1)[0]


def generate_candidate(candidate_id, base_date):
    dept = pick_weighted({d: v["weight"] for d, v in DEPARTMENTS.items()})
    config = DEPARTMENTS[dept]

    role = random.choice(config["roles"])
    source = pick_weighted(SOURCES)
    location = random.choice(LOCATIONS)
    experience_years = random.randint(0, 15)
    skills = random.sample(SKILL_POOL[dept], k=min(random.randint(3, 7), len(SKILL_POOL[dept])))
    quality_score = random.randint(40, 100)

    apply_offset = random.randint(0, 180)
    applied_date = base_date - timedelta(days=apply_offset)

    stage_dates = [applied_date]
    current_stage = "Applied"
    final_stage = "Applied"

    gate_keys = ["screen_pass", "tech1_pass", "tech2_pass", "mgr_pass", "offer_accept"]
    stage_names = ["Screened", "Tech Round 1", "Tech Round 2", "Managerial", "Offered"]

    for i, (gate, stage_name) in enumerate(zip(gate_keys, stage_names)):
        score_bonus = (quality_score - 50) / 200.0
        pass_rate = min(config[gate] + score_bonus, 0.95)

        if random.random() < pass_rate:
            avg_days = config["avg_days_per_stage"][i]
            jitter = random.randint(max(1, avg_days - 2), avg_days + 3)
            next_date = stage_dates[-1] + timedelta(days=jitter)
            stage_dates.append(next_date)
            final_stage = stage_name
        else:
            break

    if final_stage == "Offered":
        accept_rate = config["offer_accept"]
        if random.random() < accept_rate:
            avg_join = config["avg_days_per_stage"][5]
            join_date = stage_dates[-1] + timedelta(days=random.randint(avg_join, avg_join + 5))
            stage_dates.append(join_date)
            final_stage = "Hired"

    time_to_current = (stage_dates[-1] - applied_date).days

    return {
        "id": candidate_id,
        "name": fake.name(),
        "email": fake.email(),
        "phone": fake.phone_number(),
        "department": dept,
        "role": role,
        "location": location,
        "source": source,
        "experience_years": experience_years,
        "skills": ", ".join(skills),
        "quality_score": quality_score,
        "current_stage": final_stage,
        "applied_date": applied_date.strftime("%Y-%m-%d"),
        "last_stage_date": stage_dates[-1].strftime("%Y-%m-%d"),
        "time_in_pipeline_days": time_to_current,
        "stage_dates": stage_dates,
    }


def create_schema(conn):
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS stage_transitions")
    cursor.execute("DROP TABLE IF EXISTS candidates")

    cursor.execute("""
        CREATE TABLE candidates (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            department TEXT NOT NULL,
            role TEXT NOT NULL,
            location TEXT NOT NULL,
            source TEXT NOT NULL,
            experience_years INTEGER,
            skills TEXT,
            quality_score INTEGER,
            current_stage TEXT NOT NULL,
            applied_date TEXT NOT NULL,
            last_stage_date TEXT NOT NULL,
            time_in_pipeline_days INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE stage_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            stage_name TEXT NOT NULL,
            stage_order INTEGER NOT NULL,
            entered_date TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates (id)
        )
    """)

    conn.commit()


def seed_database(conn, candidates):
    cursor = conn.cursor()

    cursor.executemany("""
        INSERT INTO candidates (id, name, email, phone, department, role, location, source,
                                experience_years, skills, quality_score, current_stage,
                                applied_date, last_stage_date, time_in_pipeline_days)
        VALUES (:id, :name, :email, :phone, :department, :role, :location, :source,
                :experience_years, :skills, :quality_score, :current_stage,
                :applied_date, :last_stage_date, :time_in_pipeline_days)
    """, candidates)

    transitions = []
    for c in candidates:
        stage_list = STAGES[:len(c["stage_dates"])]
        for order_idx, (stage_name, stage_date) in enumerate(zip(stage_list, c["stage_dates"])):
            transitions.append({
                "candidate_id": c["id"],
                "stage_name": stage_name,
                "stage_order": order_idx,
                "entered_date": stage_date.strftime("%Y-%m-%d"),
            })

    cursor.executemany("""
        INSERT INTO stage_transitions (candidate_id, stage_name, stage_order, entered_date)
        VALUES (:candidate_id, :stage_name, :stage_order, :entered_date)
    """, transitions)

    conn.commit()


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    base_date = datetime(2026, 6, 27)
    candidates = [generate_candidate(i + 1, base_date) for i in range(3000)]

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    seed_database(conn, candidates)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM candidates")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stage_transitions")
    transitions = cursor.fetchone()[0]
    cursor.execute("SELECT current_stage, COUNT(*) FROM candidates GROUP BY current_stage ORDER BY COUNT(*) DESC")
    distribution = cursor.fetchall()

    conn.close()

    print(f"Database created at: {DB_PATH}")
    print(f"Total candidates seeded: {total}")
    print(f"Total stage transitions logged: {transitions}")
    print(f"Stage distribution:")
    for stage, count in distribution:
        print(f"  {stage}: {count}")


if __name__ == "__main__":
    main()
