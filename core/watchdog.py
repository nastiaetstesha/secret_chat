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
    READ_OK = "Read connection established"
    SEND_OK = "Send connection established"

    def __str__(self) -> str:
        return str(self.value)


async def watch_for_connection(queue: asyncio.Queue, timeout_s: float = 1.0, alarm_after: int = 1):
    """
    Пишет событие при любой активности. Если подряд произошло `alarm_after`
    таймаутов ожидания события длительностью `timeout_s`, логирует таймаут
    и поднимает ConnectionError, чтобы перезапустить соединение.
    """
    misses = 0
    while True:
        try:
            async with async_timeout.timeout(timeout_s) as cm:
                event = await queue.get()
            misses = 0
            ts = int(time.time())
            msg = event.value if isinstance(event, WD) else str(event)
            watchdog_logger.info(f"[{ts}] Connection is alive. Source: {msg}")
        except asyncio.CancelledError:
            raise
        
        except asyncio.TimeoutError:
            if cm.expired:
                misses += 1
                ts = int(time.time())
                watchdog_logger.info(f"[{ts}] {int(timeout_s)}s timeout is elapsed")
                if misses >= alarm_after:
                    raise ConnectionError("watchdog timeout")
            else:
                raise
