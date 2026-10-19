# Property Testing (Lock Up, Open Up, Nothing Moved)

## The School Caretaker

PyStack is the hallways of a school: it connects the filing cabinets
(PyDB), the lockers (PyKV), the library index (PySearch) and every other
room. Every evening the school is locked up, and every morning it's opened
again. Whatever a pupil left in their locker yesterday should still be
there today. That's PyStack's save and load: shut down, start up, nothing
moved.

How would you check that? The usual way: put one book in one locker, lock
up, open up, and see that the book is still there. That's an **example
test**. It's useful, but it only tells you about the one book you thought
of.

Now imagine a caretaker. Every night they fill lockers with thousands of
different things -- a book, a sock, a note written in Greek, an empty
envelope, a locker with no name on the door -- and every morning they
check a single rule:

> Whatever was left in the lockers last night is there this morning,
> exactly as it was.

That rule is a **property**. It doesn't say what any one locker holds. It
says something that must be true for *every* locker.

When the caretaker finds a locker that breaks the rule, they don't just
report "something went missing on the second floor". They try again with
less and less -- fewer lockers, smaller things, shorter names -- checking
it still goes wrong each time, until it's as simple as it can be. That
boiling-down is called **shrinking**, and it's the best part: the smallest
failing input usually points straight at the bug.

In Python, the caretaker is a library called
[Hypothesis](https://hypothesis.readthedocs.io/). PyStack's property tests
live in `tests/test_properties.py`, next to the ordinary example tests, and
the model check (more on that below) is in `tests/test_model.py`.

## A Property from PyStack

The `kv` plugin lets a Pebble program keep text under a key with
`kv_set("name", "Ada")` and read it back with `kv_get("name")`. Here's the
property that says it survives a restart:

```python
def kv_keys() -> st.SearchStrategy[str]:
    """Make any key at all: empty, spaces, emoji, accents, quotes, the lot."""
    return st.text()


def kv_values() -> st.SearchStrategy[str]:
    """Make any text a Pebble program might store with ``kv_set``."""
    # The kv plugin keeps every value as text (``kv_set`` calls ``str`` on
    # it), so text is what a program gets back -- see kv_plugin.py.
    return st.text()


def kv_contents() -> st.SearchStrategy[dict[str, str]]:
    """Make everything one kv store might hold: any keys, each with any text."""
    return st.dictionaries(kv_keys(), kv_values())


@given(contents=kv_contents())
def test_kv_data_survives_a_restart(contents: dict[str, str]) -> None:
    """Whatever a program stores with ``kv_set``, the next run reads back exactly."""
    with tempfile.TemporaryDirectory() as folder:
        first = PyStackEnvironment(db_path=Path(folder))
        for key, value in contents.items():
            call_pebble(first, "kv", "kv_set", key, value)
        first.shutdown()

        second = PyStackEnvironment(db_path=Path(folder))
        try:
            listed = call_pebble(second, "kv", "kv_keys")
            assert isinstance(listed, list)
            assert sorted(map(str, listed)) == sorted(contents)
            for key, value in contents.items():
                assert call_pebble(second, "kv", "kv_get", key) == value
        finally:
            second.shutdown()
```

Line by line:

- **`kv_keys()`, `kv_values()` and `kv_contents()`** are **strategies**:
  recipes for making random inputs. `st.text()` makes any string at all,
  including the empty string, `" "`, `"🍕"` and `"Zoë's \"key\""`.
  `kv_contents()` makes a whole dictionary of keys and values. The first
  two live in `tests/strategies.py`, because the model check uses them too.
- **`@given(contents=kv_contents())`** tells Hypothesis to run the test
  many times (100 in a normal run), each time with a fresh `contents`.
- **The docstring** says the rule in plain English. If you can't say the
  rule in one sentence, it probably isn't a good property yet.
- **`tempfile.TemporaryDirectory()`** gives each run its own empty data
  folder, like a brand-new `pystack_data/`, deleted afterwards.
- **`first = PyStackEnvironment(...)`** starts the whole of PyStack: the
  database, every plugin, the lot. That's the school opening for the day.
- **`call_pebble(first, "kv", "kv_set", key, value)`** calls the `kv_set`
  function exactly the way a Pebble program's `kv_set(key, value)` does.
  (Writing real Pebble source for every random key would mean escaping
  quotes and newlines; this skips straight to the function Pebble calls.)
- **`first.shutdown()`** locks up: it saves every plugin into the folder.
- **`second = PyStackEnvironment(...)`** is the next morning: a brand-new
  PyStack on the same folder, with nothing carried over except the files.
- **The `assert`s** are the rule itself: the same keys are listed (sorted,
  so the order they happen to come out in doesn't matter), and every key
  gives back exactly its text. This kind of property is called a
  **round-trip**.
- **`finally: second.shutdown()`** tidies up even if an `assert` fails.

Notice what the test *doesn't* say. It never says "store `name -> Ada`
and you get `Ada`". It doesn't need to know any answers. It only needs a
rule that's always true.

**A "starts without crashing" check on its own is passed by a plugin that
does nothing**, because ignoring every file never crashes. That's why the
two "odd files" properties below also check what PyStack does *next*, and
why this round-trip sits beside them: a plugin that never saves fails it
the moment there is one key to read back. The other properties check
different corners of PyStack:

| Rule | Test |
|---|---|
| Every value a table holds reaches Pebble as a plain Pebble value, and maps back exactly | `test_every_pydb_value_reaches_pebble_and_maps_back` |
| Whatever the saved engine files are called, PyStack starts and lists its own, or refuses cleanly | `test_any_engine_file_name_starts_or_raises_persistence_error` |
| Whatever ids the saved edges have, PyStack starts and a new edge gets an id nobody has | `test_new_edges_never_reuse_a_saved_edge_id` |

The first one checks the bridge between PyDB and Pebble: Pebble has no
date type, so a DATE or TIMESTAMP crosses as ISO text like `2026-10-17`,
and the property checks, with Python's own `fromisoformat`, that the text
turns back into exactly the date it came from. The other two put odd files in the data folder, the way a curious
pupil (or a crashed editor) might, and both of them found real bugs.

## Checking Against a Model

A property checks one action. But the lockers change step by step: set a
key, change it, delete it, read it, lock up for the night, open up again.
Bugs often hide in the *order* of steps -- deleting a key that was never
set, or deleting one and then restarting.

So the caretaker has a second trick. They carry a notebook and write down
every locker and what's in it, by hand. After every single step, they
compare the lockers with the notebook. If the lockers ever disagree with
the notebook, something's wrong with the school. The notebook doesn't care
about nights: it just carries on.

That notebook is a **model**: something simple that we already trust. For
the `kv` plugin, the model is a plain Python `dict`. Here's the heart of
the check in `tests/test_model.py`:

```python
class KVMachine(RuleBasedStateMachine):
    """Play random sets, deletes, reads and restarts on the kv plugin and a dict side by side."""

    keys = Bundle("keys")

    def __init__(self) -> None:
        """Start PyStack on an empty data folder, and an empty dict."""
        super().__init__()
        self.folder = Path(tempfile.mkdtemp())
        self.env = PyStackEnvironment(db_path=self.folder)
        self.model: dict[str, str] = {}

    @rule(target=keys, key=kv_keys(), value=kv_values())
    def set_new_key(self, key: str, value: str) -> str:
        """Set a fresh key in both, and remember it for later steps."""
        assert self.kv("kv_set", key, value) == "ok"
        self.model[key] = value
        return key

    @rule(key=st.one_of(keys, kv_keys()))
    def delete_key(self, key: str) -> None:
        """Delete a key from both: "ok" if it was there, an error message if not."""
        expected = "ok" if key in self.model else f"error: key '{key}' not found"
        self.model.pop(key, None)
        assert self.kv("kv_delete", key) == expected

    @rule()
    def restart(self) -> None:
        self.env.shutdown()
        self.env = PyStackEnvironment(db_path=self.folder)

    @invariant()
    def same_keys_and_values(self) -> None:
        """After every step, kv holds exactly the dict's keys and values."""
        listed = self.kv("kv_keys")
        assert sorted(map(str, listed)) == sorted(self.model)
        assert all(self.kv("kv_get", key) == value for key, value in self.model.items())


TestKVModel = cast("type[unittest.TestCase]", KVMachine.TestCase)
```

Piece by piece:

- **`RuleBasedStateMachine`** is Hypothesis's tool for testing things that
  change step by step. Hypothesis makes up a random **story** of steps and
  plays it.
- **`self.env` and `self.model`** are the school and the notebook. Every
  story starts with an empty data folder and an empty dict.
- **Each `@rule`** is one kind of step. It does the same thing to PyStack
  and to the dict. The real file has rules to set a new key and overwrite
  one (from Pebble and from the `kv-set` shell command), delete (both
  ways), read (both ways) and restart. `self.kv(...)` is `call_pebble` for
  the `kv` module.
- **`keys = Bundle("keys")`** is a bag of keys used earlier in the story.
  Two random strings almost never match, so without it the story would
  hardly ever change or delete a key that is really there. `set_new_key`
  puts its key in the bag (`target=keys`). `delete_key` picks either a key
  from the bag or a brand-new one, so it tries deleting keys that exist
  *and* keys that don't, and it checks what `kv_delete` *says* as well.
- **`restart`** is the night: lock up, open up. The dict does nothing,
  because a restart should change nothing.
- **The `@invariant()`** runs after every single step and compares
  everything: which keys there are, and every value. The real one also
  checks that the `kv-keys` shell command lists the same keys, and that
  the list `kv_keys` hands back is the caller's own copy.
- **`TestKVModel = ...TestCase`** turns the machine into a test that
  pytest can find and run. One run plays 100 random stories, each up to 20
  steps long (Hypothesis's default is 50, which finds the same bugs but
  takes most of the run time).

The `dict` is a good model because it's obviously right and it's *not*
the plugin's code. If we built the model by copying `KVPlugin`, any bug
would be in both, and they'd agree perfectly about the wrong answer.

## Try It Yourself

Let's break saving on purpose and watch the caretaker find it.

Open `src/pystack/plugins/kv_plugin.py`, find `save_state`, and change its
first line, as if you'd decided "why write a file for an empty store?":

```python
        if self._store is None or not self._store.keys():  # was: if self._store is None:
```

Now an empty store is never saved. Run the property tests:

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov
```

Hypothesis reports this (trimmed to the interesting part):

```
    @invariant()
    def same_keys_and_values(self) -> None:
        """After every step, kv holds exactly the dict's keys and values."""
        listed = self.kv("kv_keys")
        assert isinstance(listed, list)
>       assert sorted(map(str, listed)) == sorted(self.model)
E       AssertionError: assert [''] == []
E
E         Left contains one more item: ''
E       Failing test case: <state machine>
E       state = KVMachine()
E       state.same_keys_and_values()
E       keys_0 = state.set_new_key(key='', value='')
E       state.same_keys_and_values()
E       state.restart()
E       state.same_keys_and_values()
E       state.delete_key(key=keys_0)
E       state.same_keys_and_values()
E       state.restart()
E       state.same_keys_and_values()
E       state.teardown()
```

Read the story at the bottom like a script. Set the key `''`. Lock up and
open up (the key is saved). Delete it: the store is now empty. Lock up and
open up again. The empty store wasn't saved, so yesterday's file is still
on disk, and the deleted key **comes back from the dead**. The notebook
knows it was deleted.

The example tests all still pass. Only the property notices. None of them
deletes a key and then restarts, and nobody would think to write that
test until the bug had already bitten. The round-trip property stays
green too: it never deletes anything. It took the model check's random
stories, with restarts in the middle, to find it -- and Hypothesis shrank
dozens of steps down to these four.

Put the line back to `if self._store is None:` and run the tests again.
They pass.

!!! tip "Older Hypothesis versions"
    Older versions of Hypothesis print `Falsifying example:` instead of
    `Failing test case:`. It means the same thing.

## A Bug We Found

When we first wrote
`test_any_engine_file_name_starts_or_raises_persistence_error`, it failed
on PyStack's real code -- no deliberate bug needed:

```
E       ValueError: invalid literal for int() with base 10: ''
E       Failing test case: test_any_engine_file_name_starts_or_raises_persistence_error(
E           stems=['engine_'],
E       )
```

A saved search engine called `engine_.json` stopped PyStack from starting
at all.

Here's why. Search engines get ids like `engine_0` and `engine_1`, saved
as `engine_0.json` and so on. On start-up the plugin loads every file
matching `engine_*.json`, then works out the next id by reading the number
off each name with `int(...)`. But `*` matches anything, including nothing,
so `engine_.json` (or `engine_old.json`) is loaded too, and `int("")`
crashes with a `ValueError`.

The example tests only ever used files PyStack wrote itself, so every name
had a number. The caretaker didn't need to think of a bad name: the
strategy makes names like `engine_x` all the time.

The fix: only files named like the ids the plugin makes are engines.
Anything else is left alone, like any other stray file in the folder:

```python
        for path in sorted(folder.glob("engine_*.json")):
            if _is_engine_id(path.stem):  # was: no check, so every engine_*.json loaded
                self._engines[path.stem] = load_engine(path)
```

The shrunk input became an ordinary example test in
`tests/test_plugin_persistence.py`:

```python
    def test_engine_file_without_a_number_is_left_alone(self, tmp_path: Path) -> None:
        """``engine_.json`` isn't an engine PyStack saved: start-up skips it and leaves it be."""
        folder = tmp_path / "search"
        folder.mkdir()
        stray = folder / "engine_.json"
        save_engine(SearchEngine(), stray)
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(env, "search", "print(search_list())") == "[]\n"
            assert _run(env, "search", "print(search_create())") == "engine_0\n"
        finally:
            env.shutdown()
        assert stray.exists()
```

Its twin found the same kind of bug in `graphdb`: a saved edge called `e²`
crashed start-up, because Python's `isdigit()` says `"²"` is a digit but
`int("²")` can't read it. (Then a reviewer asked about very long ids:
`int()` refuses more than 4,300 digits, so an edge called `e111...1` with
5,000 ones crashed too. Now the strategy makes those as well. One digit
short is still a trap: after `e` plus 4,300 nines the next id has 4,301
digits, which Python can't write down, so ids that long don't count
towards the next number, and the counter skips any id the graph already
has.) And the model check found that deleting a key
that was never set answered `"ok"`: PyKV's `delete` returns `False` for a
missing key, but the plugin was waiting for an error that never came.

## Run It Yourself

Run just the property tests, and the model check (100 examples each, the
same every time):

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov
```

The `--no-cov` turns off the coverage check, which expects the *whole*
test suite to run and would fail on two files.

Run them the long way (2,000 random examples each, different every run)
to hunt for rarer bugs. It takes about 3 minutes:

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov --hypothesis-profile=thorough
```

The normal run uses a fixed seed, so it tries the same inputs every time
and a passing build means the same thing on every computer. The thorough
run is random, so each time you run it the caretaker fills the lockers
with a brand-new pile of things. Both settings live in `conftest.py` at
the top of the project.

## Your Turn

Write one new property for PyStack. Two environments on two different
data folders should never see each other's lockers. What's the strategy
that fills the first one's `kv` store? What's the `assert` you make on the
second one? Run it and watch it pass. Then break it on purpose -- make
`KVPlugin` keep its store in a module-level variable, shared by every
plugin -- and watch the caretaker find it.
