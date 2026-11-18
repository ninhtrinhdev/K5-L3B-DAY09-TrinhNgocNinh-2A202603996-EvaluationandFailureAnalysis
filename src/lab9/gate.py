"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)
    Also (beyond the minimum): duplicated (item, seed) rows, and a metrics block that does not
    match what its own rows add up to (a hand-edited summary)."""
    problems: list[str] = []
    rows = pr.get("rows") or []
    manifest = pr.get("manifest", {})

    # 1. NaN / inf metrics
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (NaN/inf)")

    # 2. dropped or duplicated rows
    want = manifest.get("items", 0) * len(manifest.get("seeds", []))
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {manifest.get('items')} items x "
                        f"{len(manifest.get('seeds', []))} seeds = {want} (dropped or duplicated rows)")
    keys = [(r["item_id"], r["seed"]) for r in rows]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        problems.append(f"duplicate (item, seed) rows: {dup[:3]}")

    # 3. the (item, seed) set must equal the baseline's
    base_keys = {(r["item_id"], r["seed"]) for r in base.get("rows") or []}
    if base_keys and set(keys) != base_keys:
        missing, extra = base_keys - set(keys), set(keys) - base_keys
        problems.append(f"(item, seed) set differs from the baseline: {len(missing)} missing, {len(extra)} extra")

    # 4. evaluator failures, and rows where a graded metric has no value
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s), e.g. {pr['evaluator_failures'][0]}")
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    for m in graded:
        n_none = sum(1 for r in rows if r.get(m) is None)
        if n_none:
            problems.append(f"{n_none} row(s) with no value for graded metric {m} (grader crashed or row edited)")

    # 5. the report's own summary must equal what its rows add up to
    for m in graded:
        vals = [r[m] for r in rows if r.get(m) is not None]
        if not vals or m not in (pr.get("metrics") or {}):
            continue
        got = pr["metrics"][m]
        safety = next((x.get("kind") == "safety" for x in spec["metrics"] if x["id"] == m), False)
        calc = sum(bool(v) for v in vals) if safety else sum(bool(v) for v in vals) / len(vals)
        if isinstance(got, (int, float)) and math.isfinite(got) and abs(got - calc) > 1e-3:
            problems.append(f"metric {m} reports {got} but its rows give {round(calc, 4)} (hand-edited summary)")

    # 6. ratchet: thresholds may only get stricter on the same eval-set version
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems += _looser_than(spec, base_spec)

    # 7. relabelling an item out of a slice hides its regression
    def tags(rep: dict) -> dict:
        return {r["item_id"]: sorted(r.get("slices") or []) for r in rep.get("rows") or []}
    t_pr, t_base = tags(pr), tags(base)
    changed = sorted(i for i in t_pr.keys() & t_base.keys() if t_pr[i] != t_base[i])
    if changed:
        problems.append(f"slice tags changed vs baseline for {len(changed)} item(s), e.g. {changed[0]}")
    return problems


def _threshold_looser(label: str, old: dict, old_block: bool, new: dict, new_block: bool) -> list[str]:
    out = []
    for k in ("max", "max_increase"):
        if k in old and (k not in new or new[k] > old[k]):
            out.append(f"{label}: {k} loosened ({old[k]} -> {new.get(k, 'removed')})")
    if "min" in old and ("min" not in new or new["min"] < old["min"]):
        out.append(f"{label}: min lowered ({old['min']} -> {new.get('min', 'removed')})")
    if old.get("no_significant_drop") and not new.get("no_significant_drop"):
        out.append(f"{label}: no_significant_drop dropped")
    if old_block and not new_block:
        out.append(f"{label}: blocking metric became non-blocking")
    return out


def _looser_than(spec: dict, base_spec: dict) -> list[str]:
    out: list[str] = []
    cur = {m["id"]: m for m in spec.get("metrics") or []}
    for bm in base_spec.get("metrics") or []:
        m = cur.get(bm["id"])
        if m is None:
            out.append(f"metric {bm['id']} removed")
            continue
        out += _threshold_looser(f"metric {bm['id']}", bm.get("threshold") or {}, bool(bm.get("blocking")),
                                 m.get("threshold") or {}, bool(m.get("blocking")))
    cur_sl = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    keep = ("min", "no_significant_drop")
    for bs in base_spec.get("slices") or []:
        s = cur_sl.get((bs["name"], bs["metric"]))
        if s is None:
            out.append(f"slice {bs['name']}/{bs['metric']} removed")
            continue
        out += _threshold_looser(f"slice {bs['name']}/{bs['metric']}", {k: bs[k] for k in keep if k in bs},
                                 bool(bs.get("blocking")), {k: s[k] for k in keep if k in s}, bool(s.get("blocking")))
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    bs = spec.get("bootstrap", {})
    blocked: list[str] = []
    lines: list[str] = []
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        sid = f"slice:{name}/{metric}"
        verdict, note, val = "ok", "", None
        if not a:
            verdict = "missing"          # the slice vanished from the PR report (items relabelled or dropped)
        else:
            val = sum(a.values()) / len(a)
            if "min" in sl and val < sl["min"]:
                verdict = "fail"
            keys = sorted(set(a) & set(b))
            if sl.get("no_significant_drop") and keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        shown = "-" if val is None else f"{val:.4f}"
        lines.append(f"  {sid:<34} {shown:<8} {json.dumps({k: v for k, v in sl.items() if k in ('min', 'no_significant_drop')}):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
