"""Render the per-axis PR comment (the gate's visible output).

The headline insight is made explicit: an axis can have a *raw* judge pass-rate that
would clear a naive threshold, yet still be blocked because the *bias-corrected* CI
lower bound is below baseline. That contrast is the whole point of CIGate.
"""

from __future__ import annotations

from .gate import GateReport
from .runner import RunResult

_MARK = "<!-- cigate-report -->"


def _fmt_pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}%"


def _verdict_emoji(r) -> str:
    if not r.estimate.gateable:
        return "⚪️"
    if r.regressed:
        return "🔴"
    return "🟢"


def render_pr_comment(report: GateReport, run: RunResult | None = None) -> str:
    m = report.meta
    head = "❌ **CIGate: merge blocked**" if report.regressed else "✅ **CIGate: no regression detected**"
    n_reg = sum(1 for r in report.results if r.regressed)
    if report.regressed:
        head += f" — {n_reg} axis regression(s)"

    lines = [
        _MARK,
        f"## {head}",
        "",
        f"`prompt={m.get('prompt_version')}` · "
        f"`judge={m.get('judge_model')}` · "
        f"`sample={m.get('n_eval')}/{m.get('n_golden')}` · "
        f"`cost=${report.cost_usd:.2f}`",
        "",
        "| | Axis | Raw judge | Corrected | "
        f"{int(100*0.95)}% CI | Baseline | Δ | Verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in report.results:
        e = r.estimate
        ci = f"[{_fmt_pct(e.ci_low)}, {_fmt_pct(e.ci_high)}]" if e.gateable else "—"
        delta = "—" if r.delta is None else f"{100*r.delta:+.1f} pp"
        verdict = "REGRESSED" if r.regressed else ("n/a" if not e.gateable else "ok")
        lines.append(
            f"| {_verdict_emoji(r)} | `{r.axis}` | {_fmt_pct(e.observed_pass_rate)} | "
            f"{_fmt_pct(e.corrected)} | {ci} | {_fmt_pct(r.baseline_corrected)} | "
            f"{delta} | {verdict} |"
        )

    # Headline contrast: raw would pass but corrected lower bound blocks.
    for r in report.results:
        if r.regressed and r.baseline_corrected is not None:
            raw_ok = r.estimate.observed_pass_rate >= r.baseline_corrected
            if raw_ok:
                lines += [
                    "",
                    f"> ⚠️ **`{r.axis}`**: raw judge pass-rate "
                    f"{_fmt_pct(r.estimate.observed_pass_rate)} would clear a naive gate, "
                    f"but the **bias-corrected 95% CI lower bound "
                    f"{_fmt_pct(r.estimate.ci_low)}** is below baseline "
                    f"{_fmt_pct(r.baseline_corrected)} − tolerance. Blocked.",
                ]

    # A few newly-failing examples per regressed axis.
    if run is not None and report.regressed:
        lines += ["", "<details><summary>Example newly-failing cases</summary>", ""]
        for r in report.results:
            if not r.regressed:
                continue
            fails = [c for c in run.cases if not c["verdicts"].get(r.axis, True)][:3]
            if fails:
                lines.append(f"**`{r.axis}`**")
                for c in fails:
                    lines.append(f"- `{c['id']}` — {c['question'][:90]}")
        lines += ["", "</details>"]

    lines += [
        "",
        "<sub>Gated on the bias-corrected pass-rate CI lower bound per failure-mode axis "
        "(Rogan–Gladen + adjusted-Wald, Bonferroni across axes). "
        "🟢 ok · 🔴 regressed · ⚪️ not gateable.</sub>",
    ]
    return "\n".join(lines)
