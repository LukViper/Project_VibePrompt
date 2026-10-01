"""Targeted adversarial Grill — claim/assumption → entity → ontology attack."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.schemas.assertions import AssertionStatus, AssumptionRisk, ClaimSource
from app.schemas.grill_entities import GrillAttack, GrillAttackStatus, GrillTargetType
from app.schemas.grill_ontology import AttackOntology
from app.services.integrity_store import add_assumption, add_claim
from app.services.grill_attack_generators import _next_attack_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Import target_fingerprint carefully — may live in grill_session
def _fingerprint(state: dict, target_type: str, target_id: str) -> str:
    try:
        from app.services.grill_session import target_fingerprint

        return target_fingerprint(state, target_type, target_id)
    except Exception:
        return f"{target_type}:{target_id}"


_PATTERNS: list[tuple[AttackOntology, re.Pattern[str], str, str, str]] = [
    (
        AttackOntology.RESOURCE_FEASIBILITY,
        re.compile(r"\b(7b|13b|70b|train.*(local|laptop)|vram|gpu|insufficient hardware)\b", re.I),
        "The proposed training/runtime configuration can run on available hardware.",
        "Available hardware may be insufficient for the stated model size or training plan.",
        "What hardware (GPU VRAM/CPU RAM) or optimization strategy makes this feasible?",
    ),
    (
        AttackOntology.DATA_AVAILABILITY,
        re.compile(r"\b(no dataset|without a dataset|unlabeled|lack of data)\b", re.I),
        "A suitable dataset exists and is obtainable.",
        "No concrete dataset or collection plan is recorded.",
        "Name a concrete dataset or collection method with licensing constraints.",
    ),
    (
        AttackOntology.LATENCY,
        re.compile(r"\b(real[- ]?time|low latency|milliseconds|streaming)\b", re.I),
        "The system meets an unspecified real-time / latency goal.",
        "Real-time is claimed without a measurable latency threshold.",
        "What maximum end-to-end latency is acceptable, and how will it be measured?",
    ),
    (
        AttackOntology.EVALUATION,
        re.compile(r"\b(99\.99%|perfect accuracy|100% accuracy|without evaluation)\b", re.I),
        "The accuracy/quality target is achievable and measurable.",
        "Aggressive quality targets lack an evaluation methodology.",
        "Define metrics, baselines, and a validation dataset for this target.",
    ),
    (
        AttackOntology.SCOPE,
        re.compile(r"\b(blockchain|iot|mobile|cloud).{0,40}(blockchain|iot|mobile|cloud)|four weeks.{0,30}(ai|ml|blockchain)\b", re.I),
        "All listed platforms/features fit the timeline and team.",
        "Scope spans multiple heavy subsystems relative to stated constraints.",
        "Which capabilities are MVP-critical vs deferred?",
    ),
    (
        AttackOntology.TIMELINE,
        re.compile(r"\b(solo|one person|alone).{0,40}(week|weeks)|two weeks.{0,40}(production|enterprise)\b", re.I),
        "Timeline and staffing are sufficient for the stated scope.",
        "Staffing/timeline may be incompatible with scope.",
        "What is the minimum viable slice for this team and duration?",
    ),
    (
        AttackOntology.SECURITY,
        re.compile(r"\b(security|threat|auth).{0,40}(without|no).{0,20}(threat model|auth)|without a threat model\b", re.I),
        "Security posture is adequate without further modeling.",
        "Security-sensitive work lacks an explicit threat model.",
        "What threats are in scope and which controls are mandatory?",
    ),
    (
        AttackOntology.DEPLOYMENT,
        re.compile(r"\b(production).{0,40}(without|no).{0,20}(monitor)|without monitoring\b", re.I),
        "Production deployment is safe without monitoring.",
        "Production intent lacks observability requirements.",
        "What monitoring, alerting, and rollback criteria are required?",
    ),
    (
        AttackOntology.RELIABILITY,
        re.compile(r"\b(high availability|ha|99\.9).{0,40}(without|no).{0,20}(redundan)|without redundancy\b", re.I),
        "Availability targets are achievable with the stated architecture.",
        "Availability claims lack redundancy/failover design.",
        "What redundancy and failure modes does the architecture cover?",
    ),
    (
        AttackOntology.ARCHITECTURE_MISMATCH,
        re.compile(r"\b(rest poll|polling).{0,40}(real[- ]?time|latency)|websocket.{0,40}(batch)\b", re.I),
        "Chosen transport/architecture satisfies latency/consistency needs.",
        "Architecture choice may conflict with stated interaction requirements.",
        "How does the current architecture satisfy the interaction/latency constraint?",
    ),
    (
        AttackOntology.TECHNOLOGY_JUSTIFICATION,
        re.compile(r"\b(bert|transformer|llm|kubernetes|kafka).{0,30}(because|just|simply)?\b", re.I),
        "The selected technology is justified by project constraints.",
        "Technology choice may be unsupported by evidence or necessity.",
        "What evidence or constraint justifies this technology over simpler alternatives?",
    ),
    (
        AttackOntology.REQUIREMENT_AMBIGUITY,
        re.compile(r"\b(appropriate|suitable|etc\.|and so on|as needed|somehow)\b", re.I),
        "Requirements are precise enough to implement and test.",
        "Ambiguous language prevents verifiable acceptance criteria.",
        "Replace vague terms with measurable acceptance criteria.",
    ),
    (
        AttackOntology.SCALABILITY,
        re.compile(r"\b(millions of users|scale to|single vm|one server).{0,40}(million|scale|users)\b|\bsingle vm\b", re.I),
        "The stated capacity fits the proposed topology.",
        "Scale claims may exceed the stated architecture.",
        "What capacity plan and topology support the stated scale?",
    ),
    (
        AttackOntology.COST,
        re.compile(r"\b(budget.*(0|zero|none)|\$0).{0,60}(kubernetes|paid|managed)|managed kubernetes.{0,40}(budget|\$0)\b", re.I),
        "Budget covers the proposed managed services.",
        "Cost assumptions contradict free/zero budget constraints.",
        "Which paid dependencies are eliminated to fit budget?",
    ),
    (
        AttackOntology.CONTRADICTION,
        re.compile(r"\b(offline[- ]only).{0,40}(cloud|api)|cloud.{0,40}offline[- ]only\b", re.I),
        "Requirements are mutually consistent.",
        "Stated requirements contradict each other.",
        "Which requirement is authoritative when modes conflict?",
    ),
    (
        AttackOntology.DEPENDENCY,
        re.compile(r"\b(unmaintained|abandoned).{0,30}(library|dependency)|core crypto\b", re.I),
        "Critical dependencies are maintained and trustworthy.",
        "Core functionality depends on a risky/unmaintained library.",
        "Name a supported alternative dependency and migration plan.",
    ),
    (
        AttackOntology.MAINTAINABILITY,
        re.compile(r"\b(no tests|without (tests|ci)|no ci).{0,40}(production|launch)\b", re.I),
        "The system is maintainable with stated quality practices.",
        "Launch plan lacks tests/CI needed for maintainability.",
        "What minimum test and CI gates are required before launch?",
    ),
]


def ensure_assumption_targets(state: dict, narrative: str) -> list[dict]:
    """Materialize ASSUMPTION entities for risky claims found in narrative/state."""
    created = []
    blob = " ".join(
        [
            narrative or "",
            str((state.get("project") or {}).get("objective") or ""),
            " ".join(r.get("text") or "" for r in (state.get("requirements") or []) if r.get("status") == "active"),
        ]
    )
    existing_texts = {str(a.get("text") or "").lower() for a in (state.get("assumptions") or [])}
    for ontology, pattern, claim, _issue, _q in _PATTERNS:
        if not pattern.search(blob):
            continue
        if claim.lower() in existing_texts:
            continue
        asm = add_assumption(
            state,
            text=claim,
            status=AssertionStatus.PROPOSED,
            risk_level=AssumptionRisk.HIGH if ontology in {
                AttackOntology.RESOURCE_FEASIBILITY,
                AttackOntology.DATA_AVAILABILITY,
                AttackOntology.LATENCY,
                AttackOntology.SCOPE,
            } else AssumptionRisk.MEDIUM,
            source=ClaimSource.LLM_INFERENCE,
            reason=f"targeted grill pattern:{ontology.value}",
        )
        add_claim(
            state,
            text=claim,
            source=ClaimSource.LLM_INFERENCE,
            status=AssertionStatus.MENTIONED,
            reason=f"grill-derived claim:{ontology.value}",
        )
        created.append({"assumption": asm, "ontology": ontology.value})
        existing_texts.add(claim.lower())
    return created


def generate_targeted_attacks(state: dict) -> list[dict]:
    """Generate ontology-typed attacks against concrete ProjectState entities."""
    narrative = " ".join(
        [
            str((state.get("project") or {}).get("objective") or ""),
            " ".join(r.get("text") or "" for r in (state.get("requirements") or []) if r.get("status") == "active"),
            " ".join(a.get("text") or "" for a in (state.get("assumptions") or [])),
        ]
    )
    ensure_assumption_targets(state, narrative)
    created: list[dict] = []
    blob = narrative.lower()

    for ontology, pattern, claim, issue, question in _PATTERNS:
        if not pattern.search(blob):
            continue
        target_type, target_id, target_text = _resolve_target(state, ontology, claim)
        fingerprint = _fingerprint(state, target_type.value, target_id)
        duplicate = any(
            a.get("attack_type") == ontology.value
            and a.get("target_id") == target_id
            and a.get("status") in {"OPEN", "UNRESOLVED"}
            for a in (state.get("grill_attacks") or [])
        )
        if duplicate:
            continue
        attack = GrillAttack(
            id=_next_attack_id(state),
            target_type=target_type,
            target_id=target_id,
            attack_type=ontology.value,
            claim=claim,
            challenge=question,
            rationale=issue,
            evidence_required=f"Evidence addressing: {issue}",
            failure_condition=(
                f"Implementation may proceed while the {ontology.value} issue on {target_id} remains unresolved."
            ),
            severity="HIGH" if ontology in {
                AttackOntology.RESOURCE_FEASIBILITY,
                AttackOntology.DATA_AVAILABILITY,
                AttackOntology.LATENCY,
                AttackOntology.SCOPE,
                AttackOntology.RELIABILITY,
            } else "MEDIUM",
            status=GrillAttackStatus.OPEN,
            created_at=_now(),
            blocking=ontology in {
                AttackOntology.RESOURCE_FEASIBILITY,
                AttackOntology.DATA_AVAILABILITY,
                AttackOntology.LATENCY,
                AttackOntology.SCOPE,
                AttackOntology.RELIABILITY,
            },
        ).as_dict()
        attack["target_fingerprint"] = fingerprint
        attack["target_text"] = target_text
        state.setdefault("grill_attacks", []).append(attack)
        created.append(attack)
    return created


def _resolve_target(state: dict, ontology: AttackOntology, claim: str) -> tuple[GrillTargetType, str, str]:
    """Pick a concrete ProjectState entity; ontology preferred type wins over generic matches."""
    preferred = {
        AttackOntology.TIMELINE: GrillTargetType.CONSTRAINT,
        AttackOntology.COST: GrillTargetType.CONSTRAINT,
        AttackOntology.SCOPE: GrillTargetType.CONSTRAINT,
        AttackOntology.TECHNOLOGY_JUSTIFICATION: GrillTargetType.DECISION,
        AttackOntology.DEPENDENCY: GrillTargetType.DECISION,
        AttackOntology.ARCHITECTURE_MISMATCH: GrillTargetType.ARCHITECTURE,
        AttackOntology.RELIABILITY: GrillTargetType.ARCHITECTURE,
        AttackOntology.DEPLOYMENT: GrillTargetType.ARCHITECTURE,
        AttackOntology.ASSUMPTION: GrillTargetType.ASSUMPTION,
        AttackOntology.EVALUATION: GrillTargetType.CLAIM,
        AttackOntology.RESOURCE_FEASIBILITY: GrillTargetType.ASSUMPTION,
        AttackOntology.DATA_AVAILABILITY: GrillTargetType.ASSUMPTION,
        AttackOntology.SCALABILITY: GrillTargetType.ASSUMPTION,
        AttackOntology.SECURITY: GrillTargetType.ASSUMPTION,
        AttackOntology.MAINTAINABILITY: GrillTargetType.ASSUMPTION,
        AttackOntology.LATENCY: GrillTargetType.REQUIREMENT,
        AttackOntology.REQUIREMENT_AMBIGUITY: GrillTargetType.REQUIREMENT,
        AttackOntology.CONTRADICTION: GrillTargetType.REQUIREMENT,
    }.get(ontology)

    if preferred == GrillTargetType.CONSTRAINT:
        return GrillTargetType.CONSTRAINT, "CONSTRAINT", json_safe_constraints(state)
    if preferred == GrillTargetType.DECISION:
        decisions = state.get("decisions") or []
        if decisions:
            d = decisions[-1]
            return GrillTargetType.DECISION, str(d.get("id") or f"DEC-{len(decisions)}"), d.get("summary") or claim
        return GrillTargetType.DECISION, "DEC-IMPLICIT", claim
    if preferred == GrillTargetType.ARCHITECTURE:
        arch = state.get("architecture") or {}
        return GrillTargetType.ARCHITECTURE, "ARCH", str(arch.get("summary") or arch.get("style") or claim)
    if preferred == GrillTargetType.CLAIM:
        for cl in state.get("claims") or []:
            text = str(cl.get("text") or "")
            if claim.lower() in text.lower() or text.lower() in claim.lower():
                return GrillTargetType.CLAIM, cl["id"], text or claim
        claims = state.get("claims") or []
        if claims:
            c = claims[-1]
            return GrillTargetType.CLAIM, c["id"], c.get("text") or claim
        return GrillTargetType.CLAIM, "CLM-IMPLICIT", claim
    if preferred == GrillTargetType.ASSUMPTION:
        for asm in state.get("assumptions") or []:
            text = str(asm.get("text") or "")
            if claim.lower() in text.lower() or text.lower() in claim.lower():
                return GrillTargetType.ASSUMPTION, asm["id"], text or claim
        assumptions = state.get("assumptions") or []
        if assumptions:
            a = assumptions[-1]
            return GrillTargetType.ASSUMPTION, a["id"], a.get("text") or claim
    if preferred == GrillTargetType.REQUIREMENT:
        keywords = {
            AttackOntology.LATENCY: ("real-time", "latency", "ms"),
            AttackOntology.REQUIREMENT_AMBIGUITY: ("appropriate", "suitable", "etc", "somehow"),
            AttackOntology.CONTRADICTION: ("offline", "cloud"),
        }.get(ontology, ())
        for req in state.get("requirements") or []:
            if req.get("status") != "active":
                continue
            text = (req.get("text") or "").lower()
            if not keywords or any(k in text for k in keywords):
                return GrillTargetType.REQUIREMENT, req["id"], req.get("text") or claim

    keywords = {
        AttackOntology.LATENCY: ("real-time", "latency", "ms"),
        AttackOntology.DATA_AVAILABILITY: ("dataset", "data", "corpus", "phishing"),
        AttackOntology.RESOURCE_FEASIBILITY: ("train", "model", "gpu", "7b", "vram"),
        AttackOntology.SECURITY: ("security", "auth", "threat", "pii"),
        AttackOntology.EVALUATION: ("accuracy", "evaluate", "metric"),
        AttackOntology.DEPLOYMENT: ("deploy", "production", "monitor"),
        AttackOntology.RELIABILITY: ("availability", "redundan", "failover"),
        AttackOntology.TECHNOLOGY_JUSTIFICATION: ("bert", "kubernetes", "kafka", "redis"),
        AttackOntology.ARCHITECTURE_MISMATCH: ("rest", "websocket", "api", "polling"),
        AttackOntology.SCOPE: ("blockchain", "iot", "mobile", "cloud"),
        AttackOntology.TIMELINE: ("week", "solo", "deadline"),
        AttackOntology.REQUIREMENT_AMBIGUITY: ("appropriate", "suitable", "etc", "somehow"),
        AttackOntology.SCALABILITY: ("million", "scale", "vm"),
        AttackOntology.COST: ("budget", "$0", "paid"),
        AttackOntology.CONTRADICTION: ("offline", "cloud"),
        AttackOntology.DEPENDENCY: ("unmaintained", "library", "crypto"),
        AttackOntology.MAINTAINABILITY: ("test", "ci", "launch"),
        AttackOntology.ASSUMPTION: ("assum",),
    }.get(ontology, ())
    for req in state.get("requirements") or []:
        if req.get("status") != "active":
            continue
        text = (req.get("text") or "").lower()
        if any(k in text for k in keywords):
            return GrillTargetType.REQUIREMENT, req["id"], req.get("text") or claim
    for asm in state.get("assumptions") or []:
        text = str(asm.get("text") or "")
        if claim.lower() in text.lower() or text.lower() in claim.lower():
            return GrillTargetType.ASSUMPTION, asm["id"], text or claim
    active = [r for r in (state.get("requirements") or []) if r.get("status") == "active"]
    if active:
        return GrillTargetType.REQUIREMENT, active[0]["id"], active[0].get("text") or claim
    return GrillTargetType.PROJECT, "PROJECT", (state.get("project") or {}).get("objective") or claim


def json_safe_constraints(state: dict) -> str:
    c = state.get("constraints") or {}
    parts = []
    if c.get("team_size") is not None:
        parts.append(f"team_size={c['team_size']}")
    if c.get("duration"):
        parts.append(f"duration={c['duration']}")
    if c.get("budget"):
        parts.append(f"budget={c['budget']}")
    return ", ".join(parts) or "constraints"