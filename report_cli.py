from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
import report_service


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _cmd_list_sessions() -> int:
    sessions = report_service.list_completed_sessions()
    if not sessions:
        print("No completed sessions found.")
        return 0

    print("Completed sessions:")
    for item in sessions:
        distortions = ", ".join(item.get("distortions") or []) or "None"
        print(
            f"- {item['session_id']} | {item.get('date') or 'N/A'} | "
            f"emotion={item.get('emotion') or 'N/A'} | "
            f"delta={item.get('intensity_delta')} | "
            f"distortions={distortions}"
        )
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    if args.mode == "single":
        if not args.session_id:
            raise SystemExit("--session-id is required when mode=single")
        session_ids = [args.session_id]
    elif args.mode == "custom":
        if not args.session_ids:
            raise SystemExit("--session-ids is required when mode=custom")
        session_ids = [x.strip() for x in args.session_ids.split(",") if x.strip()]
        if not session_ids:
            raise SystemExit("--session-ids did not contain any valid session id")
    else:
        session_ids = None

    report = report_service.generate_report(
        mode=args.mode,
        limit=args.limit,
        session_ids=session_ids,
        include_llm_summary=False,
    )
    report_path = Path(config.REPORTS_DIR) / f"report_{report['report_id']}.json"

    print(f"Generated report: {report['report_id']}")
    print(f"Saved to: {report_path}")
    print(f"Report type: {(report.get('scope') or {}).get('report_type')}")
    print(f"Sessions included: {len(report.get('sessions') or [])}")

    if args.print_json:
        _print_json(report)
    return 0


def _cmd_list_reports() -> int:
    reports = report_service.list_reports()
    if not reports:
        print("No reports found.")
        return 0

    print("Saved reports:")
    for item in reports:
        scope = item.get("scope") or {}
        print(
            f"- {item.get('report_id')} | {item.get('generated_at')} | "
            f"type={scope.get('report_type') or 'N/A'} | "
            f"sessions={item.get('sessions_count')} | "
            f"mode={scope.get('mode') or 'N/A'}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independent report tool for CBT thought-record sessions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-sessions", help="List completed sessions available for reports.")
    subparsers.add_parser("list-reports", help="List saved reports.")

    generate = subparsers.add_parser("generate", help="Generate a report from completed sessions.")
    generate.add_argument(
        "--mode",
        choices=["single", "recent", "custom"],
        default="recent",
        help="How to choose sessions for the report.",
    )
    generate.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of most recent sessions to include when mode=recent.",
    )
    generate.add_argument(
        "--session-id",
        help="Single session id to include when mode=single.",
    )
    generate.add_argument(
        "--session-ids",
        help="Comma-separated session ids to include when mode=custom.",
    )
    generate.add_argument(
        "--print-json",
        action="store_true",
        help="Print the full generated report JSON.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list-sessions":
        return _cmd_list_sessions()
    if args.command == "list-reports":
        return _cmd_list_reports()
    if args.command == "generate":
        return _cmd_generate(args)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
