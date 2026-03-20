"""Tests for the plugin system.

Plugins are expansion packs -- they hook into the shell, Pebble, and
web UI without modifying core code. These tests verify the plugin
lifecycle.
"""

from pathlib import Path

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import STDLIB_MODULES, StdlibModule
from py_os.kernel import Kernel
from py_os.shell import Shell

from pystack.environment import PyStackEnvironment
from pystack.plugins.base import Plugin, PluginInfo, ShellCommand
from pystack.plugins.registry import PluginRegistry


class _ExamplePlugin(Plugin):
    """A test plugin that registers a shell command and a stdlib module."""

    def info(self) -> PluginInfo:
        """Return test plugin info."""
        return PluginInfo(name="TestPlugin", description="For testing", version="1.0.0")

    def shell_commands(self) -> list[ShellCommand]:
        """Register a 'greet' shell command."""
        return [ShellCommand(name="greet", handler=lambda _args: "Hello from plugin!")]

    def pebble_stdlib(self) -> StdlibModule | None:
        """Register a 'test' stdlib module with a greet() function."""

        def _greet(_args: list[PebbleValue]) -> PebbleValue:
            return "Hello from plugin!"

        return StdlibModule(functions={"greet": (0, _greet)}, constants={})

    def pebble_module_name(self) -> str:
        """Return the module name 'test'."""
        return "test"


class _MinimalPlugin(Plugin):
    """A plugin that overrides nothing -- tests default behavior."""


class TestPluginBase:
    """Verify the Plugin base class defaults."""

    def test_default_info(self) -> None:
        """Default info should use the class name."""
        p = _MinimalPlugin()
        info = p.info()
        assert info.name == "_MinimalPlugin"

    def test_default_shell_commands(self) -> None:
        """Default shell_commands should return empty list."""
        p = _MinimalPlugin()
        assert p.shell_commands() == []

    def test_default_pebble_stdlib(self) -> None:
        """Default pebble_stdlib should return None."""
        p = _MinimalPlugin()
        assert p.pebble_stdlib() is None

    def test_default_on_boot(self) -> None:
        """Default on_boot should not raise."""
        p = _MinimalPlugin()
        p.on_boot()  # Should not raise.


class TestPluginRegistry:
    """Verify plugin registration and activation."""

    def test_register_adds_plugin(self) -> None:
        """Registering a plugin should add it to the list."""
        registry = PluginRegistry()
        plugin = _ExamplePlugin()
        registry.register(plugin)
        assert len(registry.plugins) == 1

    def test_list_plugins(self) -> None:
        """list_plugins should return info for all registered plugins."""
        registry = PluginRegistry()
        registry.register(_ExamplePlugin())
        infos = registry.list_plugins()
        assert len(infos) == 1
        assert infos[0].name == "TestPlugin"

    def test_activate_registers_shell_commands(self) -> None:
        """Activation should register shell commands."""
        kernel = Kernel()
        kernel.boot()
        try:
            shell = Shell(kernel=kernel)
            registry = PluginRegistry()
            registry.register(_ExamplePlugin())
            registry.activate_all(shell=shell)
            assert "greet" in shell._commands
            output = shell.execute("greet")
            assert output == "Hello from plugin!"
        finally:
            kernel.shutdown()

    def test_activate_registers_pebble_stdlib(self) -> None:
        """Activation should register Pebble stdlib modules."""
        registry = PluginRegistry()
        registry.register(_ExamplePlugin())
        registry.activate_all()
        assert "test" in STDLIB_MODULES
        # Clean up.
        STDLIB_MODULES.pop("test", None)

    def test_activate_calls_on_boot(self) -> None:
        """Activation should call on_boot for each plugin."""
        booted: list[bool] = []

        class _BootTracker(Plugin):
            """Track whether on_boot was called."""

            def on_boot(self) -> None:
                """Record the boot."""
                booted.append(True)

        registry = PluginRegistry()
        registry.register(_BootTracker())
        registry.activate_all()
        assert booted == [True]

    def test_discover_returns_count(self) -> None:
        """Discover should return 0 when no entry points exist."""
        registry = PluginRegistry()
        count = registry.discover()
        assert count == 0

    def test_activate_without_shell(self) -> None:
        """Activation without a shell should skip command registration."""
        registry = PluginRegistry()
        registry.register(_ExamplePlugin())
        registry.activate_all(shell=None)  # Should not raise.


class TestPluginIntegration:
    """Verify plugins work in the full environment."""

    def test_plugin_shell_command_in_env(self, tmp_path: Path) -> None:
        """A plugin's shell command should work in OS mode."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            env.plugin_registry.register(_ExamplePlugin())
            shell = env.shell
            assert isinstance(shell, Shell)
            env.plugin_registry.activate_all(shell=shell)
            output = env.execute_shell("greet")
            assert output == "Hello from plugin!"
        finally:
            env.shutdown()

    def test_plugin_pebble_stdlib_in_env(self, tmp_path: Path) -> None:
        """A plugin's Pebble stdlib module should work."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            env.plugin_registry.register(_ExamplePlugin())
            env.plugin_registry.activate_all()
            output = env.run_pebble_source('import "test"\nprint(greet())')
            assert "Hello from plugin!" in output
        finally:
            STDLIB_MODULES.pop("test", None)
            env.shutdown()
