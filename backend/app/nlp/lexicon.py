"""Shared lexicons for extraction, drift, and scope analysis.

These lists are deterministic project-engineering knowledge, not a substitute
for embeddings or NLI. They give the hybrid pipeline a rule baseline.
"""

from __future__ import annotations

LANGUAGES = {
    "python": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "dart": "Dart",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "c#": "C#",
    "c++": "C++",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
}

FRAMEWORKS = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "react": "React",
    "flutter": "Flutter",
    "spring": "Spring",
    "express": "Express",
    "vue": "Vue",
    "angular": "Angular",
    "next.js": "Next.js",
    "nextjs": "Next.js",
}

DATABASES = {
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "sqlite": "SQLite",
    "redis": "Redis",
}

MODELS = {
    "bert": "BERT",
    "distilbert": "DistilBERT",
    "gpt": "GPT",
    "lstm": "LSTM",
    "sentence transformers": "Sentence Transformers",
    "sentence-transformers": "Sentence Transformers",
    "spacy": "spaCy",
    "svm": "SVM",
    "random forest": "Random Forest",
}

HARDWARE = {
    "raspberry pi": "Raspberry Pi",
    "arduino": "Arduino",
    "esp32": "ESP32",
    "jetson": "Jetson",
    "gpu": "GPU",
}

DOMAIN_PATTERNS: dict[str, list[str]] = {
    "nlp": [
        "nlp",
        "natural language",
        "tokenization",
        "named entity",
        "sentiment",
        "text classification",
        "language model",
    ],
    "cybersecurity": [
        "cybersecurity",
        "cyber security",
        "phishing",
        "malware",
        "vulnerability",
        "intrusion",
    ],
    "computer_vision": [
        "computer vision",
        "facial recognition",
        "face recognition",
        "object detection",
        "image classification",
        "opencv",
    ],
    "mobile": [
        "mobile app",
        "mobile application",
        "android app",
        "ios app",
        "react native",
    ],
    "blockchain": [
        "blockchain",
        "ethereum",
        "smart contract",
        "crypto payment",
        "web3",
    ],
    "drone": ["drone", "uav", "quadcopter"],
    "browser_extension": ["browser extension", "chrome extension", "firefox extension"],
    "web": ["web dashboard", "web application", "web app", "website"],
    "realtime_monitoring": ["real-time email", "realtime monitoring", "real-time monitoring"],
}

DOMAIN_LABELS = {
    "nlp": "NLP",
    "cybersecurity": "Cybersecurity",
    "computer_vision": "Computer Vision",
    "mobile": "Mobile development",
    "blockchain": "Blockchain",
    "drone": "Drone control",
    "browser_extension": "Browser extension development",
    "web": "Web development",
    "realtime_monitoring": "Real-time monitoring",
}

# Delivery channels expand scope; they are not automatically a new research domain.
SCOPE_EXPANSION_DOMAINS = {"mobile", "browser_extension", "web", "realtime_monitoring"}

# Pairs that indicate the new discussion has left the original research domain.
UNRELATED_DOMAIN_PAIRS = {
    frozenset({"nlp", "computer_vision"}),
    frozenset({"nlp", "drone"}),
    frozenset({"nlp", "blockchain"}),
    frozenset({"cybersecurity", "computer_vision"}),
    frozenset({"cybersecurity", "drone"}),
    frozenset({"cybersecurity", "blockchain"}),
    frozenset({"computer_vision", "blockchain"}),
}


def domains_conflict(existing: set[str], incoming: set[str]) -> bool:
    for left in existing:
        for right in incoming:
            if left != right and frozenset({left, right}) in UNRELATED_DOMAIN_PAIRS:
                return True
    return False
