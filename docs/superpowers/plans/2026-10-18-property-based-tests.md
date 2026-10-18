# Property-Based Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every project in the series has teaching-quality property-based tests, a model check where it has state, a "property testing" docs page, and the same Hypothesis settings, with a series home page tying them together.

**Architecture:** The series sync tool (`robcox2910/robcox2910.github.io`, `src/series/`) gains one owned file (a root `conftest.py` holding the Hypothesis profiles) and one `pyproject.toml` edit (the Hypothesis floor), and rolls them out to all 17 repos. Each repo then gets its own PR, following one shared recipe. The home page comes last, so it never links to a page that doesn't exist yet.

**Tech Stack:** Python 3.14, uv, pytest, Hypothesis 6.170 (`given`, `strategies`, `stateful.RuleBasedStateMachine`), tomlkit, MkDocs Material, gh CLI.

**Spec:** `docs/superpowers/specs/2026-10-18-property-based-tests-design.md` (in pystack).

## Global Constraints

- Hypothesis floor: `hypothesis>=6.170`, in `[project.optional-dependencies] dev` (where all 17 repos keep dev dependencies; the spec's "`[dependency-groups] dev`" is corrected to this).
- Profile `ci` (loaded by default): `max_examples=100, deadline=None, derandomize=True, database=None`.
- Profile `thorough`: `max_examples=2000, deadline=None` (random, default database), used as `pytest --hypothesis-profile=thorough`.
- Profiles live in a root-level `conftest.py`, a whole file owned by the sync tool. Never edit a repo's own `tests/conftest.py` for this.
- Property tests in `tests/test_properties.py`; model check in `tests/test_model.py`.
- Every test docstring states its rule in plain English; every strategy is a named function with a one-line docstring (no bare lambdas as strategies).
- Reference models are obviously right and different from the code: dict, list, `sorted`, `sqlite3`, stdlib (`base64`, `hashlib`, `hmac`, `difflib`).
- No `assume`/`.filter` that hides a failing input. Restrict a strategy only to inputs the API documents as valid, with a comment citing where.
- No real sleeps or wall-clock time in properties; time-dependent code uses a fake clock.
- Per-test `@settings(max_examples=...)` only for genuinely expensive tests, with a `# why` comment.
- Docs page: `docs/property-testing.md` in every repo, last in the repo's own nav (just above `# series-nav:start`).
- `.hypothesis/` added to each repo's `.gitignore` (one-off edit in that repo's PR).
- CI test job: no more than about 30 s slower than the previous main run; exceeding it needs a ledgered reason.
- Work only in fresh scratch clones/worktrees off `origin/main` under the session scratchpad; never in local checkouts or `*-wt` worktrees (pynet, pymq in particular).
- One PR per repo, merged on green CI. Commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; PR footer `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- A bug fix that changes a library's public behaviour gets a patch tag (minor for an API change); pystack and pyllm are re-pinned once, in Task 20.

## Review Focus

1. `--hypothesis-profile=thorough` must actually override the root `conftest.py`'s `load_profile("ci")`. If the order is wrong, "thorough" silently runs 100 derandomized examples. Pinned by Task 1's `test_thorough_flag_overrides_ci`.
2. A repo whose own `tests/conftest.py` or test modules already set Hypothesis settings (pebble-lang, pysearch) would override the shared profiles. The recipe's step R3 greps for and removes them.
3. Time-dependent state (pykv TTL, pycoldb TTL, pymq leases, os_learning schedulers) makes model checks flaky. Pinned by the recipe rule "fake clock or leave it out of the model", checked in each per-repo review.
4. Strategies that generate awkward text (empty, NUL, surrogates, `/`, very long) for names that become file names (pydocdb collections, pygit refs, pysearch engine ids). These are the likeliest real bugs. Pinned by recipe step R2: name strategies use `st.text()` unrestricted unless the API documents a restriction.
5. The floor editor meeting a pyproject that has Hypothesis in another extra, a pin other than `>=`, or no dev extra at all. Pinned by Task 1's floor tests.

---

## Per-repo recipe (used by Tasks 2, 3 and 5-19)

Each per-repo task names its repo and anything special; the steps are these.

- [ ] **R1: Workspace.** `git -C /Users/robcox/development/python/<folder> fetch -q`, then `git -C ... worktree add <scratch>/<folder>-props -b test/properties origin/main`, then `uv sync --all-extras`. Record the duration of the test job of the latest main CI run (`gh run list -R robcox2910/<repo> --branch main -L 1`, then `gh run view --json jobs`).
- [ ] **R2: Write `tests/test_properties.py`.** Use the spec's "Starting points" row for this repo:
  - at least one round-trip and one invariant (two invariants if there is no round-trip; a third property for pycrypt, pyllm and pebble-lang);
  - a strategies section at the top, with named functions and docstrings.
- [ ] **R3: Write `tests/test_model.py`** (skip for pycrypt, pyllm and pebble-lang).
  - Use a `RuleBasedStateMachine` with `@rule`s for each mutating operation, plus an `@invariant()` (or per-rule asserts) comparing every read against the reference model.
  - Expose it as `TestXModel = XMachine.TestCase`.
  - Then `git grep -n "settings(" tests` and remove ad-hoc `max_examples`/`deadline` settings that the profiles now cover. A remaining override gets a `# why` comment.
- [ ] **R4: Prove each property can fail.** For every property and the model check:
  - add a one-line deliberate bug to the code under test;
  - run `uv run pytest tests/test_properties.py tests/test_model.py -q --no-cov -p no:randomly`;
  - confirm a failure with a shrunk `Falsifying example`, then revert.

  This is the RED evidence for tests written against existing code. Note each bug and the shrunk example in the PR description. Keep the most readable one, verbatim, for the page's "Try it yourself".
- [ ] **R5: Run both profiles.**
  - `uv run pytest -q` must pass, and so must `uv run pytest -q --hypothesis-profile=thorough`.
  - If a property fails on unmodified code, that is a **real bug**:
    1. pin the shrunk input as a plain example test in the existing test file for that module;
    2. watch it fail;
    3. fix the code;
    4. watch both pass;
    5. note it for the page and the release step (R8).
- [ ] **R6: Write `docs/property-testing.md`**, titled `# Property Testing (<subtitle>)`, with these sections in this order:
  - the everyday comparison;
  - "A property from <Project>" (one property walked through line by line);
  - "Checking against a model" (where there is one);
  - "Try it yourself" (the R4 bug and its real shrunk output);
  - "A bug we found" (only if R5 found one);
  - "Run it yourself" (`uv run pytest tests/test_properties.py` and the `--hypothesis-profile=thorough` command).

  Then add `  - Property Testing: property-testing.md` (or the repo's nav style) as the last entry before `# series-nav:start`, and add `.hypothesis/` to `.gitignore`. `uv run --with mkdocs-material mkdocs build --strict` must exit 0 (delete `site/` after).
- [ ] **R7: Check, commit and open a PR.**
  - `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pre-commit run --all-files` must all pass; revert any hook edits to files outside this task.
  - Commit as `test: property-based tests and model check`, plus `fix: ...` commits for any R5 bugs.
  - Push and open the PR. Its body lists: the properties; the model; the R4 bugs with their shrunk examples; the R5 bugs, if any; the CI time before and after; and the result of the thorough run.
- [ ] **R8: Merge and release.**
  - Merge on green CI with the scratch `release.sh <repo> <folder> <pr> <tag|->`.
  - Use a tag only if R5 changed public behaviour: patch (`v0.x.(y+1)`) for a fix, minor for an API change. Add the new tag to the ledger for Task 20.
  - Remove the worktree and the local branch.

---

### Task 1: Sync tool owns the Hypothesis profiles and floor

**Repo:** `robcox2910/robcox2910.github.io`, worked in a scratch worktree off `origin/main`, branch `feat/hypothesis-standard`.

**Files:**
- Create: `templates/conftest.py`
- Modify: `src/series/render.py` (`render`: add `rendered.files["conftest.py"]`)
- Modify: `src/series/tomledit.py` (add the floor; `apply_standard_toml` calls it)
- Modify: `templates/claude_standard.md` (one Testing bullet)
- Test: `tests/test_tomledit.py`, `tests/test_render.py`, new `tests/test_conftest_template.py`

**Interfaces:**
- Produces:
  - `HYPOTHESIS_FLOOR = "hypothesis>=6.170"` (in `series.tomledit`);
  - `ensure_dev_floor(doc: TOMLDocument) -> None`, which mutates `[project.optional-dependencies] dev`;
  - `apply_standard_toml(text: str) -> str`, which now also applies the floor;
  - an owned file `conftest.py` at each repo root, with content exactly `templates/conftest.py`.

- [ ] **Step 1: Write failing floor tests** in `tests/test_tomledit.py`:

```python
def test_floor_added_when_missing() -> None:
    out = apply_standard_toml('[project]\nname = "x"\n[project.optional-dependencies]\ndev = ["pytest>=8"]\n')
    assert '"hypothesis>=6.170"' in out and '"pytest>=8"' in out

def test_lower_floor_raised() -> None:
    out = apply_standard_toml('[project.optional-dependencies]\ndev = ["hypothesis>=6.100"]\n')
    assert '"hypothesis>=6.170"' in out and "6.100" not in out

def test_higher_floor_left_alone() -> None:
    src = '[project.optional-dependencies]\ndev = ["hypothesis>=7.0"]\n'
    assert '"hypothesis>=7.0"' in apply_standard_toml(src) and "6.170" not in apply_standard_toml(src)

def test_non_floor_pin_replaced() -> None:
    out = apply_standard_toml('[project.optional-dependencies]\ndev = ["hypothesis==6.0"]\n')
    assert '"hypothesis>=6.170"' in out and "==6.0" not in out

def test_dev_extra_created_when_absent() -> None:
    out = apply_standard_toml('[project]\nname = "x"\n')
    assert tomlkit.parse(out)["project"]["optional-dependencies"]["dev"] == ["hypothesis>=6.170"]

def test_hypothesis_in_other_extra_untouched() -> None:
    src = '[project.optional-dependencies]\npebble = ["hypothesis>=6.0"]\ndev = []\n'
    doc = tomlkit.parse(apply_standard_toml(src))["project"]["optional-dependencies"]
    assert doc["pebble"] == ["hypothesis>=6.0"] and doc["dev"] == ["hypothesis>=6.170"]

def test_floor_is_idempotent() -> None:
    once = apply_standard_toml('[project.optional-dependencies]\ndev = ["hypothesis>=6.1"]\n')
    assert apply_standard_toml(once) == once
```

- [ ] **Step 2: Run** `uv run pytest tests/test_tomledit.py -q`. Expected: the 7 new tests FAIL.
- [ ] **Step 3: Implement `ensure_dev_floor`.**
  - Find the dev entry whose requirement name (`packaging.requirements.Requirement(...).name`, lower-cased) is `hypothesis`.
  - Keep it if it has a `>=` specifier at version 6.170 or higher. Otherwise replace it in place with `HYPOTHESIS_FLOOR`, keeping its position.
  - Append `HYPOTHESIS_FLOOR` if there is no such entry.
  - Create `project` → `optional-dependencies` → `dev` if missing.
  - Add `packaging` to the hub's dependencies if it isn't already importable.
- [ ] **Step 4: Run** the same command. Expected: PASS, with the whole file green.
- [ ] **Step 5: Write `tests/test_conftest_template.py`.** It uses pytest's `pytester` fixture (enable it with `pytest_plugins = ["pytester"]` at the top of the module):

```python
def test_ci_profile_is_default(pytester) -> None:
    pytester.makeconftest(TEMPLATE.read_text())
    pytester.makepyfile("""
        from hypothesis import settings
        def test_p():
            s = settings()
            assert (s.max_examples, s.deadline, s.derandomize, s.database) == (100, None, True, None)
    """)
    pytester.runpytest("-p", "no:cacheprovider").assert_outcomes(passed=1)

def test_thorough_flag_overrides_ci(pytester) -> None:
    pytester.makeconftest(TEMPLATE.read_text())
    pytester.makepyfile("""
        from hypothesis import settings
        def test_p():
            s = settings()
            assert (s.max_examples, s.deadline, s.derandomize) == (2000, None, False)
    """)
    pytester.runpytest("--hypothesis-profile=thorough").assert_outcomes(passed=1)

def test_template_passes_the_standard(tmp_path) -> None:
    """The owned file itself passes ruff with the 37 groups and pyright strict."""
    # write TEMPLATE to tmp_path/conftest.py plus a pyproject with RUFF_SELECT; run `ruff check` and `pyright` via subprocess; assert exit 0
```

  `TEMPLATE = Path(series.render.TEMPLATES) / "conftest.py"`. Add `hypothesis>=6.170` to the hub's own dev extra.
- [ ] **Step 6: Run.** Expected: FAIL (no template).
- [ ] **Step 7: Create `templates/conftest.py`.** It has:
  - a module docstring that says, in the series voice, what the two profiles are and how to run `thorough`, and that the file is owned by `series sync` and edited in the series home repo;
  - `from hypothesis import settings`;
  - two `settings.register_profile` calls with the Global Constraints values;
  - `settings.load_profile("ci")`.

  Add `rendered.files["conftest.py"] = (TEMPLATES / "conftest.py").read_text(...)` in `render`.
- [ ] **Step 8: Add a render test**, `test_render_owns_root_conftest`: `render(project, series, tmp_path).files["conftest.py"] == TEMPLATE.read_text()`. Then, in `tests/test_sync.py`, add `test_sync_writes_conftest_and_leaves_tests_conftest_alone`:
  - make a fixture repo with a `tests/conftest.py` holding custom text;
  - run `apply_to_tree`;
  - the root `conftest.py` is written, `tests/conftest.py` is byte-identical, and a second `apply_to_tree` changes nothing.
- [ ] **Step 9: Add to `templates/claude_standard.md`'s Testing section** the bullet: "Property-based tests (Hypothesis) live in `tests/test_properties.py` and `tests/test_model.py`; the shared profiles are in the root `conftest.py` (owned by `series sync`). Run `uv run pytest --hypothesis-profile=thorough` before a release."
- [ ] **Step 10: Run** `uv run pytest -q && uv run ruff check . && uv run pyright`. Expected: all pass.
- [ ] **Step 11:** Commit, open the PR and merge on green. The workflows are unchanged, so tag `v1` doesn't move (ruling against the spec's "tag v1 moved as before": nothing a caller pins changed).
- [ ] **Step 12: Roll out.** From the merged hub `main`:
  - run `SERIES_SCRATCH=<fresh scratch dir> uv run series sync --check` and expect 17 repos drifted only in `conftest.py` and `pyproject.toml` (plus `CLAUDE.md` for the new bullet);
  - run `series sync` to open 17 PRs and merge each on green (`release.sh ... -`);
  - run `series sync --check` with a fresh scratch dir and expect exit 0.

  Each repo also needs its lock refreshed. If `uv sync --locked` fails in CI because the lock is stale, run `uv lock` in the sync branch before merging (ledger it; it's a sync-tool follow-up if it happens).

### Task 2: Pilot, PyCrypt

Follow R1-R8 for `pycrypt` (folder `pycrypt`). There's no model check.
- **Properties:**
  - the XOR round-trip, over bytes and over text;
  - the Caesar round-trip for any shift (negative and above 26);
  - HMAC sign/verify agrees with stdlib `hmac`, and a tampered message fails.
- **Page:** subtitle "(Every Key Opens Its Own Lock)".
- **After merge,** pause the rollout for the Task 4 template review.

### Task 3: Pilot, PyKV

Follow R1-R8 for `pykv`.
- **Properties:**
  - `save_store`/`load_store` round-trip (`to_dict` equality);
  - **arbitrary bytes on disk give `PersistenceError`, never another exception.** This exposes the known `UnicodeDecodeError` gap. Fix it with `except (OSError, UnicodeDecodeError)` in `load_store`, and tag the patch.
- **Model:** `BasicStore` vs dict (set, get, delete, keys, size). A `TTLStore` model only with an injected fake clock; if `TTLStore` has no clock seam, leave it out and ledger why.

### Task 4: Template review

Dispatch one reviewer on the pycrypt and pykv PRs (merged diffs) and pages against the spec's standard and anti-goals.
- Fold its findings into this plan's recipe as a ledgered ruling (for example, a fixed section wording) before Task 5.
- Fix pilot findings in a follow-up PR per repo.

### Tasks 5-19: Rollout (one PR each, R1-R8)

Use the spec's "Starting points" row for each. Notes beyond that row:

| Task | Repo (folder) | Notes |
|---|---|---|
| 5 | py-os (`os_learning`) | ~23k lines. Model: memory manager frame conservation. Keep scheduler properties to pure `select` calls; no real timers. |
| 6 | pebble-lang | No model; three properties. Existing `tests/test_format_roundtrip.py` stays where it is (the page links it); remove its `max_examples=200, deadline=None` unless measured as needed. The parser property: any text only ever raises `PebbleError`. |
| 7 | pydb | Model: table vs `sqlite3` (INTEGER/TEXT columns; insert, delete-by-key, select-all ordered by key), plus B-tree vs sorted list. |
| 8 | pydoc-db (`pydocdb`) | Arbitrary bytes on disk → `PersistenceError` (UTF-8 gap: verify, fix, patch tag). Collection names unrestricted text: case-insensitive disks are already handled by docdb file naming in pystack, but check pydocdb's own persistence. |
| 9 | pygraphdb | BFS visits exactly the reachable set. |
| 10 | pytsdb | Downsampling conserves count and sum. |
| 11 | pyvecdb | Top-k equals a brute-force sort; ties are compared as sets. |
| 12 | pycoldb | Arbitrary bytes → `PersistenceError` (UTF-8 gap: verify, fix, patch tag). TTL only with a fake clock. |
| 13 | pysearch | Existing `@settings(max_examples=MAX_EXAMPLES)` moves to the profile. |
| 14 | pymq | Model: `MessageQueue` vs list (put/get/ack/reject, with dead letters once `retries > max_retries`). The broker work-queue model only if it runs without real time; otherwise ledger it as deferred. |
| 15 | pynet | Never touch the local checkout or worktrees. Frame and codec round-trips across random chunk splits. |
| 16 | pyweb | Malformed heads only raise `HttpParseError`. |
| 17 | pygit | Object hash equals `sha1(b"blob %d\0" % len + data)`. |
| 18 | pyllm | No model; three properties. Tokenizer round-trip draws text only from the tokenizer's own alphabet (documented: unknown characters are unsupported, a known deferred minor). No `tests/__init__.py`, so check pytest still finds the root conftest. |
| 19 | pystack | Model: the kv plugin through `PyStackEnvironment` vs dict, including a restart rule; slow, so the per-test `max_examples` override carries a `# why` comment. pydb-to-Pebble value mapping is total. |

### Task 20: Re-pin dependents

For each tag created in Tasks 2-19, in one PR per dependent:
- in pystack, edit the tags in `pyproject.toml`, `uv lock --upgrade-package <pkg>`, and update `tests/test_dependency_pins.py` if it lists tags;
- in pyllm, do the same for pebble-lang and pystack.

Merge on green. If any pystack tag was created, re-pin pyllm after pystack's new tag. If no tags were created, record "Task 20: nothing to re-pin" in the ledger.

### Task 21: The series home page

**Repo:** the hub, branch `feat/property-testing-page`.

**Files:**
- Modify: `series.yml` (a `property:` one-liner per project, describing the property its page walks through, taken from each merged page)
- Modify: `src/series/config.py` (`REQUIRED_FIELDS` + `"property"`; `Project.property: str`)
- Modify: `src/series/sync.py` (`render_property_page(series: list[Project]) -> str`; `_plan_hub` adds `docs/property-testing.md`)
- Modify: hub `mkdocs.yml` nav: `- Property Testing: property-testing.md` after `Home`
- Test: `tests/test_config.py`, `tests/test_hub.py`

- [ ] **Step 1: Failing tests.**
  - `test_property_field_required`: a series entry without `property` raises `SeriesError` naming the field.
  - `test_property_page_lists_every_project_in_order`: the page contains, for each project in `series.yml` order, `[<name>](https://robcox2910.github.io/<repo>/property-testing/)` followed by its `property` text.
  - `test_hub_plan_includes_property_page`: `_plan_hub` on an empty tmp hub (with the required `mkdocs.yml`/`CLAUDE.md`) includes `docs/property-testing.md`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** The page opens with the idea explained once (an everyday comparison, then what shrinking is), then the list. Fill `property:` for all 17.
- [ ] **Step 4: Run** `uv run pytest -q`, `ruff`, `pyright`, then `uv run series hub` (it writes `docs/property-testing.md`), then `mkdocs build --strict`. Expected: all pass.
- [ ] **Step 5:** Merge on green.
- [ ] **Step 6: Verify.**
  - Every `https://robcox2910.github.io/<repo>/property-testing/` returns 200, and so does `https://robcox2910.github.io/property-testing/`.
  - `series sync --check` with a fresh `SERIES_SCRATCH` exits 0.
  - `series hub` makes no change.
