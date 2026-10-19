# Pebble's Front Door and Plugin State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pebble gets a small public API that never touches a shared module table. pystack and pyllm use only that API. pystack's plugins own their data and keep it between runs.

**Architecture:**
- pebble-lang gains `pebble/api.py`, built on a private `pebble/_pipeline.py` that threads a per-call module table through `ModuleResolver`.
- pysearch gains save/load. pygraphdb, pytsdb and pyvecdb gain a `PersistenceError`.
- pystack moves plugin state onto plugin instances, adds `load_state`/`save_state`/`on_shutdown` hooks and saves on shutdown.
- Every library change ships as a tagged release that the consumers pick up through the pinned-tag process.

**Tech Stack:** Python 3.14, uv, pytest (+ Hypothesis), ruff, pyright strict, Flask (pystack web), gh CLI.

**Spec:** `pystack/docs/superpowers/specs/2026-10-17-pebble-api-and-plugin-state-design.md`

## Global Constraints

- Repos live in `/Users/robcox/development/python/<folder>`. GitHub names: os_learning → `py-os`, pydocdb → `pydoc-db`, all others are the same as the folder.
- Every repo change goes through a PR from a feature branch, merged on green CI. Before pushing, run all of these:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - pyright, which must report `0 errors`
  - `uv run pytest`
- Do every library change in a scratch worktree off `origin/main`, under the session scratchpad. Never switch or modify these checkouts:
  - pymq's checkout (`feat/network-broker`);
  - pynet's checkout;
  - `pystack-mqnet-wt` (`feat/mqnet-demo`);
  - any other `*-wt` worktree.

  pystack and pyllm work happens in their own checkouts on a feature branch.
- Releases: `git tag -a vX.Y.Z -m vX.Y.Z origin/main && git push origin vX.Y.Z`, only after main CI is green. Each of these gets `v0.2.0`:
  - pebble-lang, pysearch, pygraphdb, pytsdb, pyvecdb, pyllm and pystack.
- Consumer bumps: edit the tag in `[tool.uv.sources]`, then `uv lock --upgrade-package <name>`. pystack's pebble-lang tag must equal pyllm's.
- **mq is out of scope.** pystack's `plugins/mq_plugin.py` and its tests change only as far as the front-door switch forces them to (spec §5).
- **Docstrings and tests:**
  - pebble-lang, pysearch and the storage libraries follow their CLAUDE.md (docstrings on everything, kid-friendly voice).
  - pyllm matches its existing test style.
- No `global` statements and no `reset_*_state()` helpers remain in pystack's plugins, except in mq.

## Review Focus

1. **First run.** With no `pystack_data/<plugin>/` folder, every plugin starts empty without error. A shutdown with no plugin use writes no plugin files (Task 8, `test_untouched_plugins_write_nothing`).
2. **Corrupt save file at boot.** `PyStackEnvironment` raises the library's `PersistenceError` naming the file, and the file's bytes are unchanged afterwards (Task 8, `test_corrupt_save_file_stops_boot_and_is_kept`).
3. **Concurrent runs.** Two `run_source` calls in threads with different `modules` each see only their own module. Afterwards the shared built-in table is unchanged (Task 1, `test_concurrent_runs_keep_their_own_modules`).
4. **A user module shadowing a built-in.** `modules={"math": ...}` raises `ValueError` and doesn't silently replace `math` (Task 1, `test_module_named_like_a_builtin_is_rejected`).
5. **Web server stop.** Ctrl-C on `pystack-web` saves the data (Task 9, `test_server_saves_when_it_stops`).

---

### Task 1: pebble-lang front door

**Files:**
- Create: `pebble-lang/src/pebble/_pipeline.py`, `pebble-lang/src/pebble/api.py`
- Modify:
  - `src/pebble/resolver.py`: `ModuleResolver.__init__` and lines 163 and 190, which read `STDLIB_MODULES`;
  - `src/pebble/__init__.py`;
  - `src/pebble/cli.py`, lines ~145-195, the run path including `--debug`.
- Test: `tests/test_api.py`

**Interfaces:**
- Produces, in `pebble/__init__.py`: `check`, `format_source`, `compile_source`, `run_source`, `Program`, `StdlibModule`, `Value`, `PebbleError`.
  - `check(source: str) -> None`: lex + parse only; raises `PebbleError`.
  - `format_source(source: str) -> str`: runs `check(source)`, then returns `Formatter(source).format()`.
  - `compile_source(source: str, *, modules: Mapping[str, StdlibModule] | None = None, base_dir: Path | None = None) -> Program`
  - `run_source(source: str, *, modules=None, base_dir=None, output: TextIO | None = None) -> str`, which is `compile_source(...).run(output)`.
  - `Program.run(self, output: TextIO | None = None) -> str` returns everything the program printed. It also writes that text to `output` when one is given.
- `ModuleResolver(*, base_dir: Path, modules: Mapping[str, StdlibModule] | None = None, cache=..., resolving=...)`:
  - `None` means `STDLIB_MODULES`.
  - Sub-resolvers it creates inherit the same `modules`.
- `_pipeline.compile_program(source, *, modules: Mapping[str, StdlibModule], base_dir: Path) -> Program` holds the exact steps pystack's `environment.py:206-244` uses today:
  - lex, parse;
  - analyzer + resolver;
  - `type_check`, compile, `optimize`;
  - merge into `CompiledProgram`.
- `Program` also has a private `_run(output, debug_hook)`, which the CLI's `--debug` uses.
- The REPL is out of scope: it compiles line by line with `run_repl` and doesn't duplicate the one-shot path. It keeps using `ModuleResolver`'s default table.

- [ ] **Step 1: Write failing tests in `tests/test_api.py`**

```python
class TestRunSource:
    def test_returns_what_the_program_printed(self) -> None:
        assert run_source('print("hi")') == "hi\n"

    def test_also_writes_to_a_given_output(self) -> None:
        out = io.StringIO(); run_source("print(1)", output=out); assert out.getvalue() == "1\n"

    def test_extra_module_is_importable_for_that_run_only(self) -> None:
        greet = StdlibModule(functions={"hello": (1, lambda a: f"hello {a[0]}")}, constants={})
        assert run_source('import "greet"\nprint(hello("Ada"))', modules={"greet": greet}) == "hello Ada\n"
        with pytest.raises(PebbleError):
            run_source('import "greet"')

    def test_shared_builtin_table_is_never_changed(self) -> None:
        before = dict(STDLIB_MODULES)
        run_source('import "greet"\nprint(hello("x"))', modules={"greet": GREET})
        assert STDLIB_MODULES == before

    def test_module_named_like_a_builtin_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="math"):
            run_source("print(1)", modules={"math": GREET})

    def test_concurrent_runs_keep_their_own_modules(self) -> None:
        # 2 threads x 50 runs; module "who" returns "A" in one thread, "B" in the other;
        # each thread asserts every output is its own letter.

    def test_base_dir_controls_file_imports(self, tmp_path: Path) -> None:
        # write tmp_path/"lib.pbl" defining fn double(n) { return n * 2 }
        assert run_source('import "lib.pbl"\nprint(double(4))', base_dir=tmp_path) == "8\n"

class TestCompileSource:
    def test_program_runs_more_than_once(self) -> None:
        program = compile_source("print(2)"); assert program.run() == program.run() == "2\n"
    def test_type_errors_surface_at_compile_time(self) -> None:
        with pytest.raises(PebbleError): compile_source('let x: int = "no"')

class TestCheckAndFormat:
    def test_check_accepts_valid_and_rejects_invalid(self) -> None:
        check("let x = 1");
        with pytest.raises(PebbleError): check("let = 1")
    def test_format_source_is_canonical(self) -> None:
        assert format_source("let   x=1") == "let x = 1\n"
    def test_format_source_rejects_invalid(self) -> None:
        with pytest.raises(PebbleError): format_source("let = 1")
```
Adjust the Pebble snippets (import syntax, the type-annotation error) to whatever the language actually accepts. Each test has to fail for the reason its name gives.

- [ ] **Step 2: Run** `uv run pytest tests/test_api.py -q`. Expected: FAIL with `ImportError` (no `run_source`).
- [ ] **Step 3: Implement the resolver `modules` parameter, `_pipeline.py`, `api.py` and the re-exports.** Collision check: any key of `modules` that is in `STDLIB_MODULES` raises `ValueError(f"module name {name!r} is already a built-in")`.
- [ ] **Step 4: Run** the `test_api.py` tests. Expected: all pass.
- [ ] **Step 5: Switch `cli.py`'s run path, including `--debug`, to `_pipeline.compile_program` and `Program._run(debug_hook=...)`.** The existing CLI tests must still pass unchanged. Then run the full suite plus the lint and type checks.
- [ ] **Step 6: Commit** `feat: a public API for running Pebble from Python`.

### Task 2: pebble-lang docs chapter and release

**Files:**
- Create: `pebble-lang/docs/concepts/using-pebble-from-python.md` and `tests/test_docs_api_examples.py`.
- Modify:
  - `mkdocs.yml` nav: add `- Using Pebble from Python: concepts/using-pebble-from-python.md` after `Modules`;
  - `README.md`: one sentence and a link.

**Interfaces:**
- Consumes: Task 1's public names.

- [ ] **Step 1: Write the failing test**

```python
CHAPTER = Path(__file__).parent.parent / "docs/concepts/using-pebble-from-python.md"

def test_every_python_example_in_the_chapter_runs() -> None:
    blocks = re.findall(r"```python\n(.*?)```", CHAPTER.read_text(encoding="utf-8"), re.S)
    assert len(blocks) >= 5
    for block in blocks:
        exec(compile(block, str(CHAPTER), "exec"), {})  # noqa: S102 -- our own docs
```
- [ ] **Step 2: Run it.** Expected: FAIL (the file doesn't exist).
- [ ] **Step 3: Write the chapter in the series' kid-friendly voice.** At least five python examples, each checking its own result with `assert`:
  1. run a program and get its output;
  2. write to an output stream;
  3. catch a `PebbleError`;
  4. `check` and `format_source`;
  5. a `greet` module written in Python, passed with `modules=`.

  Also cover:
  - one paragraph on "what's public": only these names are promised, and everything else may change;
  - a "how it works" section mapping `run_source` to lexer → parser → analyzer → compiler → VM, linking the existing concept pages.
- [ ] **Step 4: Run** the test and the full suite. Expected: pass.
- [ ] **Step 5: Ship.** PR `feat: public API for using Pebble from Python` covering Tasks 1 and 2. Merge on green, then tag `v0.2.0`, because this is a public-API change.

### Task 3: pysearch save/load and release

**Files:**
- Create: `pysearch/src/pysearch/atomic.py` (copy pygraphdb's `atomic.py` verbatim), `src/pysearch/persistence.py`, `tests/test_persistence.py`, `docs/concepts/saving.md` (add it to the nav).
- Modify:
  - `src/pysearch/engine.py`: keep the raw text in `self._documents: dict[str, str]`;
  - `src/pysearch/errors.py`: `class PersistenceError(PySearchError)`;
  - `src/pysearch/__init__.py`.

**Interfaces:**
- Produces:
  - `SearchEngine.to_dict(self) -> dict[str, object]`, which returns `{"format": 1, "documents": {doc_id: text}}`;
  - `SearchEngine.from_dict(cls, data: dict[str, object]) -> SearchEngine`, which re-adds the documents in their saved order;
  - `save_engine(engine: SearchEngine, path: str | Path) -> None`, which writes through `atomic_write_text`;
  - `load_engine(path: str | Path) -> SearchEngine`, which raises `PersistenceError(f"... {path} ...")` on an `OSError`, bad JSON, a wrong shape or an unknown `format`.

- [ ] **Step 1: Write failing tests.**
  - `test_round_trip_gives_identical_search_results` is a Hypothesis test over lists of `(unique id, text)` pairs. For every word that appears in the texts, `search(word)` gives equal results on the original and the loaded engine.
  - `test_missing_file_raises_persistence_error`
  - `test_bad_json_raises_persistence_error_naming_the_file`
  - `test_unknown_format_raises_persistence_error`
  - `test_save_never_leaves_a_half_written_file`: monkeypatch `os.replace` to raise, then assert the previous file's content is unchanged and no temp file remains.
- [ ] **Step 2: Run them.** Expected: FAIL with `ImportError`.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run** the full suite plus the lint and type checks. Expected: pass.
- [ ] **Step 5: Ship.** PR `feat: save and load a search engine`. Merge on green, then tag `v0.2.0`.

### Task 4: PersistenceError in pygraphdb, pytsdb and pyvecdb, with releases

**Files (in each of the three repos):**
- Modify: `src/<pkg>/errors.py`, which gains `class PersistenceError(<the base error>)`. The base errors are `GraphError`, `PyTSDBError` and `VecDBError` respectively.
- Modify the loaders: pygraphdb `persistence.py` `load_graph`; pytsdb `persistence.py` `load`; pyvecdb `persistence.py` `load_store`. Also update `__init__.py` exports, the docs "Saving Safely" section, and `tests/test_persistence.py`.

**Interfaces:**
- Produces: each loader raises `PersistenceError` with the path in the message for an `OSError` (missing file included), a `JSONDecodeError`, or a `KeyError`/`TypeError`/`ValueError` from a wrong shape. The error is chained `from` the original. The docstring's `Raises:` lists it.

- [ ] **Step 1: Write failing tests per repo:** `test_missing_file_raises_persistence_error`, `test_bad_json_raises_persistence_error_naming_the_file`, `test_wrong_shape_raises_persistence_error`.
- [ ] **Step 2: Run them.** Expected: FAIL, with a `FileNotFoundError`, `JSONDecodeError` or `KeyError` escaping.
- [ ] **Step 3: Implement**, following pykv's `load_store` pattern (`pykv/src/pykv/persistence.py:80-110`).
- [ ] **Step 4: Run** the full suite plus the lint and type checks in each repo. Expected: pass.
- [ ] **Step 5: Ship.** One PR per repo, `feat: a PersistenceError for unreadable save files`. Merge each on green, then tag `v0.2.0` (a new public exception).

### Task 5: pyllm uses the front door, and its release

**Files:**
- Modify:
  - `pyllm/src/pyllm/pebble/score.py`: `_require_pebble` imports `check` and `PebbleError` from `pebble`; `is_valid` calls `check`;
  - `src/pyllm/pebble/corpus.py`: `canonicalize` calls `pebble.format_source`;
  - `pyproject.toml`: pebble-lang tag `v0.2.0`;
  - `uv.lock`.
- Test: the existing `tests/pebble/` and `tests/test_corpus.py`, plus a new `tests/pebble/test_uses_public_api.py`.

- [ ] **Step 1: Write the failing test.** `test_pyllm_imports_only_pebbles_public_api` scans `src/pyllm` for `from pebble.` and `import pebble.` and asserts there are none. Only `from pebble import ...` is allowed.
- [ ] **Step 2: Run it.** Expected: FAIL. It lists `score.py` and `corpus.py`.
- [ ] **Step 3: Bump the pin, then switch the two call sites.** The friendly install hints stay.
- [ ] **Step 4: Run** the full suite plus ruff and pyright. Expected: everything passes unchanged (249+).
- [ ] **Step 5: Ship.** PR `refactor: use Pebble's public API`. Merge on green, then tag pyllm `v0.2.0`.

### Task 6: pystack runs Pebble through the front door

**Files:**
- Modify:
  - `pystack/pyproject.toml`: tags for pebble-lang, pysearch, pygraphdb, pytsdb, pyvecdb and pyllm become `v0.2.0`; also `uv.lock`;
  - `src/pystack/environment.py`, lines 11-19 and 193-244;
  - `src/pystack/plugins/registry.py`, lines 10 and 81-86;
  - `src/pystack/adapters/pebble_db.py`: delete `register_db_module`, `unregister_db_module`, `bound_db_module` and `_DB_SHELF_LOCK`; keep `make_db_module`;
  - `tests/test_pebble_db.py`.
- Test: `tests/test_pebble_front_door.py`

**Interfaces:**
- Produces:
  - `PluginRegistry.pebble_modules(self) -> dict[str, StdlibModule]`, which maps `pebble_module_name()` to `pebble_stdlib()` for every plugin whose stdlib isn't `None`;
  - `PyStackEnvironment.run_pebble_source(source)`, which calls `pebble.run_source(source, modules={"db": self._db_module, **self._plugin_registry.pebble_modules()}, base_dir=Path.cwd())`.
- Note: build the plugin modules once at activation and store them on the registry, not per run. Task 8's instance-bound modules are built once per plugin instance.

- [ ] **Step 1: Write failing tests:**
  - `test_two_environments_have_separate_db_modules`: env A creates a table through Pebble's `db`; env B's `db_tables()` doesn't list it.
  - `test_running_pebble_leaves_pebbles_shared_table_alone`: `STDLIB_MODULES` before and after a run that imports `db` and `kv` are equal.
  - `test_pystack_imports_only_pebbles_public_api`: the same scan as Task 5. It allows `from pebble import ...` only, applied to `src/pystack`. `plugins/mq_plugin.py` is exempt, to leave the mqnet branch conflict-free (spec §5); its deep imports still work because the internals stay importable.
- [ ] **Step 2: Run them.** Expected: the first two FAIL (the registry writes `STDLIB_MODULES`), and the scan FAILs listing `environment.py` and the plugins' `pebble.builtins` and `pebble.stdlib` imports.
- [ ] **Step 3: Implement.** Bump the pins, then `uv lock`. Switch every `from pebble.builtins import Value` and `from pebble.stdlib import StdlibModule` to `from pebble import Value, StdlibModule`. Delete the stopgap and update `test_pebble_db.py` to use environments instead of the removed helpers.
- [ ] **Step 4: Run** the full suite plus the lint and type checks. Expected: pass.
- [ ] **Step 5: Commit** `refactor: run Pebble through its public API; drop the shared-table stopgap`.

### Task 7: plugin lifecycle hooks; environment save and shutdown

**Files:**
- Modify: `src/pystack/plugins/base.py`, `src/pystack/plugins/registry.py`, `src/pystack/environment.py` (the `save` and `shutdown` methods at lines 180-191, and `__init__`), and `src/pystack/cli.py` or the OS shell registration (the `save` command).
- Test: `tests/test_plugin_lifecycle.py`

**Interfaces:**
- Produces, on `Plugin`, all no-ops by default:
  - `load_state(self, folder: Path) -> None`
  - `save_state(self, folder: Path) -> None`
  - `on_shutdown(self) -> None`
- Produces, on `PluginRegistry`:
  - `activate_all(self, shell, data_dir: Path)`, which for each plugin calls `load_state(data_dir / name)` and then `on_boot()`;
  - `save_all(self, data_dir: Path) -> list[tuple[str, Exception]]`;
  - `shutdown_all(self) -> list[tuple[str, Exception]]`.

  Here `name = plugin.pebble_module_name()`. The folder is created with `mkdir(parents=True, exist_ok=True)` only by `save_state` implementations that have something to write. `load_state` gets the path even if it doesn't exist.
- `PyStackEnvironment.save()`:
  - saves the database, then calls `save_all`;
  - if anything failed, it raises `ExceptionGroup("pystack could not save everything", [...])` after trying all of them.
- `PyStackEnvironment.shutdown()`:
  - saves the same way and calls `shutdown_all`;
  - never raises;
  - prints `pystack: could not save <name>: <error>` to stderr per failure, with `database` as the name for the SQL database;
  - stops the kernel last;
  - is safe to call twice: the second call does nothing.
- Shell command `save` prints `Saved.` or the error.

- [ ] **Step 1: Write failing tests**, using two tiny test plugins (`Recorder` and `Exploder`) registered in a `tmp_path` environment:
  - `test_load_state_runs_before_on_boot_with_the_plugin_folder`: the recorded order and folder are `tmp_path / "recorder"`.
  - `test_save_calls_every_plugin_and_raises_after_trying_all`: `Exploder.save_state` raises; `Recorder` was still saved; `ExceptionGroup` raised.
  - `test_shutdown_never_raises_and_reports_each_failure(capsys)`: stderr contains `pystack: could not save exploder: boom`; `Recorder.on_shutdown` ran.
  - `test_shutdown_twice_is_harmless`
  - `test_old_style_plugin_with_plain_on_boot_still_works`: a plugin overriding only `on_boot(self)`.
  - `test_save_shell_command_reports_saved`
- [ ] **Step 2: Run them.** Expected: FAIL (missing hooks).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite plus the lint and type checks. Expected: pass.
- [ ] **Step 5: Commit** `feat: plugins can load, save and shut down; pystack saves on shutdown`.

### Task 8: seven plugins own and keep their state

**Files:**
- Modify the plugins: `kv`, `docdb`, `graphdb`, `coldb`, `tsdb`, `vecdb` and `search` (`src/pystack/plugins/<name>_plugin.py`), plus `tests/test_nosql_plugins.py` and `tests/test_integration_plugins.py`. Remove `reset_*` usage, except for mq.
- Test: `tests/test_plugin_persistence.py`

**Interfaces:**
- Consumes: Task 7's hooks. Library calls:
  - pykv `save_store`/`load_store`;
  - pydocdb `save_collection`/`load_collection`;
  - pygraphdb `save_graph`/`load_graph`;
  - pycoldb `save_keyspace`/`load_keyspace`;
  - pytsdb `save`/`load`;
  - pyvecdb `save_store`/`load_store`;
  - pysearch `save_engine`/`load_engine`.
- Per plugin:
  - State moves into instance attributes, such as `self._store: BasicStore | None`.
  - The Pebble handlers become methods or closures over `self`, built once in `__init__`; `pebble_stdlib()` returns that module.
  - Shell commands use the same instance.
- Files inside each folder:

| Plugin | File(s) |
|---|---|
| kv | `store.json` |
| graph | `graph.json` |
| coldb | `keyspace.json` |
| tsdb | `db.json` |
| vecdb | `store.json` |
| docdb | `<collection>.json`, one per collection |
| search | `<engine_id>.json`, one per engine |

  Search's next id is `max(saved numeric suffixes) + 1`.
- `save_state` writes only when the plugin has state, i.e. it was loaded or created this run.

- [ ] **Step 1: Write failing tests.** For each of the seven plugins, `test_<plugin>_data_survives_a_restart` (parametrized):
  - write through Pebble in env A on `tmp_path`;
  - `A.shutdown()`;
  - read through Pebble in a new env B on the same `tmp_path`;
  - expect the same data.

  Also:
  - `test_two_environments_do_not_share_plugin_data`: kv, graph and search.
  - `test_untouched_plugins_write_nothing`: a fresh env shut down leaves no plugin folders.
  - `test_corrupt_save_file_stops_boot_and_is_kept` (parametrized over kv, graph and search): write `{not json` to the plugin file; `PyStackEnvironment(tmp_path)` raises that library's `PersistenceError`; the file's bytes are unchanged.
  - `test_search_ids_continue_after_saved_ones`
  - `test_no_global_state_left`: scans the seven plugin files for `global ` and `reset_`.
- [ ] **Step 2: Run them.** Expected: FAIL. Data is lost on restart, and A and B share state.
- [ ] **Step 3: Implement, one plugin per commit,** so each commit keeps the suite green. Update existing tests that used `reset_*` helpers to use fresh environments or fresh plugin instances.
- [ ] **Step 4: Run** the full suite plus the lint and type checks. Expected: pass, with coverage at least the configured minimum.
- [ ] **Step 5: Commit**, one commit per plugin: `refactor(<plugin>): own its state and keep it between runs`.

### Task 9: web server saves on stop; docs; pystack release

**Files:**
- Modify: `src/pystack/web/app.py`, `README.md` (a "Your data is saved" section and the `save` command), `CLAUDE.md` (the plugin hooks), and `docs/` plugin-writing page if one exists.
- Test: `tests/test_web.py`

**Interfaces:**
- `create_app(data_dir: str | Path = "pystack_data") -> Flask` stores the environment in `app.extensions["pystack_env"]`.
- The shell `exit` route calls `env.shutdown()`; that replaces `kernel.shutdown()` and stops the kernel too.
- `main()` runs `app.run(port=8080)` inside `try/finally: env.shutdown()`, and registers `atexit.register(env.shutdown)` as a backstop. `shutdown()` is idempotent, as Task 7 requires.

- [ ] **Step 1: Write failing tests:**
  - `test_server_saves_when_it_stops`: monkeypatch `Flask.run` to call `kv_set` through `/api/pebble` and then raise `KeyboardInterrupt`. Call `main()` with the data dir patched to `tmp_path`. Expect `KeyboardInterrupt`, and `tmp_path/"kv"/"store.json"` to contain the key.
  - `test_shell_exit_saves`: POST `exit` to `/api/shell` after a kv write, and the file exists.
- [ ] **Step 2: Run them.** Expected: FAIL (no file written).
- [ ] **Step 3: Implement**, then write the docs.
- [ ] **Step 4: Run** the full suite plus the lint and type checks. Then run a lone clone `uv sync --locked` plus the suite, as in theme 1.
- [ ] **Step 5: Ship.** The pystack PR covers Tasks 6-9 and the spec and plan commits. Note in it that `pystack-mqnet-wt` will need a rebase and that mq is deferred. Merge on green, then tag pystack `v0.2.0`.
