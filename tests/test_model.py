"""Model check -- the kv plugin must behave exactly like a plain Python dict, restarts and all.

A property test checks one rule for many inputs. A *model check* goes
further: Hypothesis invents a random *story* -- set this, delete that, read
the other, restart PyStack -- and plays it on two things at once:

- the kv plugin, inside a real ``PyStackEnvironment``, called the way a
  Pebble program (or the shell) calls it;
- a **model**: a plain ``dict``, which we already trust to be right.

After every step the two must agree. If they ever disagree, Hypothesis
shrinks the story to the shortest list of steps that still goes wrong.

The restart step shuts PyStack down (which saves every plugin) and starts a
brand-new environment on the same data folder. The dict just carries on,
because a restart should change nothing.

The model is deliberately *not* a copy of the plugin's code. It is the
simplest thing that is obviously correct, so when the two disagree, the
plugin is the one to suspect.

See ``docs/property-testing.md`` for the walk-through.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import cast

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, invariant, rule
from pebble import Value as PebbleValue

from pystack.environment import PyStackEnvironment
from pystack.plugins.base import ShellHandler
from pystack.plugins.kv_plugin import KVPlugin
from tests.strategies import call_pebble, kv_keys, kv_values

# --- The machine: one story, played on PyStack and on a dict ------------------


class KVMachine(RuleBasedStateMachine):
    """Play random sets, deletes, reads and restarts on the kv plugin and a dict side by side."""

    # Keys we've used before. Brand-new random keys almost never repeat, so
    # rules also pick from here to read, overwrite or delete a key that
    # really is (or was) stored.
    keys = Bundle("keys")

    def __init__(self) -> None:
        """Start PyStack on an empty data folder, and an empty dict."""
        super().__init__()
        self.folder = Path(tempfile.mkdtemp())
        self.env = PyStackEnvironment(db_path=self.folder)
        self.model: dict[str, str] = {}

    def kv(self, function: str, *args: PebbleValue) -> PebbleValue:
        """Call a ``kv`` function the way a Pebble program does."""
        return call_pebble(self.env, "kv", function, *args)

    def shell(self, command: str, *args: str) -> str:
        """Run a kv shell command (``kv-get`` and friends) on today's plugin."""
        [plugin] = [p for p in self.env.plugin_registry.plugins if isinstance(p, KVPlugin)]
        handlers: dict[str, ShellHandler] = {c.name: c.handler for c in plugin.shell_commands()}
        return handlers[command](list(args))

    @rule(target=keys, key=kv_keys(), value=kv_values())
    def set_new_key(self, key: str, value: str) -> str:
        """Set a fresh key in both, and remember it for later steps."""
        assert self.kv("kv_set", key, value) == "ok"
        self.model[key] = value
        return key

    @rule(key=keys, value=kv_values())
    def overwrite_key(self, key: str, value: str) -> None:
        """Set a key we've used before to new text, in both."""
        assert self.kv("kv_set", key, value) == "ok"
        self.model[key] = value

    @rule(key=keys, value=kv_values())
    def overwrite_key_from_the_shell(self, key: str, value: str) -> None:
        """Set a key with the ``kv-set`` shell command instead of Pebble."""
        assert self.shell("kv-set", key, value) == f"Set '{key}' = '{value}'"
        self.model[key] = value

    @rule(key=st.one_of(keys, kv_keys()))
    def delete_key(self, key: str) -> None:
        """Delete a key from both: "ok" if it was there, an error message if not."""
        expected = "ok" if key in self.model else f"error: key '{key}' not found"
        self.model.pop(key, None)
        assert self.kv("kv_delete", key) == expected

    @rule(key=st.one_of(keys, kv_keys()))
    def delete_key_from_the_shell(self, key: str) -> None:
        """Delete a key with ``kv-delete``, which answers like the Pebble one, in words."""
        expected = f"Deleted '{key}'" if key in self.model else f"Key '{key}' not found"
        self.model.pop(key, None)
        assert self.shell("kv-delete", key) == expected

    @rule(key=st.one_of(keys, kv_keys()))
    def get_key(self, key: str) -> None:
        """Read a key: the dict's value, or "not found" if the dict has none."""
        assert self.kv("kv_get", key) == self.model.get(key, "not found")

    @rule(key=st.one_of(keys, kv_keys()))
    def get_key_from_the_shell(self, key: str) -> None:
        """Read a key with ``kv-get``: the dict's value, or a "not found" message."""
        assert self.shell("kv-get", key) == self.model.get(key, f"Key '{key}' not found")

    @rule()
    def restart(self) -> None:
        """Shut PyStack down (saving everything), then start a new one on the same folder."""
        self.env.shutdown()
        self.env = PyStackEnvironment(db_path=self.folder)

    @invariant()
    def same_keys_and_values(self) -> None:
        """After every step, kv holds exactly the dict's keys and values."""
        listed = self.kv("kv_keys")
        assert isinstance(listed, list)
        assert sorted(map(str, listed)) == sorted(self.model)
        assert all(self.kv("kv_get", key) == value for key, value in self.model.items())
        # The shell lists the same keys as Pebble, in the same order.
        assert self.shell("kv-keys") == (", ".join(map(str, listed)) if listed else "(no keys)")
        # The list is the caller's own copy: changing it changes nothing stored.
        listed.append("not a key")
        assert len(cast("list[str]", self.kv("kv_keys"))) == len(self.model)

    def teardown(self) -> None:
        """Shut PyStack down and delete the story's data folder."""
        self.env.shutdown()
        shutil.rmtree(self.folder)


# why: 20 steps find the same bugs; 50 (the default) is most of the run time
KVMachine.TestCase.settings = settings(stateful_step_count=20)
# pytest runs this like any other test class: one run plays 100 random stories.
# (Hypothesis doesn't say what type ``TestCase`` is, so ``cast`` tells pyright.)
TestKVModel = cast("type[unittest.TestCase]", KVMachine.TestCase)
