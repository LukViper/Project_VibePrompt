"""AssertionOrigin semantics — explicit vs inferred requirement creation."""

from app.schemas.assertions import AssertionOrigin, AssertionStatus
from app.schemas.provenance import ProvenanceSource
from app.services.assertion_lifecycle import (
    default_requirement_assertion_status,
    default_status_for_origin,
    promotion_allowed,
)
from app.services.project_state import empty_state, _new_requirement


def test_explicit_user_requirement_confirmed():
    state = empty_state()
    req = _new_requirement(
        state,
        "Detect phishing emails",
        "functional",
        source=ProvenanceSource.USER,
        explicit=True,
        origin=AssertionOrigin.USER_EXPLICIT,
    )
    assert req["assertion_origin"] == AssertionOrigin.USER_EXPLICIT.value
    assert req["assertion_status"] == AssertionStatus.CONFIRMED.value


def test_user_inferred_requirement_proposed():
    state = empty_state()
    req = _new_requirement(
        state,
        "Maybe add dark mode",
        "functional",
        source=ProvenanceSource.USER,
        explicit=False,
        origin=AssertionOrigin.USER_INFERRED,
    )
    assert req["assertion_status"] == AssertionStatus.PROPOSED.value
    assert req["assertion_origin"] == AssertionOrigin.USER_INFERRED.value


def test_llm_inferred_requirement_proposed():
    status = default_requirement_assertion_status(
        provenance_source=ProvenanceSource.AI_RECOMMENDATION,
        origin=AssertionOrigin.LLM_INFERRED,
    )
    assert status == AssertionStatus.PROPOSED
    assert default_status_for_origin(AssertionOrigin.LLM_INFERRED) == AssertionStatus.PROPOSED


def test_grill_requirement_proposed():
    assert default_status_for_origin(AssertionOrigin.GRILL_DERIVED) == AssertionStatus.PROPOSED
    state = empty_state()
    req = _new_requirement(
        state,
        "Latency <= 500ms",
        "nonfunctional",
        source=ProvenanceSource.USER,
        explicit=False,
        origin=AssertionOrigin.GRILL_DERIVED,
    )
    assert req["assertion_status"] == AssertionStatus.PROPOSED.value
    assert req["assertion_origin"] == AssertionOrigin.GRILL_DERIVED.value


def test_research_requirement_proposed():
    state = empty_state()
    req = _new_requirement(
        state,
        "Incorporate research insight: use public phishing corpora",
        "constraint",
        source=ProvenanceSource.RESEARCH,
        origin=AssertionOrigin.RESEARCH_DERIVED,
        explicit=False,
    )
    assert req["assertion_status"] == AssertionStatus.PROPOSED.value
    assert req["assertion_origin"] == AssertionOrigin.RESEARCH_DERIVED.value


def test_proposed_cannot_be_locked_without_confirmation():
    assert not promotion_allowed(AssertionStatus.PROPOSED, AssertionStatus.LOCKED)
    assert promotion_allowed(AssertionStatus.PROPOSED, AssertionStatus.CONFIRMED)
    assert promotion_allowed(AssertionStatus.CONFIRMED, AssertionStatus.LOCKED)
