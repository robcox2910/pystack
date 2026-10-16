"""Integration tests for the PyLLM plugin (the Pebble ``llm`` module)."""

from pathlib import Path

from pebble.errors import PebbleError
from pebble.lexer import Lexer
from pebble.parser import Parser

from pystack.environment import PyStackEnvironment
from pystack.plugins.llm_plugin import _as_comment


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


def _write_pebble(tmp_path: Path, prompt: str) -> str:
    """Run a Pebble program that asks llm_write_pebble() for code; return it."""
    env = PyStackEnvironment(db_path=tmp_path)
    try:
        return env.run_pebble_source(f'import "llm"\nprint(llm_write_pebble("{prompt}"))')
    finally:
        env.shutdown()


def _parses(source: str) -> bool:
    """Return True if Pebble's own parser accepts ``source``."""
    try:
        Parser(Lexer(source).tokenize()).parse()
    except PebbleError:
        return False
    return True


def test_llm_write_pebble_turns_a_request_into_valid_code(tmp_path: Path) -> None:
    """A plain-English request comes back as code Pebble's parser accepts."""
    code = _write_pebble(tmp_path, "add two numbers")
    assert code.startswith("# add two numbers\n")
    assert _parses(code)


def test_llm_write_pebble_keeps_a_code_prompt(tmp_path: Path) -> None:
    """A prompt that is already the start of Pebble code is continued as-is."""
    code = _write_pebble(tmp_path, "let ")
    assert code.startswith("let ")
    assert _parses(code)


def test_llm_write_pebble_flattens_multi_line_requests() -> None:
    """A request spanning lines stays one comment, so it can't leak into code."""
    assert _as_comment("add\ntwo") == "# add two\n"
