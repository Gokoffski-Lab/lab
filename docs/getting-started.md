# Getting started

## Reading

Everything is on this site. Use the search box (top right).

## Fixing or adding a page (no git needed)

1. Open the page and click the **pencil icon** (top right of the page). It opens the file on GitHub.
2. Edit the text. Pages are [Markdown](https://www.markdownguide.org/basic-syntax/): `#` for headings, `-` for bullets, `**bold**`.
3. At the bottom, choose **"Create a new branch… and start a pull request"**, write one line on what you changed, and submit.
4. Winston (data steward) reviews and merges it. The site updates a few minutes later.

New workflow? Copy the [template](workflows/_template.md) and fill it in, or
[open an issue](https://github.com/Gokoffski-Lab/lab/issues/new/choose) and describe it.

## Reporting a problem

Something broken or out of date → [open an issue](https://github.com/Gokoffski-Lab/lab/issues/new/choose)
and pick **Bug** or **Workflow / docs request**.

## For people writing code

Read [Working in the monorepo](contributing/monorepo.md) first. The short version:

- Clone: `git clone https://github.com/Gokoffski-Lab/lab.git`
- Work on a branch, open a pull request. CI runs the tests for the folders you changed.
- Each subproject has its own environment; read its README first.
- Build file names with [`shared/`](https://github.com/Gokoffski-Lab/lab/tree/main/shared) helpers ([File naming](sops/file-naming.md)).
- Never commit data, `.mat`/`.pl2`/`.tif` files, spreadsheets, or anything with credentials.
