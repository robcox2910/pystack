"""Tests for the integration plugins.

Verify that each plugin (crypto, web, git, net, search, mq) registers
Pebble stdlib functions correctly and that Pebble programs can call
them through the PyStackEnvironment.
"""

import re
from pathlib import Path

from pystack.environment import PyStackEnvironment
from pystack.plugins._shared import url_parse as _url_parse
from pystack.plugins.crypto_plugin import _caesar_decrypt, _caesar_encrypt, _hash
from pystack.plugins.git_plugin import _git_diff, _git_hash
from pystack.plugins.mq_plugin import MQPlugin
from pystack.plugins.net_plugin import NetPlugin, _base64_decode, _base64_encode
from pystack.plugins.search_plugin import SearchPlugin
from pystack.plugins.web_plugin import WebPlugin

EXPECTED_SHA256_LENGTH = 64
EXPECTED_SHA1_LENGTH = 40
HTTPS_DEFAULT_PORT = 443
OVERLAP_COPIES = 3
OVERLAP_SECONDS = "0.2"
OVERLAP_MAX_ELAPSED = 0.5


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
            assert result == "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0"
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

    def test_git_hash_matches_real_git(self) -> None:
        """git_hash gives exactly what ``printf 'hello' | git hash-object --stdin`` prints."""
        assert _git_hash(["hello"]) == "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0"

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

    def test_overlap_runs_concurrently(self) -> None:
        """The overlap command should run its sleeps at the same time."""
        cmds = {c.name: c.handler for c in NetPlugin().shell_commands()}
        output = cmds["overlap"]([str(OVERLAP_COPIES), OVERLAP_SECONDS])
        assert f"{OVERLAP_COPIES} \u00d7 sleep {OVERLAP_SECONDS}" in output
        match = re.search(r"in (\d+\.\d{2})s", output)
        assert match is not None
        assert float(match.group(1)) < OVERLAP_MAX_ELAPSED

    def test_overlap_bad_args_returns_usage(self) -> None:
        """The overlap command should return usage for invalid arguments."""
        cmds = {c.name: c.handler for c in NetPlugin().shell_commands()}
        for bad in (["0"], ["x"], ["3", "-1"], ["3", "abc"], ["1", "2", "3"], ["999"], ["1", "99"]):
            assert cmds["overlap"](bad).startswith("Usage: overlap")

    def test_netecho_round_trip(self) -> None:
        """The netecho command should echo text back with a round-trip time."""
        cmds = {c.name: c.handler for c in NetPlugin().shell_commands()}
        output = cmds["netecho"](["hello", "world"])
        assert output.startswith("echo: hello world")
        assert re.search(r"\(round trip \d+\.\d ms\)$", output)

    def test_netecho_usage(self) -> None:
        """The netecho command should return usage when given no text."""
        cmds = {c.name: c.handler for c in NetPlugin().shell_commands()}
        assert cmds["netecho"]([]).startswith("Usage: netecho")

    def test_wsecho_round_trip(self) -> None:
        """The wsecho command should echo text back through a local WebSocket."""
        cmds = {c.name: c.handler for c in NetPlugin().shell_commands()}
        assert cmds["wsecho"](["hello", "socket"]) == "ws echo: hello socket"

    def test_wsecho_usage(self) -> None:
        """The wsecho command should return usage when given no text."""
        cmds = {c.name: c.handler for c in NetPlugin().shell_commands()}
        assert cmds["wsecho"]([]).startswith("Usage: wsecho")


class TestSearchPlugin:
    """Verify PySearch integration via the search plugin."""

    def test_search_create_add_query(self, tmp_path: Path) -> None:
        """Create an engine, add docs, and query should return results."""
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
            env.shutdown()

    def test_search_handlers_directly(self) -> None:
        """The search handlers should create, add, and query correctly."""
        plugin = SearchPlugin()
        engine_id = plugin.search_create([])
        assert isinstance(engine_id, str)
        assert engine_id.startswith("engine_")

        result = plugin.search_add([engine_id, "doc1", "cats and dogs"])
        assert result is True

        results = plugin.search_query([engine_id, "cats"])
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_search_unknown_engine(self) -> None:
        """Querying an unknown engine should return an error string."""
        plugin = SearchPlugin()
        result = plugin.search_query(["nonexistent", "query"])
        assert isinstance(result, str)
        assert "error" in result


class TestEnvironmentRegistersPlugins:
    """Verify that PyStackEnvironment auto-registers all plugins on boot."""

    def test_all_modules_registered(self, tmp_path: Path) -> None:
        """All thirteen plugin modules should be registered after environment boot."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            expected_modules = [
                "crypto",
                "web",
                "git",
                "net",
                "search",
                "mq",
                "kv",
                "docdb",
                "graphdb",
                "tsdb",
                "vecdb",
                "coldb",
                "llm",
            ]
            for module_name in expected_modules:
                assert module_name in env.plugin_registry.pebble_modules(), module_name
        finally:
            env.shutdown()

    def test_plugins_in_registry(self, tmp_path: Path) -> None:
        """All thirteen plugins should appear in the plugin registry."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            expected_count = 13
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
            assert "PyLLM" in names
        finally:
            env.shutdown()


class TestMQPlugin:
    """Verify PyMQ integration via the mq plugin."""

    def test_mq_create_returns_name(self) -> None:
        """The mq_create handler should return the queue name."""
        assert MQPlugin().mq_create(["orders"]) == "orders"

    def test_mq_put_and_get(self) -> None:
        """Put a message and get it back via handlers."""
        plugin = MQPlugin()
        plugin.mq_create(["tasks"])
        assert plugin.mq_put(["tasks", "do laundry"]) == "ok"
        assert plugin.mq_get(["tasks"]) == "do laundry"

    def test_mq_get_empty_returns_empty(self) -> None:
        """Getting from an empty queue should return 'empty'."""
        plugin = MQPlugin()
        plugin.mq_create(["empty-q"])
        assert plugin.mq_get(["empty-q"]) == "empty"

    def test_mq_get_unknown_queue_returns_error(self) -> None:
        """Getting from an unknown queue should return an error string."""
        assert MQPlugin().mq_get(["nonexistent"]) == "error: queue 'nonexistent' not found"

    def test_mq_put_unknown_queue_returns_error(self) -> None:
        """Putting to an unknown queue should return an error string."""
        assert MQPlugin().mq_put(["nonexistent", "msg"]) == "error: queue 'nonexistent' not found"

    def test_publish_reaches_subscribers_once(self) -> None:
        """A subscriber receives each published message once, then its inbox is empty."""
        plugin = MQPlugin()
        plugin.mq_subscribe(["news"])
        plugin.mq_publish(["news", "hello"])
        plugin.mq_publish(["other", "ignored"])
        assert plugin.mq_receive(["news"]) == ["hello"]
        assert plugin.mq_receive(["news"]) == []

    def test_mq_pebble_source(self, tmp_path: Path) -> None:
        """Run a Pebble program that creates a queue, puts, and gets a message."""
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
            env.shutdown()


MQNET_RUNS = 3
MQNET_MAX_LINES = 40


class TestMqnetCommand:
    """Verify the mqnet demo of PyMQ's networked broker."""

    def test_mqnet_story(self) -> None:
        """The mqnet command should show a crash, the lease returning and a poison job."""
        cmds = {c.name: c.handler for c in MQPlugin().shell_commands()}
        output = cmds["mqnet"]([])
        lines = output.splitlines()
        story = [
            "worker A: took job-1 (attempt 1) and crashed - connection lost",
            "broker: took job-1 back from worker A (lease returned, attempt 1 used up)",
            "worker B: job-1 done (attempt 2)",
        ]
        positions = [lines.index(line) for line in story]
        assert positions == sorted(positions)
        assert "job-2 done" in output
        assert "dead: job-boom (max_attempts)" in output
        assert "$sys.dead.jobs" in output
        assert "Traceback" not in output
        assert len(output.splitlines()) < MQNET_MAX_LINES

    def test_mqnet_is_deterministic(self) -> None:
        """The mqnet command should print the same story every run."""
        cmds = {c.name: c.handler for c in MQPlugin().shell_commands()}
        outputs = {cmds["mqnet"]([]) for _ in range(MQNET_RUNS)}
        assert len(outputs) == 1


WEBDEMO_RUNS = 3
WEBDEMO_MAX_LINES = 30


class TestWebdemoCommand:
    """Verify the webdemo tour of PyWeb's async server."""

    def test_webdemo_story(self) -> None:
        """The webdemo command should show each step of the login story in order."""
        cmds = {c.name: c.handler for c in WebPlugin().shell_commands()}
        output = cmds["webdemo"]([])
        lines = output.splitlines()
        story = [
            "GET /           -> 200 (public page)",
            "GET /api/me     -> 401 (no wristband yet)",
            "POST /login     -> 200",
            "Set-Cookie: session=… (HttpOnly; SameSite=Lax)",
            'GET /api/me     -> 200 {"user": "ada"} (wristband shown)',
            "GET /ticks      -> 200 (event stream)",
            "event: tick 1",
            "event: tick 2",
            "event: tick 3",
        ]
        positions = [lines.index(line) for line in story]
        assert positions == sorted(positions)
        assert "Traceback" not in output
        assert len(lines) < WEBDEMO_MAX_LINES

    def test_webdemo_never_prints_the_cookie_value(self) -> None:
        """The webdemo command should elide the session token."""
        cmds = {c.name: c.handler for c in WebPlugin().shell_commands()}
        assert "session=…" in cmds["webdemo"]([])
        assert "session=ey" not in cmds["webdemo"]([])

    def test_webdemo_is_deterministic(self) -> None:
        """The webdemo command should print the same story every run."""
        cmds = {c.name: c.handler for c in WebPlugin().shell_commands()}
        outputs = {cmds["webdemo"]([]) for _ in range(WEBDEMO_RUNS)}
        assert len(outputs) == 1
