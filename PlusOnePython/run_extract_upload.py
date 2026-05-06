from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plusone


DEFAULT_SITES = ["NZ", "AU"]


def default_config_path() -> Path:
    return Path(__file__).resolve().parent / "PlusOneConfig.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PlusOne extract and upload for NZ and AU.")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Path to PlusOneConfig.json.")
    parser.add_argument("--sites", nargs="+", choices=DEFAULT_SITES, default=DEFAULT_SITES, help="Sites to run.")
    parser.add_argument("--extraction", nargs="+", default=["All"], help="Extraction names: All, GLM, SUP, PUR.")
    parser.add_argument("--run-date", help="Run date in YYYY-MM-DD format. Defaults to today.")
    parser.add_argument("--what-if", action="store_true", help="Show intended actions without changing SQL, files, or SFTP.")
    parser.add_argument("--keep-going", action="store_true", help="Continue with remaining sites if one site fails.")
    return parser


def run_plusone_command(argv: list[str]) -> int:
    print(f"\n> python plusone.py {' '.join(argv)}", flush=True)
    return plusone.main(argv)


def run_extract(site: str, args: argparse.Namespace) -> int:
    command = [
        "--config",
        str(args.config),
        "extract",
        "--site",
        site,
        "--extraction",
        *args.extraction,
    ]
    if args.run_date:
        command.extend(["--run-date", args.run_date])
    if args.what_if:
        command.append("--what-if")
    return run_plusone_command(command)


def run_upload(site: str, args: argparse.Namespace) -> int:
    command = [
        "--config",
        str(args.config),
        "upload",
        "--site",
        site,
    ]
    if args.what_if:
        command.append("--what-if")
    return run_plusone_command(command)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    failed_sites: list[str] = []

    for site in args.sites:
        print(f"\n=== {site}: extract then upload ===", flush=True)
        extract_exit_code = run_extract(site, args)
        if extract_exit_code != 0:
            failed_sites.append(site)
            print(f"{site}: extract failed; upload skipped.", flush=True)
            if not args.keep_going:
                break
            continue

        upload_exit_code = run_upload(site, args)
        if upload_exit_code != 0:
            failed_sites.append(site)
            if not args.keep_going:
                break

    if failed_sites:
        print(f"\nFailed site(s): {', '.join(failed_sites)}", file=sys.stderr, flush=True)
        return 1

    print("\nExtract/upload completed successfully.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
