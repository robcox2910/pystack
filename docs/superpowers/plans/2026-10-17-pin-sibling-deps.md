# Pin Sibling Dependencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pystack and pyllm build against tagged sibling releases recorded in `uv.lock`, never against siblings' moving `main`.

**Architecture:** Tag every library, switch consumer `[tool.uv.sources]` from `path = "../x"` to `git = ..., tag = ...`, delete CI clone steps, install with `uv sync --locked`. A pytest guard keeps sources pinned. Docs describe upgrading, releasing and the temporary local override.

**Tech Stack:** uv git sources, hatch-vcs, GitHub Actions, pytest + tomllib, gh CLI.

**Spec:** `docs/superpowers/specs/2026-10-17-pin-sibling-deps-design.md` (pystack)

## Global Constraints

- Source form, exactly: `<pkg> = { git = "https://github.com/robcox2910/<repo>", tag = "vX.Y.Z" }` — no `editable`, no `rev`, no `branch`.
- GitHub repo name differs from package/folder name in two cases: `pyos-learn` → repo `py-os`; `pydocdb` → repo `pydoc-db`. Every other repo name equals the package name.
- Tags: os_learning `v0.2.0`; pebble-lang, pydb, pyweb, pygit, pycrypt, pynet, pysearch, pymq, pykv, pydocdb, pygraphdb, pytsdb, pyvecdb, pycoldb, pyllm `v0.1.0`; pystack `v0.1.0` after its PR merges.
- Tags are annotated (`git tag -a vX.Y.Z -m "vX.Y.Z"`) on `origin/main` after confirming that commit's CI is green.
- CI installs with `uv sync --locked --all-extras`; no job clones a sibling.
- Never touch pynet's `feat/event-loop` checkout or the `pystack-pynet-wt` worktree. pynet is tagged from `origin/main` with `git tag ... origin/main` — no checkout needed.
- Versioning rule (README "Releasing"): public-API change → minor bump; anything else → patch bump.
- Every PR follows the series fix workflow: ruff, ruff format, pyright `0 errors`, pytest green locally; PR; merge on green CI.

## Review Focus

1. Fresh clone with no sibling folders beside it → `uv sync --locked` must succeed (Task 2 Step 6, Task 3 Step 7).
2. Repo-name ≠ package-name (`py-os`, `pydoc-db`) → a wrong URL fails resolution; the guard test pins the exact URL map (Task 3 Step 1).
3. The local override really reverts: `uv pip install -e ../pebble-lang` then `uv sync --locked` must restore the tagged version (Task 3 Step 8).
4. pystack depends on pyllm, which pins pebble-lang itself. uv ignores a git dependency's own `tool.uv.sources`, so pystack's pebble-lang pin is the one that counts. The two must name the same tag, or pystack silently runs pyllm against a different pebble-lang than pyllm was tested with. This is checked in Task 3 Step 7 rather than by a test, to keep the suite offline.
5. hatch-vcs version from a tag → installed `importlib.metadata.version("pydb")` is `0.1.0`, not `0.0.0` or a dev version (Task 3 Step 7). Not a pytest test: it would fail during a legitimate local override.

---

### Task 1: Tag the libraries

**Files:** none (git tags only).

**Interfaces:**
- Produces: tags listed in Global Constraints on each library's `origin/main`, except pyllm (Task 2).

- [ ] **Step 1: Confirm main CI is green for each library**

Run, per repo (repo names per Global Constraints):
`gh run list -R robcox2910/<repo> --branch main --limit 1 --json conclusion -q '.[0].conclusion'`
Expected: `success` for all 15. Any other result: stop and fix before tagging.

- [ ] **Step 2: Tag and push**

Per folder: `git -C <folder> fetch -q origin && git -C <folder> tag -a <tag> -m <tag> origin/main && git -C <folder> push origin <tag>`

- [ ] **Step 3: Verify**

Run: `git ls-remote --tags https://github.com/robcox2910/<repo> <tag>` for all 15.
Expected: one line each, SHA equal to that repo's `origin/main`.

### Task 2: pyllm pins pebble-lang

**Files:**
- Modify: `pyllm/pyproject.toml` (`[tool.uv.sources]`), `pyllm/uv.lock`
- Modify: `pyllm/.github/workflows/ci.yml` (lint, test, security jobs)
- Modify: `pyllm/README.md` (new sections "Developing alongside a sibling" and "Releasing")
- Test: `pyllm/tests/test_dependency_pins.py`

**Interfaces:**
- Consumes: pebble-lang `v0.1.0` (Task 1).
- Produces: pyllm tag `v0.1.0` whose pyproject pins `pebble-lang` at `v0.1.0`.

- [ ] **Step 1: Write the failing guard test**

```python
class TestDependencyPins:
    def test_every_sibling_source_is_a_tagged_git_source(self) -> None:
        for name, source in _sources().items():
            assert set(source) == {"git", "tag"}, name
            assert source["git"] == f"{GITHUB}/{REPOS.get(name, name)}", name
            assert TAG_PATTERN.fullmatch(source["tag"]), name
```
`_sources()` reads `[tool.uv.sources]` from the repo's `pyproject.toml` with `tomllib`; `GITHUB = "https://github.com/robcox2910"`; `REPOS = {"pyos-learn": "py-os", "pydocdb": "pydoc-db"}`; `TAG_PATTERN = re.compile(r"v\d+\.\d+\.\d+")`.

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_dependency_pins.py -v`
Expected: FAIL — `{'path', 'editable'} != {'git', 'tag'}` for `pebble-lang`.

- [ ] **Step 3: Switch the source and relock**

Set `pebble-lang = { git = "https://github.com/robcox2910/pebble-lang", tag = "v0.1.0" }`, then `uv lock`.

- [ ] **Step 4: Remove CI clones**

Delete all three "Clone sibling projects" steps; change every `uv sync --all-extras` to `uv sync --locked --all-extras`.

- [ ] **Step 5: README**

"Developing alongside a sibling": `uv pip install -e ../pebble-lang` to try an unreleased change; the next `uv sync` restores the pinned tag. "Releasing": merge, `git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z`; public-API change bumps minor, otherwise patch; consumers upgrade by editing the tag and running `uv lock --upgrade-package <name>`.

- [ ] **Step 6: Verify**

Run: guard test + full suite + ruff + pyright. Then in the scratchpad: `git clone` the branch alone and run `uv sync --locked --all-extras && uv run pytest -q`.
Expected: all green; the lone clone resolves with no `../pebble-lang`.

- [ ] **Step 7: Ship and tag**

Commit `build: pin pebble-lang to v0.1.0 and stop cloning it in CI`; PR; merge on green. Then tag pyllm `v0.1.0` on the merge commit and verify with `git ls-remote`.

### Task 3: pystack pins all 16 siblings

**Files:**
- Modify: `pystack/pyproject.toml` (`[tool.uv.sources]`), `pystack/uv.lock`
- Modify: `pystack/.github/workflows/ci.yml` (lint, test, security jobs)
- Modify: `pystack/CLAUDE.md` (Dependencies section), `pystack/README.md` (install comment at line ~303 plus "Developing alongside a sibling" and "Releasing")
- Test: `pystack/tests/test_dependency_pins.py`

**Interfaces:**
- Consumes: Task 1 tags; pyllm `v0.1.0` (Task 2).
- Produces: pystack tag `v0.1.0`.

- [ ] **Step 1: Write the failing guard test**

The same `test_every_sibling_source_is_a_tagged_git_source` as Task 2, with the same constants, plus:
```python
    def test_every_sibling_has_a_pinned_source(self) -> None:
        assert set(_sources()) == SIBLINGS
```
`SIBLINGS` is the frozenset of the 16 package names in Global Constraints (`pyos-learn`, not `os_learning`).

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_dependency_pins.py -v`
Expected: the first test FAILs on a `path` source; the second passes (all 16 already have sources). It stays as a guard against a sibling being added without a pin.

- [ ] **Step 3: Switch all 16 sources and relock**

Per Global Constraints (os_learning `v0.2.0`, pyllm `v0.1.0`, rest `v0.1.0`); `uv lock`.

- [ ] **Step 4: Remove CI clones**

Delete the three "Clone sibling projects" steps; `uv sync --locked --all-extras` everywhere.

- [ ] **Step 5: Docs**

CLAUDE.md Dependencies: replace "path dependencies" line with: siblings are pinned git tags in `[tool.uv.sources]`; upgrade by editing the tag and `uv lock --upgrade-package <name>`; local override `uv pip install -e ../<folder>`, reverted by `uv sync`. README: install comment becomes "pinned sibling releases"; add the two sections as in Task 2 Step 5.

- [ ] **Step 6: Run the suite**

Run: full pytest, ruff, ruff format --check, pyright.
Expected: all green.

- [ ] **Step 7: Lone-clone and version check**

In the scratchpad, clone the branch alone; `uv sync --locked --all-extras && uv run pytest -q`; then
`uv run python -c "import importlib.metadata as m; print(m.version('pydb'), m.version('pyos-learn'))"`
Expected: suite green; prints `0.1.0 0.2.0`.
Also confirm the pebble-lang pins agree: `git -C ../pyllm show v0.1.0:pyproject.toml | grep pebble-lang` names the same tag as pystack's source (Review Focus 4).

- [ ] **Step 8: Override reverts**

In the pystack checkout: `uv pip install -e ../pebble-lang`, print pebble-lang's version (a `.dev` version), then `uv sync --locked --all-extras` and print again.
Expected: second print is `0.1.0`.

- [ ] **Step 9: Ship and tag**

Commit `build: pin every sibling to a release tag and stop cloning main in CI` (the spec and this plan are already on the branch); PR noting the `pystack-pynet-wt` branch will need a rebase; merge on green; tag pystack `v0.1.0`.

### Task 4: "Releasing" section in each library README

**Files:**
- Modify: `README.md` in the 15 libraries from Task 1: os_learning, pebble-lang, pydb, pyweb, pygit, pycrypt, pynet, pysearch, pymq, pykv, pydocdb, pygraphdb, pytsdb, pyvecdb, pycoldb. pyllm's is done in Task 2.

**Interfaces:**
- Consumes: the wording from Task 2 Step 5 "Releasing".

- [ ] **Step 1: Add the section**

Append the "Releasing" section from Task 2 Step 5, naming pystack (and for pebble-lang, pyllm) as the consumer that upgrades by tag. pynet: edit in a worktree off `origin/main`.

- [ ] **Step 2: Ship**

One PR per repo, `docs: how to release a version`; merge on green. These docs-only merges need no new tag.
