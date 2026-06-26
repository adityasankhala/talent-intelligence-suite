import csv
import os
import re
import sys
import json

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

SKILL_TAXONOMY = {
    "must_have": {
        "Excel": {
            "weight": 15,
            "keywords": ["excel", "spreadsheet", "vlookup", "pivot table", "pivot tables", "xlookup", "conditional formatting"],
        },
        "SQL": {
            "weight": 15,
            "keywords": ["sql", "mysql", "postgresql", "sqlite", "t-sql", "pl/sql", "database queries", "relational database"],
        },
        "Power BI": {
            "weight": 12,
            "keywords": ["power bi", "powerbi", "dax", "power query", "data visualization", "bi dashboards"],
        },
        "Data Visualization": {
            "weight": 8,
            "keywords": ["tableau", "data visualization", "dashboard", "charts", "reporting", "data studio", "looker"],
        },
        "Automation": {
            "weight": 10,
            "keywords": ["automation", "power automate", "automate", "workflow automation", "rpa", "scripting", "copilot", "co-pilot"],
        },
        "AI / ML Basics": {
            "weight": 8,
            "keywords": ["artificial intelligence", "machine learning", "ai", "ml", "nlp", "deep learning", "neural network"],
        },
        "Analytical Skills": {
            "weight": 7,
            "keywords": ["analytical", "problem solving", "problem-solving", "data analysis", "data-driven", "quantitative", "statistical"],
        },
        "Technical Mindset": {
            "weight": 5,
            "keywords": ["coding", "programming", "developer", "engineer", "technical", "software development"],
        },
    },
    "good_to_have": {
        "Agent-Based Systems": {
            "weight": 6,
            "keywords": ["agentic", "agent-based", "autonomous agent", "multi-agent", "langchain", "llm agents"],
        },
        "Data Pipelines": {
            "weight": 5,
            "keywords": ["data pipeline", "etl", "data engineering", "airflow", "data integration", "api", "apis", "rest api"],
        },
        "Python": {
            "weight": 5,
            "keywords": ["python", "pandas", "numpy", "flask", "fastapi", "django", "jupyter"],
        },
        "TA Analytics": {
            "weight": 4,
            "keywords": ["talent acquisition", "talent analytics", "recruitment analytics", "hr tech", "ats", "applicant tracking",
                         "talent intelligence", "sourcing", "hiring metrics", "time to hire", "time-to-hire"],
        },
    },
}


def extract_text_from_pdf(pdf_path):
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required for PDF parsing. Install it: pip install pdfplumber")

    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


def extract_candidate_name(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        first_line = lines[0]
        if len(first_line) < 60 and not re.search(r'@|http|www|\d{5,}', first_line):
            return first_line
    return "Unknown Candidate"


def extract_email(text):
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else None


def match_skills(text):
    text_lower = text.lower()
    matched = {"must_have": {}, "good_to_have": {}}
    total_score = 0
    max_score = 0

    for category in ["must_have", "good_to_have"]:
        for skill_name, config in SKILL_TAXONOMY[category].items():
            max_score += config["weight"]
            found = False

            for keyword in config["keywords"]:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text_lower):
                    found = True
                    break

            if found:
                matched[category][skill_name] = config["weight"]
                total_score += config["weight"]

    return matched, total_score, max_score


def process_single_resume(file_path):
    text = extract_text_from_file(file_path)
    name = extract_candidate_name(text)
    email = extract_email(text)
    matched, score, max_score = match_skills(text)
    pct = round(score * 100.0 / max_score, 1) if max_score > 0 else 0

    must_have_matched = list(matched["must_have"].keys())
    good_to_have_matched = list(matched["good_to_have"].keys())

    all_must_have = list(SKILL_TAXONOMY["must_have"].keys())
    all_good_to_have = list(SKILL_TAXONOMY["good_to_have"].keys())
    must_have_missing = [s for s in all_must_have if s not in must_have_matched]
    good_to_have_missing = [s for s in all_good_to_have if s not in good_to_have_matched]

    return {
        "file": os.path.basename(file_path),
        "name": name,
        "email": email,
        "match_score": score,
        "max_score": max_score,
        "match_pct": pct,
        "must_have_matched": must_have_matched,
        "must_have_missing": must_have_missing,
        "good_to_have_matched": good_to_have_matched,
        "good_to_have_missing": good_to_have_missing,
    }


def process_batch(resume_dir):
    results = []
    supported_exts = {".pdf", ".txt", ".md"}

    for fname in sorted(os.listdir(resume_dir)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in supported_exts:
            continue

        fpath = os.path.join(resume_dir, fname)
        try:
            result = process_single_resume(fpath)
            results.append(result)
        except Exception as e:
            results.append({
                "file": fname,
                "name": "ERROR",
                "email": None,
                "match_score": 0,
                "max_score": 0,
                "match_pct": 0,
                "must_have_matched": [],
                "must_have_missing": [],
                "good_to_have_matched": [],
                "good_to_have_missing": [],
                "error": str(e),
            })

    results.sort(key=lambda r: r["match_pct"], reverse=True)
    return results


def export_results_csv(results, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank", "File", "Candidate Name", "Email", "Match Score",
            "Max Score", "Match %", "Must-Have Matched", "Must-Have Missing",
            "Good-to-Have Matched", "Good-to-Have Missing"
        ])

        for rank, r in enumerate(results, 1):
            writer.writerow([
                rank,
                r["file"],
                r["name"],
                r["email"] or "N/A",
                r["match_score"],
                r["max_score"],
                r["match_pct"],
                "; ".join(r["must_have_matched"]),
                "; ".join(r["must_have_missing"]),
                "; ".join(r["good_to_have_matched"]),
                "; ".join(r["good_to_have_missing"]),
            ])


def main():
    resume_dir = os.path.join(os.path.dirname(__file__), "..", "sample_resumes")

    if len(sys.argv) > 1:
        target = sys.argv[1]
        if os.path.isdir(target):
            resume_dir = target
        elif os.path.isfile(target):
            result = process_single_resume(target)
            print(json.dumps(result, indent=2, default=str))
            return
        else:
            print(f"Path not found: {target}")
            return

    if not os.path.isdir(resume_dir):
        print(f"Resume directory not found: {resume_dir}")
        print("Create sample_resumes/ folder with .txt or .pdf files.")
        return

    files = [f for f in os.listdir(resume_dir) if os.path.splitext(f)[1].lower() in {".pdf", ".txt", ".md"}]
    if not files:
        print(f"No resume files found in {resume_dir}")
        return

    print(f"Processing {len(files)} resume(s) from {resume_dir}...\n")
    results = process_batch(resume_dir)

    csv_output = os.path.join(REPORTS_DIR, "candidate_match_ranking.csv")
    export_results_csv(results, csv_output)

    print(f"{'Rank':<6} {'Name':<25} {'Match %':>8} {'Must-Have':>10} {'Good-to-Have':>13}")
    print(f"{'-' * 65}")

    for rank, r in enumerate(results, 1):
        mh = f"{len(r['must_have_matched'])}/{len(r['must_have_matched']) + len(r['must_have_missing'])}"
        gth = f"{len(r['good_to_have_matched'])}/{len(r['good_to_have_matched']) + len(r['good_to_have_missing'])}"
        print(f"{rank:<6} {r['name']:<25} {r['match_pct']:>7}% {mh:>10} {gth:>13}")

    print(f"\nRanked results exported to: {csv_output}")


if __name__ == "__main__":
    main()
