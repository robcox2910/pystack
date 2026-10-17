"""Tests that the webdemo tour hangs up every connection it opens."""

import pytest
from pynet.streams import StreamReader, StreamWriter, open_connection

from pystack.plugins import _webdemo

TOUR_CONNECTIONS = 5


class TestWebdemoHangsUp:
    """Verify the tour's tiny HTTP client closes its sockets."""

    def test_every_client_writer_is_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every connection the tour opens should be closed when it finishes."""
        writers: list[StreamWriter] = []

        async def recording_open(host: str, port: int) -> tuple[StreamReader, StreamWriter]:
            """Open a real connection and remember its writer."""
            reader, writer = await open_connection(host, port)
            writers.append(writer)
            return reader, writer

        monkeypatch.setattr(_webdemo, "open_connection", recording_open)
        output = _webdemo.webdemo()
        assert "event: tick 3" in output
        assert len(writers) == TOUR_CONNECTIONS
        assert all(writer.is_closing() for writer in writers)
