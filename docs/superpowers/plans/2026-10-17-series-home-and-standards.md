# Series Home and Standards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every project has a live docs website and an accurate README, LICENSE, CLAUDE.md and tooling. All of the shared parts are generated from one series home repo.

**Architecture:** A new repo, `robcox2910/robcox2910.github.io`, holds:
- `series.yml`;
- the reusable CI and docs workflows;
- the series home site;
- a small Python package (`series`) whose `sync` command renders templates into each project and opens PRs.

pyllm and os_learning are brought up to the lint and type standard first. Then the sync rolls out, one PR per repo.

**Tech Stack:** Python 3.14, uv, tomlkit (comment-preserving TOML edits), PyYAML, Jinja2, pytest, MkDocs Material, GitHub Actions reusable workflows, `actions/deploy-pages`, gh CLI.

**Spec:** `pystack/docs/superpowers/specs/2026-10-17-series-home-and-standards-design.md`

## Global Constraints

- **Repos and names.** The 17 projects have these GitHub repo names: py-os, pebble-lang, pydb, pyweb, pygit, pycrypt, pynet, pysearch, pymq, pykv, pydoc-db, pygraphdb, pytsdb, pyvecdb, pycoldb, pyllm, pystack. Two local folders differ from their repo names: os_learning (py-os) and pydocdb (pydoc-db).
- **The series home repo** is `robcox2910/robcox2910.github.io`: public, local folder `/Users/robcox/development/python/robcox2910.github.io`, Python package `series` under `src/series/`.
- **Ruff rule groups.** The standard ruff `select` is exactly the 37 groups below, in this order: `["E","W","F","I","N","UP","B","C4","C90","PTH","SIM","TID","S","PERF","FURB","PIE","T10","T20","ERA","PL","RET","ARG","FBT","DTZ","ICN","PT","D","RUF","A","BLE","EM","FLY","ISC","PGH","RSE","SLF","TRY"]`.
- **Pyright** must use `typeCheckingMode = "strict"`.
- **Repo-owned settings.** The sync never edits `ignore`, `per-file-ignores`, pyright execution environments or coverage floors.
- **LICENSE.** MIT, `Copyright (c) 2026 Rob Cox`. The body text is copied byte-for-byte from `pebble-lang/LICENSE`, with only the copyright line changed.
- **Markers:**
  - README: `<!-- series:start -->` / `<!-- series:end -->` and `<!-- docs:start -->` / `<!-- docs:end -->`;
  - CLAUDE.md: `<!-- standard:start -->` / `<!-- standard:end -->`;
  - mkdocs.yml: `# theme:start` / `# theme:end` and `# series-nav:start` / `# series-nav:end`.
- **Docs sites:**
  - each project's site is at `https://robcox2910.github.io/<repo>/`, and the home is at `https://robcox2910.github.io/`;
  - Pages build type is `workflow`, deployed with `actions/upload-pages-artifact` and `actions/deploy-pages`;
  - `exclude_docs` covers `superpowers/`;
  - builds use `mkdocs build --strict`.
- **The pip-audit check** (pre-commit and CI) runs `uv export --frozen --no-emit-project --all-extras --no-hashes`, then `pip-audit -r <file> --disable-pip --no-deps`.
- **Where the sync may write.** Only in fresh clones under the session scratchpad, on the branch `chore/series-standard`, one PR per repo, merged on green CI. It never writes to local checkouts or `*-wt` worktrees.
- **No library release tags** for any of this. It's docs and tooling only.

## Review Focus

1. **A README whose series heading is worded differently.** pyllm's is `## Related projects — "from scratch in Python"`, and some have none. The first sync must replace any `## Related projects…` section, whatever its case or suffix, and insert one before `## License` (or at the end) when it's missing. Task 3: `test_first_sync_replaces_variant_heading` and `test_missing_section_inserted_before_license`.
2. **A repo whose `docs/` holds only `superpowers/`, or has no `docs/` at all.** Its site still builds with a home page made from the README. Task 5: `test_new_mkdocs_for_repo_without_docs_index`.
3. **Hand edits.** A hand edit outside every owned block survives a sync byte-for-byte, and a second sync changes nothing. Task 3: `test_text_outside_blocks_untouched` and Task 6: `test_apply_twice_is_idempotent`.
4. **Existing pages that break `mkdocs build --strict`,** for example a page linking to `../src/...`. Task 10's dry run builds every site locally and records each fix needed.
5. **CLAUDE.md lines specific to one repo.** For example, pystack's sibling-pin rules are never lost: they move into "## Project notes", and the PR body lists them. Task 4: `test_repo_specific_lines_move_to_project_notes`.

---

### Task 1: Series home repo, `series.yml` and its loader

**Files (in `robcox2910.github.io/`):**
- Create:
  - `pyproject.toml`: uv project `series-home` with deps tomlkit, pyyaml, jinja2; dev deps pytest, pytest-cov, ruff, pyright, pre-commit, pip-audit; the 37-group ruff `select`, pystack's `ignore` list, strict pyright and `--cov-fail-under=90`;
  - `series.yml`;
  - `src/series/__init__.py`;
  - `src/series/config.py`;
  - `tests/test_config.py`;
  - `README.md`, `CLAUDE.md`, `LICENSE`, `.gitignore`.

**Interfaces:**
- Produces: `@dataclass(frozen=True) class Project: name: str; repo: str; folder: str; package: str; teaches: str; builds_on: tuple[str, ...]`, with:
  - `site_url` (property) → `f"https://robcox2910.github.io/{repo}/"`;
  - `github_url` (property) → `f"https://github.com/robcox2910/{repo}"`.
- Produces: `load_series(path: Path = SERIES_FILE) -> list[Project]`, which raises `SeriesError` for:
  - a missing field;
  - a duplicate name or repo;
  - an unknown `builds_on` name;
  - a `builds_on` that points at a later project.
- `series.yml` order and wording:
  - Start from pystack's README Related Projects table (PyOS, Pebble, PyDB, PyCrypt, PyWeb, PyNet, PyGit, PySearch, PyMQ, PyLLM, PyStack).
  - Add the six storage databases after PyDB: PyKV, PyDocDB, PyGraphDB, PyTSDB, PyVecDB, PyColDB.
  - PyStack comes last.
  - `builds_on`: PyStack lists all 16. PyLLM lists Pebble. Everything else lists `[]`, except where a dependency exists in that project's `pyproject.toml`.

- [ ] **Step 1: Write failing tests:**
  - `test_series_has_all_17_projects_in_order`: names list equality;
  - `test_folder_and_repo_differ_for_pyos_and_pydocdb`;
  - `test_builds_on_names_exist_and_come_earlier`;
  - `test_missing_field_raises_series_error`: a tmp YAML file;
  - `test_site_url`: PyDB → `https://robcox2910.github.io/pydb/`.
- [ ] **Step 2: Run them.** Expected: `ImportError`.
- [ ] **Step 3: Implement** `config.py` and `series.yml`.
- [ ] **Step 4: Run them.** Expected: pass. ruff, pyright and pre-commit are clean.
- [ ] **Step 5: Create the GitHub repo and push.**
  - `gh repo create robcox2910/robcox2910.github.io --public --source . --push`, with the initial commit on `main`.
  - Then turn on Pages: `gh api -X POST repos/robcox2910/robcox2910.github.io/pages -f build_type=workflow`.

### Task 2: Reusable workflows

**Files (series home):**
- `.github/workflows/python-ci.yml`: `on: workflow_call`, inputs `python-version` (default `"3.14"`). It has three jobs:
  - **lint:** `uv sync --locked --all-extras`, ruff check, ruff format --check, pyright.
  - **test:** `uv run pytest`.
  - **security:** `continue-on-error: true`; runs the Global Constraints pip-audit command.
- `.github/workflows/docs.yml`: `on: workflow_call`, inputs `coverage-report` (bool, default false).
  - **Build job:** if `coverage-report` is set, `uv sync --locked --all-extras && uv run pytest --cov-report=html:docs/coverage`. Then `uvx --from mkdocs==1.6.1 --with mkdocs-material==9.6.* mkdocs build --strict -d site`, then `actions/upload-pages-artifact@v3`.
  - **Deploy job:** `actions/deploy-pages@v4`, permissions `pages: write, id-token: write`, environment `github-pages`.
  - **Check job:** retries `curl -sf` on `${{ steps.deploy.outputs.page_url }}` for up to 5 minutes.
- `.github/workflows/ci.yml` (the hub's own): `uses: ./.github/workflows/python-ci.yml`.
- `.github/workflows/site.yml` (the hub's own): `uses: ./.github/workflows/docs.yml` on push to main.
- Templates (the per-project callers, written by sync in Task 5): `templates/ci.yml` calls `robcox2910/robcox2910.github.io/.github/workflows/python-ci.yml@v1`. `templates/docs.yml` likewise calls `docs.yml@v1` on push to main and `workflow_dispatch`, with `coverage-report: {{ coverage_report }}`.

- [ ] **Step 1:** `uvx actionlint .github/workflows/*.yml templates/*.yml`. Expected: no findings. Template placeholders are `{{ }}` inside YAML strings, so render one template first if actionlint rejects it.
- [ ] **Step 2:** push, then check that the hub's CI run passes: `gh run watch`.
- [ ] **Step 3:** tag `v1` (annotated) and push. Commit `ci: reusable python-ci and docs workflows`.

### Task 3: Marked blocks

**Files (series home):** `src/series/blocks.py`, `tests/test_blocks.py`

**Interfaces:**
- Produces: `replace_block(text: str, start: str, end: str, body: str) -> str | None`. It replaces the text between the markers, keeping the markers, and returns `None` if the markers are absent. It raises `BlockError` if there's only one marker or more than one pair.
- Produces: `upsert_section_block(text: str, *, heading_pattern: str, start: str, end: str, body: str, before_heading: str = "## License") -> str`, which works in this order:
  1. If the markers are present, use `replace_block`.
  2. Otherwise, if a level-2 heading matches `heading_pattern` (a regex, case-insensitive), replace that whole section, from the heading to the next `## ` or the end of file, with `start\nbody\nend`.
  3. Otherwise, insert the block before `before_heading` if present, or else at the end.

- [ ] **Step 1: Write failing tests:**
  - `test_replace_between_markers_only`;
  - `test_text_outside_blocks_untouched`: bytes before and after the block are equal;
  - `test_single_marker_raises`;
  - `test_first_sync_replaces_variant_heading`: input `## Related projects — "from scratch in Python"` plus a table, pattern `related projects`;
  - `test_missing_section_inserted_before_license`;
  - `test_missing_section_appended_when_no_license`;
  - `test_upsert_is_idempotent`: applying it twice gives equal output.
- [ ] **Step 2: Run them.** Expected: `ImportError`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: pass.
- [ ] **Step 5: Commit** `feat: marked-block editing`.

### Task 4: `pyproject` keys and the CLAUDE.md first sync

**Files (series home):** `src/series/tomledit.py`, `src/series/claude_md.py`, `tests/test_tomledit.py`, `tests/test_claude_md.py`

**Interfaces:**
- Produces: `apply_standard_toml(text: str) -> str`. Using tomlkit, it sets `tool.ruff.lint.select` to the 37 groups and `tool.pyright.typeCheckingMode` to `"strict"`, creating the tables if they're missing. All other content and comments stay unchanged.
- Produces: `split_claude_md(text: str, standard: str) -> tuple[str, list[str]]`. It returns the new text and the moved lines, as follows:
  1. If the standard markers exist, it uses `replace_block` and the moved list is empty.
  2. Otherwise it removes level-2 sections headed `Code Style`, `Linting`, `Testing`, `Commits` or `Dependencies` (exact names, any case).
  3. Every non-blank line from those sections that doesn't appear (stripped) in `standard` goes into the moved list.
  4. It inserts the marked standard block after the H1 title (or at the top).
  5. It appends the moved lines under `## Project notes`, creating that section if it's missing and adding to it if it exists.

- [ ] **Step 1: Write failing tests:**
  - `test_select_replaced_and_comments_kept`;
  - `test_ignore_and_per_file_ignores_untouched`;
  - `test_missing_tables_created`;
  - `test_generic_sections_replaced_by_block`;
  - `test_repo_specific_lines_move_to_project_notes`: use pystack's current CLAUDE.md as the fixture, copied into `tests/fixtures/`, and assert the sibling-pin lines are in the moved list and under "## Project notes";
  - `test_other_sections_untouched`;
  - `test_second_split_is_idempotent`.
- [ ] **Step 2: Run them.** Expected: `ImportError`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: pass.
- [ ] **Step 5: Commit** `feat: standard pyproject keys and CLAUDE.md split`.

### Task 5: Templates and rendering

**Files (series home):** `templates/` (LICENSE, pre-commit-config.yaml, ci.yml, docs.yml, readme_series.md.j2, readme_docs.md.j2, claude_standard.md, mkdocs_theme.yml, mkdocs_series_nav.yml.j2, mkdocs_new.yml.j2), `src/series/render.py`, `tests/test_render.py`

**Interfaces:**
- Produces: `@dataclass class Rendered: files: dict[str, str]; blocks: dict[str, list[tuple[...]]]`. `files` maps a repo-relative path to its full content. `blocks` maps a repo-relative path to `(heading_pattern | None, start, end, body)` entries.
- Produces: `render(project: Project, series: list[Project], repo_root: Path) -> Rendered`. It reads `repo_root` only to decide two things: whether `mkdocs.yml` and `docs/index.md` exist, and whether `docs/coverage` is wanted. `coverage_report` is true only when the existing `docs.yml` runs pytest with an HTML coverage report.

**Content rules:**
- **README series block:** a table with the columns `Project | What it teaches | Repository | Docs`, listing all 17 in `series.yml` order, with the current project's row in bold.
- **README docs block:** `## Documentation`, followed by `Full docs (with kid-friendly explanations of every idea): <site_url>`.
- **`claude_standard.md`:** the generic sections from pystack's CLAUDE.md (Code Style, Linting, Testing, Commits, Dependencies, Releasing), worded generically. It refers to `per-file-ignores` as repo-owned.
- **`mkdocs_theme.yml`:** pebble-lang's theme block. Everything except palette colours is fixed; the builder picks the colours.
- **`mkdocs_series_nav.yml.j2`:** a `- The series:` nav entry. It lists "Series home" first, then all 17 projects with their `site_url`, the current project included (rendered as plain text, as `[You are here] <name>`, or as a link: builder's choice).
- **`mkdocs_new.yml.j2`:** used only when there is no `mkdocs.yml`. It contains:
  - `site_name`, `site_url`, `repo_url`;
  - the theme block markers, plus `exclude_docs: superpowers/`;
  - a nav of `index.md` plus every `docs/**/*.md` outside `superpowers/`, sorted;
  - the series-nav markers.
- **When `docs/index.md` is missing,** render adds `docs/index.md` as a file whose content is the README with its relative links rewritten to GitHub URLs.

- [ ] **Step 1: Write failing tests** (these use `tmp_path` fake repos):
  - `test_series_table_lists_all_17_in_order_and_bolds_current`;
  - `test_docs_block_links_site_url`;
  - `test_license_has_2026_rob_cox`;
  - `test_ci_caller_uses_v1`;
  - `test_new_mkdocs_for_repo_without_docs_index`: no `docs/` directory, so `mkdocs.yml` and `docs/index.md` are both rendered, the nav has the index, and `exclude_docs` has `superpowers/`;
  - `test_existing_mkdocs_gets_blocks_not_file`;
  - `test_superpowers_docs_never_in_nav`.
- [ ] **Step 2: Run them.** Expected: `ImportError`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: pass.
- [ ] **Step 5: Commit** `feat: render the standard for a project`.

### Task 6: The sync command

**Files (series home):** `src/series/sync.py`, the `[project.scripts] series = "series.sync:main"` entry, `tests/test_sync.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4 and 5.
- Produces:
  - `apply_to_tree(repo_root: Path, project: Project, series: list[Project]) -> SyncResult(changed: list[str], moved_claude_lines: list[str])`. It writes `Rendered.files`, applies the blocks (with `upsert_section_block` for `heading_pattern` entries and `replace_block` or insert-at-documented-place for the others), runs `apply_standard_toml` on `pyproject.toml`, and runs `split_claude_md` on `CLAUDE.md`, creating CLAUDE.md as an H1 plus the block if it's missing.
  - `check_tree(...) -> list[str]` returns the paths that would change, without writing anything.
- CLI: `series sync [--check] [--repo NAME]`:
  - For each project, it clones `gh repo clone robcox2910/<repo> <scratch>/<repo> -- --depth 50` into `$SERIES_SCRATCH`, which is required, so it never runs in local checkouts.
  - `--check` prints the drift per repo and exits 1 if any repo has drift.
  - Without `--check`, it does `git switch -c chore/series-standard`, then `apply_to_tree`, then commits `chore: series standard (LICENSE, docs site, tooling, CLAUDE.md)` with the attribution line, pushes, and runs `gh pr create`. The PR body lists the changed files and every moved CLAUDE.md line.
- `series home` renders `docs/index.md` for the hub from `series.yml`: a learning-path list grouped as "Start here", "Storage", "Systems" and "Putting it together", with one card per project. The builder picks the grouping; it's reviewed in the hub PR.

- [ ] **Step 1: Write failing tests** (on a `tmp_path` fake repo built from pystack-like fixtures):
  - `test_apply_twice_is_idempotent`;
  - `test_check_reports_drift_then_clean_after_apply`;
  - `test_unowned_files_untouched`: an extra file's bytes are unchanged;
  - `test_moved_lines_reported`;
  - `test_cli_refuses_without_scratch_env`.
- [ ] **Step 2: Run them.** Expected: `ImportError`.
- [ ] **Step 3: Implement.** Keep the git and gh calls in a small `_run(cmd, cwd)` helper; the tests don't cover it.
- [ ] **Step 4: Run them.** Expected: pass. Coverage ≥ 90%.
- [ ] **Step 5: Commit** `feat: series sync command`.

### Task 7: The series home site goes live

- [ ] **Step 1:** generate the home page with `uv run series home`, add `mkdocs.yml` (theme block plus series-nav), and run `mkdocs build --strict` locally. Expected: success.
- [ ] **Step 2:** commit `docs: series home page`, push, then wait for `site.yml`. Expected: deploy succeeds and `curl -sf https://robcox2910.github.io/` returns 200.
- [ ] **Step 3:** the series home repo then syncs itself (`apply_to_tree` on its own checkout is allowed: it's the only repo whose checkout is ours) so that its README and CLAUDE.md follow the standard. Commit.

### Task 8: pyllm brought up to the standard

**Files:** `pyllm/pyproject.toml` (37 groups, pystack's `ignore`, strict pyright), all of `pyllm/src`, `pyllm/tests`, `pyllm/.gitignore` (`.coverage`), `pyllm/CLAUDE.md` (project notes only: numpy autograd, bundled checkpoints `src/pyllm/data/*.npz`, the referee, corpus regeneration).

- [ ] **Step 1:** in a pyllm branch `chore/standard`, apply the pyproject keys and record the counts from `uv run ruff check . --statistics` and `uv run pyright`. Expected: about 400 ANN plus D and other findings.
- [ ] **Step 2:** fix them in commits grouped by package (`autograd`, `nn`, `models`, `tokenizer`, `training`, `pebble`, top-level, tests).
  - Behaviour must not change: the full suite stays at 250 passed after every commit.
  - Repo-level `per-file-ignores` are allowed only for tests (S101 is already ignored) and must be listed in the PR.
- [ ] **Step 3:** `git rm --cached .coverage`, add `.coverage` to `.gitignore`, and add the CLAUDE.md project notes.
- [ ] **Step 4:** ruff, format, `pyright` (0 errors) and the suite (250 passed). PR `chore: bring pyllm up to the series standard`; merge on green.

### Task 9: os_learning brought up to the standard

**Files:** `os_learning/pyproject.toml` (37 groups, drop TCH, keep its own `ignore` plus `per-file-ignores` `"tests/**" = ["SLF001"]` if needed), `os_learning/src/**`, `os_learning/CLAUDE.md` (replace the trading content with notes on py_os: the shell package `py_os/shell/commands/*`, the `_missing_subsystem` pattern, C90 max-complexity 15).

- [ ] **Step 1:** branch from origin/main in a scratch worktree (never the local checkout), apply the keys, and record the counts. Expected: about 348.
- [ ] **Step 2:** fix them, with EM101 and the A/BLE fixes in src. The suite must stay green after every commit (the count from `uv run pytest -q` at the start of the task).
- [ ] **Step 3:** CLAUDE.md project notes. Run ruff, pyright and the suite. PR `chore: bring os_learning up to the series standard`; merge on green.

### Task 10: Dry run across all 17

- [ ] **Step 1:** `SERIES_SCRATCH=<scratchpad>/series uv run series sync --check`. Save the report to the plan workspace.
- [ ] **Step 2:** for each repo, in its scratch clone, run `apply_to_tree` without pushing, then `uvx --from mkdocs==1.6.1 --with mkdocs-material==9.6.* mkdocs build --strict`. Record every failure, such as broken relative links or missing nav pages.
- [ ] **Step 3:** fix template or render problems in the series home (each with a test, RED→GREEN, then re-tag `v1` only if a workflow changed). Fix content problems per repo, inside that repo's sync PR in Task 11. Commit.

### Task 11: Rollout

- [ ] **Step 1:** turn on Pages for every repo: `gh api -X POST repos/robcox2910/<repo>/pages -f build_type=workflow`, or `-X PUT` if a branch-based Pages config already exists.
- [ ] **Step 2:** `uv run series sync`, which opens 17 PRs. For repos that Task 10 flagged, push the content fixes onto that PR's branch.
- [ ] **Step 3:** merge each PR on green CI.
- [ ] **Step 4:** wait for each repo's docs workflow, then verify that all 18 sites return 200 and that every README's site link is the one in `series.yml`.
- [ ] **Step 5:** `series sync --check` exits 0.

### Task 12: Cross-links

- [ ] **Step 1:** add at most 10 "See also" links between existing concept pages where projects meet. This is done in one PR per touched repo. Candidates:
  - PyDB saving → PyStack "Your data is saved";
  - Pebble "Using Pebble from Python" → PyStack;
  - PyLLM Pebble pages → Pebble;
  - PyWeb ↔ PyNet HTTP;
  - PyMQ → PyStack mqnet.
- [ ] **Step 2:** each touched site rebuilds with `--strict` and its links return 200. Merge on green.
