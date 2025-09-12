import anyio
import asyncio
import anyio
import logging

from core.reader import read_msgs
from core.sender import send_msgs
from core.watchdog import watch_for_connection


logger = logging.getLogger("conn")


async def handle_connection(
    host: str,
    listen_port: int,
    send_port: int,
    token_file: str,
    gui_queue: asyncio.Queue,
    save_queue: asyncio.Queue,
    sending_queue: asyncio.Queue,
    status_queue: asyncio.Queue,
    watchdog_queue: asyncio.Queue,
    watchdog_timeout: float = 1.0,
    watchdog_alarm_after: int = 1,
    reconnect_delay: float = 1.0,
):
    """
    Запускает read_msgs, send_msgs и watch_for_connection в одной TaskGroup.
    Когда watchdog кидает ConnectionError — плавно отменяет задачи и переподключается.
    """
    while True:
        try:
            try:
                async with anyio.create_task_group() as tg:
                    tg.start_soon(
                        read_msgs, host, listen_port,
                        gui_queue, save_queue,
                        status_queue, watchdog_queue,
                    )
                    tg.start_soon(
                        send_msgs, host, send_port,
                        sending_queue, token_file,
                        status_queue, watchdog_queue,
                    )
                    tg.start_soon(
                        watch_for_connection, watchdog_queue,
                        watchdog_timeout, watchdog_alarm_after,
                    )

            except* ConnectionError as eg:
                first = eg.exceptions[0] if eg.exceptions else None
                logger.info(
                    "watchdog/conn error → переподключение%s. Ждём %.1fs…",
                    f" ({first})" if first else "",
                    reconnect_delay,
                )
                await asyncio.sleep(reconnect_delay)

        except anyio.get_cancelled_exc_class():
            raise
