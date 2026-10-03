"""Run a golden set against a target and score it.

  cd evals
  uv run python run.py golden/example.yaml --target fake          # harness self-test, no API
  uv run python run.py golden/<scenario>.yaml                       # local API at http://localhost:8000
  uv run python run.py golden/<scenario>.yaml --target https://fde-api.onrender.com
  ... --only case-a,case-b   --no-judge   --compare results/<earlier>.json   --k 5

Exit code: 0 every threshold met · 1 a threshold missed, a case errored, or the judge
couldn't score · 2 bad input.
"""

import argparse
import asyncio
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from contract import GoldenSet, Thresholds
from golden import load_golden
from judge import ClaudeJudge, Judge, JudgeError
from langfuse_sink import LangfuseSink
from metrics import citations_valid, guardrail, retrieval_hit
from targets import FakeTarget, HttpTarget, Target

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


@dataclass
class CaseResult:
    id: str
    question: str
    action: str | None = None
    answer: str | None = None
    hit: bool | None = None  # None = not applicable to this case
    citations: bool | None = None
    guardrails: bool | None = None
    faithfulness: float | None = None
    faithful: bool | None = None
    judge_error: str | None = None
    error: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        if self.error or self.judge_error:
            return False
        return all(
            c is not False for c in (self.hit, self.citations, self.guardrails, self.faithful)
        )


async def evaluate(
    golden: GoldenSet,
    target: Target,
    judge: Judge | None,
    k: int,
    only: set[str] | None = None,
    concurrency: int = 5,
    sink: LangfuseSink | None = None,
) -> list[CaseResult]:
    cases = [c for c in golden.cases if not only or c.id in only]
    sem = asyncio.Semaphore(concurrency)

    async def one(case) -> CaseResult:
        async with sem:
            res = CaseResult(case.id, case.question)
            try:
                resp = await target.ask(case.question, case.user_id)
            except Exception as e:  # noqa: BLE001 — any target failure is reported per case
                res.error = f"{type(e).__name__}: {e}"[:200]
                return res
            res.action, res.answer = resp.action, resp.answer
            for name, check in (
                ("hit", retrieval_hit(case, resp, k)),
                ("citations", citations_valid(case, resp)),
                ("guardrails", guardrail(case, resp)),
            ):
                setattr(res, name, check.ok)
                if check.ok is False:
                    res.reasons.append(f"{name}: {check.reason}")
            if judge and resp.action == "answer" and resp.answer.strip():
                try:
                    v = await judge.faithfulness(case.question, resp.answer, resp.retrieved)
                    res.faithfulness = v.score
                    res.faithful = v.score >= golden.thresholds.faithfulness
                    if not res.faithful:
                        claims = "; ".join(v.unsupported_claims) or v.reasoning
                        res.reasons.append(f"faithfulness {v.score:.2f}: unsupported: {claims}")
                except JudgeError as e:
                    res.judge_error = str(e)
                    res.reasons.append(f"faithfulness: judge error ({e})")
            if sink:
                scores = {
                    name: float(val)
                    for name, val in (
                        ("hit", res.hit),
                        ("citations", res.citations),
                        ("guardrails", res.guardrails),
                        ("faithfulness", res.faithfulness),
                    )
                    if val is not None
                }
                sink.record(
                    case.id,
                    {"question": case.question, "expect": case.expect},
                    {"answer": resp.answer, "action": resp.action, "citations": resp.citations},
                    scores,
                )
            return res

    return list(await asyncio.gather(*(one(c) for c in cases)))


def _rate(values: list) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(results: list[CaseResult], t: Thresholds, judged: bool) -> dict:
    def collect(attr: str) -> list:
        return [getattr(r, attr) for r in results if getattr(r, attr) is not None]

    metrics = {
        "hit_rate": (collect("hit"), t.hit_rate),
        "citations": (collect("citations"), t.citations),
        "guardrails": (collect("guardrails"), t.guardrails),
        "faithfulness": (collect("faithfulness"), t.faithfulness),
    }
    summary: dict = {"metrics": {}, "errors": sum(1 for r in results if r.error)}
    summary["judge_errors"] = sum(1 for r in results if r.judge_error)
    ok = summary["errors"] == 0 and summary["judge_errors"] == 0
    for name, (values, threshold) in metrics.items():
        value = _rate(values)
        skipped = name == "faithfulness" and not judged
        met = None if value is None or skipped else value >= threshold
        summary["metrics"][name] = {
            "value": value,
            "n": len(values),
            "threshold": threshold,
            "met": met,
            "skipped": skipped,
        }
        ok = ok and met is not False
    summary["passed_cases"] = sum(1 for r in results if r.passed)
    summary["total_cases"] = len(results)
    summary["pass"] = ok
    return summary


def _mark(v: bool | None) -> str:
    return "–" if v is None else ("✅" if v else "❌")


def print_report(results: list[CaseResult], summary: dict, judged: bool) -> None:
    width = max([len(r.id) for r in results] + [4])
    print(f"\n{'case':<{width}}  hit  cite guard faith")
    for r in results:
        if r.error:
            print(f"{r.id:<{width}}  ❌ error: {r.error}")
            continue
        faith = "–" if r.faithfulness is None else f"{r.faithfulness:.2f}"
        if r.judge_error:
            faith = "err"
        flag = "" if r.passed else "  ←"
        row = f"{r.id:<{width}}  {_mark(r.hit)}   {_mark(r.citations)}   {_mark(r.guardrails)}"
        print(f"{row}   {faith}{flag}")
        for reason in r.reasons:
            print(f"{'':<{width}}    {reason}")

    print()
    for name, m in summary["metrics"].items():
        if m["skipped"]:
            print(f"{name:<13} skipped (--no-judge)")
            continue
        if m["value"] is None:
            print(f"{name:<13} n/a (no applicable cases)")
            continue
        print(
            f"{name:<13} {m['value']:.2f} (n={m['n']})  ≥ {m['threshold']:.2f}  {_mark(m['met'])}"
        )
    if summary["errors"]:
        print(f"errors        {summary['errors']} case(s) failed to get a response")
    if summary["judge_errors"]:
        print(f"judge errors  {summary['judge_errors']} (credentials? or use --no-judge)")
    verdict = "PASS" if summary["pass"] else "FAIL"
    print(f"\nRESULT: {verdict}  ({summary['passed_cases']}/{summary['total_cases']} cases passed)")


def print_compare(previous: dict, summary: dict, results: list[CaseResult]) -> None:
    print("\ncompare with previous run:")
    for name, m in summary["metrics"].items():
        before = previous["summary"]["metrics"].get(name, {}).get("value")
        now = m["value"]
        if before is None or now is None:
            continue
        print(f"  {name:<13} {before:.2f} → {now:.2f}  ({now - before:+.2f})")
    before_pass = {c["id"]: c["passed"] for c in previous["cases"]}
    for r in results:
        if r.id not in before_pass or before_pass[r.id] == r.passed:
            continue
        print(f"  {'fixed' if r.passed else 'broke'}: {r.id}")


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def save(results: list[CaseResult], summary: dict, meta: dict, results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{meta['run_id']}-{meta['golden']}.json"
    cases = [asdict(r) | {"passed": r.passed} for r in results]
    path.write_text(json.dumps({"meta": meta, "summary": summary, "cases": cases}, indent=2))
    return path


def main(argv: list[str] | None = None, judge: Judge | None = None) -> int:
    p = argparse.ArgumentParser(description="Run a golden set against /ask and score it.")
    p.add_argument("golden", help="golden-set YAML, e.g. golden/example.yaml")
    p.add_argument("--target", default="http://localhost:8000", help='API base URL, or "fake"')
    p.add_argument("--k", type=int, help="top-k for retrieval hit (default: the golden file's k)")
    p.add_argument("--only", help="comma-separated case ids to run")
    p.add_argument("--no-judge", action="store_true", help="skip the LLM faithfulness judge")
    p.add_argument("--compare", help="earlier results JSON to diff against")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--results-dir", default=str(HERE / "results"))
    p.add_argument("--no-save", action="store_true")
    args = p.parse_args(argv)

    load_dotenv(ROOT / ".env")
    try:
        golden = load_golden(args.golden)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    only = {s.strip() for s in args.only.split(",")} if args.only else None
    if only and (unknown := only - {c.id for c in golden.cases}):
        print(f"error: unknown case id(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    previous = json.loads(Path(args.compare).read_text()) if args.compare else None

    k = args.k or golden.k
    target: Target = FakeTarget() if args.target == "fake" else HttpTarget(args.target)
    if not args.no_judge and judge is None:
        judge = ClaudeJudge()
    if args.no_judge:
        judge = None
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    sink = LangfuseSink(run_id)
    meta = {
        "run_id": run_id,
        "golden": golden.name,
        "target": target.name,
        "k": k,
        "judge_model": judge.model if judge else None,
        "git_commit": _git_commit(),
        "langfuse": sink.enabled,
    }
    print(
        f"golden: {golden.name} ({len(golden.cases)} cases) · target: {target.name} · k={k}"
        f" · judge: {meta['judge_model'] or 'off'} · langfuse: {'on' if sink.enabled else 'off'}"
    )

    async def go() -> list[CaseResult]:
        try:
            return await evaluate(golden, target, judge, k, only, args.concurrency, sink)
        finally:
            if isinstance(target, HttpTarget):
                await target.aclose()

    results = asyncio.run(go())
    sink.flush()
    summary = summarize(results, golden.thresholds, judged=judge is not None)
    print_report(results, summary, judged=judge is not None)
    if previous:
        print_compare(previous, summary, results)
    if not args.no_save:
        path = save(results, summary, meta, Path(args.results_dir))
        shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        print(f"\nsaved: {shown}")
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
