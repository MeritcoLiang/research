from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "restart_web.ps1"


def _source() -> str:
    raw = SCRIPT.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig")


def test_backend_probe_uses_a_temporary_python_file() -> None:
    source = _source()
    assert "-c $code" not in source
    assert 'Join-Path $CacheDir "backend-import-probe.py"' in source
    assert "function Write-BackendImportProbe" in source
    assert "$output = & $script:PythonBin $BackendProbeFile @targets 2>&1" in source


def test_embedded_backend_probe_is_valid_python() -> None:
    source = _source()
    marker = "function Write-BackendImportProbe {"
    block = source.split(marker, maxsplit=1)[1].split("function Test-BackendImports", maxsplit=1)[0]
    probe = block.split("$code = @'", maxsplit=1)[1].split("'@", maxsplit=1)[0]
    compile(probe.lstrip("\r\n"), "backend-import-probe.py", "exec")


def test_restart_still_prepares_before_stopping_services() -> None:
    source = _source()
    block = source.split("function Restart-Services {", maxsplit=1)[1].split(
        "function Install-Dependencies", maxsplit=1
    )[0]
    assert block.index("Invoke-GitUpdate") < block.index("Prepare-Runtime")
    assert block.index("Prepare-Runtime") < block.index("Stop-Services")
