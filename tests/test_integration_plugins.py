"""Tests for the integration plugins.

Verify that each plugin (crypto, web, git, net, search, mq) registers
Pebble stdlib functions correctly and that Pebble programs can call
them through the PyStackEnvironment.
"""

from pathlib import Path

from pebble.stdlib import STDLIB_MODULES

from pystack.environment import PyStackEnvironment
from pystack.plugins._shared import url_parse as _url_parse
from pystack.plugins.crypto_plugin import _caesar_decrypt, _caesar_encrypt, _hash
from pystack.plugins.git_plugin import _git_diff, _git_hash
from pystack.plugins.mq_plugin import _mq_create, _mq_get, _mq_put, reset_mq_state
from pystack.plugins.net_plugin import _base64_decode, _base64_encode
from pystack.plugins.search_plugin import (
    _search_add,
    _search_create,
    _search_query,
    reset_engines,
)
from pystack.plugins.web_plugin import WebPlugin

EXPECTED_SHA256_LENGTH = 64
EXPECTED_SHA1_LENGTH = 40
HTTPS_DEFAULT_PORT = 443


class TestCryptoPlugin:
    """Verify PyCrypt integration via the crypto plugin."""

    def test_hash_function_returns_sha256(self, tmp_path: Path) -> None:
        """The hash() function should return a 64-char SHA-256 hex string."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            output = env.run_pebble_source('import "crypto"\nprint(hash("hello"))')
            result = output.strip()
            assert len(result) == EXPECTED_SHA256_LENGTH
            assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        finally:
            env.shutdown()

    def test_caesar_encrypt_decrypt_roundtrip(self, tmp_path: Path) -> None:
        """Encrypting then decrypting with the same shift should recover the original text."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = (
                'import "crypto"\n'
                'let enc = caesar_encrypt("Hello", 3)\n'
                "let dec = caesar_decrypt(enc, 3)\n"
                "print(dec)"
            )
            output = env.run_pebble_source(source)
            assert output.strip() == "Hello"
        finally:
            env.shutdown()

    def test_hmac_sign_and_verify(self, tmp_path: Path) -> None:
        """Signing a message and verifying it should return true."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = (
                'import "crypto"\n'
                'let tag = hmac_sign("message", "secret")\n'
                'print(hmac_verify("message", tag, "secret"))'
            )
            output = env.run_pebble_source(source)
            assert output.strip() == "true"
        finally:
            env.shutdown()

    def test_hash_handler_directly(self) -> None:
        """The _hash handler should return a SHA-256 hex string."""
        result = _hash(["hello"])
        assert isinstance(result, str)
        assert len(result) == EXPECTED_SHA256_LENGTH

    def test_caesar_handlers_directly(self) -> None:
        """Caesar encrypt/decrypt handlers should work with Pebble values."""
        encrypted = _caesar_encrypt(["ABC", 1])
        assert encrypted == "BCD"
        decrypted = _caesar_decrypt(["BCD", 1])
        assert decrypted == "ABC"


class TestWebPlugin:
    """Verify PyWeb/PyNet HTTP integration via the web plugin."""

    def test_url_parse_returns_dict(self, tmp_path: Path) -> None:
        """The url_parse() function should return a dict with URL components."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = (
                'import "web"\nlet u = url_parse("https://example.com:8080/path")\nprint(u["host"])'
            )
            output = env.run_pebble_source(source)
            assert output.strip() == "example.com"
        finally:
            env.shutdown()

    def test_url_parse_handler_directly(self) -> None:
        """The _url_parse handler should return a dict with scheme, host, port, path."""
        result = _url_parse(["https://example.com:443/hello"])
        assert isinstance(result, dict)
        assert result["scheme"] == "https"
        assert result["host"] == "example.com"
        assert result["port"] == HTTPS_DEFAULT_PORT
        assert result["path"] == "/hello"

    def test_web_plugin_registers_module(self) -> None:
        """The WebPlugin should register a 'web' stdlib module."""
        plugin = WebPlugin()
        stdlib = plugin.pebble_stdlib()
        assert stdlib is not None
        assert "http_get" in stdlib.functions
        assert "url_parse" in stdlib.functions


class TestGitPlugin:
    """Verify PyGit integration via the git plugin."""

    def test_git_hash_returns_sha1(self, tmp_path: Path) -> None:
        """The git_hash() function should return a 40-char SHA-1 hex string."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            output = env.run_pebble_source('import "git"\nprint(git_hash("hello"))')
            result = output.strip()
            assert len(result) == EXPECTED_SHA1_LENGTH
            assert result == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
        finally:
            env.shutdown()

    def test_git_diff_shows_changes(self, tmp_path: Path) -> None:
        """The git_diff() function should show added and removed lines."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = 'import "git"\nlet d = git_diff("old line", "new line")\nprint(d)'
            output = env.run_pebble_source(source)
            assert "-" in output
            assert "+" in output
        finally:
            env.shutdown()

    def test_git_hash_handler_directly(self) -> None:
        """The _git_hash handler should return a SHA-1 hex string."""
        result = _git_hash(["test"])
        assert isinstance(result, str)
        assert len(result) == EXPECTED_SHA1_LENGTH

    def test_git_diff_handler_directly(self) -> None:
        """The _git_diff handler should produce diff output."""
        result = _git_diff(["alpha", "beta"])
        assert isinstance(result, str)
        assert "- alpha" in result
        assert "+ beta" in result


class TestNetPlugin:
    """Verify PyNet integration via the net plugin."""

    def test_base64_roundtrip(self, tmp_path: Path) -> None:
        """Encoding then decoding Base64 should recover the original text."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = (
                'import "net"\n'
                'let enc = base64_encode("Hello!")\n'
                "let dec = base64_decode(enc)\n"
                "print(dec)"
            )
            output = env.run_pebble_source(source)
            assert output.strip() == "Hello!"
        finally:
            env.shutdown()

    def test_url_parse_in_net(self, tmp_path: Path) -> None:
        """The net url_parse() function should parse URL components."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = (
                'import "net"\nlet u = url_parse("http://localhost:3000/api")\nprint(u["port"])'
            )
            output = env.run_pebble_source(source)
            assert output.strip() == "3000"
        finally:
            env.shutdown()

    def test_base64_handlers_directly(self) -> None:
        """The base64 encode/decode handlers should round-trip correctly."""
        encoded = _base64_encode(["Hello, world!"])
        assert isinstance(encoded, str)
        assert encoded == "SGVsbG8sIHdvcmxkIQ=="
        decoded = _base64_decode([encoded])
        assert decoded == "Hello, world!"

    def test_url_parse_handler_directly(self) -> None:
        """The _url_parse handler should return a dict."""
        result = _url_parse(["http://example.com/path"])
        assert isinstance(result, dict)
        assert result["host"] == "example.com"


class TestSearchPlugin:
    """Verify PySearch integration via the search plugin."""

    def test_search_create_add_query(self, tmp_path: Path) -> None:
        """Create an engine, add docs, and query should return results."""
        reset_engines()
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = (
                'import "search"\n'
                "let e = search_create()\n"
                'search_add(e, "d1", "the cat sat on the mat")\n'
                'search_add(e, "d2", "the dog chased the ball")\n'
                'let results = search_query(e, "cat")\n'
                "print(len(results))"
            )
            output = env.run_pebble_source(source)
            count = int(output.strip())
            assert count >= 1
        finally:
            reset_engines()
            env.shutdown()

    def test_search_handlers_directly(self) -> None:
        """The search handlers should create, add, and query correctly."""
        reset_engines()
        try:
            engine_id = _search_create([])
            assert isinstance(engine_id, str)
            assert engine_id.startswith("engine_")

            result = _search_add([engine_id, "doc1", "cats and dogs"])
            assert result is True

            results = _search_query([engine_id, "cats"])
            assert isinstance(results, list)
            assert len(results) >= 1
        finally:
            reset_engines()

    def test_search_unknown_engine(self) -> None:
        """Querying an unknown engine should return an error string."""
        reset_engines()
        result = _search_query(["nonexistent", "query"])
        assert isinstance(result, str)
        assert "error" in result


class TestEnvironmentRegistersPlugins:
    """Verify that PyStackEnvironment auto-registers all plugins on boot."""

    def test_all_modules_registered(self, tmp_path: Path) -> None:
        """All twelve plugin modules should be registered after environment boot."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            expected_modules = [
                "crypto", "web", "git", "net", "search", "mq",
                "kv", "docdb", "graphdb", "tsdb", "vecdb", "coldb",
            ]
            for module_name in expected_modules:
                assert module_name in STDLIB_MODULES, f"{module_name} not registered"
        finally:
            env.shutdown()

    def test_plugins_in_registry(self, tmp_path: Path) -> None:
        """All twelve plugins should appear in the plugin registry."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            expected_count = 12
            infos = env.plugin_registry.list_plugins()
            assert len(infos) >= expected_count
            names = {info.name for info in infos}
            assert "PyCrypt" in names
            assert "PyWeb" in names
            assert "PyGit" in names
            assert "PyNet" in names
            assert "PySearch" in names
            assert "PyMQ" in names
            assert "PyKV" in names
            assert "PyDocDB" in names
            assert "PyGraphDB" in names
            assert "PyTSDB" in names
            assert "PyVecDB" in names
            assert "PyColDB" in names
        finally:
            env.shutdown()


class TestMQPlugin:
    """Verify PyMQ integration via the mq plugin."""

    def test_mq_create_returns_name(self) -> None:
        """The mq_create handler should return the queue name."""
        reset_mq_state()
        try:
            result = _mq_create(["orders"])
            assert result == "orders"
        finally:
            reset_mq_state()

    def test_mq_put_and_get(self) -> None:
        """Put a message and get it back via handlers."""
        reset_mq_state()
        try:
            _mq_create(["tasks"])
            result = _mq_put(["tasks", "do laundry"])
            assert result == "ok"
            msg = _mq_get(["tasks"])
            assert msg == "do laundry"
        finally:
            reset_mq_state()

    def test_mq_get_empty_returns_empty(self) -> None:
        """Getting from an empty queue should return 'empty'."""
        reset_mq_state()
        try:
            _mq_create(["empty-q"])
            result = _mq_get(["empty-q"])
            assert result == "empty"
        finally:
            reset_mq_state()

    def test_mq_get_unknown_queue_returns_error(self) -> None:
        """Getting from an unknown queue should return an error string."""
        reset_mq_state()
        try:
            result = _mq_get(["nonexistent"])
            assert isinstance(result, str)
            assert "error" in result
        finally:
            reset_mq_state()

    def test_mq_put_unknown_queue_returns_error(self) -> None:
        """Putting to an unknown queue should return an error string."""
        reset_mq_state()
        try:
            result = _mq_put(["nonexistent", "msg"])
            assert isinstance(result, str)
            assert "error" in result
        finally:
            reset_mq_state()

    def test_mq_pebble_source(self, tmp_path: Path) -> None:
        """Run a Pebble program that creates a queue, puts, and gets a message."""
        reset_mq_state()
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = (
                'import "mq"\n'
                'let q = mq_create("test")\n'
                'mq_put("test", "hello from pebble")\n'
                'let msg = mq_get("test")\n'
                "print(msg)"
            )
            output = env.run_pebble_source(source)
            assert output.strip() == "hello from pebble"
        finally:
            reset_mq_state()
            env.shutdown()
