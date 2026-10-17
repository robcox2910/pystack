# Pin sibling dependencies to tags

**Date:** 2026-10-17
**Repos:** pystack, pyllm (consumers); os_learning, pebble-lang, pydb, pyweb,
pygit, pycrypt, pynet, pysearch, pymq, pykv, pydocdb, pygraphdb, pytsdb,
pyvecdb, pycoldb, pyllm (libraries)

## Problem

pystack and pyllm depend on sibling repos through `path = "../<repo>"` uv
sources, and their CI clones each sibling's `main` with `git clone --depth 1`.
Any merge to a sibling's `main` changes what the consumer builds against, with
no review in the consumer. pygit#4 (a deliberate API change) broke pystack's
`main` until pystack#17. No repo except os_learning has a tag, so hatch-vcs
versions are meaningless.

## Goals

- A sibling merging to `main` can never change or break a consumer's build.
- Every consumer build is reproducible from its own `uv.lock`.
- Upgrading a sibling is an explicit, CI-checked PR in the consumer.
- Cross-repo local development stays easy.

Non-goals: publishing to PyPI; a monorepo or uv workspace; automated bump bots.

## Design

### 1. Tag the libraries

Tag each library's current `main` and push the tag:

| Repo | Tag |
|---|---|
| os_learning (pyos-learn) | `v0.2.0` (existing `v0.1.0` is 30 commits old) |
| every other library listed above | `v0.1.0` |

pystack itself is also tagged `v0.1.0` after the change merges, so it has a
real version too.

### 2. Consumers pin by tag

`[tool.uv.sources]` entries become git sources pinned to a tag:

```toml
pydb = { git = "https://github.com/robcox2910/pydb", tag = "v0.1.0" }
```

pystack pins all 16 siblings; pyllm pins pebble-lang. `uv.lock` records the
resolved commit SHA.

### 3. CI stops cloning siblings

Remove every "Clone sibling projects" step (lint, test and security jobs in
pystack; lint and test in pyllm). Install with `uv sync --locked --all-extras`
so a stale lockfile fails CI rather than being silently re-resolved.

### 4. Upgrading a sibling

1. In the library: merge the change, then `git tag vX.Y.Z && git push origin vX.Y.Z`.
2. In the consumer: edit the tag in `[tool.uv.sources]`, run
   `uv lock --upgrade-package <name>`, open a PR. CI proves the pair works.

Versioning is 0.x semver: a change to a library's public API bumps the minor
version (`v0.1.0` → `v0.2.0`); anything else bumps the patch. Each library's
README gets a short "Releasing" section saying this.

### 5. Cross-repo local development

Sources stay pinned in git. To try an unreleased library change from a
consumer, install the sibling checkout over the pinned one:

```bash
uv pip install -e ../pebble-lang
```

The next `uv sync` restores the pinned tag. This is documented in the
consumers' CLAUDE.md / README "Developing alongside a sibling" section.

## In-flight work

The `feat/pynet-event-loop` branch (worktree `pystack-pynet-wt`) and pynet's
local `feat/event-loop` checkout are left untouched. When that work lands, pynet
is tagged (e.g. `v0.2.0`) and the pystack branch points its pynet source at the
tag; the branch will need a `pyproject.toml`/`uv.lock` rebase.

## Testing

- `uv sync --locked` and the full suite pass in pystack and pyllm with git
  sources, from a clean clone (no sibling folders next to it).
- CI on the PRs runs with no clone steps and passes.
- `uv run python -c "import importlib.metadata as m; print(m.version('pydb'))"`
  reports `0.1.0` in pystack's environment.
