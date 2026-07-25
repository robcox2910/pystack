"""PyStack plugin exposing PyLLM (the brain) to Pebble as the ``llm`` module.

This is the loop-closing plugin: it lets a Pebble program ``import "llm"`` and ask
PyLLM to write text -- including *more Pebble code*. The brain of the series
writing the language of the series. It calls PyLLM's cached public API, so the
model is loaded once and reused.
"""

import pyllm
from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler


@pebble_handler
def _llm_generate(args: list[PebbleValue]) -> PebbleValue:
    """Write Pebble-flavoured code from a prompt string."""
    prompt = str(args[0]) if args else "let "
    return pyllm.generate_pebble(prompt=prompt, max_new_tokens=120)


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
        """Expose ``llm_generate`` (writes Pebble) and ``llm_dream`` (Pokemon)."""
        return StdlibModule(
            functions={
                "llm_generate": (1, _llm_generate),
                "llm_dream": (1, _llm_dream),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Add a ``dream`` shell command that generates Pokemon names."""
        return [
            ShellCommand(
                name="dream",
                handler=lambda args: pyllm.generate_pokemon(
                    prompt=" ".join(args), max_new_tokens=40
                ),
                help_text="Dream up new Pokemon names with PyLLM.",
            )
        ]
