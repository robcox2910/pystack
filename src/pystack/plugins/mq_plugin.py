"""PyMQ integration plugin for PyStack.

Bridge PyMQ's message queue and pub/sub primitives into Pebble so kids
can create queues, put and get messages, and publish/subscribe to topics
from their Pebble programs.

A message queue is like the order rail at a busy kitchen -- cooks pin up
tickets and chefs grab them one at a time, in order.

Shell command ``mqnet`` runs PyMQ's networked broker -- a real post office
with a front door -- on a free local port. Two workers collect parcels
(jobs): worker A takes the first job and crashes before finishing it (its
connection is lost), so the broker takes the lease back and worker B gets
the job on its second attempt. A poison job nobody can do ends up in the
dead-letter box.

Messages still waiting when PyStack stops are saved in
``pystack_data/mq/queues.json`` and are there again next time, like a real
broker. Pub/sub subscriptions are live only, like a radio: they don't
outlive the run.

Pebble module name: ``mq``

Example Pebble usage::

    import "mq"
    let q = mq_create("orders")
    mq_put("orders", "one coffee please")
    let msg = mq_get("orders")
    print(msg)
"""

from pathlib import Path

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pymq.broker import BrokerClient, BrokerServer, Delivery, QueueConfig, TopicEvent
from pymq.persistence import load_queues, save_queues
from pymq.pubsub import PubSub
from pymq.queue import BaseMessageQueue, MessageQueue
from pynet.loop import Event, run, sleep, timeout

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_method

LOOPBACK = "127.0.0.1"
MQNET_TIMEOUT = 5.0
MQNET_MAX_ATTEMPTS = 2
MQNET_ACK_TIMEOUT = 0.5
MQNET_RETRY_DELAY = 0.1
MQNET_POLL = 0.01
POISON_JOB = "job-boom"
_QUEUES_FILE = "queues.json"


async def _mqnet_story(out: list[str]) -> None:
    """Tell the mqnet story, appending one line per step to ``out``."""
    a_has_job = Event()
    job_done = Event()
    dead_seen = Event()
    dead_topics: list[str] = []

    async def worker_a(delivery: Delivery) -> None:
        """Take the first job and never settle it: worker A is about to crash."""
        out.append(
            f"worker A: took {delivery.body} (attempt {delivery.attempt})"
            " and crashed - connection lost"
        )
        a_has_job.set()

    async def worker_b(delivery: Delivery) -> None:
        """Finish every job except the poison one, which is handed back each time."""
        if delivery.body == POISON_JOB:
            out.append(f"worker B: {delivery.body} failed (attempt {delivery.attempt})")
            await delivery.nack(error="poison job")
            return
        out.append(f"worker B: {delivery.body} done (attempt {delivery.attempt})")
        job_done.set()

    async def on_dead(event: TopicEvent) -> None:
        """Remember the dead-letter announcement."""
        dead_topics.append(event.topic)
        dead_seen.set()

    server = BrokerServer()
    await server.start(LOOPBACK, 0)
    try:
        async with (
            timeout(MQNET_TIMEOUT),
            BrokerClient(LOOPBACK, server.port) as boss,
            BrokerClient(LOOPBACK, server.port) as ann,
            BrokerClient(LOOPBACK, server.port) as bob,
        ):
            out.append("broker: listening on a free local port")
            config = QueueConfig(
                max_attempts=MQNET_MAX_ATTEMPTS,
                ack_timeout=MQNET_ACK_TIMEOUT,
                retry_delay=MQNET_RETRY_DELAY,
            )
            await boss.declare_queue("jobs", config)
            await boss.subscribe("$sys.dead.*", on_dead)
            out.append("boss: declared queue 'jobs' (2 attempts per job)")
            await ann.consume("jobs", worker_a, prefetch=1, auto_ack=False)
            await boss.put("jobs", "job-1")
            await a_has_job.wait()
            await ann.close()  # the crash: worker A's connection drops, job-1 unacked
            while (await boss.stats("jobs")).ready != 1:
                await sleep(MQNET_POLL)  # wait for the broker to take the lease back
            out.append("broker: took job-1 back from worker A (lease returned, attempt 1 used up)")
            await bob.consume("jobs", worker_b, prefetch=1)
            await job_done.wait()
            job_done.clear()
            await boss.put("jobs", "job-2")
            await job_done.wait()
            await boss.put("jobs", POISON_JOB)
            await dead_seen.wait()
            letters = await boss.dead_letters("jobs")
            out.extend(f"dead: {d.envelope.body} ({d.reason}) - {d.error}" for d in letters)
            out.append(f"announced: {dead_topics[0]}")
    finally:
        await server.close()
    out.append("broker: closed")


def _mqnet_cmd(_args: list[str]) -> str:
    """Run a small job-queue story against a real PyMQ broker on localhost."""
    lines: list[str] = []
    try:
        run(_mqnet_story(lines))
    except Exception as exc:  # noqa: BLE001
        lines.append(f"error: {exc}")
    return "\n".join(lines)


class MQPlugin(Plugin):
    """Integrate PyMQ message queue functions into PyStack.

    Register queue and pub/sub functions in Pebble's ``mq`` stdlib
    module, and ``mq-put`` / ``mq-get`` / ``mqnet`` shell commands.
    """

    def __init__(self) -> None:
        """Start with no queues; they are created on first use or loaded at start-up."""
        self._queues: dict[str, BaseMessageQueue] | None = None
        self._pubsub = PubSub()
        self._inboxes: dict[str, list[str]] = {}

    def _get_queues(self) -> dict[str, BaseMessageQueue]:
        """Return this plugin's queues, creating the table on first use."""
        if self._queues is None:
            self._queues = {}
        return self._queues

    def _put(self, name: str, message: str) -> None:
        """Put *message* on queue *name*, creating the queue if needed."""
        self._get_queues().setdefault(name, MessageQueue(name)).put(message)

    def _take(self, name: str) -> str | None:
        """Take and acknowledge the next message body, or None if the queue is empty."""
        queue = self._get_queues()[name]
        msg = queue.get()
        if msg is None:
            return None
        queue.acknowledge(msg)
        return msg.body

    @pebble_method
    def mq_create(self, args: list[PebbleValue]) -> PebbleValue:
        """Create a named message queue and return its name."""
        name = str(args[0])
        self._get_queues().setdefault(name, MessageQueue(name))
        return name

    @pebble_method
    def mq_put(self, args: list[PebbleValue]) -> PebbleValue:
        """Put a message on a named queue."""
        name = str(args[0])
        if name not in self._get_queues():
            return f"error: queue '{name}' not found"
        self._put(name, str(args[1]))
        return "ok"

    @pebble_method
    def mq_get(self, args: list[PebbleValue]) -> PebbleValue:
        """Get the next message body from a named queue, or 'empty'."""
        name = str(args[0])
        if name not in self._get_queues():
            return f"error: queue '{name}' not found"
        body = self._take(name)
        return "empty" if body is None else body

    @pebble_method
    def mq_publish(self, args: list[PebbleValue]) -> PebbleValue:
        """Publish a message to a topic."""
        self._pubsub.publish(str(args[0]), str(args[1]))
        return "ok"

    @pebble_method
    def mq_subscribe(self, args: list[PebbleValue]) -> PebbleValue:
        """Subscribe to a topic and store messages for later retrieval."""
        topic = str(args[0])
        if topic not in self._inboxes:
            inbox: list[str] = []
            self._inboxes[topic] = inbox

            def _handler(_t: str, msg: str) -> None:
                inbox.append(msg)

            self._pubsub.subscribe(topic, _handler)
        return topic

    @pebble_method
    def mq_receive(self, args: list[PebbleValue]) -> PebbleValue:
        """Get all stored messages for a subscribed topic."""
        topic = str(args[0])
        if topic not in self._inboxes:
            return f"error: not subscribed to '{topic}'"
        result: list[PebbleValue] = list(self._inboxes[topic])
        self._inboxes[topic].clear()
        return result

    def load_state(self, folder: Path) -> None:
        """Load the saved queues, if there are any."""
        path = folder / _QUEUES_FILE
        if path.exists():
            self._queues = load_queues(path)

    def save_state(self, folder: Path) -> None:
        """Save the queues, if this run used or loaded any."""
        if self._queues is None:
            return
        folder.mkdir(parents=True, exist_ok=True)
        save_queues(self._queues.values(), folder / _QUEUES_FILE)

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
                "mq_create": (1, self.mq_create),
                "mq_put": (2, self.mq_put),
                "mq_get": (1, self.mq_get),
                "mq_publish": (2, self.mq_publish),
                "mq_subscribe": (1, self.mq_subscribe),
                "mq_receive": (1, self.mq_receive),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the mq-put, mq-get and mqnet shell commands."""

        def _mq_put_cmd(args: list[str]) -> str:
            """Put a message on a named queue."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: mq-put <queue> <message>"
            name = args[0]
            message = " ".join(args[1:])
            self._put(name, message)
            return f"Queued on '{name}': {message}"

        def _mq_get_cmd(args: list[str]) -> str:
            """Get the next message from a named queue."""
            if not args:
                return "Usage: mq-get <queue>"
            name = args[0]
            if name not in self._get_queues():
                return f"Queue '{name}' not found"
            body = self._take(name)
            return "Queue is empty" if body is None else body

        return [
            ShellCommand(
                name="mqnet",
                handler=_mqnet_cmd,
                help_text="Run a networked PyMQ broker with crashing workers",
            ),
            ShellCommand(name="mq-put", handler=_mq_put_cmd, help_text="Put message on a queue"),
            ShellCommand(name="mq-get", handler=_mq_get_cmd, help_text="Get message from a queue"),
        ]
