# The series home: docs websites, one source of truth, one standard

**Date:** 2026-10-17
**Theme:** 6 of the October 2026 series audit ("tooling and docs drift")
**Repos:** all 17 projects, plus one new repo, `robcox2910/robcox2910.github.io`

## Why

The 17 "from scratch" projects are meant to be learned from, and a learner's
first step is **reading the project on GitHub**. Today what they find there
is inconsistent, and some of it is untrue:

- **Broken docs links.** Every README's "Full docs at
  robcox2910.github.io/<project>" link is a 404. Not one docs website exists.
  pebble-lang's deploy workflow succeeds, but GitHub Pages was never turned
  on for the repo.
- **Missing licenses.** 15 of the 17 repos have no LICENSE file, though
  pystack's README says MIT.
- **Inconsistent series tables.** The "Related Projects" tables differ from
  repo to repo (different subsets, orders and wording).
- **Drifted tooling.**
  - pyllm runs 6 ruff rule groups (the series standard is 37), basic pyright,
    no pre-commit, and has no CLAUDE.md or LICENSE.
  - Six storage repos have no pre-commit.
  - os_learning's CLAUDE.md was copied from a trading repo.
  - The pre-commit pip-audit hook audits its own isolated environment, not
    the project.

The user wants a **proper docs website** for every project, and the projects
to **go hand in hand**: a learner moves naturally between them. The series is
mostly complete ("but never say never"), so the fix should be light, without
a project generator, while still making it easy to add a project later.

## Goals

- Every project has a live docs website at
  `https://robcox2910.github.io/<repo>/`, built from its own `docs/` folder,
  with one shared look and a menu listing the whole series.
- A series home page at `https://robcox2910.github.io/` shows the learning
  path: what each project teaches and which projects build on which.
- The series list (order, names, repos, one-line descriptions, "builds on")
  is written **once**, in `series.yml`. Every README table, every site's
  series menu and the home page are generated from it.
- Every repo has an MIT LICENSE, a working "Full docs" link, and the
  standard README sections.
- Every repo meets one tooling standard: the same 37 ruff rule groups,
  strict pyright, the same pre-commit hooks (with a pip-audit that audits
  the project), and CI from one shared workflow.
- Every repo has an accurate CLAUDE.md: a shared standard section plus its
  own project notes.

## Non-goals

- A project generator (copier/cookiecutter). If a new project comes along,
  it copies an existing repo and runs the sync tool, which fills in the
  shared parts.
- A single combined website with every project's pages in one build.
- Rewriting the docs content itself, beyond fixing links and adding the
  series menu and "see also" links.
- Changing each repo's coverage floor. It stays where it lives today, in
  each repo's `pyproject.toml` (`--cov-fail-under`), and isn't duplicated
  into CI. *(Claude's call.)*

## Anti-goals (would be a failure even if it "works")

- A README or site that links to something that doesn't exist.
- Shared content edited by hand in 17 places. If the series list or the
  standard changes, one edit plus one sync run must update everything.
- A sync tool that silently overwrites a repo's own content. It owns only
  clearly marked blocks and files, and anything else is left alone.
- Pushing to anyone's in-progress branches or checkouts. All changes go
  through PRs on fresh branches from `origin/main`.

## Design

### 1. The series home repo: `robcox2910/robcox2910.github.io` (new, public)

A GitHub "user site" repo, so its Pages site is served at
`https://robcox2910.github.io/`. It holds everything shared:

| Path | What it is |
|---|---|
| `series.yml` | The single source of truth (below) |
| `docs/` + `mkdocs.yml` | The series home page: intro, learning path, one card per project |
| `.github/workflows/python-ci.yml` | Reusable CI: lint, format, pyright, tests, security |
| `.github/workflows/docs.yml` | Reusable docs build and deploy to that repo's Pages |
| `templates/` | The managed files and blocks the sync tool writes (below) |
| `tools/sync.py` | Renders `templates/` + `series.yml` into each project repo and opens PRs |
| `tests/` | Tests for `sync.py` and for `series.yml` validity |

The repo follows the same standard as the others (uv, ruff, pyright, tests).

`series.yml` holds one entry per project, in learning-path order:

```yaml
- name: PyOS                        # display name
  repo: py-os                       # GitHub repo
  folder: os_learning               # local folder name
  package: pyos-learn               # Python package name
  teaches: Operating systems        # one-liner for tables and menus
  builds_on: []                     # names of projects it uses
```

The order and the "teaches" wording come from the current pystack table,
which is the most complete. The six storage databases (pykv, pydocdb,
pygraphdb, pytsdb, pyvecdb, pycoldb) aren't in that table, so their wording
is drafted fresh. **The builder drafts the learning-path order**, and the
user reviews it in the series-home PR.

Reusable workflows are referenced by tag:
`uses: robcox2910/robcox2910.github.io/.github/workflows/python-ci.yml@v1`.
A project's own `ci.yml` and `docs.yml` shrink to a few lines, with inputs
only where repos really differ (for example, whether the docs build runs the
tests for an HTML coverage report).

### 2. Docs websites

- Every repo gets a `mkdocs.yml` using **Material for MkDocs** (already used
  by pebble-lang, pydb and os_learning), with a shared theme block (palette,
  fonts, features) written by the sync tool.
- Repos without one get a new `mkdocs.yml` whose nav lists their existing
  learner-facing `docs/` pages. Internal working documents under
  `docs/superpowers/` (design specs and plans) are **never published**: the
  shared mkdocs settings `exclude_docs` them, and nothing links to them.
  *(Claude's call: the sites are for learners.)* If a repo has no `docs/index.md`, its README becomes the
  home page (copied at build time, or via a short index page that points to
  the concept pages; builder's choice).
- Every site's nav ends with a **"The series"** section, generated from
  `series.yml`: the series home first, then every project, with the current
  project marked.
- `docs.yml` (calling the reusable workflow) builds with `mkdocs build
  --strict` and deploys to the `gh-pages` branch on every push to `main`.
  **GitHub Pages is turned on** for every repo (source: the `gh-pages`
  branch) via `gh api`.
- Every README's "Full docs" link points to its live site, and **CI checks
  that the link returns 200** after deploy. That check runs in the docs
  workflow, not the PR workflow, because the site only exists after deploy.
- "See also" cross-links where projects meet (for example PyDB's saving page
  to PyStack's "Your data is saved", or Pebble's public-API chapter to
  PyStack) are added by hand to a small, listed set of pages. **The builder
  picks at most about 10 high-value links**; this isn't a full cross-linking
  pass.

### 3. The standard (owned by the sync tool)

The sync tool owns these **whole files**:

- `LICENSE`: MIT, "Copyright (c) 2026 Rob Cox" (the same text as
  pebble-lang's).
- `.pre-commit-config.yaml`: the standard hooks. The pip-audit hook becomes a
  **local hook** that runs `uv export --frozen --no-emit-project --all-extras
  --no-hashes` and audits that file with `pip-audit -r ... --disable-pip
  --no-deps`, so it checks the project's real third-party dependencies (as
  pystack's CI now does).
- `.github/workflows/ci.yml` and `docs.yml`: the thin callers of the
  reusable workflows.

It also owns these **marked blocks** inside files that are otherwise the
repo's own:

- `README.md`:
  - the "Related Projects" table, between `<!-- series:start -->` and
    `<!-- series:end -->`;
  - the "Documentation" section, which carries the live site link.
- `CLAUDE.md`: a "Series standard" block (code style, linting, testing,
  commits, dependencies, releasing). The rest of each repo's CLAUDE.md is
  its own project notes. **First sync:** today every CLAUDE.md has unmarked
  generic sections (Code Style, Linting, Testing, Commits, Dependencies).
  The first sync replaces exactly those headed sections with the marked
  block, under these rules:
  - Any line in them that isn't standard text moves into a "Project notes"
    section below the block. Pystack's sibling-pin rules and its Plugins
    section are examples.
  - The PR description lists every moved line, so nothing is lost silently.
  - Sections with other headings are left alone.

  *(Claude's call.)*
- `pyproject.toml`: `[tool.ruff.lint] select` (exactly the 37 groups, the
  same everywhere) and `[tool.pyright] typeCheckingMode = "strict"`. The tool edits these keys
  only, via a TOML-aware editor that preserves comments. Per-repo
  `ignore`, `per-file-ignores`, coverage floors and so on stay the repo's
  own.
- `mkdocs.yml`: the theme block and the "The series" nav section.

`tools/sync.py`:

- **Run modes:**
  - `--check` reports drift and exits non-zero if any repo differs from the
    templates;
  - the default run writes the changes into a fresh branch in a scratch
    clone of each repo (never into a local checkout), pushes it and opens
    one PR per repo;
  - `--repo NAME` limits the run to one repo.
- **Never writes outside its owned files and blocks.** If a marked block is
  missing, it inserts it at a documented place (the "Related Projects"
  section replaces the existing one on the first sync) and says so in the
  PR.
- **Idempotent:** running it twice makes no second change.

### 4. pyllm brought up to the standard

pyllm (about 2,600 lines) gets everything above, plus it must actually
**pass** the standard:

- the 37 rule groups, with about 400 missing type annotations plus
  docstrings;
- strict pyright;
- pre-commit;
- a CLAUDE.md;
- a LICENSE;
- `.coverage` untracked and gitignored.

Tests keep passing, with no behaviour changes. This is the biggest single
piece and is done in its own PR(s) before pyllm is synced.

### 4b. os_learning brought up to the standard

os_learning (py-os, ~23k lines) selects 28 rule groups: it lacks A, BLE,
EM, FLY, ISC, PGH, RSE, SLF and T10, and has TCH, which isn't one of the
37. Turning the 37 on finds about 348 violations (about 217 SLF001 and 125
EM101). It gets the same treatment as pyllm, in its own PR(s) before it's
synced:

- Fix the source code.
- Private access in **tests** (SLF001) may be allowed with a repo-level
  `per-file-ignores` for `tests/**`, which is the repo's own setting and not
  the shared `select`.
- TCH goes.

*(Claude's call: one standard, no per-repo additions to `select`.)*

### 5. CLAUDE.md content

- **Every repo** gets the shared "Series standard" block.
- **os_learning:** its trading-repo content is replaced with accurate notes
  on os_learning itself (package `py_os`; the shell split into
  `py_os/shell/commands/*`; the `_missing_subsystem` pattern; complexity
  limit 15).
- **pyllm:** a new CLAUDE.md (numpy autograd, the bundled checkpoints, the
  referee).
- **Every other repo:** keeps its own notes below the block.

### 6. Repos with in-progress work

The sync tool only ever works in scratch clones and opens PRs. It never
touches local checkouts or `*-wt` worktrees.

## Order of work

1. **Create the series home repo:**
   - `series.yml`;
   - the reusable workflows, tagged `v1`;
   - `sync.py` with tests;
   - the home site, live at `robcox2910.github.io`.
2. **pyllm uplift** (§4) and **os_learning uplift** (§4b).
3. **Sync dry run** (`--check`) across all 17 repos. Review the drift report.
4. **Sync for real:** one PR per repo, merged on green CI. Turn on Pages for
   each repo and confirm its "Full docs" link returns 200.
5. **Hand-written content:**
   - the "see also" links;
   - os_learning's and pyllm's CLAUDE.md project notes.

Library repos get no new release tags: these are docs and tooling changes.

## Testing

- **`sync.py` unit tests:**
  - a block is replaced only between its markers;
  - a missing block is inserted at the documented place;
  - a second run makes no change;
  - `--check` exits non-zero on drift;
  - TOML key edits keep comments and other keys;
  - an owned file that differs is rewritten, and an unowned file is never
    touched.
- **`series.yml` validation test:** every entry has every field, repo
  names exist, and every `builds_on` name exists in the file.
- **After the rollout:**
  - `sync.py --check` passes for all 17 repos;
  - every repo's CI passes on the reusable workflow;
  - all 18 sites (17 plus the home page) return 200;
  - every README "Full docs" link resolves.

## Left to the builder

- The exact Material theme options and colours.
- The home page's wording and layout.
- Where the README docs link sits in each README.
- How repos without `docs/index.md` get a home page.
- Which ~10 cross-links to add.
- The internal structure of `sync.py`, apart from its run modes, its owned
  files and blocks, and the guarantees above.
