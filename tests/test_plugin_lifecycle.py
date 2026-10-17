"""Tests for the plugin lifecycle: load at start-up, save, and shut down.

Plugins keep their data in their own folder inside the environment's data
folder. They load it when PyStack starts and save it when PyStack stops,
like a game that reloads your progress every time you open it.
"""

from pathlib import Path

import pytest

from pystack.environment import PyStackEnvironment
from pystack.plugins.base import Plugin, PluginInfo
from pystack.plugins.registry import PluginRegistry


class _Recorder(Plugin):
    """A plugin that writes down every lifecycle hook it receives."""

    def __init__(self) -> None:
        self.events: list[tuple[str, Path | None]] = []

    def info(self) -> PluginInfo:
        return PluginInfo(name="Recorder")

    def load_state(self, folder: Path) -> None:
        self.events.append(("load", folder))

    def on_boot(self) -> None:
        self.events.append(("boot", None))

    def save_state(self, folder: Path) -> None:
        self.events.append(("save", folder))

    def on_shutdown(self) -> None:
        self.events.append(("shutdown", None))


class _Exploder(Plugin):
    """A plugin whose save always fails."""

    def info(self) -> PluginInfo:
        return PluginInfo(name="Exploder")

    def save_state(self, folder: Path) -> None:
        self.tried = folder
        msg = "boom"
        raise RuntimeError(msg)


class _OldStyle(Plugin):
    """A plugin written before the new hooks existed: it only overrides on_boot()."""

    def __init__(self) -> None:
        self.booted = False

    def info(self) -> PluginInfo:
        return PluginInfo(name="OldStyle")

    def on_boot(self) -> None:
        self.booted = True


class TestRegistryLifecycle:
    """The registry calls the hooks in the right order with the right folders."""

    def test_load_state_runs_before_on_boot_with_the_plugin_folder(self, tmp_path: Path) -> None:
        """Each plugin loads from <data_dir>/<module name>/ and then boots."""
        recorder = _Recorder()
        registry = PluginRegistry()
        registry.register(recorder)
        registry.activate_all(data_dir=tmp_path)
        assert recorder.events == [("load", tmp_path / "recorder"), ("boot", None)]

    def test_old_style_plugin_with_plain_on_boot_still_works(self, tmp_path: Path) -> None:
        """Plugins that only override on_boot() keep working unchanged."""
        plugin = _OldStyle()
        registry = PluginRegistry()
        registry.register(plugin)
        registry.activate_all(data_dir=tmp_path)
        assert plugin.booted
        assert registry.save_all(tmp_path) == []
        assert registry.shutdown_all() == []


class TestEnvironmentSaveAndShutdown:
    """Saving tries every plugin; shutting down never crashes."""

    def test_save_calls_every_plugin_and_raises_after_trying_all(self, tmp_path: Path) -> None:
        """One failing plugin doesn't stop the others being saved."""
        env = PyStackEnvironment(db_path=tmp_path)
        exploder, recorder = _Exploder(), _Recorder()
        env.plugin_registry.register(exploder)
        env.plugin_registry.register(recorder)
        try:
            with pytest.raises(ExceptionGroup, match="could not save") as caught:
                env.save()
            assert ("save", tmp_path / "recorder") in recorder.events
            assert [str(e) for e in caught.value.exceptions] == ["boom"]
        finally:
            env.shutdown()

    def test_shutdown_never_raises_and_reports_each_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Shutdown prints one line per failure and still shuts every plugin down."""
        env = PyStackEnvironment(db_path=tmp_path)
        recorder = _Recorder()
        env.plugin_registry.register(_Exploder())
        env.plugin_registry.register(recorder)
        env.shutdown()
        assert "pystack: could not save exploder: boom" in capsys.readouterr().err
        assert ("shutdown", None) in recorder.events

    def test_shutdown_twice_is_harmless(self, tmp_path: Path) -> None:
        """The second shutdown does nothing at all."""
        env = PyStackEnvironment(db_path=tmp_path)
        recorder = _Recorder()
        env.plugin_registry.register(recorder)
        env.shutdown()
        env.shutdown()
        assert recorder.events.count(("shutdown", None)) == 1

    def test_save_shell_command_reports_saved(self, tmp_path: Path) -> None:
        """Typing ``save`` in the PyStack shell saves everything."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            assert env.shell is not None
            assert env.shell.execute("save") == "Saved."
        finally:
            env.shutdown()
