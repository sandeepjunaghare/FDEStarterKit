"""Data contracts: what POST /ask returns (pane A implements it) and what a golden set contains.

POST /ask
  request:  {"question": str, "user_id": str}
  response: AskResponse below. `retrieved` is what the retriever returned, in rank order;
            `citations` are chunk_ids from `retrieved` that the answer relies on; `action` says
            what the guardrails did.

POST /chat takes the same request, runs the same pipeline and streams SSE; its final `done` event
is this same AskResponse, so the UI and the evals see one answer shape.
"""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

Action = Literal["answer", "refuse", "redact", "escalate"]
CaseType = Literal["answerable", "out_of_scope", "pii", "domain_rule"]


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc: str
    text: str
    score: float | None = None


class AskResponse(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    action: Action = "answer"
    retrieved: list[RetrievedChunk] = Field(default_factory=list)


class ExpectedSource(BaseModel):
    """Where the answer lives: a document plus a snippet, so re-chunking doesn't break the case."""

    doc: str
    contains: str | None = None


class GoldenCase(BaseModel):
    id: str
    question: str
    type: CaseType = "answerable"
    expect: Action | None = None  # defaults: answerable → answer, everything else → refuse
    expected_sources: list[ExpectedSource] = Field(default_factory=list)
    reference_answer: str | None = None
    user_id: str = "eval"

    @model_validator(mode="after")
    def _defaults_and_checks(self) -> Self:
        if self.expect is None:
            self.expect = "answer" if self.type == "answerable" else "refuse"
        if self.type == "answerable" and not self.expected_sources:
            raise ValueError(f"case {self.id!r}: answerable cases need expected_sources")
        return self


class Thresholds(BaseModel):
    hit_rate: float = 0.8
    citations: float = 1.0
    guardrails: float = 1.0
    faithfulness: float = 0.8


class GoldenSet(BaseModel):
    name: str
    k: int = 5
    thresholds: Thresholds = Field(default_factory=Thresholds)
    cases: list[GoldenCase]

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        ids = [c.id for c in self.cases]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate case ids: {dupes}")
        return self
