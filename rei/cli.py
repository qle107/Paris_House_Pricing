"""CLI: ingest, init-db, refresh-views, score."""
from __future__ import annotations

import argparse

from rei.ingestion.registry import all_sources, get_collector


def main() -> None:
    ap = argparse.ArgumentParser(prog="rei.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db")
    sub.add_parser("refresh-views")
    sub.add_parser("list-sources")

    pi = sub.add_parser("ingest")
    pi.add_argument("source", choices=all_sources())
    pi.add_argument("--communes", help="comma-separated INSEE codes")
    pi.add_argument("--years", help="comma-separated years (DVF)")

    ps = sub.add_parser("score")
    ps.add_argument("--profile", default="value_add_opportunistic")

    args = ap.parse_args()
    if args.cmd == "init-db":
        from rei.etl.load import bootstrap_database
        bootstrap_database()
    elif args.cmd == "refresh-views":
        from rei.etl.load import refresh_matviews
        refresh_matviews()
    elif args.cmd == "list-sources":
        for s in all_sources():
            print(s)
    elif args.cmd == "ingest":
        kwargs = {}
        if args.communes:
            kwargs["communes"] = args.communes.split(",")
        if args.years:
            kwargs["years"] = [int(y) for y in args.years.split(",")]
        rows = get_collector(args.source).run(**kwargs)
        print(f"{args.source}: {rows} rows")
    elif args.cmd == "score":
        from rei.scoring.engine import score
        print(score(args.profile).head(25).to_string(index=False))


if __name__ == "__main__":
    main()
