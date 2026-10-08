"""Conversation Manager — orchestration over NLP + ProjectState.

Chooses the next conversational *action*. Missing schema fields are readiness
signals only; they do not automatically become the next question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from app.schemas.state import ConversationStage, migrate_state


class OrchestratorAction(str, Enum):
    RESPOND = "RESPOND"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    EXPLORE = "EXPLORE"
    GENERATE_IDEAS = "GENERATE_IDEAS"
    RESEARCH = "RESEARCH"
    GRILL = "GRILL"
    PROPOSE_ARCHITECTURE = "PROPOSE_ARCHITECTURE"
    COMPILE_PROMPT = "COMPILE_PROMPT"
    UPDATE_STATE = "UPDATE_STATE"
    RESET_OR_CHANGE_DIRECTION = "RESET_OR_CHANGE_DIRECTION"
    SELECT_IDEA = "SELECT_IDEA"
    REJECT_IDEA = "REJECT_IDEA"
    FINALIZE = "FINALIZE"
    APPLY_RESEARCH = "APPLY_RESEARCH"


@dataclass
class ManagerResult:
    stage: ConversationStage
    action: OrchestratorAction = OrchestratorAction.RESPOND
    next_question: str | None = None  # conversational follow-up only (never a schema gap)
    pivot_notice: str | None = None
    conflict_notice: str | None = None
    direction_change: bool = False
    suggested_actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


_DIRECTION_CHANGE = re.compile(
    r"\b("
    r"actually[,.]?\s*(forget|scrap|drop|never\s*mind|nvm)|"
    r"forget (that|this|it|the (previous|old|last))|"
    r"something completely different|"
    r"start over|"
    r"change (of )?direction|"
    r"pivot (to|toward|towards)|"
    r"instead[,.]?\s*i want|"
    r"rather[,.]?\s*i want|"
    r"new idea[:\s]"
    r")\b",
    re.I,
)

_TOO_BIG = re.compile(
    r"\b("
    r"too (big|broad|ambitious|much|large|complex|hard)|"
    r"(unrealistic|overscoped|over[- ]?scoped|scope creep)|"
    r"(narrow|simplify|scale back|cut down) (the )?(scope|idea|project)|"
    r"can'?t (finish|do) (all|that)|"
    r"feels (unrealistic|too big)"
    r")\b",
    re.I,
)

_NLP_INTEREST = (
    "What part of NLP interests you most—text classification, information extraction, "
    "generation, misinformation, security, or something else?"
)
_CYBER_INTEREST = (
    "Then we can narrow it toward areas like threat detection, phishing, log analysis, "
    "malware analysis, or digital forensics. Which direction interests you?"
)
_LOG_FOCUS = (
    "What do you want the log analyzer to focus on—suspicious activity, attack detection, "
    "system failures, anomaly detection, or log summarization?"
)
_PHISHING_FOCUS = (
    "What part of phishing detection interests you most—email content, URLs, "
    "sender behavior, or a combination?"
)
_DATA_SCIENCE_FOCUS = (
    "Are you more interested in prediction, classification, recommendation, "
    "anomaly detection, or another data-science direction?"
)
_CHURN_FOCUS = (
    "For churn prediction, are you mainly interested in identifying customers likely to leave, "
    "explaining why they leave, or designing interventions to reduce churn?"
)
_ML_FOCUS = (
    "Within machine learning, do you want to emphasize supervised prediction, "
    "clustering/segmentation, anomaly detection, or something else?"
)


class ConversationManager:
    """Deterministic orchestration layered over NLP analysis + ProjectState."""

    def current_stage(self, state: dict) -> ConversationStage:
        state = migrate_state(state)
        try:
            return ConversationStage(state.get("conversation_stage"))
        except Exception:
            return ConversationStage.DISCOVERY

    def detect_direction_change(self, message: str, state: dict) -> bool:
        if not _DIRECTION_CHANGE.search(message or ""):
            return False
        has_direction = bool(
            (state.get("core_idea") or {}).get("primary_objective")
            or (state.get("project") or {}).get("objective")
            or (state.get("project") or {}).get("problem")
            or (state.get("exploration") or {}).get("current_direction")
            or any(r.get("status") == "active" for r in (state.get("requirements") or []))
        )
        return has_direction

    def detect_pivot(self, message: str, state: dict) -> str | None:
        lowered = message.lower()
        tech = state.get("technology") or {}
        if re.search(r"\b(actually|instead|switch to|change to|rather use)\b", lowered):
            if re.search(r"\b(flutter|react|django|fastapi|vue|angular|swift|kotlin)\b", lowered):
                match = re.search(r"\b(flutter|react|django|fastapi|vue|angular)\b", lowered)
                new = match.group(1) if match else "the new stack"
                old = tech.get("frameworks") or tech.get("languages") or []
                old_text = ", ".join(old) if old else "the previous frontend/backend choice"
                return (
                    f"Technology pivot detected toward {new}. "
                    f"This may affect architecture and deployment previously based on {old_text}."
                )
        return None

    def conflict_summary(self, state: dict) -> str | None:
        open_conflicts = [c for c in (state.get("conflicts") or []) if c.get("status") == "open"]
        if not open_conflicts:
            return None
        last = open_conflicts[-1]
        return (
            f"Conflict detected: {last.get('explanation')}. "
            "I will not silently choose a side — please clarify which requirement should win."
        )

    def recent_questions(self, state: dict) -> list[str]:
        ctx = state.get("conversation_context") or {}
        return list(ctx.get("recent_questions") or [])

    def explore_question(self, message: str, state: dict, intent: str) -> str | None:
        """Context-aware follow-up. Never a missing team/duration/subject form field."""
        lowered = (message or "").lower()
        academic = (state.get("academic") or {}).get("subject") or ""
        project = state.get("project") or {}
        core = state.get("core_idea") or {}
        exploration = state.get("exploration") or {}
        objective = (core.get("primary_objective") or project.get("objective") or "").lower()
        problem = (project.get("problem") or core.get("problem") or "").lower()
        direction = (exploration.get("current_direction") or "").lower()
        interests = " ".join(str(x) for x in (state.get("conversation_context") or {}).get("interests") or [])
        blob = f"{lowered} {academic} {objective} {problem} {direction} {interests}".lower()
        recent = {q.strip().lower() for q in self.recent_questions(state) if q}

        def _pick(question: str | None) -> str | None:
            if not question:
                return None
            if question.strip().lower() in recent:
                return None
            # Also skip if a near-identical recent question was already asked.
            for prior in recent:
                if len(prior) > 24 and (prior in question.lower() or question.lower() in prior):
                    return None
            return question

        # Concrete product / topic before domain-general prompts.
        if re.search(r"\bchurn\b", blob):
            return _pick(_CHURN_FOCUS)
        if re.search(r"\b(linux\s+)?log\s+analy[sz]er\b|\blog analysis\b", blob):
            return _pick(_LOG_FOCUS)
        if re.search(r"\bphish(ing)?\b", blob):
            return _pick(_PHISHING_FOCUS)
        if re.search(r"\b(data\s*science|foundation of data|fds)\b", blob):
            # If they already named churn / fraud / forecast, dig into that instead.
            if re.search(r"\b(churn|fraud|forecast|segment|recommend|anomal)\b", lowered):
                pass
            else:
                return _pick(_DATA_SCIENCE_FOCUS)
        if re.search(r"\b(machine learning|\bml\b|supervised learning|clustering)\b", blob) and not re.search(
            r"\b(nlp|cyber|phish|log)\b", blob
        ):
            return _pick(_ML_FOCUS)
        if re.search(r"\bcryptography|cyber\s*security|cybersecurity|infosec\b", blob) and not re.search(
            r"\b(phish|malware|forensic|threat detection|network security|log)\b", lowered
        ):
            return _pick(_CYBER_INTEREST)
        if re.search(r"\bnlp\b|natural language|text (classif|mining|generation)|misinformation", blob):
            if re.search(r"\b(classif|extract|generat|phish|log|sentiment|summar|misinfo)\b", lowered):
                return None
            return _pick(_NLP_INTEREST)

        # Soft fallback: only when still open-ended — never the old generic "user outcome" loop.
        if intent in {"PROJECT_DESCRIPTION", "CHANGE_SCOPE"} and not (objective or problem or direction):
            if re.search(r"\b(project|something|idea)\b", lowered):
                topic = _soft_topic_label(lowered, academic)
                if topic:
                    return _pick(
                        f"Within {topic}, which direction feels most interesting—"
                        f"a prediction problem, a detection/classification problem, "
                        f"or a tool that helps people analyze data?"
                    )
        return None

    def select_action(
        self,
        state: dict,
        intent: str,
        message: str,
        *,
        direction_change: bool = False,
    ) -> OrchestratorAction:
        if direction_change:
            return OrchestratorAction.RESET_OR_CHANGE_DIRECTION
        if intent == "REQUEST_GRILL" or _TOO_BIG.search(message or ""):
            return OrchestratorAction.GRILL
        if intent == "REQUEST_RESEARCH" or self._wants_research(message):
            return OrchestratorAction.RESEARCH
        if intent == "GENERATE_IDEAS":
            return OrchestratorAction.GENERATE_IDEAS
        if intent == "REQUEST_ARCHITECTURE" or self._wants_architecture(message):
            return OrchestratorAction.PROPOSE_ARCHITECTURE
        if intent == "GENERATE_PROMPT":
            return OrchestratorAction.COMPILE_PROMPT
        if intent == "FINALIZE_PROJECT":
            return OrchestratorAction.FINALIZE
        if intent == "SELECT_IDEA":
            return OrchestratorAction.SELECT_IDEA
        if intent == "REJECT_IDEA":
            return OrchestratorAction.REJECT_IDEA
        if intent == "APPLY_RESEARCH":
            return OrchestratorAction.APPLY_RESEARCH
        if intent == "ASK_FEASIBILITY":
            return OrchestratorAction.GRILL
        if intent in {"CHANGE_TECHNOLOGY", "ADD_REQUIREMENT", "REMOVE_REQUIREMENT", "MODIFY_REQUIREMENT"}:
            return OrchestratorAction.UPDATE_STATE
        core = state.get("core_idea") or {}
        project = state.get("project") or {}
        has_idea = bool(core.get("primary_objective") or project.get("objective") or project.get("problem"))
        exploratory_intents = {"PROJECT_DESCRIPTION", "CHANGE_SCOPE"}
        if intent in exploratory_intents and not has_idea:
            return OrchestratorAction.EXPLORE
        if (
            intent in exploratory_intents
            and has_idea
            and not core.get("locked")
            and self.explore_question(message, state, intent)
        ):
            return OrchestratorAction.EXPLORE
        if intent == "ASK_QUESTION":
            return OrchestratorAction.RESPOND
        return OrchestratorAction.RESPOND

    def advance_after_message(self, state: dict, intent: str, message: str) -> ManagerResult:
        state = migrate_state(state)
        stage = self.current_stage(state)
        notes: list[str] = []
        suggested: list[str] = []
        direction_change = self.detect_direction_change(message, state)
        action = self.select_action(state, intent, message, direction_change=direction_change)

        if action == OrchestratorAction.RESET_OR_CHANGE_DIRECTION:
            stage = ConversationStage.DISCOVERY
            suggested = ["explore new direction", "clarify focus"]
            notes.append("Direction change — archive prior exploration and start a new branch.")
        elif action == OrchestratorAction.GRILL:
            stage = ConversationStage.GRILL
            suggested = ["address grill findings", "narrow scope"]
        elif action == OrchestratorAction.RESEARCH:
            stage = ConversationStage.RESEARCH
            suggested = ["apply research findings to requirements"]
        elif action == OrchestratorAction.GENERATE_IDEAS:
            stage = ConversationStage.IDEATION
            suggested = ["select an idea", "customize an idea"]
        elif action == OrchestratorAction.PROPOSE_ARCHITECTURE:
            stage = ConversationStage.ARCHITECTURE
            suggested = ["accept architecture", "adjust tech choices"]
        elif action == OrchestratorAction.COMPILE_PROMPT:
            stage = ConversationStage.PROMPT_GENERATION
        elif action == OrchestratorAction.FINALIZE:
            stage = ConversationStage.REVIEW
        elif action == OrchestratorAction.SELECT_IDEA:
            stage = ConversationStage.IDEA_SELECTED
            suggested = ["customize the idea", "add constraints"]
        elif action == OrchestratorAction.APPLY_RESEARCH:
            stage = ConversationStage.REQUIREMENTS
        elif action == OrchestratorAction.EXPLORE:
            stage = ConversationStage.DISCOVERY
            suggested = ["narrow the domain", "propose concrete ideas"]
        elif (state.get("core_idea") or {}).get("locked"):
            if intent in {
                "ADD_REQUIREMENT",
                "REMOVE_REQUIREMENT",
                "MODIFY_REQUIREMENT",
                "CHANGE_TECHNOLOGY",
                "CHANGE_SCOPE",
            }:
                stage = ConversationStage.REQUIREMENTS
            elif stage in {
                ConversationStage.DISCOVERY,
                ConversationStage.IDEATION,
                ConversationStage.IDEA_SELECTED,
            }:
                stage = ConversationStage.CUSTOMIZATION
        elif intent == "PROJECT_DESCRIPTION":
            stage = ConversationStage.DISCOVERY

        question = None
        if action in {
            OrchestratorAction.EXPLORE,
            OrchestratorAction.ASK_CLARIFICATION,
            OrchestratorAction.RESET_OR_CHANGE_DIRECTION,
        }:
            question = self.explore_question(message, state, intent)

        pivot = None if direction_change else self.detect_pivot(message, state)
        conflict = self.conflict_summary(state)
        return ManagerResult(
            stage=stage,
            action=action,
            next_question=question,
            pivot_notice=pivot,
            conflict_notice=conflict,
            direction_change=direction_change,
            suggested_actions=suggested,
            notes=notes,
        )

    def _wants_research(self, message: str) -> bool:
        return bool(
            re.search(
                r"\b(already exist|existing (systems|tools|papers)|find (datasets?|papers?|apis?)|"
                r"recent (papers?|work)|what technologies|known limitations|are there (any )?systems)\b",
                message,
                re.I,
            )
        )

    def _wants_architecture(self, message: str) -> bool:
        return bool(
            re.search(
                r"\b("
                r"how should i (build|architect|structure|implement)|"
                r"how (do|would|should) (i|we) build|"
                r"propose (an? )?(architecture|tech stack)|"
                r"system design|"
                r"what (architecture|stack|tech)"
                r")\b",
                message,
                re.I,
            )
        )

    def apply_stage(self, state: dict, stage: ConversationStage) -> dict:
        state = migrate_state(state)
        state["conversation_stage"] = stage.value
        return state


def _soft_topic_label(lowered: str, academic: str) -> str | None:
    if re.search(r"\bdata\s*science|foundation of data\b", lowered) or re.search(
        r"\bdata\s*science\b", (academic or "").lower()
    ):
        return "data science"
    if re.search(r"\bmachine learning|\bml\b", lowered):
        return "machine learning"
    if academic and academic.lower() not in {"the course", "course"}:
        # Avoid dumping raw "on foundation of…" subjects into the question.
        cleaned = re.sub(r"^(on|about|for|in)\s+", "", academic.strip(), flags=re.I)
        if cleaned and len(cleaned.split()) <= 4 and "foundation of" not in cleaned.lower():
            return cleaned
    return None


def research_needed(message: str, state: dict | None = None) -> bool:
    return ConversationManager()._wants_research(message)
