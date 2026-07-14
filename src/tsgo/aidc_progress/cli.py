"""Command-line entry point for the AIDC progress expert."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from .agent import run_aidc_progress
from .models import AIDCResearchRequest
from .render import render_report_markdown, save_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aidc-progress",
        description="检索政府网站和当地媒体，生成 AIDC 项目进展与最新消息报告。",
    )
    parser.add_argument("--name", required=True, help="项目、园区、运营商或项目代号。")
    parser.add_argument("--county", required=True, help="County，例如 Loudoun County。")
    parser.add_argument("--state", required=True, help="州，例如 Virginia。")
    parser.add_argument("--alias", action="append", default=[], help="可重复：项目别名或代号。")
    parser.add_argument(
        "--location-hint",
        action="append",
        default=[],
        help="可重复：道路、地址、路口或社区名称。",
    )
    parser.add_argument("--as-of-date", default=date.today().isoformat(), help="检索截止日期 YYYY-MM-DD。")
    parser.add_argument("--lookback-years", type=int, default=8)
    parser.add_argument("--provider", choices=["openai", "azure"], default=None)
    parser.add_argument("--model", default=None, help="OpenAI model 或 Azure deployment 名称。")
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument(
        "--output-dir",
        default=os.getenv("AIDC_OUTPUT_DIR", "reports/aidc"),
        help="Markdown/JSON 输出目录。",
    )
    parser.add_argument("--stdout-only", action="store_true", help="只输出 Markdown，不写文件。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = AIDCResearchRequest(
        name=args.name,
        county=args.county,
        state=args.state,
        aliases=args.alias,
        location_hints=args.location_hint,
        as_of_date=args.as_of_date,
        lookback_years=args.lookback_years,
    )
    try:
        report = run_aidc_progress(
            request,
            provider=args.provider,
            model_name=args.model,
            max_turns=args.max_turns,
        )
    except Exception as exc:
        print(f"AIDC progress run failed: {exc}", file=sys.stderr)
        return 1

    markdown = render_report_markdown(report)
    print(markdown)
    if not args.stdout_only:
        json_path, markdown_path = save_report(report, Path(args.output_dir))
        print(f"JSON: {json_path}", file=sys.stderr)
        print(f"Markdown: {markdown_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
