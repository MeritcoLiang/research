"""Live AIDCProgressExpert demo using the requested Loudoun County test case."""

from __future__ import annotations

from datetime import date

from tsgo.aidc_progress.cli import main


if __name__ == "__main__":
    raise SystemExit(
        main(
            [
                "--name",
                "AWS Stone Ridge",
                "--county",
                "Loudoun County",
                "--state",
                "Virginia",
                "--alias",
                "Reeds Farm Lane",
                "--location-hint",
                "Stone Ridge",
                "--as-of-date",
                date.today().isoformat(),
            ]
        )
    )
