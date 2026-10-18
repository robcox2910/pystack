# Property-based tests: teaching the idea across the series

**Date:** 2026-10-18
**Theme:** 3 of the October 2026 series audit ("property-based tests")
**Repos:** all 17 projects, plus the series home repo
`robcox2910/robcox2910.github.io`

## Why

Almost every test in the series checks an example someone thought of:
"put `hello` on the queue, get `hello` back". Property-based tests state a
rule instead, such as "whatever you put on the queue comes back off it, in
order", and let a tool (Hypothesis) try thousands of random inputs to break
it. When one fails, Hypothesis **shrinks** it to the smallest input that
still fails, which is often a surprise: an empty string, a negative number,
a name with a slash in it.

Only pebble-lang (2 tests) and pysearch (1 test) use Hypothesis today, each
with its own ad-hoc settings.

The user wants **both** confidence and teaching, **mainly teaching the
idea**: a learner reading a project should come away understanding what a
property is, why it finds bugs examples miss, and how to write one. Every
project is brought to **the same standard**.

## Goals

- Every one of the 17 projects meets the standard below.
- A learner can read any project's property tests and its docs page and
  understand the idea without having seen another project.
- The series home site introduces the idea once and links to every
  project's page, in learning-path order.
- Hypothesis settings are the same in every repo and can't drift.
- Any real bug a property finds is fixed, and becomes part of the lesson.

## Non-goals

- Replacing the existing example tests. Properties sit beside them.
- Coverage targets. Coverage floors stay where they are.
- Fuzzing for security (no long-running fuzz jobs, no corpus storage).
- Property tests for pystack's web UI or the shells' interactive input.

## Anti-goals (would be a failure even if it "works")

- Properties that restate the implementation (`assert f(x) == f(x)`, or a
  reference model that copies the code under test). The reference must be
  something obviously right and different: a dict, a list, `sorted`,
  `sqlite3`, the standard library (`base64`, `hashlib`, `hmac`, `difflib`).
- Tests a learner can't read: unnamed lambdas as strategies, clever
  composite strategies with no docstring, magic numbers.
- Slow or flaky CI. A property that is slow or non-deterministic in CI is a
  failure even if it passes.
- Silencing a property that found a bug (`assume` or a filter that hides the
  failing input) instead of fixing the bug.

## The standard (every project)

1. **At least two properties:**
   - **A round-trip**, where the project has a pair of inverse operations:
     save/load, encode/decode, encrypt/decrypt, parse/format,
     serialise/deserialise.
   - **An invariant**: a rule that always holds, such as "search results
     are sorted by score", "a B-tree's keys come out in order", or "the
     scheduler always picks a process from the ready queue".

   A project with no natural round-trip takes two invariants instead.
2. **A model check (stateful test)** wherever the project has something you
   change step by step: a store, queue, table, graph, index, file system or
   memory manager. It uses Hypothesis's `RuleBasedStateMachine`: random
   sequences of operations run on the real thing and on a plain reference
   (a dict, a list, or `sqlite3` for pydb), and after every step the two
   must agree. Every project has one except pycrypt, pyllm and pebble-lang,
   which have no such state; those three take a third property instead.
3. **A docs page** in the project's site, in the series' usual voice. Its
   working title is "Testing with a Million Examples"; the builder may pick
   a per-project subtitle in the usual "(The ...)" style. It contains:
   - an everyday comparison that explains the idea;
   - one of the project's own properties, walked through line by line;
   - the model check (where there is one), explained the same way;
   - **"Try it yourself"**: a deliberate, one-line bug the reader can add,
     and the shrunk failing example Hypothesis reports for it, shown in
     the page;
   - if a property found a real bug in this project, the story of that bug
     (the shrunk input, why examples missed it, the fix).

   The page is `docs/property-testing.md` in every repo (the same name
   everywhere, so the home page can link to `/<repo>/property-testing/`).
   It goes last in the repo's own nav, just above the series-owned
   "The series" block; repos whose nav is discovered automatically need
   no nav edit. *(Claude's call.)*
4. **Tests written to teach:**
   - property tests live in `tests/test_properties.py` (and
     `tests/test_model.py` for the model check), so learners can find them;
   - every test's docstring states its rule in plain English;
   - strategies are named for what they make (`pet_names()`,
     `any_message()`, `small_vectors()`) and each has a one-line docstring.
5. **Shared settings**, owned by the series sync tool:
   - `hypothesis` is in each repo's `[dependency-groups] dev` with a floor
     of `>=6.170` (check the exact floor against PyPI and every repo's
     `requires-python`). Sync adds it if missing and raises a lower floor;
     a higher floor is left alone. `--check` reports a missing or lower
     floor as drift;
   - the two profiles live in a **root-level `conftest.py`**, a whole file
     owned by the sync tool (like `LICENSE`). pytest loads a rootdir
     `conftest.py` for every test, so each repo's own `tests/conftest.py`
     (os_learning, pebble-lang and pydb have one) is never touched, and the
     imports sit at the top of a file that passes the 37 ruff groups.
     *(Claude's call: a marked block inside a project-owned Python file
     would fight ruff's import rules.)* The file registers:
     - `ci` (loaded by default): 100 examples, `deadline=None`,
       `derandomize=True` and `database=None`, so CI is repeatable, never
       flaky, and writes no `.hypothesis/` folder;
     - `thorough`: 2,000 examples, `deadline=None`, random (not
       derandomized), for local runs with
       `pytest --hypothesis-profile=thorough` (Hypothesis's own pytest
       option, applied after the file loads `ci`);
   - per-test `@settings(max_examples=...)` overrides only where a test is
     genuinely expensive, with a comment saying why. pebble-lang and
     pysearch's existing ad-hoc settings move onto the profiles;
   - `.hypothesis/` (written by local `thorough` runs) is added to each
     repo's `.gitignore` in its own PR, as a one-off edit, not sync-owned.
     *(Claude's call.)*

   The sync tool gains the root `conftest.py` and the dependency floor,
   and `--check` reports drift in both.

   The tradeoff, stated: with `derandomize=True`, CI replays the same
   examples every run, so it guards against regressions but won't find new
   bugs; new bugs are found by `thorough` runs. A scheduled `thorough` CI
   run is deferred, alongside the deferred weekly `--check` workflow.
   *(Claude's call.)*

## Series home page

One new page on `https://robcox2910.github.io/`: the idea explained once
(the same everyday comparison style), then a list linking to every
project's page, each with a one-line description of the property it shows.
It is generated from `series.yml` like the rest of the home site, so adding
a project adds its link: `series.yml` gains a required `property` field
(the one-liner), and the list follows `series.yml` order, the learning
path. *(Claude's call.)*

## Starting points per project

From a read-only survey on 2026-10-17. These are candidates, not
requirements; the builder picks the most teachable and checks the
invariant actually holds before relying on it.

| Project | Round-trip / invariant candidates | Model check against |
|---|---|---|
| PyOS (os_learning) | slab write/read; disk schedulers return a permutation of requests | memory manager or slab vs dict; file system vs dict |
| Pebble | formatter idempotence (exists); optimised vs unoptimised output agree; parser only raises `PebbleError` | — |
| PyDB | record/table/schema serialise round-trips; B-tree keys sorted | table vs `sqlite3`; B-tree vs sorted list |
| PyKV | save/load round-trip | `BasicStore` vs dict; `TTLStore` vs dict with a fake clock |
| PyDocDB | save/load; `find` matches a plain Python filter | collection vs list of dicts |
| PyGraphDB | save/load; BFS visits exactly the reachable nodes | graph vs dict of sets |
| PyColDB | save/load; compaction never changes what reads return | column family vs nested dicts |
| PyTSDB | save/load; downsampling conserves count and sum | series vs sorted list |
| PyVecDB | save/load; distance symmetry; top-k equals brute force | store vs dict |
| PySearch | save/load (exists); results sorted by score | engine vs brute-force term scan |
| PyMQ | save/load; protocol encode/decode | `MessageQueue` vs list; broker work queue: no lost or duplicated messages |
| PyNet | base64 vs stdlib; frame encode/decode across arbitrary chunk splits | message decoder fed random chunks |
| PyWeb | HTTP head parse/encode round-trip; malformed input only raises `HttpParseError` | route table vs a linear list |
| PyGit | object store write/read; tree build/parse; hash matches git's rule | object store vs dict |
| PyCrypt | XOR/Caesar round-trips; HMAC matches stdlib `hmac` | — |
| PyLLM | tokenizer `decode(encode(s)) == s`; checkpoint save/load | — |
| PyStack | value mapping between pydb and Pebble is total | plugin data survives restart vs dict (kv) |

## Real bugs found

When a property fails on the current code:

- the failing shrunk input becomes a plain example test too (so it's
  pinned even with the property removed);
- the bug is fixed test-first in that project's PR;
- the project's docs page tells the story;
- if the fix changes a library's public behaviour, it gets a patch release
  tag (or minor, for an API change). Dependents (pystack, pyllm) are
  re-pinned once, in one PR each after the rollout, not repo by repo.
  *(Claude's call.)*

**Known one to fold in:** pykv, pydocdb and pycoldb's loaders catch only
`OSError` (to be verified on `origin/main` first), so a save file that
isn't UTF-8 text raises a raw
`UnicodeDecodeError` instead of `PersistenceError` naming the file (found
in review of pymq#10, where it was fixed). Their save/load round-trip
properties should be written so they'd catch it (arbitrary bytes on disk
must give `PersistenceError`).

## Order of work

1. **Series home repo:** the Hypothesis block and dependency floor in the
   sync tool (with tests), the home page, tag `v1` moved as before.
2. **Pilot on two projects:** PyCrypt (simplest: pure round-trips) and PyKV
   (round-trip plus the first model check). Review the two pages and tests
   as the template for the rest.
3. **Roll out** to the remaining 15, one PR per repo, merged on green CI.
   All work happens in fresh clones or worktrees off `origin/main` in a
   scratch folder, never in local checkouts or `*-wt` worktrees (pynet's
   checkout in particular).
4. **Sync** (`series sync`) so every repo's profile block matches, and
   `series sync --check` is clean.

## Testing (how we know it's done)

- Every repo: `tests/test_properties.py` exists with at least the standard's
  properties; `tests/test_model.py` exists for the 14 stateful projects;
  CI green on the `ci` profile.
- Every repo also passes once locally with `--hypothesis-profile=thorough`
  (recorded in the PR description).
- Each repo's CI test job takes no more than about 30 seconds longer than
  before (measured from the PR's CI run; a repo that needs more gets a
  ledgered reason, not a silent pass).
- `series sync --check` is clean for all 17; all 18 sites return 200 and
  the new pages are in each nav.
- The sync tool's tests cover inserting, updating and leaving alone the
  Hypothesis block and the dependency floor.

## Left to the builder

- Which candidate properties to use per project, and the exact wording and
  analogy on each page.
- Example counts within the `ci`/`thorough` profiles if 100/2,000 turn out
  wrong for a heavy repo (ledgered, with the reason).
- The structure of strategies, provided they are named and documented.
