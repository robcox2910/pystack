"""PyCrypt integration plugin for PyStack.

Bridge PyCrypt's cryptographic primitives into Pebble so kids can hash
text, encrypt with Caesar ciphers, and sign messages with HMAC -- all
from their Pebble programs.

Pebble module name: ``crypto``

Example Pebble usage::

    import "crypto"
    let h = hash("hello")
    print(h)

    let encrypted = caesar_encrypt("SECRET", 3)
    print(encrypted)
"""

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pycrypt.caesar import decrypt as caesar_dec
from pycrypt.caesar import encrypt as caesar_enc
from pycrypt.hashing import sha256
from pycrypt.hmac import hmac_sign as _hmac_sign
from pycrypt.hmac import hmac_verify as _hmac_verify

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand


def _hash(args: list[PebbleValue]) -> PebbleValue:
    """Return the SHA-256 hash of a text string."""
    try:
        return sha256(str(args[0]))
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def _caesar_encrypt(args: list[PebbleValue]) -> PebbleValue:
    """Encrypt text using the Caesar cipher with the given shift."""
    try:
        text = str(args[0])
        shift = int(args[1])  # type: ignore[arg-type]
        return caesar_enc(text, shift)
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def _caesar_decrypt(args: list[PebbleValue]) -> PebbleValue:
    """Decrypt text using the Caesar cipher with the given shift."""
    try:
        text = str(args[0])
        shift = int(args[1])  # type: ignore[arg-type]
        return caesar_dec(text, shift)
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def _hmac_sign_handler(args: list[PebbleValue]) -> PebbleValue:
    """Create an HMAC-SHA256 tag for a message with a secret key."""
    try:
        message = str(args[0])
        key = str(args[1])
        return _hmac_sign(message, key)
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def _hmac_verify_handler(args: list[PebbleValue]) -> PebbleValue:
    """Verify that a message matches its HMAC tag."""
    try:
        message = str(args[0])
        tag = str(args[1])
        key = str(args[2])
        return _hmac_verify(message, tag, key)
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


class CryptoPlugin(Plugin):
    """Integrate PyCrypt cryptographic functions into PyStack.

    Register hashing, Caesar cipher, and HMAC functions in Pebble's
    ``crypto`` stdlib module, and a ``hash`` shell command.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyCrypt",
            description="Cryptographic primitives for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "crypto"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the crypto stdlib module with hash, Caesar, and HMAC functions."""
        return StdlibModule(
            functions={
                "hash": (1, _hash),
                "caesar_encrypt": (2, _caesar_encrypt),
                "caesar_decrypt": (2, _caesar_decrypt),
                "hmac_sign": (2, _hmac_sign_handler),
                "hmac_verify": (3, _hmac_verify_handler),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the hash shell command."""

        def _hash_cmd(args: list[str]) -> str:
            """Print the SHA-256 hash of the given text."""
            if not args:
                return "Usage: hash <text>"
            text = " ".join(args)
            return sha256(text)

        return [ShellCommand(name="hash", handler=_hash_cmd, help_text="Print SHA-256 hash")]
