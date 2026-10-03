"""Load and validate a golden-set YAML file."""

from pathlib import Path

import yaml

from contract import GoldenSet


def load_golden(path: str | Path) -> GoldenSet:
    path = Path(path)
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping with 'cases'")
    data.setdefault("name", path.stem)
    return GoldenSet.model_validate(data)
