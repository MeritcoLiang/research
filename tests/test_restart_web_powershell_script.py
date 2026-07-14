from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "restart_web.ps1"


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def test_windows_restart_script_contract() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'GIT_PULL" "auto"' in source
    assert "git pull --ff-only" in source
    assert "--porcelain --untracked-files=no" in source
    assert "-SkipGitPull" in source
    assert "-RequireGitPull" in source
    assert "web,azure,deepseek,aidc" in source
    assert "Invoke-WebRequest" in source
    assert "Start-Process $script:NodeBin" in source
    assert "node_modules\\vite\\bin\\vite.js" in source
    assert "$quotedVitePath = '\"' + $vitePath + '\"'" in source
    assert "-ForceKillPorts" in source

    restart_block = source.split("function Restart-Services {", maxsplit=1)[1].split(
        "function Install-Dependencies", maxsplit=1
    )[0]
    assert restart_block.index("Invoke-GitUpdate") < restart_block.index("Prepare-Runtime")
    assert restart_block.index("Prepare-Runtime") < restart_block.index("Stop-Services")


def test_windows_git_update_retries_and_can_continue_locally() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for text in [
        'GIT_RETRIES" "3"',
        'GIT_RETRY_DELAY" "3"',
        'GIT_HTTP_VERSION" "HTTP/1.1"',
        'http.version=$GitHttpVersion',
        "for ($attempt = 1; $attempt -le $GitRetries; $attempt++)",
        "GIT_PULL=auto：继续使用本地 commit=",
        "GIT_PULL=always",
    ]:
        assert text in source


def test_windows_backend_import_failure_is_actionable() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for text in [
        "Get-BackendImportTargets",
        "python={sys.executable}",
        "version={sys.version}",
        "[OK] {name}",
        "[FAIL] {name}",
        "traceback.print_exc()",
        "Test-BackendImports -Quiet",
        "上方已经列出具体失败模块和 Python traceback",
    ]:
        assert text in source


def test_windows_restart_help_is_documented() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for text in [
        "powershell -ExecutionPolicy Bypass",
        "git fetch --prune",
        "git pull --ff-only",
        "doctor",
        "install",
        "GIT_REMOTE=origin",
        "GIT_RETRIES=3",
        "GIT_HTTP_VERSION=HTTP/1.1",
        "NODE_BIN=node.exe",
    ]:
        assert text in source


def test_windows_restart_powershell_parser_when_available() -> None:
    executable = _powershell()
    if executable is None:
        pytest.skip("PowerShell is not installed in this test environment")

    escaped = str(SCRIPT).replace("'", "''")
    command = (
        "$tokens=$null; $errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}', "
        "[ref]$tokens, [ref]$errors) > $null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    subprocess.run([executable, "-NoProfile", "-Command", command], check=True)


def test_windows_restart_help_runs_when_powershell_available() -> None:
    executable = _powershell()
    if executable is None:
        pytest.skip("PowerShell is not installed in this test environment")
    result = subprocess.run(
        [executable, "-NoProfile", "-File", str(SCRIPT), "help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "git pull --ff-only" in result.stdout
    assert "-SkipGitPull" in result.stdout
    assert "-RequireGitPull" in result.stdout
    assert "[FAIL]" in result.stdout
