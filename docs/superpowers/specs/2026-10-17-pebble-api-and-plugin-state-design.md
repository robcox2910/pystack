# Pebble's front door, and plugins that own (and keep) their data

**Date:** 2026-10-17
**Theme:** 2 of the October 2026 series audit ("shared global state")
**Repos:** pebble-lang, pysearch, pygraphdb, pytsdb, pyvecdb, pystack, pyllm
(pymq: deferred, see §5)

## Why

Two kinds of shared global state cause real bugs and coupling:

1. **Pebble's module table.** `pebble.stdlib.STDLIB_MODULES` is one
   process-wide dict. pystack writes `db` and every plugin module (`kv`,
   `graph`, ...) into it, so two pystack environments see and remove each
   other's modules. pystack#14 papered over this with an RLock that rebinds
   `STDLIB_MODULES["db"]` per run (`pystack/adapters/pebble_db.py:108`).
   pystack also wires Pebble's nine internal pieces together by hand
   (`pystack/environment.py:206-244`), so any internal change in Pebble can
   break it. Pebble's own `cli.py` and `repl.py` duplicate the same wiring.
2. **pystack's plugin state.** Eleven module-level variables (`_store`,
   `_graph`, `_queues`, `_engines`, ...) in `pystack/plugins/*_plugin.py`
   hold plugin data, mutated with `global`. Two environments share one kv
   store, tests need `reset_*_state()` helpers, and everything is lost on
   exit.

The user wants both a clean-up (pystack correct, no reliance on Pebble's
internals) **and** a learner-facing feature: "Using Pebble from Python",
with its own docs chapter. Plugin data should be **saved so it's there next
time**, like a real database or broker.

## Goals

- Pebble has a small, documented public API ("the front door"). Each run
  gets its own extra modules; nothing is written to a shared table.
- pystack and pyllm use only the front door. pystack's RLock stopgap is
  deleted.
- Each pystack plugin instance owns its state; two environments in one
  process are fully independent.
- Plugin data is loaded at start-up and saved at shutdown, under the
  environment's data folder.
- A kid-friendly docs chapter in pebble-lang, whose examples are tested.

## Non-goals

- Saving after every change (write-ahead logging). Saving happens on clean
  shutdown and on an explicit `save`; a crash loses changes since the last
  save, and the docs say so.
- Removing or renaming Pebble's internal modules. They stay importable, but
  only the front door is promised.
- pymq persistence in this round (§5).
- Any change to Pebble the language itself.

## Anti-goals (would be a failure even if it "works")

- Learners having to understand lexers, analyzers and resolvers just to run
  a program from Python.
- A front door that is just the old pipeline re-exported: callers must not
  need to pass Pebble-internal objects.
- Saving that can leave a half-written file (must use each library's
  existing crash-safe save).

## Design

### 1. pebble-lang: the front door (minor release, `v0.2.0`)

New module `pebble/api.py`, re-exported from `pebble/__init__.py`:

```python
def check(source: str) -> None
    """Raise PebbleError if source doesn't lex and parse."""

def format_source(source: str) -> str
    """Return source in Pebble's one canonical formatting (PebbleError if invalid)."""

def compile_source(
    source: str,
    *,
    modules: Mapping[str, StdlibModule] | None = None,
    base_dir: Path | None = None,
) -> Program

def run_source(
    source: str,
    *,
    modules: Mapping[str, StdlibModule] | None = None,
    base_dir: Path | None = None,
    output: TextIO | None = None,
) -> str
    """Compile and run; return everything the program printed."""
```

- `Program` is an opaque, runnable result of `compile_source`, with
  `program.run(output=None) -> str`. It carries its own module handlers,
  so running it never consults a global table.
- `modules` are **extra** modules for this call only, layered over the
  built-ins (`math`, ...). A name in `modules` that collides with a
  built-in raises `ValueError` (explicit beats surprising).
- `base_dir` is where `import "file"` looks; default `Path.cwd()`
  (today's behaviour).
- `StdlibModule` and `Value` are part of the public API (re-exported from
  `pebble`), because writing your own module needs them.
- `ModuleResolver` takes the module table as a constructor argument
  instead of reading `STDLIB_MODULES`; `STDLIB_MODULES` becomes the
  read-only-by-convention table of built-ins.
- `pebble file.pbl` (the CLI's normal run) uses the front door. The REPL
  (which keeps variables between lines via `vm.run_repl`) and `--debug`
  (which passes a `debug_hook`) need more than one-shot runs, so they and
  the front door all share one **private** pipeline helper
  (`pebble/_pipeline.py`); the duplicated wiring goes, but sessions and
  debugging are not part of the public promise. *(Builder's call, made by
  Claude: keeps v0.2.0's promise small.)*
- Errors: unchanged `PebbleError` subclasses propagate from all four
  functions.

`register_module` from the original theme note is dropped: per-call
`modules=` replaces it, and a global registration function would
re-create the shared state this theme removes.

**Docs chapter:** `docs/.../using-pebble-from-python.md` (placed in the
existing docs nav), in the series' kid-friendly voice. It covers running a
program, capturing output, catching errors, checking/formatting, and
writing your own module in Python (a `greet` module). Every code example in
the chapter is exercised by `tests/test_docs_api_examples.py`.

### 2. pysearch: save and load (minor release, `v0.2.0`)

Add `save_engine(engine, path)` / `load_engine(path) -> SearchEngine`
(names matching the series' `save_store`/`load_store` style), backed by a
`to_dict`/`from_dict` pair and the repo's crash-safe `atomic_write_text`
(copy it in, as the other storage repos did). Round-trip preserves
documents, ids and search results. Corrupt or unreadable files raise a
`PersistenceError`. Includes a short "Saving your index" docs section.

### 2b. pygraphdb, pytsdb, pyvecdb: a `PersistenceError` (minor release, `v0.2.0`)

Their loaders let `JSONDecodeError`/`TypeError`/`KeyError` escape. Each gets
a `PersistenceError` (matching pykv/pydocdb/pycoldb) raised for unreadable or
malformed files, with the path in the message. This is theme 5's remaining
item, folded in here because pystack's boot behaviour depends on it. *(Claude's
call: theme 5 was already requested.)* It's a new public exception, so
`v0.2.0`.

### 3. pystack: plugins own their state, and keep it

- **Instance state.** Each plugin's module-level state (every plugin except
  mq, see §5) moves onto the
  plugin instance; the Pebble module a plugin exposes is built from bound
  methods/closures over that instance. All `global` statements and
  `reset_*_state()` helpers are deleted; tests use fresh environments.
- **Front door.** `PyStackEnvironment` collects `{name: module}` from the
  `db` adapter and every active plugin, and calls
  `pebble.run_source(source, modules=..., base_dir=Path.cwd())`.
  `environment.py` no longer imports Pebble internals; the registry no
  longer writes `STDLIB_MODULES`; `bound_db_module` and its RLock are
  deleted.
- **Lifecycle.** `on_boot(self)` keeps its signature, so third-party
  plugins loaded through the `pystack.plugins` entry point don't break.
  `Plugin` gains three hooks, all no-ops by default:
  `load_state(self, folder: Path) -> None` (called at start-up, before
  `on_boot`), `save_state(self, folder: Path) -> None`, and
  `on_shutdown(self) -> None`. `folder` is
  `<db_path>/<pebble_module_name()>/` (default `pystack_data/kv/`, etc.),
  created on demand. *(Claude's call: additive hooks instead of changing
  `on_boot`.)*
- **Saving and shutdown.** `PyStackEnvironment.save()` saves the SQL database and calls every
  plugin's `save_state`; it raises if anything failed (an `ExceptionGroup`
  after trying all of them), so the `save` command shows the error.
  `PyStackEnvironment.shutdown()` saves the same way, then calls every
  `on_shutdown`; it never raises (it runs inside `finally:` blocks and must
  not hide the original error) but prints one line per failure to stderr:
  `pystack: could not save <plugin>: <error>`. The SQL save follows the same
  rule instead of today's silent suppression. *(Claude's call.)*
- **What saves:** kv, docdb, graphdb, coldb, tsdb, vecdb (existing library
  save/load), search (§2). mq is untouched this round (§5). llm, git, crypto,
  web, net have nothing to save.
- **Load failure at boot** (corrupt file): the plugin raises the library's
  `PersistenceError` with the file path, rather than starting empty and
  overwriting the user's data at shutdown.
- **Shell:** a `save` command calls `environment.save()`. `.quit` and end of
  a script already call `shutdown()`.
- **Web server:** `pystack/web/app.py` does *not* call `shutdown()` today, so
  web users lose data. The server calls `env.shutdown()` when it stops
  (wrapping `app.run` in `try/finally`, plus `atexit` as a backstop), and
  the shell-over-web `exit` path calls it too. *(Claude's call: without it
  the "there next time" goal fails for web users.)*
- **Search ids:** saved engines keep their ids, and new ids continue after
  the highest saved one, so nothing clashes across runs. Programs find
  engines with the existing list call. *(Claude's call.)*
- **Upgrade:** pebble-lang, pysearch, pygraphdb, pytsdb, pyvecdb and pyllm
  pins bumped to `v0.2.0` via the pinned-tag process.

### 4. pyllm: use the front door

`score.is_valid` uses `pebble.check`; `corpus.canonicalize` uses
`pebble.format_source`. pebble-lang pin bumped to `v0.2.0`; pyllm released
as `v0.2.0` and pystack's pyllm pin bumped to match (keeping the pebble-lang
tags aligned).

### 5. Deferred: the mq plugin and pymq persistence

The user wants message saving "like a real broker". But there is in-flight
work: pymq's `feat/network-broker` branch, and pystack's `feat/mqnet-demo`
branch (worktree `pystack-mqnet-wt`), which adds ~100 lines to
`plugins/mq_plugin.py` on top of its module-level state. The user chose to
wait for that work to land:

- This round leaves `mq_plugin.py` and its tests as they are, apart from
  what the front-door switch strictly requires (its Pebble module is passed
  via `modules=` like every other plugin's).
- After both branches land, a follow-up gives pymq save/load (as in §2,
  `v0.3.0` or next minor), moves the mq plugin's state onto the instance,
  and makes it save like the others.
- Never switch or modify those branches' checkouts or worktrees.

## Order of work

1. pebble-lang front door + docs chapter → tag `v0.2.0`.
2. pysearch save/load → tag `v0.2.0`; pygraphdb, pytsdb, pyvecdb
   `PersistenceError` → tag `v0.2.0` each.
3. pyllm switch → tag `v0.2.0`.
4. pystack switch (instance state, lifecycle, persistence, front door,
   pins bumped) → tag `v0.2.0`.

## Testing

- pebble-lang: two `run_source` calls with different `modules` in one
  process (and concurrently in threads) never see each other's modules;
  `STDLIB_MODULES` is unchanged after any call; collision `ValueError`;
  `base_dir` imports; docs examples run.
- pysearch: save/load round-trip (Hypothesis where it fits), corrupt-file
  `PersistenceError`.
- pystack: two environments in one process have independent kv/graph/...;
  data written, environment shut down, new environment on the same folder
  sees it (one test per saving plugin); corrupt file at boot raises and
  leaves the file untouched; `on_shutdown` failure in one plugin doesn't
  skip the others.
- pyllm: existing scoring/corpus tests pass unchanged on the front door.

## Left to the builder

Internal shape of `Program`; where exactly the docs chapter sits in each
nav; file names inside each plugin's folder; how bound modules are built
(closures vs bound methods).
