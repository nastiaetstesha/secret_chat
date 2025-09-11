import asyncio
import contextlib
import logging
import gui
from utils import RECONNECT_DELAY_START, RECONNECT_DELAY_MAX
from core.watchdog import WD

logger = logging.getLogger("reader")


async def read_msgs(host, port, gui_queue, save_queue, status_queue=None, watchdog_queue=None):
    delay = RECONNECT_DELAY_START
    while True:
        reader = writer = None
        try:
            if status_queue:
                await status_queue.put(gui.ReadConnectionStateChanged.INITIATED)

            reader, writer = await asyncio.open_connection(host, port)

            if status_queue:
                await status_queue.put(gui.ReadConnectionStateChanged.ESTABLISHED)

            delay = RECONNECT_DELAY_START
            while True:
                line = await reader.readline()
                if not line:
                    break
                text = line.decode('utf-8', errors='replace').rstrip('\n')
                await gui_queue.put(text)
                await save_queue.put(text)
                if watchdog_queue:
                    await watchdog_queue.put(WD.CHAT_RX)

        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            if status_queue:
                await status_queue.put(gui.ReadConnectionStateChanged.CLOSED)
            if writer:
                with contextlib.suppress(Exception):
                    writer.close()
                    await writer.wait_closed()

        await asyncio.sleep(delay)
        delay = min(delay * 2, RECONNECT_DELAY_MAX)

