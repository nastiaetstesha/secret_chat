import asyncio
import logging
import time
from enum import Enum
import async_timeout

watchdog_logger = logging.getLogger("watchdog")


class WD(str, Enum):
    PROMPT = "Prompt before auth"
    AUTH_OK = "Authorization done"
    CHAT_RX = "New message in chat"
    MSG_SENT = "Message sent"

    def __str__(self) -> str:
        return str(self.value)


async def watch_for_connection(queue: asyncio.Queue, timeout_s: float = 1.0):
    """
    Печатает:
      - при событии: "[ts] Connection is alive. Source: <текст>"
      - при простое дольше timeout_s: "[ts] 1s timeout is elapsed"
    """
    while True:
        try:
            async with async_timeout.timeout(timeout_s) as cm:
                event = await queue.get()
            ts = int(time.time())
            msg = event.value if isinstance(event, WD) else str(event)
            watchdog_logger.info(f"[{ts}] Connection is alive. Source: {msg}")
        except asyncio.TimeoutError:

            if cm.expired:
                ts = int(time.time())
                watchdog_logger.info(f"[{ts}] {int(timeout_s)}s timeout is elapsed")
            else:
                raise
