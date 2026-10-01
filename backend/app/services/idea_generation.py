"""Project idea generation, semantic deduplication, and constraint filtering.

Produces detailed idea cards (problem, solution, users, architecture, risks, …).
Owned / locked core ideas are respected — generation stores alternatives, does not overwrite.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, ValidationError

from app.config.settings import get_settings
from app.llm.base import TaskKind
from app.llm.gemini import extract_json
from app.llm.prompts import idea_prompt
from app.llm.router import get_provider
from app.models import Idea
from app.nlp.similarity import cluster_by_similarity, most_complete
from app.schemas.state import ConversationStage, migrate_state
from app.services.project_state import public_state, set_stage
from app.services.versioning import StateVersioning


class IdeaDraft(BaseModel):
    title: str
    problem: str = ""
    why_it_matters: str = ""
    solution: str = ""
    users: str = ""
    objective: str = ""
    required_concepts: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    architecture: str = ""
    ai_nlp: str = ""
    data: str = ""
    technology: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    estimated_scope: str = "medium"
    research_extension: str = ""
    risks: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)

    def details_dict(self) -> dict:
        return {
            "why_it_matters": self.why_it_matters,
            "solution": self.solution,
            "users": self.users,
            "architecture": self.architecture,
            "ai_nlp": self.ai_nlp,
            "data": self.data,
            "research_extension": self.research_extension,
            "risks": self.risks,
        }


def generate_ideas(session, project, multi: bool | None = None) -> list[Idea]:
    state = migrate_state(project.state or {})
    multi = get_settings().enable_multi_perspective if multi is None else multi
    provider = get_provider(TaskKind.IDEATION)
    drafts = _from_provider(state) if provider.available else []
    if len(drafts) < 3:
        drafts.extend(_templates(state))
    if multi:
        drafts.extend(_perspective_templates(state))
    drafts = _filter_constraints(drafts, state)
    drafts = _deduplicate(drafts)
    drafts = drafts[:5]
    session.query(Idea).filter(
        Idea.project_id == project.id,
        Idea.selected.is_(False),
        Idea.rejected.is_(False),
    ).delete()
    rows = []
    alternatives = []
    for draft in drafts:
        row = Idea(
            project_id=project.id,
            title=draft.title,
            problem=draft.problem,
            objective=draft.objective,
            required_concepts=draft.required_concepts,
            features=draft.features,
            technology=draft.technology,
            difficulty=draft.difficulty,
            estimated_scope=draft.estimated_scope,
            extensions=draft.extensions,
            details=draft.details_dict(),
            source="gemini" if provider.available else "deterministic_fallback",
            perspective="multi" if multi else "single",
        )
        session.add(row)
        rows.append(row)
        alternatives.append(_idea_summary(draft))
    session.flush()

    # Persist alternatives on ProjectState without overwriting a locked core idea.
    state["idea"]["alternatives"] = alternatives
    if not (state.get("core_idea") or {}).get("locked"):
        state = set_stage(state, ConversationStage.IDEATION)
    state = StateVersioning.bump(state, "generate_ideas")
    project.state = public_state(state)
    StateVersioning.snapshot(session, project, "generate_ideas")
    return rows


def format_ideas_for_chat(ideas: list[Idea]) -> str:
    lines = ["Here are detailed project ideas you can customize or select:"]
    for index, idea in enumerate(ideas, start=1):
        details = idea.details or {}
        lines.append(f"\n{index}. {idea.title}")
        lines.append(f"   Problem: {idea.problem}")
        if details.get("why_it_matters"):
            lines.append(f"   Why it matters: {details['why_it_matters']}")
        if details.get("solution"):
            lines.append(f"   Solution: {details['solution']}")
        if details.get("users"):
            lines.append(f"   Users: {details['users']}")
        lines.append(f"   Objective: {idea.objective}")
        if idea.features:
            lines.append(f"   Features: {', '.join(idea.features[:5])}")
        if details.get("architecture"):
            lines.append(f"   Architecture: {details['architecture']}")
        if details.get("ai_nlp"):
            lines.append(f"   AI/NLP: {details['ai_nlp']}")
        if idea.technology:
            lines.append(f"   Technology: {', '.join(idea.technology)}")
        lines.append(f"   Difficulty: {idea.difficulty}; scope: {idea.estimated_scope}")
        if details.get("research_extension"):
            lines.append(f"   Research extension: {details['research_extension']}")
        if details.get("risks"):
            lines.append(f"   Risks: {', '.join(details['risks'][:3])}")
    lines.append(
        "\nPick an idea with Select below, ask for more ideas, "
        "or tell me the domain/idea you want to work on and we will continue from that."
    )
    return "\n".join(lines)


def wants_ideation(message: str, state: dict) -> bool:
    import re

    if (state.get("core_idea") or {}).get("locked"):
        return False
    return bool(
        re.search(
            r"\b(don'?t know|do not know|not sure|no idea|"
            r"suggest(?:\s+\w+){0,3}\s+ideas?|give me (?:more )?(?:project )?ideas?|"
            r"generate ideas|more (?:project )?ideas|other ideas|different ideas|"
            r"not happy with (these|the) ideas|show (me )?more|"
            r"what (can|should) i (build|make)|brainstorm)\b",
            message,
            re.I,
        )
    )


def _idea_summary(draft: IdeaDraft) -> dict:
    return {
        "title": draft.title,
        "problem": draft.problem,
        "objective": draft.objective,
        "features": draft.features,
        "technology": draft.technology,
        "difficulty": draft.difficulty,
        "estimated_scope": draft.estimated_scope,
        **draft.details_dict(),
    }


def _from_provider(state: dict) -> list[IdeaDraft]:
    provider = get_provider(TaskKind.IDEATION)
    try:
        raw = provider.generate(idea_prompt(state, "balanced"), {"state": state}, task=TaskKind.IDEATION)
        payload = extract_json(raw)
    except Exception:
        return []
    if isinstance(payload, dict):
        payload = payload.get("ideas") or payload.get("candidates") or []
    drafts = []
    for item in payload:
        try:
            drafts.append(IdeaDraft.model_validate(item))
        except ValidationError:
            continue
    return drafts


def _templates(state: dict) -> list[IdeaDraft]:
    subject = (state.get("academic") or {}).get("subject") or ""
    concepts = list((state.get("academic") or {}).get("required_concepts") or [])
    duration = (state.get("constraints") or {}).get("duration") or "the available time"
    objective = (state.get("project") or {}).get("objective") or ""
    problem = (state.get("project") or {}).get("problem") or ""
    direction = ((state.get("exploration") or {}).get("current_direction") or "")
    blob = f"{subject} {objective} {problem} {direction} {concepts}".lower()
    phishing = "phish" in blob
    cyber = "cyber" in blob or phishing or "security" in blob
    data_science = bool(
        re.search(r"\b(data\s*science|foundation of data|churn|forecast|segment|fraud detection)\b", blob)
    )
    nlp = bool(re.search(r"\bnlp\b|natural language|text classif|misinfo", blob))
    ideas: list[IdeaDraft] = []

    if phishing or (cyber and not data_science):
        ideas.append(IdeaDraft(
            title="Context-aware phishing email analyzer",
            problem="Phishing emails imitate legitimate context and bypass keyword filters.",
            why_it_matters="Students and staff still fall for phishing that looks contextually real.",
            solution="Classify phishing emails with explainable NLP indicators and a confidence score.",
            users="Students and SOC analysts reviewing suspicious mail",
            objective="Classify phishing emails and show a confidence score.",
            required_concepts=concepts or ["tokenization", "Named Entity Recognition", "text classification"],
            features=["Email classification", "Confidence score", "Indicator explanation"],
            architecture="Ingest → preprocess → classifier → explanation API → simple review UI",
            ai_nlp="Supervised text classification with optional NER for spoofed entities",
            data="Labeled phishing/ham emails; hold-out evaluation set",
            technology=["Python", "BERT"],
            difficulty="medium",
            estimated_scope="medium",
            research_extension="Compare transformer vs classical TF-IDF baselines on the same split",
            risks=["Dataset bias", "False positives on legitimate marketing mail"],
            extensions=["Browser extension for live mailbox checks"],
        ))
        ideas.extend([
            IdeaDraft(
                title="Automated security log analysis",
                problem="Security logs are too large for a student team to inspect by hand.",
                why_it_matters="Missed anomalies in logs lead to delayed incident response.",
                solution="Classify suspicious log events with NLP features and summarize for analysts.",
                users="Junior security analysts",
                objective="Classify suspicious log events with NLP features.",
                required_concepts=concepts or ["tokenization", "classification"],
                features=["Log ingestion", "Event classification", "Analyst summary"],
                architecture="Log parser → feature pipeline → classifier → dashboard",
                ai_nlp="Sequence/text classification over log lines",
                data="Public or synthetic security logs with labels",
                technology=["Python", "PostgreSQL"],
                difficulty="medium",
                estimated_scope="medium",
                research_extension="Evaluate few-shot labeling for rare event classes",
                risks=["Noisy labels", "Class imbalance"],
                extensions=["Alert export"],
            ),
            IdeaDraft(
                title="Semantic vulnerability assistant",
                problem="Vulnerability descriptions are inconsistent across advisories.",
                why_it_matters="Teams waste time matching reports to known CVEs.",
                solution="Match a reported issue to known vulnerability descriptions with similarity search.",
                users="Developers triaging security reports",
                objective="Match a reported issue to known vulnerability descriptions.",
                required_concepts=concepts or ["semantic similarity"],
                features=["Advisory search", "Similarity ranking", "Evidence snippet"],
                architecture="Advisory index → embeddings → ranked retrieval API",
                ai_nlp="Sentence embeddings + cosine ranking",
                data="CVE/advisory text corpus",
                technology=["Python", "Sentence Transformers"],
                difficulty="medium",
                estimated_scope="medium",
                research_extension="Measure retrieval precision@k against hand-labeled queries",
                risks=["Stale advisory index", "Ambiguous report wording"],
                extensions=["CVE import"],
            ),
        ])

    if data_science or "churn" in blob:
        ideas.extend(_data_science_ideas(concepts, duration))

    if nlp and not phishing:
        ideas.extend([
            IdeaDraft(
                title="Fake citation detector",
                problem="Generated academic text can invent citations.",
                why_it_matters="Fabricated references undermine academic integrity.",
                solution="Detect unsupported citations in writing samples via NER and support checks.",
                users="Instructors and students reviewing drafts",
                objective="Detect unsupported citations in academic writing samples.",
                required_concepts=concepts or ["Named Entity Recognition"],
                features=["Citation extraction", "Support check", "Review report"],
                architecture="Document upload → citation extract → support verifier → report",
                ai_nlp="NER for citations plus heuristic/API verification",
                data="Sample papers with planted fake citations for evaluation",
                technology=["Python", "spaCy"],
                difficulty="medium",
                estimated_scope="small",
                research_extension="Benchmark detection rate vs human spot-checks",
                risks=["Incomplete bibliographic APIs", "False alarms on obscure works"],
                extensions=["Classroom upload page"],
            ),
            IdeaDraft(
                title="Academic requirement analyzer",
                problem="Project briefs hide requirements in unstructured prose.",
                why_it_matters="Missed requirements cause late redesigns in student projects.",
                solution="Extract and link requirements from a project brief into a structured list.",
                users="Student teams writing specs",
                objective="Extract and link requirements from a project brief.",
                required_concepts=concepts or ["requirement extraction"],
                features=["Requirement extraction", "Duplicate linking", "Spec export"],
                architecture="Brief ingest → NLP extract → linking → markdown/spec export",
                ai_nlp="Intent/slot extraction with similarity linking",
                data="Sample briefs with gold requirement spans",
                technology=["Python", "FastAPI"],
                difficulty="medium",
                estimated_scope="medium",
                research_extension="Compare rule+embedding pipeline vs LLM extraction accuracy",
                risks=["Ambiguous brief language", "Over-extraction"],
                extensions=["Conflict report"],
            ),
            IdeaDraft(
                title="Course-forum question classifier",
                problem="Course discussion forums mix urgent blockers with general chit-chat.",
                why_it_matters="TAs waste time sorting messages instead of answering hard questions.",
                solution="Classify forum posts by urgency/topic and route them to the right queue.",
                users="Teaching assistants and instructors",
                objective="Classify course-forum posts by topic and urgency with measurable accuracy.",
                required_concepts=concepts or ["text classification", "evaluation metrics"],
                features=["Post classification", "Urgency flag", "Queue view"],
                architecture="Forum export → preprocess → classifier → TA queue",
                ai_nlp="Supervised text classification",
                data="Labeled forum posts from a course (or a public forum sample)",
                technology=["Python", "scikit-learn"],
                difficulty="low",
                estimated_scope="small",
                research_extension="Compare bag-of-words vs embeddings under the same split",
                risks=["Small labeled set", "Topic drift across terms"],
                extensions=["Slack/Discord ingest"],
            ),
        ])

    if not ideas:
        # Generic but natural starter set — never paste raw subject into "X project prototype".
        ideas.extend(_data_science_ideas(concepts, duration)[:3])
        ideas.append(IdeaDraft(
            title="Academic requirement analyzer",
            problem="Project briefs hide requirements in unstructured prose.",
            why_it_matters="Missed requirements cause late redesigns in student projects.",
            solution="Extract and link requirements from a project brief into a structured list.",
            users="Student teams writing specs",
            objective=objective or "Extract and link requirements from a project brief.",
            required_concepts=concepts or ["requirement extraction"],
            features=["Requirement extraction", "Duplicate linking", "Spec export"],
            architecture="Brief ingest → NLP extract → linking → markdown/spec export",
            ai_nlp="Intent/slot extraction with similarity linking",
            data="Sample briefs with gold requirement spans",
            technology=["Python", "FastAPI"],
            difficulty="medium",
            estimated_scope="medium",
            research_extension="Compare rule+embedding pipeline vs LLM extraction accuracy",
            risks=["Ambiguous brief language", "Over-extraction"],
            extensions=["Conflict report"],
        ))
    return ideas


def _data_science_ideas(concepts: list[str], duration: str) -> list[IdeaDraft]:
    return [
        IdeaDraft(
            title="Customer Churn Prediction with Explainable AI",
            problem="Businesses struggle to spot customers who are about to leave before it is too late.",
            why_it_matters="Early, explainable churn signals let teams act while retention is still possible.",
            solution="Train a churn classifier and surface the top factors driving each prediction.",
            users="Product and customer-success teams",
            objective="Predict which customers are likely to churn and explain the main drivers.",
            required_concepts=concepts or ["supervised learning", "feature importance", "evaluation metrics"],
            features=["Churn score", "Feature explanations", "Evaluation dashboard"],
            architecture="Data prep → model training → explanation layer → simple review UI",
            ai_nlp="Optional text features from support tickets; otherwise tabular ML",
            data="Anonymized customer activity table with churn labels",
            technology=["Python", "scikit-learn", "SHAP"],
            difficulty="medium",
            estimated_scope="medium",
            research_extension="Compare logistic regression vs tree ensembles on the same split",
            risks=["Label leakage", "Class imbalance"],
            extensions=["Retention playbook suggestions"],
        ),
        IdeaDraft(
            title="Sales Forecasting System",
            problem="Manual sales forecasts are inconsistent and hard to defend.",
            why_it_matters="Reliable short-horizon forecasts improve inventory and staffing decisions.",
            solution="Build a time-series forecasting pipeline with baseline comparisons and error reports.",
            users="Operations and sales planning teams",
            objective=f"Forecast near-term sales within {duration} and report prediction error clearly.",
            required_concepts=concepts or ["time series", "train/test split", "error metrics"],
            features=["Forecast chart", "Baseline comparison", "Error report"],
            architecture="Historical ingest → feature engineering → forecaster → dashboard",
            ai_nlp="Not required",
            data="Historical sales by product/region",
            technology=["Python", "pandas", "Prophet or ARIMA"],
            difficulty="medium",
            estimated_scope="medium",
            research_extension="Ablate holiday/promotion features",
            risks=["Sparse history", "Concept drift"],
            extensions=["What-if scenario slider"],
        ),
        IdeaDraft(
            title="Customer Segmentation using Clustering",
            problem="Treating all customers the same wastes marketing effort.",
            why_it_matters="Segments reveal distinct behaviors that deserve different product strategies.",
            solution="Cluster customers on behavioral features and profile each segment.",
            users="Marketing analysts",
            objective="Produce interpretable customer segments with clear profile summaries.",
            required_concepts=concepts or ["clustering", "dimensionality reduction", "feature scaling"],
            features=["Segment explorer", "Profile cards", "Silhouette/quality report"],
            architecture="Feature store extract → clustering → profiling notebook/UI",
            ai_nlp="Optional embedding of free-text feedback",
            data="Customer activity and demographic features",
            technology=["Python", "scikit-learn"],
            difficulty="medium",
            estimated_scope="small",
            research_extension="Compare k-means vs hierarchical clustering stability",
            risks=["Poor feature choice", "Unstable clusters"],
            extensions=["Segment-targeted campaign export"],
        ),
        IdeaDraft(
            title="Fraud Detection using Machine Learning",
            problem="Fraudulent transactions are rare and easy to miss in raw ledgers.",
            why_it_matters="Even a small lift in fraud recall reduces financial and trust damage.",
            solution="Train an imbalanced-class detector with precision-recall focused evaluation.",
            users="Risk analysts",
            objective="Flag likely fraudulent transactions with a reviewable score.",
            required_concepts=concepts or ["classification", "imbalanced learning", "precision-recall"],
            features=["Risk score", "Alert queue", "PR-curve evaluation"],
            architecture="Transaction stream/batch → model → analyst review UI",
            ai_nlp="Not required unless free-text merchant notes are used",
            data="Labeled transaction dataset with rare positive class",
            technology=["Python", "scikit-learn", "XGBoost"],
            difficulty="medium",
            estimated_scope="medium",
            research_extension="Compare resampling strategies under fixed recall targets",
            risks=["Severe class imbalance", "Delayed labels"],
            extensions=["Rule+ML hybrid filter"],
        ),
        IdeaDraft(
            title="Demand Prediction System",
            problem="Over/under-ordering inventory wastes budget and hurts availability.",
            why_it_matters="Demand prediction ties data-science practice to a clear operational outcome.",
            solution="Predict short-term demand and compare against a naive baseline.",
            users="Inventory planners",
            objective="Predict demand for a small catalog and quantify forecast error.",
            required_concepts=concepts or ["regression", "baselines", "cross-validation"],
            features=["Demand forecast", "Baseline gap", "SKU drill-down"],
            architecture="Sales history → features → regressor → planner view",
            ai_nlp="Not required",
            data="SKU-level sales history",
            technology=["Python", "scikit-learn"],
            difficulty="medium",
            estimated_scope="small",
            research_extension="Test lag/feature windows for robustness",
            risks=["Seasonality", "Stockouts truncating observed demand"],
            extensions=["Reorder suggestion"],
        ),
    ]


def _perspective_templates(state: dict) -> list[IdeaDraft]:
    base = _templates(state)
    varied = []
    for idea in base[:3]:
        varied.append(idea.model_copy(update={"title": f"Feasible: {idea.title}", "difficulty": "low", "estimated_scope": "small"}))
        varied.append(idea.model_copy(update={"title": f"Technical: {idea.title}", "technology": idea.technology + ["PostgreSQL"]}))
    return varied


def _filter_constraints(drafts: list[IdeaDraft], state: dict) -> list[IdeaDraft]:
    avoid = [item.lower() for item in (state.get("constraints") or {}).get("avoid") or []]
    rejected = [item.get("title", "").lower() for item in state.get("rejected_ideas") or []]
    kept = []
    for draft in drafts:
        blob = f"{draft.title} {draft.problem} {draft.objective}".lower()
        if any(item and item in blob for item in avoid):
            continue
        if draft.title.lower() in rejected:
            continue
        if draft.estimated_scope == "large" and (state.get("constraints") or {}).get("team_size") == 1:
            draft = draft.model_copy(update={"estimated_scope": "medium", "difficulty": "medium"})
        kept.append(draft)
    return kept


def _deduplicate(drafts: list[IdeaDraft]) -> list[IdeaDraft]:
    payloads = [draft.model_dump() for draft in drafts]
    for item in payloads:
        item["_key"] = f"{item['title']}. {item['problem']}"
    clusters = cluster_by_similarity(payloads, "_key", threshold=0.82)
    chosen = []
    for cluster in clusters:
        best = most_complete(cluster)
        best.pop("_key", None)
        chosen.append(IdeaDraft.model_validate(best))
    return chosen
