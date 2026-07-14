from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "restart_web.sh"


def test_restart_web_shell_syntax() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_restart_web_help_documents_hardened_defaults() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "help"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = result.stdout
    assert "web,azure,deepseek,aidc" in output
    assert "doctor" in output
    assert "install" in output
    assert "HTTP endpoint" in output
    assert "FORCE_KILL_PORTS=0" in output


def test_restart_prepares_before_stopping_old_service() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    block = source.split("restart_services() {", maxsplit=1)[1].split("}", maxsplit=1)[0]
    assert block.index("prepare_runtime") < block.index("stop_services")
    assert "BACKEND_HEALTH_PATH=\"${BACKEND_HEALTH_PATH:-/openapi.json}\"" in source
    assert "BACKEND_INSTALL=\"${BACKEND_INSTALL:-auto}\"" in source
