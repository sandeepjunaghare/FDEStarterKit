"""Deterministic checks: retrieval hit @k, citation validity, guardrail behaviour. No LLM."""

from dataclasses import dataclass

from contract import AskResponse, GoldenCase


@dataclass
class Check:
    """ok=None means the check doesn't apply (e.g. retrieval for an out-of-scope question)."""

    ok: bool | None
    reason: str = ""


NOT_APPLICABLE = Check(None)


def retrieval_hit(case: GoldenCase, resp: AskResponse, k: int) -> Check:
    """Hit if any expected source (doc + snippet, case-insensitive) is in the top-k chunks."""
    if case.type != "answerable":
        return NOT_APPLICABLE
    top = resp.retrieved[:k]
    for src in case.expected_sources:
        needle = (src.contains or "").lower()
        if any(c.doc == src.doc and needle in c.text.lower() for c in top):
            return Check(True)
    wanted = "; ".join(
        f'{s.doc} "{s.contains}"' if s.contains else s.doc for s in case.expected_sources
    )
    got = ", ".join(dict.fromkeys(c.doc for c in top)) or "nothing"
    return Check(False, f"{wanted} not in top-{k} (got {got})")


def citations_valid(case: GoldenCase, resp: AskResponse) -> Check:
    """An answer must cite at least one chunk, and only chunks that were actually retrieved."""
    if resp.action != "answer":
        return NOT_APPLICABLE
    if not resp.citations:
        return Check(False, "answer has no citations")
    retrieved = {c.chunk_id for c in resp.retrieved}
    unknown = [c for c in resp.citations if c not in retrieved]
    if unknown:
        return Check(False, f"cites {', '.join(unknown)} which were not retrieved")
    return Check(True)


def guardrail(case: GoldenCase, resp: AskResponse) -> Check:
    """The action must match the expected one; over-refusing an answerable case also fails."""
    if resp.action == case.expect:
        return Check(True)
    return Check(False, f"expected {case.expect}, got {resp.action}")
