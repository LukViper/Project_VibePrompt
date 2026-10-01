"""RQ1 synthetic controlled conversation dataset (≥100 scenarios).

Label: SYNTHETIC CONTROLLED BENCHMARK — no real-world generalization claim.
Gold annotations are stored alongside conversations for post-hoc evaluation only.
"""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.rq1_requirement_preservation.annotations import DATASET_LABEL, GoldAnnotation

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "evaluation" / "datasets" / "rq1"
DATA_PATH = DATA_DIR / "scenarios_v2.json"
LEGACY_PATH = DATA_DIR / "scenarios_v1.json"


def _templates() -> list[dict]:
    """Diverse conversation templates covering RE phenomena."""
    return [
        {
            "messages": [
                "I want a phishing detection system.",
                "Use BERT.",
                "Actually don't use BERT.",
                "Response time must be below 500 ms.",
                "Use PostgreSQL.",
                "Actually PostgreSQL is unnecessary. Use SQLite.",
            ],
            "gold": GoldAnnotation(
                requirements=["phishing detection system", "response time below 500 ms"],
                constraints=["use sqlite"],
                technologies=["sqlite"],
                decisions=["reject bert", "replace postgresql with sqlite"],
                rejected_items=["use bert", "use postgresql"],
                superseded_items=["use postgresql"],
                assertion_origins={
                    "phishing detection system": "USER_EXPLICIT",
                    "response time below 500 ms": "USER_EXPLICIT",
                },
            ),
            "tags": ["explicit", "technology", "removal", "replacement", "constraint"],
        },
        {
            "messages": [
                "Build a log analyzer for security.",
                "Include authentication.",
                "No authentication after all.",
                "Must support CSV export.",
            ],
            "gold": GoldAnnotation(
                requirements=["log analyzer for security", "support csv export"],
                constraints=[],
                technologies=[],
                decisions=["remove authentication"],
                rejected_items=["authentication"],
                superseded_items=[],
                assertion_origins={
                    "log analyzer for security": "USER_EXPLICIT",
                    "support csv export": "USER_EXPLICIT",
                },
            ),
            "tags": ["explicit", "removal", "multi_turn"],
        },
        {
            "messages": [
                "Student NLP project on spam classification.",
                "Team of one, four weeks.",
                "Use TF-IDF first, maybe deep learning later.",
            ],
            "gold": GoldAnnotation(
                requirements=["spam classification"],
                constraints=["team of one", "four weeks", "tf-idf"],
                technologies=["tf-idf"],
                decisions=["prefer tf-idf initially"],
                rejected_items=[],
                superseded_items=[],
                assertion_origins={
                    "spam classification": "USER_EXPLICIT",
                    "tf-idf": "USER_EXPLICIT",
                    "deep learning later": "USER_INFERRED",
                },
            ),
            "tags": ["constraint", "technology", "inferred", "ambiguous"],
        },
        {
            "messages": [
                "We need an inventory API.",
                "It must support CRUD for products.",
                "Add rate limiting under 100 requests per minute.",
                "Wait — make the rate limit 1000 per minute instead.",
            ],
            "gold": GoldAnnotation(
                requirements=["inventory api", "crud for products", "rate limiting 1000 per minute"],
                constraints=["1000 requests per minute"],
                technologies=[],
                decisions=["raise rate limit to 1000"],
                rejected_items=["100 requests per minute"],
                superseded_items=["rate limiting under 100 requests per minute"],
                assertion_origins={
                    "inventory api": "USER_EXPLICIT",
                    "crud for products": "USER_EXPLICIT",
                    "rate limiting 1000 per minute": "USER_EXPLICIT",
                },
            ),
            "tags": ["modification", "constraint", "multi_turn"],
        },
        {
            "messages": [
                "Mobile app for expense tracking.",
                "Use Flutter.",
                "Offline mode is required.",
                "Actually drop offline mode; always-online is fine.",
                "Sync to Firebase.",
            ],
            "gold": GoldAnnotation(
                requirements=["expense tracking", "sync to firebase"],
                constraints=["always-online"],
                technologies=["flutter", "firebase"],
                decisions=["remove offline mode", "use firebase"],
                rejected_items=["offline mode"],
                superseded_items=["offline mode"],
                assertion_origins={
                    "expense tracking": "USER_EXPLICIT",
                    "flutter": "USER_EXPLICIT",
                    "sync to firebase": "USER_EXPLICIT",
                },
            ),
            "tags": ["technology", "removal", "scope_change"],
        },
        {
            "messages": [
                "Recommend something for document search.",
                "Perhaps Elasticsearch would be appropriate.",
                "Must handle PDFs and Word docs.",
                "Budget is zero; prefer open source only.",
            ],
            "gold": GoldAnnotation(
                requirements=["document search", "handle pdfs and word docs"],
                constraints=["budget zero", "open source only"],
                technologies=["elasticsearch"],
                decisions=["prefer open source"],
                rejected_items=[],
                superseded_items=[],
                assertion_origins={
                    "document search": "USER_EXPLICIT",
                    "elasticsearch": "USER_INFERRED",
                    "handle pdfs and word docs": "USER_EXPLICIT",
                },
            ),
            "tags": ["inferred", "ambiguous", "constraint"],
        },
        {
            "messages": [
                "Build a real-time chat backend.",
                "Use WebSocket.",
                "Also support REST polling.",
                "No — drop REST polling; WebSocket only.",
                "Messages must persist in Redis.",
            ],
            "gold": GoldAnnotation(
                requirements=["real-time chat backend", "messages persist in redis"],
                constraints=["websocket only"],
                technologies=["websocket", "redis"],
                decisions=["drop rest polling"],
                rejected_items=["rest polling"],
                superseded_items=["support rest polling"],
                assertion_origins={
                    "real-time chat backend": "USER_EXPLICIT",
                    "websocket": "USER_EXPLICIT",
                    "messages persist in redis": "USER_EXPLICIT",
                },
            ),
            "tags": ["contradiction", "technology", "replacement"],
        },
        {
            "messages": [
                "Academic recommender system for courses.",
                "Use collaborative filtering.",
                "Dataset will somehow be collected later.",
                "Team of three, one semester.",
            ],
            "gold": GoldAnnotation(
                requirements=["course recommender system", "collaborative filtering"],
                constraints=["team of three", "one semester"],
                technologies=["collaborative filtering"],
                decisions=[],
                rejected_items=[],
                superseded_items=[],
                assertion_origins={
                    "course recommender system": "USER_EXPLICIT",
                    "collaborative filtering": "USER_EXPLICIT",
                    "dataset collected later": "USER_INFERRED",
                },
            ),
            "tags": ["ambiguous", "inferred", "constraint"],
        },
        {
            "messages": [
                "I need Kubernetes for a student blog.",
                "Actually Kubernetes is overkill. Use a single VPS.",
                "Nginx + SQLite is enough.",
                "Must support Markdown posts.",
            ],
            "gold": GoldAnnotation(
                requirements=["student blog", "support markdown posts"],
                constraints=["single vps"],
                technologies=["nginx", "sqlite"],
                decisions=["reject kubernetes", "use single vps"],
                rejected_items=["kubernetes"],
                superseded_items=["kubernetes"],
                assertion_origins={
                    "student blog": "USER_EXPLICIT",
                    "support markdown posts": "USER_EXPLICIT",
                    "nginx": "USER_EXPLICIT",
                },
            ),
            "tags": ["technology", "scope_change", "removal"],
        },
        {
            "messages": [
                "Fraud detection pipeline.",
                "Latency must be under 200 ms.",
                "Use Kafka for events.",
                "Do not use Kafka; use a simple queue.",
                "Store features in Redis.",
            ],
            "gold": GoldAnnotation(
                requirements=["fraud detection pipeline", "latency under 200 ms", "store features in redis"],
                constraints=["latency under 200 ms"],
                technologies=["redis", "simple queue"],
                decisions=["replace kafka with simple queue"],
                rejected_items=["kafka"],
                superseded_items=["use kafka for events"],
                assertion_origins={
                    "fraud detection pipeline": "USER_EXPLICIT",
                    "latency under 200 ms": "USER_EXPLICIT",
                    "store features in redis": "USER_EXPLICIT",
                },
            ),
            "tags": ["constraint", "technology", "replacement", "contradiction"],
        },
        {
            "messages": [
                "Build an analytics dashboard.",
                "Support dark mode maybe.",
                "Must export CSV and PDF.",
                "Auth is required.",
            ],
            "gold": GoldAnnotation(
                requirements=["analytics dashboard", "export csv and pdf", "auth is required"],
                constraints=[],
                technologies=[],
                decisions=[],
                rejected_items=[],
                superseded_items=[],
                assertion_origins={
                    "analytics dashboard": "USER_EXPLICIT",
                    "export csv and pdf": "USER_EXPLICIT",
                    "auth is required": "USER_EXPLICIT",
                    "dark mode": "USER_INFERRED",
                },
            ),
            "tags": ["explicit", "inferred", "ambiguous"],
        },
        {
            "messages": [
                "Migrate from monolith to microservices.",
                "Start with the billing module only.",
                "Keep the monolith for everything else.",
                "Use gRPC between services.",
            ],
            "gold": GoldAnnotation(
                requirements=["migrate billing module to microservice", "use grpc between services"],
                constraints=["billing module only"],
                technologies=["grpc"],
                decisions=["partial migration"],
                rejected_items=[],
                superseded_items=[],
                assertion_origins={
                    "migrate billing module to microservice": "USER_EXPLICIT",
                    "use grpc between services": "USER_EXPLICIT",
                },
            ),
            "tags": ["scope_change", "technology", "multi_turn"],
        },
    ]


def generate_rq1_conversations(n: int = 120) -> list[dict]:
    templates = _templates()
    rows: list[dict] = []
    for i in range(n):
        base = templates[i % len(templates)]
        gold = base["gold"]
        # Lexical variant: append a turn index marker that should not change gold
        messages = list(base["messages"])
        if i >= len(templates):
            messages = messages + [f"(Follow-up note for variant {i}: keep prior decisions.)"]
        rows.append(
            {
                "id": f"RQ1-{i + 1:03d}",
                "dataset_label": DATASET_LABEL,
                "synthetic": True,
                "messages": messages,
                "tags": list(base["tags"]),
                "variant": i % len(templates),
                "gold_requirements": list(gold.requirements),
                "gold_constraints": list(gold.constraints),
                "gold_technologies": list(gold.technologies),
                "gold_decisions": list(gold.decisions),
                "rejected": list(gold.rejected_items),
                "superseded": list(gold.superseded_items),
                "assertion_origins": dict(gold.assertion_origins),
            }
        )
    return rows


def write_dataset(n: int = 120, path: Path | None = None) -> Path:
    path = path or DATA_PATH
    rows = generate_rq1_conversations(n=n)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return path


def load_dataset(path: Path | None = None) -> list[dict]:
    path = path or DATA_PATH
    if not path.exists():
        write_dataset(path=path)
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        row.setdefault("dataset_label", DATASET_LABEL)
        row.setdefault("synthetic", True)
    return rows


if __name__ == "__main__":
    out = write_dataset()
    print(json.dumps({"path": str(out), "n": len(load_dataset()), "label": DATASET_LABEL}, indent=2))
