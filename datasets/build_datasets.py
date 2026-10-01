"""Create the annotated V1 datasets. Labels are an initial single-annotator gold set."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INTENT_TRAIN = {
    "PROJECT_DESCRIPTION": [
        "I need a project for NLP and I am working alone.",
        "This is for a machine learning course lasting eight weeks.",
        "I have to build something for my cybersecurity class.",
        "We are a team of three and the deadline is one semester.",
        "The professor wants a project that uses named entity recognition.",
        "I am starting from a vague idea about student advising.",
        "Our course project has to demonstrate text classification.",
        "I have four weeks and I want an academic NLP project.",
    ],
    "ADD_REQUIREMENT": [
        "Let's add a browser extension.",
        "Also include a confidence score.",
        "We should also support export to CSV.",
        "Add a dashboard for the results.",
        "Please include an admin review screen.",
        "And let's add email notifications.",
        "Include a history of previous classifications.",
        "Let's add a requirement for audit logs.",
    ],
    "REMOVE_REQUIREMENT": [
        "Let's remove the mobile application.",
        "Remove facial recognition.",
        "Drop the blockchain payment system.",
        "Delete the admin panel.",
        "Get rid of the real-time monitoring feature.",
        "Scrap the drone control requirement.",
        "Please remove the second database.",
        "Remove the requirement for offline mode.",
    ],
    "MODIFY_REQUIREMENT": [
        "Change the confidence score to a percentage.",
        "Modify the dashboard so it only shows flagged emails.",
        "Update the report to include evidence sentences.",
        "Instead of a graph, show a table of results.",
        "Make the classifier explain its decision.",
        "Change the login requirement to guest access.",
        "Update the existing search requirement.",
        "Modify the export requirement to use JSON.",
    ],
    "ASK_QUESTION": [
        "What does the professor usually expect in the report?",
        "How should I cite the dataset?",
        "Which section of the spec describes testing?",
        "What is the difference between these two ideas?",
        "Where would the model run?",
        "Why is PostgreSQL suggested?",
        "When should I lock the core idea?",
        "What open questions are still missing?",
    ],
    "ASK_FEASIBILITY": [
        "Is it feasible to fine-tune BERT in five weeks?",
        "Can we actually train a model with this dataset size?",
        "Is it possible to finish a browser extension and the API?",
        "Will it fit in a six week solo project?",
        "Can one student deploy both web and mobile?",
        "Is real-time inference feasible on a laptop?",
        "Can we actually test facial recognition without hardware?",
        "Is it possible to complete the API and the tests?",
    ],
    "SELECT_IDEA": [
        "I select idea 2.",
        "Let's go with the phishing detector.",
        "I will take idea 1.",
        "Choose idea 4.",
        "Select the academic requirement analyzer.",
        "I'll go with idea 3.",
        "Select idea 5.",
        "I choose the log analysis idea.",
    ],
    "REJECT_IDEA": [
        "Reject idea 2.",
        "I don't like idea 4.",
        "Skip idea 1.",
        "Reject the drone idea.",
        "I don't like idea 3.",
        "Skip idea 5.",
        "Reject idea 1.",
        "I don't like the citation detector idea.",
    ],
    "REQUEST_GRILL": [
        "Grill me on this project.",
        "Enter grill mode.",
        "Find the weaknesses before we compile the prompt.",
        "Tear this apart.",
        "Grill mode please.",
        "Find the weaknesses in the requirements.",
        "Please grill this specification.",
        "Look for weaknesses.",
    ],
    "REQUEST_PROFESSIONAL_REVIEW": [
        "Give me a professional review.",
        "Professional mode please.",
        "Review this as a supervisor.",
        "I want a supervisor review.",
        "Professional review of the current state.",
        "Review this like a project supervisor.",
        "Please run professional mode.",
        "Supervisor review before we finalize.",
    ],
    "CHANGE_TECHNOLOGY": [
        "Use BERT and PostgreSQL.",
        "Switch the backend from Python to Java.",
        "Let's use React instead of Flutter.",
        "Replace MySQL with PostgreSQL.",
        "Use FastAPI for the backend.",
        "Change the model to DistilBERT.",
        "Switch to MongoDB.",
        "Use Python rather than Java.",
    ],
    "CHANGE_SCOPE": [
        "I want something related to cybersecurity.",
        "Narrow the scope to email classification only.",
        "Expand the scope to include a mobile client.",
        "Let's pivot toward education technology.",
        "Reduce the scope to a command-line tool.",
        "Change direction toward academic writing.",
        "Move toward a smaller prototype.",
        "Increase the scope of the evaluation.",
    ],
    "FINALIZE_PROJECT": [
        "Finalize the project.",
        "Lock the spec.",
        "We are done with requirements.",
        "Mark the project ready.",
        "Finalize the requirements now.",
        "Lock the project specification.",
        "I want to finalize.",
        "We are done. Finalize it.",
    ],
    "GENERATE_PROMPT": [
        "Generate the prompt.",
        "Compile the final prompt.",
        "Export the agent prompt.",
        "Generate a prompt for Cursor.",
        "Compile the prompt from the specification.",
        "Create the final coding prompt.",
        "Generate the prompt now.",
        "Export the prompt for Codex.",
    ],
}

INTENT_TEST = {
    "PROJECT_DESCRIPTION": [
        "I need a project for NLP. I am working alone and have five weeks.",
        "Our professor expects a software project in computer networks.",
    ],
    "ADD_REQUIREMENT": [
        "Let's add a browser extension.",
        "Also include a confusion-matrix page.",
    ],
    "REMOVE_REQUIREMENT": [
        "Let's remove the mobile application.",
        "Remove facial recognition.",
    ],
    "MODIFY_REQUIREMENT": [
        "Change the result page to show the confidence score first.",
        "Update the existing login requirement.",
    ],
    "ASK_QUESTION": [
        "What database did we already choose?",
        "How many requirements are active?",
    ],
    "ASK_FEASIBILITY": [
        "Is it feasible to add a browser extension in five weeks?",
        "Can we actually evaluate the model this term?",
    ],
    "SELECT_IDEA": [
        "Select idea 1.",
        "I will take the phishing analyzer.",
    ],
    "REJECT_IDEA": [
        "Reject idea 5.",
        "I don't like idea 2.",
    ],
    "REQUEST_GRILL": [
        "Grill mode.",
        "Find the weaknesses.",
    ],
    "REQUEST_PROFESSIONAL_REVIEW": [
        "Professional review.",
        "Review this as a supervisor.",
    ],
    "CHANGE_TECHNOLOGY": [
        "Use BERT and PostgreSQL.",
        "Switch the backend to Java.",
    ],
    "CHANGE_SCOPE": [
        "I want something related to cybersecurity.",
        "Narrow the scope to classification only.",
    ],
    "FINALIZE_PROJECT": [
        "Finalize the project.",
        "Lock the spec.",
    ],
    "GENERATE_PROMPT": [
        "Generate the prompt.",
        "Compile the final prompt.",
    ],
}

SIMILARITY = [
    ("Detect phishing emails.", "Identify malicious email messages.", 3, "SUPPORTS"),
    ("Provide a confidence score.", "Show how sure the classifier is.", 3, "SUPPORTS"),
    ("The backend must use Python.", "The server should be written in Python.", 3, "SUPPORTS"),
    ("Store results in PostgreSQL.", "Use Postgres as the database.", 3, "SUPPORTS"),
    ("Add a browser extension.", "Add a Chrome extension for Gmail.", 2, "EXTENDS"),
    ("Classify emails.", "Build a web dashboard.", 1, "UNRELATED"),
    ("Detect phishing emails.", "Add facial recognition.", 0, "UNRELATED"),
    ("The backend must use Python.", "The backend must use Java.", 1, "CONTRADICTS"),
    ("Tokenize the email body.", "Split the message into tokens.", 3, "SUPPORTS"),
    ("Named entity recognition on email headers.", "Extract organizations from the header.", 2, "SUPPORTS"),
    ("Avoid a basic sentiment application.", "Do not build a simple sentiment demo.", 3, "SUPPORTS"),
    ("Real-time email monitoring.", "Batch classify a mailbox export.", 1, "MODIFIES"),
    ("Add blockchain payments.", "Add a drone control panel.", 0, "UNRELATED"),
    ("Generate a specification.", "Compile an agent-ready prompt.", 1, "EXTENDS"),
    ("Team of one.", "I am working alone.", 3, "SUPPORTS"),
    ("Six week deadline.", "The project lasts six weeks.", 3, "SUPPORTS"),
    ("Add a mobile application.", "Add an Android and iOS client.", 2, "EXTENDS"),
    ("Explain the classification.", "Show which tokens influenced the label.", 2, "SUPPORTS"),
    ("Use BERT.", "Fine-tune a transformer encoder.", 2, "SUPPORTS"),
    ("Store users passwords in plain text.", "Hash and salt credentials.", 0, "CONTRADICTS"),
]

DRIFT = [
    ("Classify phishing emails", "Identify malicious email messages", 0),
    ("Classify phishing emails", "Provide a confidence score for the email label", 0),
    ("Classify phishing emails", "Add a browser extension for the classifier", 0),
    ("Classify phishing emails", "Add facial recognition", 1),
    ("Classify phishing emails", "Control a drone from the dashboard", 1),
    ("Classify phishing emails", "Add a blockchain payment system", 1),
    ("Extract requirements from a brief", "Link duplicate requirements", 0),
    ("Extract requirements from a brief", "Add object detection for classroom photos", 1),
    ("Analyze security logs", "Rank suspicious log lines", 0),
    ("Analyze security logs", "Build a social network", 1),
    ("Detect unsupported citations", "Extract citation strings", 0),
    ("Detect unsupported citations", "Add cryptocurrency mining", 1),
]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    train = [{"text": text, "intent": label} for label, texts in INTENT_TRAIN.items() for text in texts]
    test = [{"text": text, "intent": label} for label, texts in INTENT_TEST.items() for text in texts]
    write_jsonl(ROOT / "intent_train.jsonl", train)
    write_jsonl(ROOT / "intent_test.jsonl", test)
    pairs = []
    for text_a, text_b, similarity, relationship in SIMILARITY:
        pairs.append({
            "text_a": text_a,
            "text_b": text_b,
            "intent": "",
            "relationship": relationship,
            "similarity": similarity,
        })
    write_jsonl(ROOT / "similarity.jsonl", pairs)
    write_jsonl(ROOT / "relationship.jsonl", pairs)
    write_jsonl(
        ROOT / "drift_validation.jsonl",
        [{"objective": a, "requirement": b, "drift": label} for a, b, label in DRIFT],
    )
    conversations = ROOT / "conversations"
    conversations.mkdir(exist_ok=True)
    for index, (name, payload) in enumerate(_conversations(), start=1):
        (conversations / f"{index:02d}_{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(train)} train intents, {len(test)} test intents, {len(pairs)} pairs")


def _conversations():
    return [
        ("stable_project", {
            "messages": ["I need an NLP project. I am working alone for six weeks. Classify short reviews."],
            "expect": {"subject": "NLP", "team_size": 1, "conflict": False},
        }),
        ("requirement_additions", {
            "messages": ["Build an NLP email classifier.", "Let's add a confidence score."],
            "expect": {"added": "confidence score"},
        }),
        ("requirement_removal", {
            "messages": ["Let's add a mobile application.", "Let's remove the mobile application."],
            "expect": {"removed": "mobile"},
        }),
        ("technology_replacement", {
            "messages": ["The backend must use Python.", "Switch the backend from Python to Java."],
            "expect": {"technology_change": "Java"},
        }),
        ("explicit_contradiction", {
            "messages": ["The backend must use Python.", "The backend must use Java."],
            "expect": {"conflict": True},
        }),
        ("scope_creep", {
            "messages": ["Classify phishing emails with NLP.", "Let's add a mobile app.", "Also include a browser extension."],
            "expect": {"scope": True},
        }),
        ("project_drift", {
            "messages": ["Maybe an NLP-based phishing detector.", "And let's add facial recognition."],
            "expect": {"drift": True, "domain": "Computer Vision"},
        }),
        ("related_changes", {
            "messages": ["Classify phishing emails.", "Let's add a confidence score.", "Also include an explanation of the indicators."],
            "expect": {"drift": False},
        }),
        ("conflicting_technical_requirements", {
            "messages": ["Use PostgreSQL.", "Use MySQL as the database."],
            "expect": {"conflict": True},
        }),
        ("final_specification", {
            "messages": ["I need an NLP project. I am working alone and have five weeks. Maybe an NLP-based phishing detector. Use BERT and PostgreSQL."],
            "expect": {"specification": True, "prompt": True},
        }),
    ]


if __name__ == "__main__":
    main()
