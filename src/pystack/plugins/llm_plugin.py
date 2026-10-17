"""PyStack plugin exposing PyLLM (the brain) to Pebble as the ``llm`` module.

A language model is like an imaginative friend who has read tons of text and
can keep writing in the same style -- give it a few words and it dreams up
what might come next.

This is the loop-closing plugin: it lets a Pebble program ``import "llm"`` and ask
PyLLM to write text -- including *more Pebble code*. The brain of the series
writing the language of the series. It calls PyLLM's cached public API, so the
model is loaded once and reused.
"""

import pyllm
from pebble import StdlibModule
from pebble import Value as PebbleValue

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler


@pebble_handler
def _llm_generate(args: list[PebbleValue]) -> PebbleValue:
    """Write Pebble-flavoured code from a prompt string."""
    prompt = str(args[0]) if args else "let "
    return pyllm.generate_pebble(prompt=prompt, max_new_tokens=120)


def _as_comment(request: str) -> str:
    """Turn a plain-English request into a one-line Pebble comment.

    Like writing the task at the top of your page: ``# add two numbers``. Any
    line breaks are squashed into spaces so the request can't leak into the code.
    """
    return "# " + " ".join(request.split()) + "\n"


@pebble_handler
def _llm_write_pebble(args: list[PebbleValue]) -> PebbleValue:
    """Write Pebble code that is guaranteed to parse (the referee is watching).

    PyLLM's grammar referee only lets the model write legal Pebble. If the prompt
    is already the start of some code (``"let "``) we carry on from it; if it's a
    plain-English request the referee rejects it, so we pin it to the top as a
    comment and let the model write real code underneath.
    """
    prompt = str(args[0]) if args else "let "
    try:
        return pyllm.generate_pebble(prompt=prompt, max_new_tokens=120, constrained=True)
    except ValueError:  # the referee blew the whistle on the prompt itself
        return pyllm.generate_pebble(
            prompt=_as_comment(prompt), max_new_tokens=120, constrained=True
        )


@pebble_handler
def _llm_dream(args: list[PebbleValue]) -> PebbleValue:
    """Dream up Pokemon-ish names from a prompt string."""
    prompt = str(args[0]) if args else ""
    return pyllm.generate_pokemon(prompt=prompt, max_new_tokens=40)


class LLMPlugin(Plugin):
    """Wires PyLLM into PyStack as the Pebble ``llm`` module (and a shell command)."""

    def info(self) -> PluginInfo:
        """Return metadata naming PyLLM the brain of the series."""
        return PluginInfo(
            name="PyLLM",
            description="A from-scratch language model -- the brain of the series.",
        )

    def pebble_module_name(self) -> str:
        """Pebble programs reach PyLLM via ``import "llm"``."""
        return "llm"

    def pebble_stdlib(self) -> StdlibModule:
        """Expose ``llm_generate`` / ``llm_write_pebble`` (Pebble) and ``llm_dream``."""
        return StdlibModule(
            functions={
                "llm_generate": (1, _llm_generate),
                "llm_write_pebble": (1, _llm_write_pebble),
                "llm_dream": (1, _llm_dream),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Add a ``dream`` shell command that generates Pokemon names."""

        def _dream_cmd(args: list[str]) -> str:
            """Dream up new Pokemon names, returning a friendly error on failure."""
            try:
                return pyllm.generate_pokemon(prompt=" ".join(args), max_new_tokens=40)
            except Exception as exc:  # noqa: BLE001
                return f"error: {exc}"

        return [
            ShellCommand(
                name="dream",
                handler=_dream_cmd,
                help_text="Dream up new Pokemon names with PyLLM.",
            )
        ]
