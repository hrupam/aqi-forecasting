"""
Collect every city's backtest results into one file: reports/summary_all_cities.json
(used for the final presentation and the README results table).

    python tools/summarize_results.py              # writes the JSON and prints a summary
    python tools/summarize_results.py --markdown   # prints the README results table
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def city_summary(slug: str) -> dict | None:
    bt = ROOT / "reports" / slug / "backtest.json"
    meta = ROOT / "data" / slug / "processed" / "meta.json"
    if not bt.exists() or not meta.exists():
        return None
    b, m = json.loads(bt.read_text()), json.loads(meta.read_text())
    if m.get("mode") == "demo":
        return None
    out = {"slug": slug, "city": m.get("city", slug), "station": m.get("station"),
           "period": b.get("period"), "qc": m.get("qc"),
           "model_file_time": (ROOT / "models" / slug / "pm25_quantile_gbm.joblib").stat().st_mtime}
    for k in ("summary_0-24h", "summary_24-48h"):
        out[k] = b.get(k)
    out["alerts"] = b.get("alerts")
    out["by_horizon"] = [{k: r[k] for k in ("h", "mae_model", "mae_persistence", "mae_cams", "coverage_80")}
                         for r in b.get("by_horizon", [])]
    out["reliability"] = b.get("reliability")
    out["importance_top"] = dict(list((b.get("importance") or {}).items())[:8])
    return out


def kolkata_extras() -> dict:
    h = pd.read_csv(ROOT / "data/kolkata/processed/hourly.csv", parse_dates=["time"]).set_index("time")
    pm = h["pm25"].copy()
    pm.index = pd.to_datetime(pm.index, utc=True).tz_convert("Asia/Kolkata")
    daily = pm.resample("D").mean()
    winter = {}
    for ym in ("2025-11", "2025-12", "2026-01", "2026-10", "2026-11"):
        d = daily.loc[ym].dropna() if ym in daily.index.strftime("%Y-%m") else pd.Series(dtype=float)
        winter[ym] = {"days": int(len(d)), "days_above_60": int((d > 60).sum()),
                      "mean": round(float(d.mean()), 1) if len(d) else None}
    fc = pd.read_csv(ROOT / "reports/kolkata/forecast.csv")
    return {"monthly_mean": {int(k): round(float(v), 1) for k, v in pm.groupby(pm.index.month).mean().items()},
            "diurnal_mean": {int(k): round(float(v), 1) for k, v in pm.groupby(pm.index.hour).mean().items()},
            "winter": winter, "strip": fc["q50"].head(48).round(1).tolist(), "strip_issue": fc["issue_time"].iloc[0],
            "last_obs": str(pm.last_valid_index())}


def markdown_table(cities: list[dict]) -> str:
    """The README results table."""
    rows = ["| City (station) | Test period | MAE 0–24 h | MAE 24–48 h | vs persistence (day 1 / 2) | vs CAMS (day 1 / 2) | 80 % range holds |",
            "|---|---|---|---|---|---|---|"]
    for c in cities:
        s1, s2 = c["summary_0-24h"], c["summary_24-48h"]
        p = c["period"]
        rows.append(f"| **{c['city']}** ({c['station']}) | {p['test_start'][:10]} → {p['test_end'][:10]} "
                    f"| {s1['mae_model']:.1f} | {s2['mae_model']:.1f} "
                    f"| {s1['skill_vs_persistence']:.0%} / {s2['skill_vs_persistence']:.0%} "
                    f"| {s1['skill_vs_cams']:.0%} / {s2['skill_vs_cams']:.0%} "
                    f"| {s1['coverage_80']:.0%} / {s2['coverage_80']:.0%} |")
    return "\n".join(rows)


def main():
    cities = [c for c in (city_summary(p.name) for p in sorted((ROOT / "reports").iterdir()) if p.is_dir()) if c]
    if "--markdown" in sys.argv:
        print(markdown_table(cities))
        return
    out = {"cities": cities, "kolkata": kolkata_extras()}
    path = ROOT / "reports" / "summary_all_cities.json"
    path.write_text(json.dumps(out, indent=1, default=str))
    print(f"{len(cities)} cities -> {path}")
    for c in cities:
        s1, s2 = c["summary_0-24h"], c["summary_24-48h"]
        print(f"  {c['city']:<12} MAE {s1['mae_model']:.1f}/{s2['mae_model']:.1f}  "
              f"vs persistence {s1['skill_vs_persistence']:+.0%}/{s2['skill_vs_persistence']:+.0%}  "
              f"vs CAMS {s1['skill_vs_cams']:+.0%}/{s2['skill_vs_cams']:+.0%}  test {c['period']['test_start'][:10]}..{c['period']['test_end'][:10]}")


if __name__ == "__main__":
    main()
