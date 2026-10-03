"""Where answers come from: the real API over HTTP (POST /ask), or a deterministic fake pipeline."""

import re
from typing import Protocol

import httpx2

from contract import AskResponse, RetrievedChunk


class Target(Protocol):
    name: str

    async def ask(self, question: str, user_id: str) -> AskResponse: ...


class HttpTarget:
    """Black-box: evaluates whatever is deployed at base_url, local or Render."""

    def __init__(self, base_url: str, timeout: float = 90.0, transport=None):
        self.name = base_url.rstrip("/")
        # 90 s: a sleeping Render free instance takes 30–60 s to wake.
        self._client = httpx2.AsyncClient(base_url=self.name, timeout=timeout, transport=transport)

    async def ask(self, question: str, user_id: str) -> AskResponse:
        r = await self._client.post("/ask", json={"question": question, "user_id": user_id})
        r.raise_for_status()
        return AskResponse.model_validate(r.json())

    async def aclose(self) -> None:
        await self._client.aclose()


# A tiny fictional corpus, so the harness can be exercised before the real pipeline exists.
FAKE_CORPUS = {
    "plan-gold.md": [
        "Specialist visits cost a $40 copay per visit after the deductible is met.",
        "Primary care visits cost a $15 copay and are not subject to the deductible.",
        "The annual deductible is $1,500 per person and $3,000 per family.",
    ],
    "emergency.md": [
        "Emergency room visits cost a $250 copay, waived if you are admitted to the hospital.",
        "Urgent care visits cost a $50 copay.",
    ],
    "pharmacy.md": [
        "Generic drugs cost $10 for a 30-day supply at in-network pharmacies.",
        "Brand-name drugs cost $45 for a 30-day supply.",
    ],
}

_OUT_OF_SCOPE = ("weather", "stock", "recipe", "sports")
_MEDICAL_ADVICE = ("should i stop", "should i take", "dosage", "diagnose")
_WORD = re.compile(r"[a-z0-9$]+")
_STOP = {"the", "a", "an", "is", "my", "what", "for", "of", "to", "do", "i", "how", "much", "does"}


class FakeTarget:
    """Keyword retrieval over FAKE_CORPUS; refuses out-of-scope and medical-advice questions."""

    name = "fake"

    def __init__(self) -> None:
        self.chunks = [
            RetrievedChunk(chunk_id=f"{doc.split('.')[0]}-{i}", doc=doc, text=text)
            for doc, texts in FAKE_CORPUS.items()
            for i, text in enumerate(texts)
        ]

    async def ask(self, question: str, user_id: str) -> AskResponse:
        q = question.lower()
        if any(w in q for w in _OUT_OF_SCOPE):
            return AskResponse(
                answer="I can only answer questions about your plan.", action="refuse"
            )
        if any(w in q for w in _MEDICAL_ADVICE):
            return AskResponse(
                answer="I can't give medical advice. Please ask your doctor.", action="refuse"
            )
        terms = set(_WORD.findall(q)) - _STOP
        scored = []
        for c in self.chunks:
            words = set(_WORD.findall(c.text.lower()))
            overlap = len(terms & words)
            if overlap:
                scored.append(c.model_copy(update={"score": float(overlap)}))
        scored.sort(key=lambda c: c.score or 0.0, reverse=True)
        if not scored:
            return AskResponse(
                answer="I couldn't find that in your plan documents.", action="refuse"
            )
        top = scored[0]
        return AskResponse(answer=top.text, citations=[top.chunk_id], retrieved=scored[:5])
