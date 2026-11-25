# Working in the monorepo

How to organize and add code in `Gokoffski-Lab/lab`. Short version: **one folder per tool,
each tool runs on its own, docs change in the same pull request as the code, and data never goes in.**

## 1. Where new code goes

Pick a folder by asking **where does it run?**

| It… | Goes in | Example |
|---|---|---|
| records, presents stimuli, or exports from an instrument | `acquisition/<name>/` | Blackfly + Plexon sync, OptoDrum export |
| runs on already-recorded data | `analysis/<name>/` | ERG POI stats, flatmount merge, spike sorting |
| is the metadata database or dashboard | `data-system/` | new table, Streamlit page |
| is used by **two or more** subprojects | `shared/` | naming, vocab, CRSP path helpers |
| is a SLURM job | `analysis/hpc3/<job>/` (calls code from its subproject) | |
| is only text (SOP, how-to, decision) | `docs/` | |

If it doesn't fit, ask before making a new top-level folder. The top level stays small.

**Name subprojects by what they do** (`erg`, `sholl`, `flatmount-merge`), not by project or person
(`wet-pig-stuff`, `winston-scripts`). One tool can serve several projects; pass the project in as metadata.

## 2. What every subproject has

Copy a template from [`templates/`](https://github.com/Gokoffski-Lab/lab/tree/main/templates):

- **`README.md`** with the standard header: Status · Owner · Language · Runs on · Docs. Then Install / Run / Test.
- **Its own environment**: `pyproject.toml` (Python) or a toolbox list (MATLAB). There's no repo-wide environment,
  so a dependency upgrade in one tool can't break another.
- **`tests/`** with small **fake** inputs. Even one smoke test is enough to start.
- **Config, not literals**: paths and tunable parameters in a config file or function arguments. No hard-coded `C:\Users\...` or CRSP paths.
- **A docs page** in `docs/workflows/` for anything a lab member runs (copy `_template.md`), added to `mkdocs.yml` `nav`.
- **A CI workflow**: copy `templates/ci-subproject.yml` to `.github/workflows/<name>.yml`.

Status values: 🧪 experimental (may change or be deleted) → ✅ active (others rely on it) → 🗄️ retired
(kept for reproducibility, add `RETIRED.md` saying what replaced it). Don't delete code that produced published or GLP results.

## 3. Rules that keep it from turning into a junk drawer

1. **Subprojects never import from each other.** If two need the same code, move it to `shared/` in its own pull request.
   (`behavior-video/shared/schema` is internal to that one subproject, which is fine.)
2. **Names come from `shared/`** (`build_filename` / `lab_filename`), and eye codes are OD/OS/OU.
3. **No data, no secrets, nothing unpublished**: the repo is public ([decision 0004](../decisions/0004-public-repo.md)).
   CI blocks data file types and files over 5 MB.
4. **Notebooks** are for exploration. Keep them in `<subproject>/notebooks/`, clear outputs before committing,
   and move anything that becomes routine into `src/`.
5. **Big decisions get a short record** in `docs/decisions/` (what, why, consequences).

## 4. Day-to-day git workflow

```bash
git switch main && git pull
git switch -c sholl/add-cellpose-seeds        # branch: <subproject>/<short-description>
# ...edit, test...
git add analysis/sholl docs/workflows/sholl-snt.md
git commit -m "sholl: generate SNT seeds from Cellpose 3D labels"
git push -u origin sholl/add-cellpose-seeds
# open a pull request on GitHub, CI runs only the affected tests
```

- **Commit message prefix = subproject** (`sholl:`, `ephys:`, `docs:`, `shared:`). Then `git log -- analysis/sholl` reads like that tool's changelog.
- **Small pull requests, one subproject each.** The exception: a change to `shared/` plus the callers it updates.
- **`main` is always runnable.** Branch protection requires CI to pass, and requires review for `shared/`, `data-system/` and `docs/sops/` (CODEOWNERS).
- Working alone on experimental code? Still use a branch and a PR. It's the record of what changed and why.
- **Tag releases a paper or GLP study used:** `git tag sholl-v1.0 && git push --tags`. Cite the tag (and commit hash) in methods.

## 5. Bringing code in from elsewhere

| Source | How |
|---|---|
| A git repo (keep history) | `git subtree add --prefix=<dest> <repo-url-or-path> main` |
| A folder with no git | copy the code files into `<dest>/`, commit `"<sub>: import from <machine> (<date>)"` |
| Code on a lab PC you can't push from | zip the code only (no data), move it to a machine with git, then as above |

After importing: add the standard README header, remove hard-coded paths, add one test, then archive the old repo
with a README pointing here.

If an old repo keeps getting commits during the transition, `git subtree pull --prefix=<dest> <url> main` brings them over.
To publish a tool as its own repo later: `git subtree split --prefix=<dest> -b <name>-standalone`.

## 6. Lab members who don't use git

- **Docs:** pencil icon on any page → edit in the browser → "propose changes" (pull request).
- **Tools:** install the way the tool's README says (Fiji update site, a zip from the Releases page, or `pip install`). Nobody has to clone the repo to *use* a tool.
- **Problems:** open an issue (Bug / Workflow request).
