from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "restart_web.ps1"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8-sig")


def test_import_probe_uses_a_temp_python_file() -> None:
    source = _source()
    assert 'backend-import-probe.py' in source
    assert 'Write-BackendImportProbe' in source
    assert '[System.IO.File]::WriteAllText($BackendProbeFile' in source
    assert '& $script:PythonBin $BackendProbeFile @targets' in source
    assert '& $script:PythonBin -c $code' not in source


def test_embedded_import_probe_is_valid_python() -> None:
    source = _source()
    match = re.search(r"function Write-BackendImportProbe \{.*?\$code = @'\r?\n(.*?)\r?\n'@", source, re.S)
    assert match is not None
    compile(match.group(1), "backend-import-probe.py", "exec")


def test_probe_change_preserves_restart_safety_order() -> None:
    source = _source()
    block = source.split("function Restart-Services {", maxsplit=1)[1].split(
        "function Install-Dependencies", maxsplit=1
    )[0]
    assert block.index("Invoke-GitUpdate") < block.index("Prepare-Runtime")
    assert block.index("Prepare-Runtime") < block.index("Stop-Services")
