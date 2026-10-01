"""Change / conflict / impact analysis (Master Spec §§8.5, 9–10).

Compares new user intent against ProjectState and returns COMPATIBLE,
SCOPE_CHANGE, CONFLICT, or UNCERTAIN with affected components and options.
Does not silently rewrite the user's platform or auth requirements.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.decisions import ChangeKind, propose_decision
from app.schemas.provenance import ProvenanceSource


_PLATFORM_TOKENS = {
    "android": "Android",
    "ios": "iOS",
    "iphone": "iOS",
    "ipad": "iOS",
    "web": "Web",
    "browser": "Web",
    "pwa": "Web",
    "desktop": "Desktop",
}


def extract_platforms(text: str) -> list[str]:
    lowered = (text or "").lower()
    found: list[str] = []
    for token, label in _PLATFORM_TOKENS.items():
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            if label not in found:
                found.append(label)
    # Prefer canonical mobile trio ordering when all present
    order = ["Android", "iOS", "Web", "Desktop"]
    return [p for p in order if p in found] + [p for p in found if p not in order]


def current_platforms(state: dict) -> list[str]:
    raw = (state.get("project") or {}).get("platform")
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str) and raw.strip():
        return extract_platforms(raw) or [raw.strip()]
    # Infer from technology / requirements text
    blob = " ".join(
        [
            str((state.get("technology") or {}).get("framework") or ""),
            " ".join(str(x) for x in ((state.get("technology") or {}).get("frameworks") or [])),
            " ".join(
                (req.get("text") or "")
                for req in (state.get("requirements") or [])
                if req.get("status") == "active"
            ),
        ]
    )
    inferred = extract_platforms(blob)
    return inferred or ["Web"]  # conservative default when web frameworks mentioned elsewhere


def authentication_required(state: dict) -> bool | None:
    for note in state.get("security") or []:
        text = str(note).lower()
        if "authentication_required=false" in text or "no login" in text or "no auth" in text:
            return False
        if "authentication_required=true" in text or "login required" in text:
            return True
    for req in state.get("requirements") or []:
        if req.get("status") != "active":
            continue
        text = (req.get("text") or "").lower()
        if re.search(r"\b(no login|without (login|sign[- ]?in)|anonymous|no authentication)\b", text):
            return False
        if re.search(r"\b(login|sign[- ]?in|authenticate|private (project|history|account))\b", text):
            return True
    return None


def current_database(state: dict) -> str | None:
    tech = state.get("technology") or {}
    if tech.get("database"):
        return str(tech["database"])
    dbs = tech.get("databases") or []
    if dbs:
        return str(dbs[0])
    engine = (state.get("database") or {}).get("engine")
    return str(engine) if engine else None


def analyze_message_impact(state: dict, message: str) -> dict[str, Any]:
    """Return impact analysis for a user message without mutating state."""
    findings: list[dict[str, Any]] = []
    platforms_new = extract_platforms(message)
    platforms_old = current_platforms(state)

    if platforms_new and set(platforms_new) != set(platforms_old):
        mobile_expand = (
            set(platforms_old) <= {"Web"}
            and "Android" in platforms_new
            and "iOS" in platforms_new
            and "Web" in platforms_new
        )
        affected = [
            "frontend architecture",
            "navigation",
            "state management",
            "deployment",
            "platform APIs",
            "testing",
            "application packaging",
        ]
        alternatives = [
            {
                "name": "Flutter",
                "pros": ["One codebase for Android, iOS, and Web", "Strong student ecosystem"],
                "cons": ["Web fidelity trade-offs", "Dart learning curve"],
            },
            {
                "name": "React Native + separate Web",
                "pros": ["Familiar React skills", "Mature native modules"],
                "cons": ["Two UI stacks to maintain", "More packaging work"],
            },
            {
                "name": "Separate Web + native apps",
                "pros": ["Best platform fit", "Independent release cycles"],
                "cons": ["Highest cost for a solo/short timeline", "Duplicated logic risk"],
            },
        ]
        # Never silently convert to PWA-only
        if mobile_expand:
            alternatives.append({
                "name": "Web + PWA only (not equivalent)",
                "pros": ["Fastest if native stores are not required"],
                "cons": [
                    "Does NOT satisfy Android + iOS + Web as stated",
                    "Must not be chosen silently — user must opt in",
                ],
            })
        findings.append({
            "kind": ChangeKind.SCOPE_CHANGE.value if mobile_expand or len(platforms_new) > len(platforms_old) else ChangeKind.CONFLICT.value,
            "slot": "platform",
            "previous": platforms_old,
            "incoming": platforms_new,
            "summary": (
                f"CHANGE DETECTED\n\nPrevious platforms: {', '.join(platforms_old) or 'unspecified'}\n"
                f"New platforms: {', '.join(platforms_new)}\n\n"
                "Potentially affected:\n- " + "\n- ".join(affected)
            ),
            "affected_components": affected,
            "alternatives": alternatives,
            "decision_required": True,
            "note": "Do not silently convert Android+iOS+Web into Web+PWA.",
        })

    # Auth vs private histories
    wants_private = bool(
        re.search(r"\b(private (project|history|histories|account)|personal data|my projects only)\b", message, re.I)
    )
    wants_login = bool(re.search(r"\b(login|sign[- ]?in|authenticate|auth required)\b", message, re.I))
    wants_no_login = bool(
        re.search(r"\b(no login|without (login|sign[- ]?in)|anonymous|no authentication)\b", message, re.I)
    )
    auth_state = authentication_required(state)

    if wants_private and auth_state is False:
        findings.append({
            "kind": ChangeKind.CONFLICT.value,
            "slot": "authentication",
            "previous": False,
            "incoming": "private histories",
            "summary": (
                "Potential conflict: private project histories usually need identity/ownership, "
                "but authentication_required is currently false."
            ),
            "affected_components": ["identity", "ownership", "privacy", "persistence", "authentication"],
            "alternatives": [
                {"name": "Add login / accounts", "pros": ["True private histories"], "cons": ["More scope"]},
                {"name": "Device-local only privacy", "pros": ["No accounts"], "cons": ["No cross-device private history"]},
                {"name": "Guest codes / local keys", "pros": ["Lightweight"], "cons": ["Weaker account recovery"]},
            ],
            "decision_required": True,
        })
    if wants_login and auth_state is False:
        findings.append({
            "kind": ChangeKind.CONFLICT.value,
            "slot": "authentication",
            "previous": False,
            "incoming": True,
            "summary": "Direct conflict/change: switching from no-login to login required.",
            "affected_components": ["authentication", "session storage", "API authorization"],
            "alternatives": [
                {"name": "Require login", "pros": ["Private data", "Sync"], "cons": ["Onboarding friction"]},
                {"name": "Keep optional guest + optional login", "pros": ["Flexible"], "cons": ["Two paths to maintain"]},
            ],
            "decision_required": True,
        })
    if wants_no_login and auth_state is True:
        findings.append({
            "kind": ChangeKind.CONFLICT.value,
            "slot": "authentication",
            "previous": True,
            "incoming": False,
            "summary": "Direct conflict/change: switching from login required to no login.",
            "affected_components": ["authentication", "private data access"],
            "alternatives": [
                {"name": "Remove login", "pros": ["Simpler V1"], "cons": ["No private server-side history"]},
                {"name": "Keep login", "pros": ["Preserves private histories"], "cons": ["More implementation"]},
            ],
            "decision_required": True,
        })

    # Database switch
    db_new = None
    if re.search(r"\bmongodb\b", message, re.I):
        db_new = "MongoDB"
    elif re.search(r"\bpostgres(ql)?\b", message, re.I):
        db_new = "PostgreSQL"
    elif re.search(r"\bsqlite\b", message, re.I):
        db_new = "SQLite"
    db_old = current_database(state)
    if db_new and db_old and db_new.lower() != db_old.lower():
        findings.append({
            "kind": ChangeKind.SCOPE_CHANGE.value,
            "slot": "database",
            "previous": db_old,
            "incoming": db_new,
            "summary": f"Database change detected: {db_old} → {db_new}.",
            "affected_components": [
                "schema / collections",
                "migrations",
                "ORM or drivers",
                "query patterns",
                "backup/restore",
            ],
            "alternatives": [
                {"name": f"Keep {db_old}", "pros": ["No migration cost"], "cons": ["Ignores new preference"]},
                {"name": f"Move to {db_new}", "pros": ["Matches new preference"], "cons": ["Rewrite data access"]},
            ],
            "decision_required": True,
        })
    elif db_new and not db_old and re.search(r"\b(switch|replace|change|use|using)\b", message, re.I):
        findings.append({
            "kind": ChangeKind.UNCERTAIN.value,
            "slot": "database",
            "previous": None,
            "incoming": db_new,
            "summary": f"Database preference mentioned ({db_new}) but no prior ACTIVE database decision is locked.",
            "affected_components": ["data layer"],
            "alternatives": [
                {"name": db_new, "pros": ["Matches stated preference"], "cons": ["Needs explicit approval"]},
                {"name": "Defer database choice", "pros": ["Avoid premature lock-in"], "cons": ["Blocks detailed schema work"]},
            ],
            "decision_required": True,
        })

    # Uncertain tech wording
    if re.search(r"\b(not sure|unsure|maybe|either|undecided|don'?t know which)\b", message, re.I) and re.search(
        r"\b(flutter|react|postgres|mongo|database|framework|stack)\b", message, re.I
    ):
        findings.append({
            "kind": ChangeKind.UNCERTAIN.value,
            "slot": "technology",
            "previous": None,
            "incoming": message.strip(),
            "summary": "UNCERTAIN technical decision — evidence does not justify picking a winner yet.",
            "affected_components": ["technology stack"],
            "alternatives": [],
            "decision_required": True,
            "note": "Do not fabricate certainty.",
        })

    primary = findings[0]["kind"] if findings else ChangeKind.COMPATIBLE.value
    return {
        "change_kind": primary if findings else ChangeKind.COMPATIBLE.value,
        "findings": findings,
        "requires_user_decision": any(f.get("decision_required") for f in findings),
    }


def apply_impact_to_state(state: dict, impact: dict) -> dict:
    """Record impact findings as PROPOSED decisions; update platform only as stated user intent when clear."""
    for finding in impact.get("findings") or []:
        slot = finding.get("slot")
        # Preserve stated platform requirement on the project without choosing Flutter/PWA.
        if slot == "platform" and finding.get("incoming"):
            state.setdefault("project", {})["platform"] = list(finding["incoming"])
        status = "UNCERTAIN" if finding.get("kind") == ChangeKind.UNCERTAIN.value else "PROPOSED"
        from app.schemas.decisions import DecisionStatus

        decision = propose_decision(
            kind="impact_" + str(finding.get("kind") or "change").lower(),
            summary=(finding.get("summary") or "")[:300],
            value=finding.get("incoming"),
            slot=slot,
            details={
                "previous": finding.get("previous"),
                "incoming": finding.get("incoming"),
                "affected_components": finding.get("affected_components") or [],
                "note": finding.get("note"),
            },
            source=ProvenanceSource.INFERRED,
            reason="change impact analysis",
            alternatives=finding.get("alternatives") or [],
            status=DecisionStatus.UNCERTAIN if status == "UNCERTAIN" else DecisionStatus.PROPOSED,
            confidence=0.55 if status != "UNCERTAIN" else 0.35,
        )
        # Platform list from user statement is USER intent for the requirement, but framework choice stays proposed.
        if slot == "platform":
            decision["provenance"] = {
                **decision["provenance"],
                "source": ProvenanceSource.USER.value,
                "reason": "user stated platforms",
                "user_approved": False,
            }
        state.setdefault("decisions", []).append(decision)
        if finding.get("kind") == ChangeKind.CONFLICT.value:
            state.setdefault("conflicts", []).append({
                "id": f"CON-{len(state.get('conflicts') or []) + 1:03d}",
                "status": "open",
                "slot": slot,
                "existing": finding.get("previous"),
                "incoming": finding.get("incoming"),
                "explanation": finding.get("summary"),
                "affected_components": finding.get("affected_components") or [],
            })
    state["last_impact"] = {
        "change_kind": impact.get("change_kind"),
        "finding_count": len(impact.get("findings") or []),
    }
    return state


def format_impact_for_chat(impact: dict) -> str:
    findings = impact.get("findings") or []
    if not findings:
        return ""
    parts = ["Impact analysis:"]
    for finding in findings:
        parts.append("")
        parts.append(finding.get("summary") or finding.get("kind"))
        alts = finding.get("alternatives") or []
        if alts:
            parts.append("")
            parts.append("Alternatives (you decide — nothing is locked yet):")
            for alt in alts:
                parts.append(f"- {alt.get('name')}")
                if alt.get("pros"):
                    parts.append("  Pros: " + "; ".join(alt["pros"]))
                if alt.get("cons"):
                    parts.append("  Cons: " + "; ".join(alt["cons"]))
        if finding.get("note"):
            parts.append(finding["note"])
    parts.append("")
    parts.append("Your decision: reply with the option you want, or ask for research before choosing.")
    return "\n".join(parts)
