import logging
from .auth import get_client
from schwab.streaming import StreamClient

logger = logging.getLogger(__name__)

class SchwabStreamer:
    """
    Wrapper for Schwab WebSocket streaming.
    Phase 2: Ross Cameron real-time screener.
    """
    def __init__(self):
        self.client = get_client()
        self.stream_client = StreamClient(self.client)

    async def subscribe_level1_equities(self, symbols, fields):
        """
        Subscribe to Level 1 quotes.
        """
        await self.stream_client.level1_equity_subs(symbols, fields=fields)

    async def start(self, handler):
        """
        Start the stream and pass messages to handler.
        """
        self.stream_client.add_level1_equity_handler(handler)
        await self.stream_client.run()
