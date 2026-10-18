"""Strategies -- recipes for random keys and values, shared by the property tests.

A strategy tells Hypothesis how to invent one kind of input. Each one here
is a named function, named for what it makes, with a one-line docstring.
``tests/test_properties.py`` and ``tests/test_model.py`` both use them, and
both use ``call_pebble`` at the bottom to talk to a plugin.
"""

from hypothesis import strategies as st
from pebble import Value as PebbleValue

from pystack.environment import PyStackEnvironment


def kv_keys() -> st.SearchStrategy[str]:
    """Make any key at all: empty, spaces, emoji, accents, quotes, the lot."""
    return st.text()


def kv_values() -> st.SearchStrategy[str]:
    """Make any text a Pebble program might store with ``kv_set``."""
    # The kv plugin keeps every value as text (``kv_set`` calls ``str`` on
    # it), so text is what a program gets back -- see kv_plugin.py.
    return st.text()


def call_pebble(
    env: PyStackEnvironment, module: str, function: str, *args: PebbleValue
) -> PebbleValue:
    """Call one of *env*'s Pebble functions exactly as a Pebble program would.

    ``import "kv"`` and then ``kv_get("name")`` in Pebble ends up calling
    the ``kv_get`` handler with the list ``["name"]``. Calling the handler
    ourselves skips writing (and escaping) Pebble source for every step.
    """
    _arity, handler = env.plugin_registry.pebble_modules()[module].functions[function]
    assert handler is not None, f"{module}.{function} has no handler"
    return handler(list(args))
