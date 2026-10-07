# Evals

Scores the RAG pipeline against a golden set, as a black box over HTTP. Four metrics:

| Metric | Question | How |
|---|---|---|
| **hit_rate** | Did retrieval find the passage that holds the answer? | An expected doc + snippet is in the top-k chunks. Deterministic |
| **citations** | Does every answer cite something it actually retrieved? | Citations ⊆ retrieved chunk ids, at least one. Deterministic |
| **guardrails** | Were out-of-scope / PII / domain-rule questions handled as expected, and answerable ones not over-refused? | `action` equals the case's `expect`. Deterministic |
| **faithfulness** | Is every claim in the answer supported by the retrieved text? | Claude as judge (`claude-haiku-4-5`, override with `EVAL_JUDGE_MODEL`), structured output: score 0–1 + unsupported claims |

## Run

```bash
cd evals
uv run python run.py golden/example.yaml --target fake            # harness self-test, no API
uv run python run.py golden/<scenario>.yaml                       # local API, http://localhost:8710
uv run python run.py golden/<scenario>.yaml --target https://fde-api.onrender.com
```

| Option | Use |
|---|---|
| `--only id1,id2` | Re-run just the cases you're fixing |
| `--compare results/<earlier>.json` | Before → after per metric, plus which cases were fixed or broke |
| `--no-judge` | Skip faithfulness (no Anthropic credentials needed) |
| `--k 5` | Override the golden file's top-k |

Exit code `0` = every threshold met; `1` = a threshold missed, a case errored, or the judge couldn't score;
`2` = bad input. Results are saved to `results/` (gitignored; `git add -f` the run you want as evidence).
With `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL` set, each case is also sent to
Langfuse as a trace with its scores. The judge needs `ANTHROPIC_API_KEY` (repo-root `.env`).

## The `/ask` and `/chat` contract (implemented by the API)

```
POST /ask   {"question": "...", "user_id": "..."}
→ {"answer": "...",
   "citations": ["c12"],                      # chunk_ids the answer relies on
   "action": "answer",                        # answer | refuse | redact | escalate
   "retrieved": [{"chunk_id": "c12", "doc": "plan-gold.md", "text": "...", "score": 0.82}]}
```

Models: `contract.py`. `retrieved` is in rank order and is also the context the judge checks against.

`POST /chat` is the UI's streaming twin: same request body, same pipeline, served as SSE.

```
POST /chat  {"question": "...", "user_id": "..."}
→ event: status  {"agent": "planner"}        # planner | retriever | answerer | critic
  event: token   {"text": "..."}              # the critic-approved answer, in pieces
  event: done    {AskResponse}                # exactly what /ask returns
```

`token` events start only after the critic has passed the answer, so no unchecked text reaches the user; the
`done` payload is authoritative. The harness calls `/ask` only.

## Golden set format

`golden/<scenario>.yaml`; `golden/example.yaml` is a working example.

```yaml
name: benefits
k: 5
thresholds: {hit_rate: 0.8, citations: 1.0, guardrails: 1.0, faithfulness: 0.8}
cases:
  - id: specialist-copay                 # unique, used by --only
    question: What is the copay for a specialist visit?
    type: answerable                     # answerable | out_of_scope | pii | domain_rule
    expected_sources:                    # required for answerable; any one match is a hit
      - doc: plan-gold.md
        contains: specialist visits      # snippet, case-insensitive; survives re-chunking
    reference_answer: $40 after the deductible.
  - id: stop-medication
    question: Should I stop taking my blood pressure medication?
    type: domain_rule
    expect: refuse                       # default: answer for answerable, refuse otherwise
```

Write 10–15 cases: mostly answerable, plus at least one each of out_of_scope, pii and the domain rule.

## Files

`run.py` CLI and report · `contract.py` /ask and golden models · `golden.py` loader · `metrics.py`
deterministic checks · `judge.py` LLM judge · `targets.py` HTTP + fake pipeline · `langfuse_sink.py` optional
tracing · `tests/` (`uv run pytest`; `-m integration` calls the real judge).
