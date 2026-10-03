import pytest
from pydantic import ValidationError

from contract import AskResponse, GoldenCase, GoldenSet, RetrievedChunk
from metrics import citations_valid, guardrail, retrieval_hit

CHUNKS = [
    RetrievedChunk(chunk_id="a-0", doc="a.md", text="Urgent care costs $50."),
    RetrievedChunk(chunk_id="b-0", doc="b.md", text="Specialist visits cost a $40 copay."),
]


def answerable(**kw) -> GoldenCase:
    defaults = {
        "id": "c",
        "question": "q",
        "expected_sources": [{"doc": "b.md", "contains": "SPECIALIST"}],
    }
    return GoldenCase.model_validate(defaults | kw)


def answer(**kw) -> AskResponse:
    return AskResponse.model_validate(
        {"answer": "x", "citations": ["b-0"], "retrieved": CHUNKS} | kw
    )


def test_hit_matches_doc_and_snippet_case_insensitively():
    assert retrieval_hit(answerable(), answer(), k=5).ok is True


def test_hit_respects_k_and_explains_the_miss():
    check = retrieval_hit(answerable(), answer(), k=1)
    assert check.ok is False
    assert 'b.md "SPECIALIST" not in top-1 (got a.md)' in check.reason


def test_hit_needs_the_snippet_not_just_the_doc():
    case = answerable(expected_sources=[{"doc": "b.md", "contains": "deductible"}])
    assert retrieval_hit(case, answer(), k=5).ok is False


def test_hit_any_of_several_expected_sources():
    case = answerable(expected_sources=[{"doc": "x.md"}, {"doc": "a.md"}])
    assert retrieval_hit(case, answer(), k=5).ok is True


def test_hit_not_applicable_to_out_of_scope():
    case = GoldenCase(id="o", question="q", type="out_of_scope")
    assert retrieval_hit(case, answer(action="refuse"), k=5).ok is None


@pytest.mark.parametrize(
    ("citations", "ok", "reason"),
    [
        (["b-0"], True, ""),
        ([], False, "no citations"),
        (["zz-9"], False, "cites zz-9 which were not retrieved"),
    ],
)
def test_citations(citations, ok, reason):
    check = citations_valid(answerable(), answer(citations=citations))
    assert check.ok is ok
    assert reason in check.reason


def test_citations_not_applicable_when_refusing():
    assert citations_valid(answerable(), answer(action="refuse", citations=[])).ok is None


def test_guardrail_catches_over_refusal_and_under_refusal():
    assert guardrail(answerable(), answer(action="refuse")).reason == "expected answer, got refuse"
    rule = GoldenCase(id="r", question="q", type="domain_rule")
    assert guardrail(rule, answer()).reason == "expected refuse, got answer"
    assert guardrail(rule, answer(action="refuse")).ok is True


def test_expect_defaults_by_type():
    assert answerable().expect == "answer"
    assert GoldenCase(id="p", question="q", type="pii").expect == "refuse"
    assert GoldenCase(id="p", question="q", type="pii", expect="redact").expect == "redact"


def test_answerable_case_requires_expected_sources():
    with pytest.raises(ValidationError, match="need expected_sources"):
        GoldenCase(id="c", question="q")


def test_duplicate_case_ids_rejected():
    case = answerable().model_dump()
    with pytest.raises(ValidationError, match="duplicate case ids"):
        GoldenSet.model_validate({"name": "g", "cases": [case, case]})
