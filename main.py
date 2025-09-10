import asyncio
import contextlib
import logging

import gui
from utils import (
    build_parser,
    setup_logging,
    DEFAULT_HOST,
    DEFAULT_LISTEN_PORT,
    RECONNECT_DELAY_START,
    RECONNECT_DELAY_MAX,
)

logger = logging.getLogger("runner")


def parse_args():
    return build_parser(
        "Run minechat GUI that listens chat messages.",
        DEFAULT_HOST,
        DEFAULT_LISTEN_PORT,
    ).parse_args()


async def read_msgs(host: str, port: int, queue: asyncio.Queue):
    """
    Подключается к серверу и непрерывно читает чат.
    Каждую полученную строку помещает в messages_queue.
    Умеет переподключаться с экспоненциальной паузой.
    """
    delay = RECONNECT_DELAY_START

    while True:
        reader = writer = None
        try:
            reader, writer = await asyncio.open_connection(host, port)
            logger.info("Подключились к %s:%s", host, port)
            delay = RECONNECT_DELAY_START

            while True:
                line = await reader.readline()
                if not line:
                    logger.info("Сервер закрыл соединение")
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                await queue.put(text)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Ошибка чтения: %s", e)
        finally:
            if writer:
                with contextlib.suppress(Exception):
                    writer.close()
                    await writer.wait_closed()

        logger.info("Повторное подключение через %s с", delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, RECONNECT_DELAY_MAX)


async def main():
    args = parse_args()
    setup_logging(args.log_level)

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()

    await messages_queue.put("GUI: подключаюсь к чату…")

    gui_task = asyncio.create_task(
        gui.draw(messages_queue, sending_queue, status_updates_queue)
    )
    reader_task = asyncio.create_task(
        read_msgs(args.host, args.port, messages_queue)
    )

    try:
        await asyncio.gather(gui_task, reader_task)
    except gui.TkAppClosed:
        reader_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reader_task


if __name__ == "__main__":
    asyncio.run(main())
