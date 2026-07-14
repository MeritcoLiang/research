from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TSCONFIG = ROOT / "web" / "tsconfig.json"
STATE_INSPECTOR = ROOT / "web" / "src" / "components" / "StateInspector.tsx"
EVENT_REDUCER = ROOT / "web" / "src" / "graph" / "eventReducer.ts"


def test_web_typescript_target_supports_replace_all() -> None:
    config = json.loads(TSCONFIG.read_text(encoding="utf-8"))
    compiler_options = config["compilerOptions"]

    assert compiler_options["target"] == "ES2021"
    assert "ES2021" in compiler_options["lib"]


def test_replace_all_call_sites_are_covered_by_es2021_config() -> None:
    assert ".replaceAll(" in STATE_INSPECTOR.read_text(encoding="utf-8")
    assert ".replaceAll(" in EVENT_REDUCER.read_text(encoding="utf-8")
