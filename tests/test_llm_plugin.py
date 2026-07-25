"""Integration tests for the PyLLM plugin (the Pebble ``llm`` module)."""

from pathlib import Path

from pystack.environment import PyStackEnvironment


def test_pebble_can_import_llm_and_generate(tmp_path: Path) -> None:
    """A Pebble program can import "llm" and call llm_generate()."""
    env = PyStackEnvironment(db_path=tmp_path)
    try:
        out = env.run_pebble_source(
            'import "llm"\nlet code = llm_generate("add two numbers")\nprint(code)'
        )
        assert out.strip()  # non-empty generated text
    finally:
        env.shutdown()


def test_pebble_can_dream_pokemon(tmp_path: Path) -> None:
    """A Pebble program can call llm_dream() to get Pokemon-ish names."""
    env = PyStackEnvironment(db_path=tmp_path)
    try:
        out = env.run_pebble_source('import "llm"\nprint(llm_dream("pik"))')
        assert out.strip()
    finally:
        env.shutdown()
