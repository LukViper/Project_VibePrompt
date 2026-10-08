"""Hybrid requirement, constraint, and entity extraction.

Rules and lexicons run first. Optional LLM JSON is accepted only after
Pydantic validation and is merged into the rule result, never trusted alone.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, ValidationError

from app.nlp.lexicon import (
    DATABASES,
    DOMAIN_PATTERNS,
    FRAMEWORKS,
    HARDWARE,
    LANGUAGES,
    MODELS,
)
from app.nlp.preprocessing import preprocess

WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
}


class ExtractedRequirement(BaseModel):
    type: str = "functional"
    text: str
    slot: str | None = None
    slot_value: str | None = None
    domain: str | None = None
    actor: str | None = None
    acceptance: str | None = None
    capability: str | None = None


def enrich_requirement_structure(req: ExtractedRequirement) -> ExtractedRequirement:
    """Infer actor / capability / acceptance when not already set."""
    text = req.text
    actor = req.actor
    capability = req.capability
    acceptance = req.acceptance
    if not actor:
        match = re.search(
            r"\b(the )?(user|student|admin|analyst|developer|instructor|system|api client)s?\b",
            text,
            re.I,
        )
        if match:
            actor = match.group(2).lower()
        elif req.type == "functional":
            actor = "user"
    if not capability:
        match = re.search(
            r"\b(must|should|shall|need to|can)\s+(.+)$",
            text,
            re.I,
        )
        if match:
            capability = match.group(2).strip(" .")
        else:
            capability = text
    if not acceptance and req.type == "functional":
        acceptance = f"Given a typical input, the system {capability or text}."
    return req.model_copy(update={
        "actor": actor,
        "capability": capability,
        "acceptance": acceptance,
    })



class ExtractionResult(BaseModel):
    requirements: list[ExtractedRequirement] = Field(default_factory=list)
    technology: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    hardware: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    subject: str | None = None
    team_size: int | None = None
    duration: str | None = None
    budget: str | None = None
    required_topics: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    problem: str | None = None
    objective: str | None = None
    removal_target: str | None = None
    core_idea_proposed: bool = False
    method: str = "rules"


class LLMExtraction(BaseModel):
    requirements: list[ExtractedRequirement] = Field(default_factory=list)
    technology: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    hardware: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    subject: str | None = None
    team_size: int | None = None
    duration: str | None = None
    budget: str | None = None
    required_topics: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    problem: str | None = None
    objective: str | None = None


def _scan_lexicon(text: str, lexicon: dict[str, str]) -> list[str]:
    lowered = text.lower()
    found = []
    for needle, canonical in lexicon.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", lowered) and canonical not in found:
            found.append(canonical)
    return found


def _normalize_domain_text(text: str) -> str:
    """Correct common domain typos before lexicon matching."""
    lowered = (text or "").lower()
    replacements = [
        (r"\bdata\s*scienc\w*\b", "data science"),
        (r"\bdatascienc\w*\b", "data science"),
        (r"\bcompu\w{0,4}ter\s*netw\w*\b", "computer networks"),
        (r"\bcompu\w{0,4}ter\s*net\b", "computer networks"),
        (r"\bnetwroks?\b", "networks"),
        (r"\bcyber\s*secu?r?i?ty\b", "cybersecurity"),
        (r"\bciber\b", "cyber"),
    ]
    for pattern, repl in replacements:
        lowered = re.sub(pattern, repl, lowered, flags=re.I)
    return lowered


def detect_domains(text: str) -> list[str]:
    lowered = _normalize_domain_text(text)
    found = []
    for domain, patterns in DOMAIN_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns) and domain not in found:
            found.append(domain)
    # Informal combo: "Cyber and Computer" / "Cyber + Computer" ⇒ networks too.
    if (
        "cybersecurity" in found
        and "computer_networks" not in found
        and re.search(r"\bcomputers?\b", lowered)
        and "vision" not in lowered
    ):
        found.append("computer_networks")
    return found


def compose_subject_label(domains: list[str], *, fallback: str | None = None) -> str | None:
    """Build a stable multi-domain subject like 'Cybersecurity + Computer Networks'."""
    from app.nlp.lexicon import DOMAIN_LABELS

    order = [
        "data_science",
        "cybersecurity",
        "computer_networks",
        "nlp",
        "computer_vision",
        "blockchain",
        "mobile",
        "drone",
    ]
    labels = [DOMAIN_LABELS[d] for d in order if d in domains and d in DOMAIN_LABELS]
    # Preserve any extra domains not in the preferred order.
    for domain in domains:
        label = DOMAIN_LABELS.get(domain)
        if label and label not in labels:
            labels.append(label)
    if len(labels) >= 2:
        return " + ".join(labels)
    if len(labels) == 1:
        return labels[0]
    return fallback


def _duration(text: str) -> str | None:
    match = re.search(
        r"\b(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s+"
        r"(week|month|semester|day)s?\b",
        text,
        re.I,
    )
    if not match:
        return None
    raw = match.group(1).lower()
    count = WORD_NUMBERS.get(raw, int(raw) if raw.isdigit() else None)
    unit = match.group(2).lower()
    if count is None:
        return f"{match.group(1)} {unit}"
    label = unit if count == 1 else f"{unit}s"
    return f"{count} {label}"


def _team_size(text: str) -> int | None:
    lowered = text.lower()
    if re.search(r"\b(working alone|by myself|on my own|solo|just me|i am alone)\b", lowered):
        return 1
    match = re.search(r"\b(?:team|group) of (\d+)\b", lowered)
    if match:
        return int(match.group(1))
    match = re.search(r"\bwe are (\d+|two|three|four|five)\b", lowered)
    if match:
        raw = match.group(1)
        return WORD_NUMBERS.get(raw, int(raw) if raw.isdigit() else None)
    return None


_SUBJECT_STOP = {
    "with", "using", "and", "or", "to", "for", "in", "on", "a", "an", "the",
    "my", "our", "this", "that", "something", "anything", "project", "course",
    "ideas", "idea", "prototype", "detailed", "more", "other",
}


def _subject(text: str) -> str | None:
    # Prefer composed multi-domain subjects so "Cyber + Computer Networks" does not
    # collapse to whichever single label is checked first.
    domains = detect_domains(text)
    composed = compose_subject_label(domains)
    if composed and (" + " in composed or len(domains) == 1):
        # Single known domain from lexicon, or an explicit multi-domain combo.
        if len(domains) >= 2:
            return composed
    normalized = _normalize_domain_text(text)
    if re.search(r"\bNLP\b|natural language processing", text, re.I):
        domains = list(dict.fromkeys([*domains, "nlp"]))
    if re.search(r"\bcyber(?:security)?\b", normalized, re.I):
        domains = list(dict.fromkeys([*domains, "cybersecurity"]))
    if re.search(
        r"\b(computer\s+networks?|computer\s+networking|networking)\b",
        normalized,
        re.I,
    ):
        domains = list(dict.fromkeys([*domains, "computer_networks"]))
    if re.search(r"\b(data\s*science|foundation(?:s)? of data science)\b", normalized, re.I):
        domains = list(dict.fromkeys([*domains, "data_science"]))
    composed = compose_subject_label(domains)
    if composed and " + " in composed:
        return composed
    if "data_science" in domains:
        return "Data Science"
    if re.search(r"\bmachine learning\b", text, re.I):
        return "Machine Learning"
    if composed:
        return composed
    # Short subject-only turns: "for computer networks?", "about NLP", "in cybersecurity"
    short = re.search(
        r"^\s*(?:for|about|in|on|regarding)\s+([A-Za-z][A-Za-z0-9 +/\-]{1,40})\s*\??\s*$",
        text.strip(),
        re.I,
    )
    if short:
        value = short.group(1).strip(" .?")
        if value and value.lower() not in _SUBJECT_STOP and len(value.split()) <= 5:
            short_domains = detect_domains(value)
            short_label = compose_subject_label(short_domains)
            if short_label:
                return short_label
            # Only accept bare short subjects when they look like a course topic,
            # not conversational filler ("for ideas", "about something").
            if not re.search(
                r"\b(ideas?|project|something|help|me|this|that|please|suggest)\b",
                value,
                re.I,
            ):
                return value.title() if value.islower() else value
    match = re.search(
        r"\b(?:project|course|subject|class) (?:is |for |in |on |about )?"
        r"([A-Za-z][A-Za-z0-9 +/]{1,40})",
        text,
        re.I,
    )
    if match:
        value = match.group(1).strip(" .")
        value = re.split(
            r"\b(I|The|and|Professor|working|with|using|to|for)\b",
            value,
            flags=re.I,
        )[0].strip(" .")
        # Drop filler lead-ins like "on foundation of data science" fragments.
        value = re.sub(r"^(on|about|for|in)\s+", "", value, flags=re.I).strip()
        if value and value.lower() not in _SUBJECT_STOP:
            lowered = value.lower()
            value_domains = detect_domains(value)
            value_label = compose_subject_label(value_domains)
            if value_label:
                return value_label
            if lowered in {"nlp", "natural language processing"}:
                return "NLP"
            if re.search(r"\bcomputer\s+networks?\b", lowered):
                return "Computer Networks"
            if "data science" in lowered or "foundation" in lowered and "data" in lowered:
                return "Data Science"
            if lowered.startswith("on ") or lowered in {"on", "about", "something"}:
                return None
            return value
    return None


def merge_subject_labels(existing: str | None, incoming: str | None) -> str | None:
    """Union subject labels so later turns do not erase a prior domain."""
    if not incoming:
        return existing
    if not existing:
        return incoming
    if existing.strip().lower() == incoming.strip().lower():
        return existing

    def _parts(label: str) -> list[str]:
        return [p.strip() for p in re.split(r"\s*\+\s*", label) if p.strip()]

    merged: list[str] = []
    for part in _parts(existing) + _parts(incoming):
        if not any(part.lower() == m.lower() for m in merged):
            merged.append(part)
    # Map known labels back through domain ids for stable ordering.
    from app.nlp.lexicon import DOMAIN_LABELS

    reverse = {v.lower(): k for k, v in DOMAIN_LABELS.items()}
    domain_ids = []
    extras = []
    for part in merged:
        key = reverse.get(part.lower())
        if key:
            domain_ids.append(key)
        else:
            extras.append(part)
    composed = compose_subject_label(list(dict.fromkeys(domain_ids)))
    if composed and extras:
        return " + ".join([composed, *extras])
    if composed:
        return composed
    return " + ".join(merged)


def _split_items(blob: str) -> list[str]:
    blob = re.sub(r"\s+and\s+", ", ", blob, flags=re.I)
    items = []
    for part in blob.split(","):
        cleaned = part.strip(" .;")
        cleaned = re.sub(r"^(a|an|the)\s+", "", cleaned, flags=re.I)
        if cleaned and cleaned.lower() not in {"and", "or"}:
            items.append(cleaned)
    return items


def _normalize_avoid_phrase(phrase: str) -> str:
    phrase = phrase.strip(" .;:")
    phrase = re.sub(r"[-_]", " ", phrase)
    phrase = re.sub(r"^(?:using|adding|building|calling|including)\s+", "", phrase, flags=re.I)
    phrase = re.sub(r"\b(application|app|system|project)$", "", phrase, flags=re.I).strip()
    phrase = re.sub(r"^(a|an|the)\s+", "", phrase, flags=re.I)
    return phrase.strip(" .")


def _is_rejection_utterance(text: str) -> bool:
    """True when the utterance forbids/rejects a feature rather than requiring it."""
    return bool(
        re.search(
            r"(?:"
            r"(?:don't|do not|never|must not|shall not)\s+"
            r"(?:add|use|include|call|build|enable|install|introduce|support|rely on)|"
            r"\bavoid\s+(?:using|adding|building|calling|including)|"
            r"(?:don't|do not)\s+want\s+to\s+(?:build|make|do|use|add)|"
            r"\bnot\s+(?:a|an)\s+"
            r")\b",
            text,
            re.I,
        )
    )


def _avoid(text: str) -> list[str]:
    patterns = [
        r"(?:don't|do not) want to (?:build|make|do)\s+(.+)",
        r"(?:don't|do not) want\s+(.+)",
        r"\bavoid(?: building)?\s+(.+)",
        r"\bnot (?:a|an)\s+(.+)",
        # Explicit forbid polarity: "do not add X", "never use Y", "avoid using Z"
        r"(?:don't|do not|never|must not|shall not)\s+"
        r"(?:add|use|include|call|build|enable|install|introduce|support|rely on)\s+(.+)",
        r"\bavoid\s+(?:using|adding|building|calling|including)\s+(.+)",
        r"\bno\s+(?:adding|using)\s+(.+)",
    ]
    found = []
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        phrase = _normalize_avoid_phrase(match.group(1))
        if phrase and phrase not in found:
            found.append(phrase)
    return found


def _split_polarity_sentences(sentences: list[str]) -> tuple[list[str], list[str]]:
    """Partition sentences into positive (may yield requirements) vs rejection (avoid only)."""
    positive: list[str] = []
    avoid_items: list[str] = []
    for sentence in sentences:
        sent_avoid = _avoid(sentence)
        if sent_avoid or _is_rejection_utterance(sentence):
            for item in sent_avoid:
                if item not in avoid_items:
                    avoid_items.append(item)
            # If patterns missed the object, keep a cleaned remnant for avoid.
            if not sent_avoid and _is_rejection_utterance(sentence):
                cleaned = re.sub(
                    r"^(?:please\s+)?(?:don't|do not|never|must not|shall not)\s+"
                    r"(?:add|use|include|call|build|enable|install|introduce|support|rely on)\s+",
                    "",
                    sentence,
                    flags=re.I,
                )
                cleaned = re.sub(
                    r"^(?:please\s+)?avoid\s+(?:using|adding|building|calling|including)\s+",
                    "",
                    cleaned,
                    flags=re.I,
                )
                phrase = _normalize_avoid_phrase(cleaned)
                if phrase and phrase not in avoid_items:
                    avoid_items.append(phrase)
        else:
            positive.append(sentence)
    return positive, avoid_items


def _required_topics(text: str) -> list[str]:
    match = re.search(
        r"(?:professor expects|required topics|must cover|should cover|expects us to cover)\s+(.+)",
        text,
        re.I,
    )
    if not match:
        return []
    return _split_items(match.group(1).strip(" ."))


def _clean_requirement(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = re.sub(
        r"^(and |also )?(the system should|system should|should|must|need to|let's|lets|please)\s+",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"^(add|include)\s+(a|an|the)\s+", "", text, flags=re.I)
    text = text[:1].upper() + text[1:] if text else text
    return text


def _functional_clauses(sentence: str, technologies: list[str]) -> list[str]:
    working = sentence
    for tech in technologies:
        working = re.sub(rf"\busing {re.escape(tech)}\b", "", working, flags=re.I)
    working = re.sub(r"\s+", " ", working).strip(" .")
    if re.search(r"\b(and|&)\b", working) and re.search(r"\b(classify|provide|detect|display|store|generate|support)\b", working, re.I):
        parts = re.split(r"\s+and\s+", working, flags=re.I)
    else:
        parts = [working]
    clauses = []
    for part in parts:
        if re.search(r"\b(should|must|need to|shall|let's add|add a|add an)\b", sentence, re.I) or re.search(
            r"\b(classify|detect|provide|display|identify|monitor|analyze|analyse)\b", part, re.I
        ):
            cleaned = _clean_requirement(part)
            if len(cleaned) > 3:
                clauses.append(cleaned)
    return clauses


def _removal_target(text: str) -> str | None:
    match = re.search(r"\b(?:remove|drop|delete|scrap|get rid of)\s+(?:the\s+)?(.+)", text, re.I)
    if not match:
        return None
    return match.group(1).strip(" .")


def _slot_assignments(text: str, languages: list[str], databases: list[str], frameworks: list[str], models: list[str]) -> list[ExtractedRequirement]:
    assignments = []
    lowered = text.lower()
    backend = None
    if re.search(r"\bbackend\b", lowered):
        backend = languages[0] if languages else (frameworks[0] if frameworks else None)
    elif languages and re.search(r"\b(use|using|switch to)\b", lowered):
        backend = languages[0]
    if backend:
        assignments.append(ExtractedRequirement(
            type="constraint",
            text=f"The backend must use {backend}",
            slot="backend",
            slot_value=backend,
        ))
    if databases:
        assignments.append(ExtractedRequirement(
            type="constraint",
            text=f"Use {databases[0]} as the database",
            slot="database",
            slot_value=databases[0],
        ))
    if models:
        assignments.append(ExtractedRequirement(
            type="constraint",
            text=f"Use {models[0]} as the model",
            slot="model",
            slot_value=models[0],
        ))
    return assignments


def _propose_core_idea(text: str, domains: list[str]) -> tuple[str | None, str | None, bool]:
    lowered = text.lower()
    if "phishing" in lowered and re.search(r"\b(detector|detection|classifier|analyzer|analyser)\b", lowered):
        return "Detect phishing emails", "NLP-based phishing detection", True
    if re.search(r"\b(maybe|idea|build|want)\b", lowered) and re.search(r"\b(detector|classifier|analyzer|system|platform)\b", lowered):
        phrase = text.strip(" .")
        return phrase, phrase, True
    if domains and re.search(r"\brelated to\b", lowered):
        return None, None, False
    return None, None, False


def extract_information(text: str) -> ExtractionResult:
    prepared = preprocess(text)
    body = prepared["text"]
    positive_sentences, avoid_items = _split_polarity_sentences(prepared["sentences"] or [body])
    # Also catch whole-utterance avoid patterns (single-sentence preprocess edge cases).
    for item in _avoid(body):
        if item not in avoid_items:
            avoid_items.append(item)

    # Lexicon / tech adoption only from non-rejection sentences so forbidden tech
    # (e.g. "Do not add Redis") is never treated as selected stack.
    positive_body = " ".join(positive_sentences).strip() or (
        "" if (_is_rejection_utterance(body) or avoid_items) else body
    )
    languages = _scan_lexicon(positive_body, LANGUAGES) if positive_body else []
    frameworks = _scan_lexicon(positive_body, FRAMEWORKS) if positive_body else []
    databases = _scan_lexicon(positive_body, DATABASES) if positive_body else []
    hardware = _scan_lexicon(positive_body, HARDWARE) if positive_body else []
    models = _scan_lexicon(positive_body, MODELS) if positive_body else []
    domains = detect_domains(positive_body) if positive_body else detect_domains(body)
    technology = []
    for item in languages + frameworks + databases + models + hardware:
        if item not in technology:
            technology.append(item)

    requirements: list[ExtractedRequirement] = []
    removal = _removal_target(body)
    # Rejection-only utterances must not invent positive requirements or tech slots.
    if not removal and positive_body:
        for sentence in positive_sentences:
            for clause in _functional_clauses(sentence, technology):
                if any(req.text.lower() == clause.lower() for req in requirements):
                    continue
                domain = detect_domains(clause)
                requirements.append(enrich_requirement_structure(ExtractedRequirement(
                    type="functional",
                    text=clause,
                    domain=domain[0] if domain else None,
                )))
        add_match = re.search(r"\b(?:add|include)\s+(?:a|an|the)?\s*(.+)", positive_body, re.I)
        if add_match and not requirements and not _is_rejection_utterance(positive_body):
            phrase = _clean_requirement(add_match.group(1))
            domain = detect_domains(phrase)
            requirements.append(enrich_requirement_structure(ExtractedRequirement(
                type="functional",
                text=phrase,
                domain=domain[0] if domain else (domains[0] if len(domains) == 1 else None),
            )))
        requirements.extend(_slot_assignments(positive_body, languages, databases, frameworks, models))

    # If the utterance only forbids something, treat the avoid phrase as removal target
    # so ProjectState can deactivate a prior positive match of the same feature.
    if not removal and avoid_items and not positive_sentences:
        removal = avoid_items[0]

    problem, objective, proposed = _propose_core_idea(body, domains)
    # Do not propose a core idea from a pure rejection utterance.
    if avoid_items and not positive_sentences:
        problem, objective, proposed = None, None, False

    result = ExtractionResult(
        requirements=requirements,
        technology=technology,
        programming_languages=languages,
        frameworks=frameworks,
        databases=databases,
        hardware=hardware,
        models=models,
        subject=_subject(body if not (_is_rejection_utterance(body) and not positive_body) else positive_body or body),
        team_size=_team_size(body),
        duration=_duration(body),
        budget=_budget(body),
        required_topics=_required_topics(body),
        avoid=avoid_items,
        domains=domains,
        problem=problem,
        objective=objective,
        removal_target=removal,
        core_idea_proposed=proposed,
        method="rules+lexicon",
    )
    return result


def _budget(text: str) -> str | None:
    match = re.search(r"\bbudget(?: of)?\s+([$€£]?\d[\d,]*)", text, re.I)
    if match:
        return match.group(1)
    if re.search(r"\bno budget\b", text, re.I):
        return "none"
    return None


def merge_validated_llm(base: ExtractionResult, payload: dict) -> ExtractionResult:
    try:
        extra = LLMExtraction.model_validate(payload)
    except ValidationError:
        base.method = base.method + "+llm_rejected"
        return base
    data = base.model_dump()
    for field in ("subject", "team_size", "duration", "budget", "problem", "objective"):
        if data.get(field) in (None, "", []) and getattr(extra, field):
            data[field] = getattr(extra, field)
    for field in ("technology", "programming_languages", "frameworks", "databases", "hardware", "models", "required_topics", "avoid", "domains"):
        for item in getattr(extra, field):
            if item not in data[field]:
                data[field].append(item)
    existing = {req["text"].lower() for req in data["requirements"]}
    for req in extra.requirements:
        if req.text.lower() not in existing:
            data["requirements"].append(req.model_dump())
    # Polarity: LLM positives must not restate avoid (lazy import avoids cycle with project_state).
    avoid = list(data.get("avoid") or [])
    if avoid:
        from app.services.project_state import _text_matches_avoid

        kept_reqs = []
        for req in data["requirements"]:
            text = req.get("text") or ""
            slot_value = req.get("slot_value")
            if _text_matches_avoid(text, avoid):
                continue
            if slot_value and _text_matches_avoid(str(slot_value), avoid):
                continue
            kept_reqs.append(req)
        data["requirements"] = kept_reqs
        for field in (
            "technology",
            "programming_languages",
            "frameworks",
            "databases",
            "hardware",
            "models",
        ):
            data[field] = [
                item for item in (data.get(field) or [])
                if not _text_matches_avoid(str(item), avoid)
            ]
    data["method"] = base.method + "+llm_validated"
    return ExtractionResult.model_validate(data)
