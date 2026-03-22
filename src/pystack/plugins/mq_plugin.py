"""PyMQ integration plugin for PyStack.

Bridge PyMQ's message queue and pub/sub primitives into Pebble so kids
can create queues, put and get messages, and publish/subscribe to topics
from their Pebble programs.

Pebble module name: ``mq``

Example Pebble usage::

    import "mq"
    let q = mq_create("orders")
    mq_put("orders", "one coffee please")
    let msg = mq_get("orders")
    print(msg)
"""

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pymq.pubsub import PubSub
from pymq.queue import MessageQueue

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

_queues: dict[str, MessageQueue] = {}
_pubsub_instance: PubSub | None = None
_topic_messages: dict[str, list[str]] = {}


def _get_pubsub() -> PubSub:
    """Return the shared PubSub instance, creating it if needed."""
    global _pubsub_instance  # noqa: PLW0603
    if _pubsub_instance is None:
        _pubsub_instance = PubSub()
    return _pubsub_instance


@pebble_handler
def _mq_create(args: list[PebbleValue]) -> PebbleValue:
    """Create a named message queue and return its name."""
    name = str(args[0])
    if name not in _queues:
        _queues[name] = MessageQueue(name)
    return name


@pebble_handler
def _mq_put(args: list[PebbleValue]) -> PebbleValue:
    """Put a message on a named queue."""
    name = str(args[0])
    message = str(args[1])
    if name not in _queues:
        return f"error: queue '{name}' not found"
    _queues[name].put(message)
    return "ok"


@pebble_handler
def _mq_get(args: list[PebbleValue]) -> PebbleValue:
    """Get the next message body from a named queue, or 'empty'."""
    name = str(args[0])
    if name not in _queues:
        return f"error: queue '{name}' not found"
    msg = _queues[name].get()
    if msg is None:
        return "empty"
    _queues[name].acknowledge(msg)
    return msg.body


@pebble_handler
def _mq_publish(args: list[PebbleValue]) -> PebbleValue:
    """Publish a message to a topic."""
    topic = str(args[0])
    message = str(args[1])
    _get_pubsub().publish(topic, message)
    return "ok"


@pebble_handler
def _mq_subscribe(args: list[PebbleValue]) -> PebbleValue:
    """Subscribe to a topic and store messages for later retrieval."""
    topic = str(args[0])
    if topic not in _topic_messages:
        _topic_messages[topic] = []

        def _handler(_t: str, msg: str) -> None:
            _topic_messages[topic].append(msg)

        _get_pubsub().subscribe(topic, _handler)
    return topic


@pebble_handler
def _mq_receive(args: list[PebbleValue]) -> PebbleValue:
    """Get all stored messages for a subscribed topic."""
    topic = str(args[0])
    if topic not in _topic_messages:
        return f"error: not subscribed to '{topic}'"
    result: list[PebbleValue] = list(_topic_messages[topic])
    _topic_messages[topic].clear()
    return result


def reset_mq_state() -> None:
    """Reset all module-level state for testing."""
    global _pubsub_instance  # noqa: PLW0603
    _queues.clear()
    _pubsub_instance = None
    _topic_messages.clear()


class MQPlugin(Plugin):
    """Integrate PyMQ message queue functions into PyStack.

    Register queue and pub/sub functions in Pebble's ``mq`` stdlib
    module, and ``mq-put`` / ``mq-get`` shell commands.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyMQ",
            description="Message queue and pub/sub for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "mq"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the mq stdlib module with queue and pub/sub functions."""
        return StdlibModule(
            functions={
                "mq_create": (1, _mq_create),
                "mq_put": (2, _mq_put),
                "mq_get": (1, _mq_get),
                "mq_publish": (2, _mq_publish),
                "mq_subscribe": (1, _mq_subscribe),
                "mq_receive": (1, _mq_receive),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the mq-put and mq-get shell commands."""

        def _mq_put_cmd(args: list[str]) -> str:
            """Put a message on a named queue."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: mq-put <queue> <message>"

            name = args[0]
            message = " ".join(args[1:])
            if name not in _queues:
                _queues[name] = MessageQueue(name)
            _queues[name].put(message)
            return f"Queued on '{name}': {message}"

        def _mq_get_cmd(args: list[str]) -> str:
            """Get the next message from a named queue."""
            if not args:
                return "Usage: mq-get <queue>"
            name = args[0]
            if name not in _queues:
                return f"Queue '{name}' not found"
            msg = _queues[name].get()
            if msg is None:
                return "Queue is empty"
            _queues[name].acknowledge(msg)
            return msg.body

        return [
            ShellCommand(name="mq-put", handler=_mq_put_cmd, help_text="Put message on a queue"),
            ShellCommand(name="mq-get", handler=_mq_get_cmd, help_text="Get message from a queue"),
        ]
