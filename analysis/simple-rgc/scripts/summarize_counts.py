"""Summarise RGC counts in two stages: review status first, analysis only on reviewed counts.

Stage 1, always written (summary/review/):
    REVIEW_STATUS.md                   how many fields of each retina have been manually reviewed
    review_status.csv                  the same, per retina
    field_review.csv                   every field: automated count, manual count, cells removed and added
    agreement.txt                      automated vs manual agreement over reviewed fields
    cutoff_calibration.csv             how well each brightness cut-off reproduces the manual counts
    auto_vs_manual.png

Stage 2, per project, only when every field of every retina in that project is reviewed
(summary/<project>/):
    REPORT.md, tables/*.csv, stats/statistics.txt, figures/*.png
    Densities come from the manual (reviewed) counts.
    --preliminary writes stage 2 for unreviewed projects from the automated counts instead,
    with every output marked PRELIMINARY.

Inputs:
    <run>/counts/field_counts.csv            automated counts (simple_rgc_count.groovy)
    <run>/cells/<sample>/<image>_cells.csv   automated objects with brightness contrast
    <run>/manual/manual_counts.csv           reviewed counts (review_counts.groovy)
    <run>/manual/<sample>/<image>_points.csv reviewed points
    config/sample_groups.csv                 sample, project, animal, eye, group

Usage: python scripts/summarize_counts.py [run_dir] [--groups config/sample_groups.csv] [--preliminary]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from math import comb
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
FIELD_RE = re.compile(r"_(?P<mag>\d+x)_(?P<quadrant>[a-z])(?P<position>\d+)$", re.I)
CUTS = np.round(np.arange(1.00, 1.401, 0.025), 3)
REFERENCE_GROUP = "control"
PALETTE = ["#2a6fb0", "#d1495b", "#3a9d5d", "#8e5bb5", "#d88c2a", "#5b6b73"]


def sem(x):
    x = pd.Series(x).dropna()
    return x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan


def df_md(df: pd.DataFrame, floatfmt="{:.1f}") -> str:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else floatfmt.format(v))
    head = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join(["---"] * len(d.columns)) + "|"
    rows = ["| " + " | ".join(map(str, r)) + " |" for r in d.values]
    return "\n".join([head, sep] + rows)


# ---------------------------------------------------------------- loading
def load(run: Path, groups_csv: Path):
    fc = pd.read_csv(run / "counts" / "field_counts.csv")
    fc = fc.drop_duplicates(subset=["file", "series"], keep="last")
    grp = pd.read_csv(groups_csv, dtype=str).fillna("")
    for col in ["project", "animal", "eye", "group"]:
        if col not in grp:
            grp[col] = ""
    fc = fc.merge(grp[["sample", "project", "animal", "eye", "group"]], on="sample", how="left")
    missing = sorted(fc.loc[fc.group.isna() | (fc.group == ""), "sample"].unique())
    if missing:
        print(f"WARNING: {missing} have no group in {groups_csv.name}; they are left out of the analysis",
              file=sys.stderr)
    fc[["project", "animal", "eye", "group"]] = fc[["project", "animal", "eye", "group"]].fillna("")
    fc.loc[fc.project == "", "project"] = "unassigned"
    parts = fc["image"].str.extract(FIELD_RE)
    fc["quadrant"] = parts["quadrant"].str.lower()
    fc["position"] = pd.to_numeric(parts["position"], errors="coerce")

    man_path = run / "manual" / "manual_counts.csv"
    if man_path.exists():
        man = pd.read_csv(man_path, dtype={"note": str})
        man = man.drop_duplicates(subset=["sample", "image"], keep="last")
        fc = fc.merge(man[["sample", "image", "n_auto_kept", "n_removed", "n_added", "n_final",
                           "reviewer", "reviewed_at"]], on=["sample", "image"], how="left")
    else:
        for c in ["n_auto_kept", "n_removed", "n_added", "n_final", "reviewer", "reviewed_at"]:
            fc[c] = np.nan
    fc["reviewed"] = fc["n_final"].notna()
    fc["density_manual_per_mm2"] = fc["n_final"] / fc["field_area_mm2"]
    return fc


def load_cells(run: Path, fc: pd.DataFrame) -> pd.DataFrame:
    out = []
    for r in fc.itertuples():
        p = run / "cells" / r.sample / f"{r.image}_cells.csv"
        if p.exists():
            c = pd.read_csv(p)
            c.insert(0, "image", r.image)
            c.insert(0, "sample", r.sample)
            out.append(c)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def load_points(run: Path, sample: str, image: str) -> pd.DataFrame | None:
    p = run / "manual" / sample / f"{image}_points.csv"
    return pd.read_csv(p) if p.exists() else None


# ---------------------------------------------------------------- stage 1: review
def review_status(fc: pd.DataFrame) -> pd.DataFrame:
    g = fc.groupby(["project", "group", "sample"], dropna=False)
    st = g.agg(fields=("image", "count"), reviewed=("reviewed", "sum")).reset_index()
    st["remaining"] = st.fields - st.reviewed
    st["status"] = np.where(st.remaining == 0, "complete", np.where(st.reviewed == 0, "not started", "in progress"))
    return st


def field_review_table(fc: pd.DataFrame) -> pd.DataFrame:
    d = fc[fc.reviewed].copy()
    d["kept"] = d.n_auto_kept - d.n_removed
    d["precision_auto"] = d.kept / d.n_auto_kept.replace(0, np.nan)
    d["recall_auto"] = d.kept / d.n_final.replace(0, np.nan)
    d["pct_difference"] = 100 * (d.n_filtered - d.n_final) / d.n_final.replace(0, np.nan)
    return d[["project", "group", "sample", "image", "n_simplergc", "n_filtered", "n_auto_kept", "n_removed",
              "n_added", "n_final", "precision_auto", "recall_auto", "pct_difference", "reviewer", "reviewed_at"]]


def agreement_text(fr: pd.DataFrame) -> str:
    if fr.empty:
        return "No fields reviewed yet.\n"
    diff = fr.n_filtered - fr.n_final
    bias, sd = diff.mean(), diff.std(ddof=1)
    lines = [
        f"Reviewed fields: {len(fr)} ({fr['sample'].nunique()} retinas)",
        f"Automated count (filtered) total: {int(fr.n_filtered.sum())}; manual total: {int(fr.n_final.sum())}",
        f"Cells removed by reviewers (false detections): {int(fr.n_removed.sum())} "
        f"({100 * fr.n_removed.sum() / max(fr.n_auto_kept.sum(), 1):.1f}% of automated cells)",
        f"Cells added by reviewers (missed): {int(fr.n_added.sum())} "
        f"({100 * fr.n_added.sum() / max(fr.n_final.sum(), 1):.1f}% of final cells)",
        f"Per-field difference, automated minus manual: mean {bias:+.1f} cells"
        + (f", 95% limits of agreement {bias - 1.96 * sd:+.1f} to {bias + 1.96 * sd:+.1f}" if len(fr) > 1 else ""),
        f"Mean absolute % difference per field: {fr.pct_difference.abs().mean():.1f}%",
    ]
    if len(fr) > 2 and fr.n_final.std() > 0:
        r = stats.pearsonr(fr.n_filtered, fr.n_final)
        lines.append(f"Pearson r (automated vs manual counts): {r.statistic:.3f}")
    by = fr.groupby("sample").agg(fields=("image", "count"), auto=("n_filtered", "sum"), manual=("n_final", "sum"),
                                  removed=("n_removed", "sum"), added=("n_added", "sum")).reset_index()
    by["pct_difference"] = 100 * (by.auto - by.manual) / by.manual.replace(0, np.nan)
    lines += ["", "Per retina (reviewed fields only):", by.round(1).to_string(index=False)]
    return "\n".join(lines) + "\n"


def cutoff_calibration(run: Path, fc: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    """For each brightness cut-off: how far the automated count is from the manual count, and
    how many of the kept objects match a reviewed cell (a final point inside the object's radius)."""
    rows = []
    for r in fc[fc.reviewed].itertuples():
        pts = load_points(run, r.sample, r.image)
        obj = cells[(cells["sample"] == r.sample) & (cells["image"] == r.image)]
        if pts is None or obj.empty:
            continue
        fin = pts[pts.status != "removed"][["x_px", "y_px"]].to_numpy()
        ox, oy = obj.x_px.to_numpy(), obj.y_px.to_numpy()
        rad = np.sqrt(obj.area_px.to_numpy() / np.pi)
        if len(fin):
            dist = np.sqrt((ox[:, None] - fin[None, :, 0]) ** 2 + (oy[:, None] - fin[None, :, 1]) ** 2)
            is_cell = (dist <= rad[:, None]).any(axis=1)
        else:
            is_cell = np.zeros(len(obj), bool)
        for c in CUTS:
            keep = obj.contrast.to_numpy() >= c
            rows.append(dict(sample=r.sample, image=r.image, cutoff=c, n_auto=int(keep.sum()),
                             n_true=int((keep & is_cell).sum()), n_manual=int(r.n_final)))
    if not rows:
        return pd.DataFrame()
    d = pd.DataFrame(rows)
    d["abs_pct_err"] = 100 * (d.n_auto - d.n_manual).abs() / d.n_manual.replace(0, np.nan)
    d["pct_err"] = 100 * (d.n_auto - d.n_manual) / d.n_manual.replace(0, np.nan)
    out = d.groupby("cutoff").agg(fields=("image", "count"), auto_total=("n_auto", "sum"),
                                  manual_total=("n_manual", "sum"), matched=("n_true", "sum"),
                                  mean_pct_error=("pct_err", "mean"),
                                  mean_abs_pct_error=("abs_pct_err", "mean")).reset_index()
    out["precision"] = out.matched / out.auto_total.replace(0, np.nan)
    out["recall"] = out.matched / out.manual_total.replace(0, np.nan)
    return out


def fig_auto_vs_manual(fr: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(5, 5))
    samples = sorted(fr["sample"].unique())
    for i, s in enumerate(samples):
        d = fr[fr["sample"] == s]
        ax.scatter(d.n_final, d.n_filtered, s=22, color=PALETTE[i % len(PALETTE)], label=s)
    hi = max(fr.n_final.max(), fr.n_filtered.max()) * 1.08
    ax.plot([0, hi], [0, hi], color="k", lw=1, ls="--")
    ax.set_xlim(0, hi); ax.set_ylim(0, hi)
    ax.set_xlabel("manual count per field (reviewed)")
    ax.set_ylabel("automated count per field (filtered)")
    ax.set_title("Automated vs manual counts", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "auto_vs_manual.png", dpi=150)
    plt.close(fig)


def write_stage1(run: Path, fc, cells, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    st = review_status(fc)
    fr = field_review_table(fc)
    agree = agreement_text(fr)
    cal = cutoff_calibration(run, fc, cells) if not fr.empty and not cells.empty else pd.DataFrame()
    st.to_csv(out / "review_status.csv", index=False)
    fr.to_csv(out / "field_review.csv", index=False)
    (out / "agreement.txt").write_text(agree, encoding="utf-8")
    if not cal.empty:
        cal.to_csv(out / "cutoff_calibration.csv", index=False)
    if not fr.empty:
        fig_auto_vs_manual(fr, out)
    best = ""
    if not cal.empty:
        b = cal.loc[cal.mean_abs_pct_error.idxmin()]
        best = (f"\nBest-matching brightness cut-off on the reviewed fields: **{b.cutoff:.3f}** "
                f"(mean absolute error {b.mean_abs_pct_error:.1f}% per field). The pipeline uses "
                f"{fc.min_contrast.iloc[0]}. See `cutoff_calibration.csv`.\n")
    total, done = len(fc), int(fc.reviewed.sum())
    md = f"""# Manual review status

{done} of {total} fields reviewed ({100 * done / max(total, 1):.0f}%).

Review fields in Fiji with `scripts/review_counts.groovy` (Plugins > RGC > Review Counts Full).
A project's density analysis is written only when every field of every retina in it is reviewed.

{df_md(st)}

## Automated vs manual
```
{agree}```
{best}
{"![automated vs manual](auto_vs_manual.png)" if not fr.empty else ""}
"""
    (out / "REVIEW_STATUS.md").write_text(md, encoding="utf-8")
    return st


# ---------------------------------------------------------------- stage 2: analysis
def retina_table(fc: pd.DataFrame, col: str) -> pd.DataFrame:
    g = fc.groupby(["group", "animal", "eye", "sample"])
    out = g.agg(n_fields=("image", "count"), total_area_mm2=("field_area_mm2", "sum"),
                density_mean=(col, "mean"), density_sd=(col, "std"), density_sem=(col, sem),
                density_auto_mean=("density_filtered_per_mm2", "mean"),
                median_soma_diameter_um=("median_diameter_um", "median")).reset_index()
    return out


def group_table(ret: pd.DataFrame) -> pd.DataFrame:
    ref = ret.loc[ret.group == REFERENCE_GROUP, "density_mean"]
    rows = []
    for g, d in ret.groupby("group"):
        rows.append(dict(group=g, n_retinas=len(d), mean=d.density_mean.mean(), sd=d.density_mean.std(ddof=1),
                         sem=sem(d.density_mean),
                         pct_of_control=100 * d.density_mean.mean() / ref.mean() if len(ref) else np.nan))
    return pd.DataFrame(rows)


def paired_table(ret: pd.DataFrame) -> pd.DataFrame:
    """Left vs right eye of the same animal, when both are present."""
    if not (ret.animal != "").any():
        return pd.DataFrame()
    w = ret[ret.animal != ""].pivot_table(index="animal", columns="eye", values="density_mean")
    if not {"L", "R"} <= set(w.columns):
        return pd.DataFrame()
    w = w.dropna(subset=["L", "R"]).reset_index()
    w["L_pct_of_R"] = 100 * w.L / w.R
    return w[["animal", "L", "R", "L_pct_of_R"]]


def mixed_model(fc: pd.DataFrame, col: str) -> str:
    try:
        import statsmodels.formula.api as smf
    except ImportError:
        return "statsmodels not installed; mixed model skipped"
    if fc.group.nunique() < 2 or fc["sample"].nunique() < 3:
        return "mixed model skipped: needs at least 2 groups and 3 retinas"
    d = fc.copy()
    d["y"] = d[col]
    try:
        m = smf.mixedlm(f"y ~ C(group, Treatment('{REFERENCE_GROUP}')) + C(position)", d,
                        groups=d["sample"]).fit(reml=True)
        return str(m.summary())
    except Exception as e:  # noqa: BLE001
        return f"mixed model failed: {e}"


def tests_text(ret: pd.DataFrame, paired: pd.DataFrame, fc: pd.DataFrame, col: str) -> str:
    lines = []
    ref = ret.loc[ret.group == REFERENCE_GROUP, "density_mean"].to_numpy()
    if len(ref) == 0:
        lines.append(f"No '{REFERENCE_GROUP}' retinas in this project, so no group comparison.\n")
    for g, d in ret.groupby("group"):
        if g == REFERENCE_GROUP or len(ref) == 0:
            continue
        b = d.density_mean.to_numpy()
        lines.append(f"=== {g} vs {REFERENCE_GROUP} (retina means, cells/mm^2) ===")
        lines.append(f"{REFERENCE_GROUP} n={len(ref)}: {np.round(ref, 1).tolist()}")
        lines.append(f"{g} n={len(b)}: {np.round(b, 1).tolist()}")
        if len(ref) >= 2 and len(b) >= 2:
            t = stats.ttest_ind(b, ref, equal_var=False)
            u = stats.mannwhitneyu(b, ref, alternative="two-sided")
            lines.append(f"{g}/{REFERENCE_GROUP} = {100 * b.mean() / ref.mean():.1f}%")
            lines.append(f"Welch t-test: t={t.statistic:.3f}, p={t.pvalue:.4f}")
            lines.append(f"Mann-Whitney U: U={u.statistic:.1f}, p={u.pvalue:.4f} "
                         f"(smallest attainable p with these n: {2 / comb(len(ref) + len(b), len(b)):.3f})")
        else:
            lines.append("too few retinas for unpaired tests")
        lines.append("")
    if not paired.empty:
        lines.append("=== Left vs right eye of the same animal ===")
        lines.append(paired.round(1).to_string(index=False))
        if len(paired) >= 2:
            t = stats.ttest_rel(paired.L, paired.R)
            lines.append(f"Paired t-test (L vs R): t={t.statistic:.3f}, p={t.pvalue:.4f}; "
                         f"mean L/R = {paired.L_pct_of_R.mean():.1f}%")
        lines.append("")
    lines.append("=== Field-level linear mixed model (random intercept per retina) ===")
    lines.append(mixed_model(fc, col))
    return "\n".join(lines)


def color_map(groups):
    return {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(sorted(groups, key=lambda g: (g != REFERENCE_GROUP, g)))}


def fig_retina(fc, ret, col, cmap, out: Path, label):
    ret = ret.sort_values(["group", "sample"], key=lambda s: s.map(lambda g: (g != REFERENCE_GROUP, g))
                          if s.name == "group" else s)
    fig, ax = plt.subplots(figsize=(max(5, 0.9 * len(ret) + 2), 4.2))
    for i, r in enumerate(ret.itertuples()):
        y = fc.loc[fc["sample"] == r.sample, col].to_numpy()
        x = i + np.random.default_rng(i).uniform(-0.15, 0.15, len(y))
        c = cmap.get(r.group, "grey")
        ax.scatter(x, y, s=14, color=c, alpha=0.45, linewidths=0)
        ax.errorbar(i, r.density_mean, yerr=r.density_sd, fmt="o", color=c, ms=7, capsize=4, lw=1.5)
    ax.set_xticks(range(len(ret)), ret["sample"])
    ax.set_ylabel(f"RGC density, {label} (cells / mm²)")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Per-field density by retina (dots = fields, marker = mean ± SD)", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "density_by_retina.png", dpi=150)
    plt.close(fig)


def fig_group(ret, paired, cmap, out: Path, label):
    groups = sorted(ret.group.unique(), key=lambda g: (g != REFERENCE_GROUP, g))
    fig, ax = plt.subplots(figsize=(1.6 * len(groups) + 2.5, 4.2))
    for i, g in enumerate(groups):
        d = ret[ret.group == g]
        y = d.density_mean.to_numpy()
        ax.bar(i, y.mean(), color=cmap[g], alpha=0.25, width=0.6)
        ax.errorbar(i, y.mean(), yerr=sem(y) if len(y) > 1 else 0, color=cmap[g], capsize=6, lw=1.5)
        ax.scatter(np.full(len(y), i), y, color=cmap[g], s=40, zorder=3)
        for yv, s in zip(y, d["sample"]):
            ax.annotate(s, (i, yv), xytext=(8, 0), textcoords="offset points", fontsize=8, va="center")
    if not paired.empty and set(groups) >= {REFERENCE_GROUP}:
        eye_group = ret.groupby("eye").group.first().to_dict()
        if "L" in eye_group and "R" in eye_group and eye_group["L"] in groups and eye_group["R"] in groups:
            xl, xr = groups.index(eye_group["L"]), groups.index(eye_group["R"])
            for p in paired.itertuples():
                ax.plot([xr, xl], [p.R, p.L], color="grey", lw=0.8, alpha=0.6)
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylabel(f"RGC density, {label} (cells / mm²)")
    ax.set_ylim(bottom=0)
    ax.set_title("Groups (dots = retinas, bar = mean ± SEM, lines join eyes of one animal)", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "density_by_group.png", dpi=150)
    plt.close(fig)


def fig_position(fc, col, cmap, out: Path, label):
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for g, d in fc.groupby("group"):
        per = d.groupby(["sample", "position"])[col].mean().reset_index()
        m = per.groupby("position")[col].agg(["mean", sem]).reset_index()
        ax.errorbar(m.position.astype(str), m["mean"], yerr=m["sem"], marker="o", capsize=4,
                    color=cmap.get(g, "grey"), label=g)
    ax.set_xlabel("field position (digit in file name)")
    ax.set_ylabel(f"density, {label} (cells / mm²)")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "density_by_position.png", dpi=150)
    plt.close(fig)


def write_stage2(project: str, fc: pd.DataFrame, out: Path, preliminary: bool):
    if out.exists():
        shutil.rmtree(out)
    for sub in ["tables", "stats", "figures"]:
        (out / sub).mkdir(parents=True, exist_ok=True)
    fc = fc[fc.group != ""].copy()
    col = "density_filtered_per_mm2" if preliminary else "density_manual_per_mm2"
    label = "automated, PRELIMINARY" if preliminary else "manually reviewed"
    ret = retina_table(fc, col)
    grp = group_table(ret)
    paired = paired_table(ret)
    txt = tests_text(ret, paired, fc, col)
    cmap = color_map(ret.group.unique())

    fc.to_csv(out / "tables" / "field_counts.csv", index=False)
    ret.to_csv(out / "tables" / "retina_summary.csv", index=False)
    grp.to_csv(out / "tables" / "group_summary.csv", index=False)
    if not paired.empty:
        paired.to_csv(out / "tables" / "left_vs_right.csv", index=False)
    (out / "stats" / "statistics.txt").write_text(txt, encoding="utf-8")
    fig_retina(fc, ret, col, cmap, out / "figures", label)
    fig_group(ret, paired, cmap, out / "figures", label)
    fig_position(fc, col, cmap, out / "figures", label)

    banner = ("> **PRELIMINARY.** Densities below come from automated counts that have not been fully "
              "reviewed by hand. Do not use them for conclusions.\n\n" if preliminary else "")
    reviewers = ", ".join(sorted(fc.reviewer.dropna().astype(str).unique())) if not preliminary else "n/a"
    md = f"""# {project}: RGC density

{banner}Retinas: {fc['sample'].nunique()} · fields: {len(fc)} · density source: {label} · reviewers: {reviewers}

## Groups (mean of retina means, cells/mm²)
{df_md(grp)}

## Retinas
{df_md(ret, "{:.1f}")}

{"## Left vs right eye" + chr(10) + df_md(paired) if not paired.empty else ""}

## Statistics
```
{txt}
```

![density by retina](figures/density_by_retina.png)
![density by group](figures/density_by_group.png)
![density by position](figures/density_by_position.png)
"""
    (out / "REPORT.md").write_text(md, encoding="utf-8")
    return ret


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", default=str(ROOT / "results" / "simple_rgc"))
    ap.add_argument("--groups", default=str(ROOT / "config" / "sample_groups.csv"))
    ap.add_argument("--preliminary", action="store_true",
                    help="also analyse projects that are not fully reviewed, from automated counts")
    a = ap.parse_args()
    run = Path(a.run)
    summ = run / "summary"
    summ.mkdir(parents=True, exist_ok=True)

    fc = load(run, Path(a.groups))
    cells = load_cells(run, fc)
    st = write_stage1(run, fc, cells, summ / "review")
    print(st.to_string(index=False))

    planned = pd.read_csv(a.groups, dtype=str).fillna("")
    for project, d in fc.groupby("project"):
        if project == "unassigned":
            continue
        # every retina listed for the project in the groups file must be counted, and every field reviewed
        listed = set(planned.loc[planned.get("project", "") == project, "sample"])
        not_counted = sorted(listed - set(d["sample"]))
        complete = bool(d.reviewed.all()) and not not_counted
        target = summ / re.sub(r"[^\w.-]+", "_", project)
        progress = f"{int(d.reviewed.sum())}/{len(d)} fields reviewed"
        if not_counted:
            progress += f"; not counted yet: {', '.join(not_counted)}"
        if complete:
            write_stage2(project, d, target, preliminary=False)
            print(f"{project}: all {len(d)} fields reviewed -> {target}")
        elif a.preliminary:
            write_stage2(project, d, target, preliminary=True)
            print(f"{project}: {progress} -> PRELIMINARY {target}")
        else:
            if target.exists():
                shutil.rmtree(target)
            print(f"{project}: {progress}; analysis waits")
    print(f"\nreview status: {summ / 'review' / 'REVIEW_STATUS.md'}")


if __name__ == "__main__":
    main()
