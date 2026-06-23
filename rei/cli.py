"""CLI: ingest, init-db, refresh-views, score."""
from __future__ import annotations

import argparse

from rei.ingestion.registry import all_sources, get_collector


def _apply_storage(args) -> None:
    """Optional per-run backend override (e.g. `--storage files` with no Postgres)."""
    backend = getattr(args, "storage", None)
    if backend:
        from config.settings import settings
        settings.storage = backend


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

    pt = sub.add_parser("train")
    pt.add_argument("--horizon", type=int, default=5)
    pt.add_argument("--storage", choices=["postgres", "files"], default=None,
                    help="backend for this run (default: REI_STORAGE, else postgres)")

    pp = sub.add_parser("predict")
    pp.add_argument("--storage", choices=["postgres", "files"], default=None,
                    help="backend for this run (default: REI_STORAGE, else postgres)")

    pb = sub.add_parser("backtest")
    pb.add_argument("--horizon", type=int, default=5)
    pb.add_argument("--storage", choices=["postgres", "files"], default=None,
                    help="backend for this run (default: REI_STORAGE, else postgres)")

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
    elif args.cmd == "train":
        _apply_storage(args)
        from rei.ml.train import train
        print(train(horizon=args.horizon))
    elif args.cmd == "predict":
        _apply_storage(args)
        from rei.ml.predict import predict_all
        print(predict_all().head(25).to_string(index=False))
    elif args.cmd == "backtest":
        _apply_storage(args)
        from rei.ml.backtest import walk_forward
        print(walk_forward(horizon=args.horizon).to_string(index=False))


if __name__ == "__main__":
    main()
