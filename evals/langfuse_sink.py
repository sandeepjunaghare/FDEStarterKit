"""Optional: send each case to Langfuse as a trace with its scores. On only when keys are set.

Uses the Langfuse Python SDK v4 (env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL).
Failures here never fail the eval; they print a warning.
"""

import os
import sys
from typing import Any


class LangfuseSink:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.enabled = bool(
            os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
        )
        self._client: Any = None
        if self.enabled:
            try:
                from langfuse import get_client

                self._client = get_client()
            except Exception as e:  # noqa: BLE001 — optional integration, never fatal
                self._warn(e)

    def record(self, case_id: str, inputs: dict, outputs: dict, scores: dict[str, float]) -> None:
        if not self._client:
            return
        try:
            with self._client.start_as_current_observation(
                as_type="span", name=f"eval:{case_id}"
            ) as span:
                span.update(input=inputs, output=outputs, metadata={"run_id": self.run_id})
                for name, value in scores.items():
                    span.score_trace(name=name, value=value, data_type="NUMERIC")
        except Exception as e:  # noqa: BLE001
            self._warn(e)

    def flush(self) -> None:
        if self._client:
            try:
                self._client.flush()
            except Exception as e:  # noqa: BLE001
                self._warn(e)

    def _warn(self, e: Exception) -> None:
        print(f"warning: Langfuse disabled ({type(e).__name__}: {e})", file=sys.stderr)
        self._client = None
