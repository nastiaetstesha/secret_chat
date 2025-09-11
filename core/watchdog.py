import asyncio
import logging
import time
from enum import Enum


watchdog_logger = logging.getLogger("watchdog")


class WD(str, Enum):
    PROMPT = "Prompt before auth"
    AUTH_OK = "Authorization done"
    CHAT_RX = "New message in chat"
    MSG_SENT = "Message sent"

    def __str__(self) -> str:
        return str(self.value)


async def watch_for_connection(queue: asyncio.Queue):
    """
    Одна корутина-писатель: печатает все события живости соединения.
    Другие корутины просто кладут в queue значения WD.* (или строки).
    """
    while True:
        event = await queue.get()
        ts = int(time.time())
        # WD -> берем .value, иначе просто str(event)
        msg = event.value if isinstance(event, WD) else str(event)
        watchdog_logger.info(f"[{ts}] Connection is alive. {msg}")
