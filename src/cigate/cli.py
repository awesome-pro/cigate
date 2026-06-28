"""``cigate`` command-line interface.

    cigate run      — evaluate the SUT over a sampled golden set -> results.json
    cigate gate     — evaluate + compare to baseline -> report.md + summary.json (exit 1 if regressed)
    cigate baseline — promote a (full) run to the committed baseline
    cigate calibrate— measure judge TPR/TNR + Cohen's kappa (see calibrate.py)
"""

from __future__ import annotations

import argparse
import sys

from . import baseline as baseline_mod
from . import report as report_mod
from .config import load_config
from .gate import baseline_from_run, evaluate_gate
from .runner import run as run_eval


def _print_summary(report) -> None:
    for r in report.results:
        e = r.estimate
        flag = "REGRESSED" if r.regressed else ("n/a" if not e.gateable else "ok")
        base = "—" if r.baseline_corrected is None else f"{r.baseline_corrected:.3f}"
        print(f"  {r.axis:16s} corrected={e.corrected:.3f} "
              f"CI=[{e.ci_low:.3f},{e.ci_high:.3f}] baseline={base}  {flag}")
    print(f"  cost=${report.cost_usd:.2f}  regressed={report.regressed}")


def cmd_run(args) -> int:
    cfg = load_config(args.config)
    res = run_eval(cfg, fraction=args.fraction, seed=args.seed)
    res.save(args.out)
    print(f"[cigate run] mode={'mock' if cfg.mock_mode() else 'real'} "
          f"n_eval={res.meta['n_eval']} cost=${res.cost_usd:.2f} -> {args.out}")
    return 0


def cmd_gate(args) -> int:
    cfg = load_config(args.config)
    fraction = 1.0 if args.full else args.fraction
    res = run_eval(cfg, fraction=fraction, seed=args.seed)
    base = baseline_mod.load_baseline(args.baseline or cfg.baseline_path)
    report = evaluate_gate(res, cfg, base)

    md = report_mod.render_pr_comment(report, res)
    with open(args.out_report, "w") as f:
        f.write(md)
    import json
    with open(args.out_summary, "w") as f:
        json.dump(report.to_json(), f, indent=2)

    print(f"[cigate gate] mode={'mock' if cfg.mock_mode() else 'real'}")
    _print_summary(report)
    print(f"  report -> {args.out_report}  summary -> {args.out_summary}")

    if report.regressed and args.fail_on_regression:
        print("[cigate gate] REGRESSION DETECTED -> failing the check (exit 1)")
        return 1
    return 0


def cmd_baseline(args) -> int:
    cfg = load_config(args.config)
    if not args.promote:
        print("nothing to do; pass --promote to write the baseline")
        return 0
    res = run_eval(cfg, fraction=1.0, seed=args.seed)
    doc = baseline_from_run(res, cfg)
    out = args.out or cfg.baseline_path
    baseline_mod.save_baseline(out, doc)
    print(f"[cigate baseline] promoted full run -> {out} (n_eval={res.meta['n_eval']})")
    return 0


def cmd_calibrate(args) -> int:
    from .calibrate import run_calibration
    return run_calibration(args)


def cmd_report(args) -> int:
    if args.auditor:
        from .auditor import run_auditor
        return run_auditor(args)
    print("nothing to do; pass --auditor to generate the auditor pack")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cigate", description="Eval-gated CI/CD for AI products.")
    # --config is shared by all subcommands (usable after the subcommand, e.g.
    # `cigate gate --config evalconfig_cuad.yaml`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="evalconfig.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", parents=[common], help="evaluate the SUT over a sampled golden set")
    pr.add_argument("--fraction", type=float, default=None)
    pr.add_argument("--seed", type=int, default=None)
    pr.add_argument("--out", default="results.json")
    pr.set_defaults(func=cmd_run)

    pg = sub.add_parser("gate", parents=[common], help="evaluate + compare to baseline")
    pg.add_argument("--fraction", type=float, default=None)
    pg.add_argument("--seed", type=int, default=None)
    pg.add_argument("--full", action="store_true", help="evaluate the full golden set")
    pg.add_argument("--baseline", default=None)
    pg.add_argument("--out-report", default="report.md")
    pg.add_argument("--out-summary", default="summary.json")
    pg.add_argument("--fail-on-regression", action="store_true")
    pg.set_defaults(func=cmd_gate)

    pb = sub.add_parser("baseline", parents=[common], help="promote a full run to the baseline")
    pb.add_argument("--promote", action="store_true")
    pb.add_argument("--seed", type=int, default=None)
    pb.add_argument("--out", default=None)
    pb.set_defaults(func=cmd_baseline)

    pc = sub.add_parser("calibrate", parents=[common], help="measure judge TPR/TNR + Cohen's kappa")
    pc.add_argument("--out", default="calibration.json")
    pc.add_argument("--perturb-judge", action="store_true",
                    help="simulate judge drift to demonstrate detection")
    pc.set_defaults(func=cmd_calibrate)

    prp = sub.add_parser("report", parents=[common], help="generate reports (auditor pack)")
    prp.add_argument("--auditor", action="store_true", help="generate the auditor pack")
    prp.add_argument("--out", default="auditor_pack.md")
    prp.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
