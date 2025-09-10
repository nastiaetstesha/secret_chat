import asyncio
import contextlib
import logging
import os
import datetime as dt

import aiofiles

import gui

from utils import (
    build_parser,
    setup_logging,
    expand_path_and_mkdirs,
    DEFAULT_HOST,
    DEFAULT_LISTEN_PORT,
    DEFAULT_HISTORY,
    DEFAULT_SEND_PORT,
    RECONNECT_DELAY_START,
    RECONNECT_DELAY_MAX,
)

logger = logging.getLogger("runner")


def parse_args():
    parser = build_parser(
        "Run minechat GUI with history persistence.",
        DEFAULT_HOST,
        DEFAULT_LISTEN_PORT,
    )
    parser.add_argument(
        "--history",
        default=os.getenv("MINECHAT_HISTORY", DEFAULT_HISTORY),
        help="Путь к файлу истории (ENV: MINECHAT_HISTORY)",
        )
    parser.add_argument(
        "--send-port",
        type=int,
        default=int(os.getenv("MINECHAT_SEND_PORT", DEFAULT_SEND_PORT)),
        help="Порт для отправки сообщений (ENV: MINECHAT_SEND_PORT)",
        )
    return parser.parse_args()


def _now_ts() -> str:
    """Отметка времени как в консольном клиенте: [DD.MM.YY HH:MM]."""
    return dt.datetime.now().strftime("[%d.%m.%y %H:%M]")


async def preload_history(filepath: str, messages_queue: asyncio.Queue):
    """Загружает историю из файла и отправляет строки в GUI-очередь."""
    path = os.path.expanduser(filepath)
    if not os.path.exists(path):
        return

    try:
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            async for line in f:
                await messages_queue.put(line.rstrip("\n"))
        logger.info("История загружена из %s", path)
    except Exception as e:
        logger.warning("Не удалось загрузить историю %s: %s", path, e)


async def save_messages(filepath: str, queue: asyncio.Queue):
    """
    Асинхронно пишет новые сообщения в файл истории.
    Ожидает строки в очереди; каждую строку дописывает с таймстемпом.
    """
    path = expand_path_and_mkdirs(filepath)
    try:
        async with aiofiles.open(path, mode="a", encoding="utf-8") as f:
            while True:
                msg = await queue.get()
                stamped = f"{_now_ts()} {msg.rstrip()}"
                await f.write(stamped + "\n")
                await f.flush()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("Ошибка записи истории в %s: %s", path, e)


async def read_msgs(host: str, port: int, gui_queue: asyncio.Queue, save_queue: asyncio.Queue,
                    status_queue: asyncio.Queue | None = None):
    """
    Подключается к серверу и непрерывно читает чат.
    Каждую строку отправляет в GUI и в очередь сохранения.
    Переподключается с экспоненциальной паузой.
    """
    delay = RECONNECT_DELAY_START

    while True:
        reader = writer = None
        try:
            if status_queue:
                await status_queue.put(gui.ReadConnectionStateChanged.INITIATED)

            reader, writer = await asyncio.open_connection(host, port)
            logger.info("Подключились к %s:%s", host, port)
            if status_queue:
                await status_queue.put(gui.ReadConnectionStateChanged.ESTABLISHED)

            delay = RECONNECT_DELAY_START

            while True:
                line = await reader.readline()
                if not line:
                    logger.info("Сервер закрыл соединение")
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\n")

                await gui_queue.put(text)
                await save_queue.put(text)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Ошибка чтения: %s", e)
        finally:
            if status_queue:
                await status_queue.put(gui.ReadConnectionStateChanged.CLOSED)
            if writer:
                with contextlib.suppress(Exception):
                    writer.close()
                    await writer.wait_closed()

        logger.info("Повторное подключение через %s с", delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, RECONNECT_DELAY_MAX)


async def send_msgs(host: str, port: int, queue: asyncio.Queue,
                    status_queue: asyncio.Queue | None = None):
    """
    Пока что «заглушка отправки»: читает пользовательский ввод из очереди
    и печатает в терминал. Сеть не трогаем.
    """

    if status_queue:
        await status_queue.put(gui.SendingConnectionStateChanged.INITIATED)
        await status_queue.put(gui.SendingConnectionStateChanged.ESTABLISHED)

    try:
        while True:
            text = await queue.get()
            text = (text or "").strip()
            if not text:
                continue
            print(f"Пользователь написал: {text}")
            # позже здесь будет отправка в сокет и обработка протокола
    except asyncio.CancelledError:
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
        raise

async def main():
    args = parse_args()
    setup_logging(args.log_level)

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    save_queue = asyncio.Queue()

    history_path = expand_path_and_mkdirs(args.history)

    await preload_history(history_path, messages_queue)

    gui_task = asyncio.create_task(gui.draw(messages_queue, sending_queue, status_updates_queue))
    reader_task = asyncio.create_task(read_msgs(args.host, args.port, messages_queue, save_queue, status_updates_queue))
    saver_task = asyncio.create_task(save_messages(history_path, save_queue))
    sender_task = asyncio.create_task(send_msgs(args.host, args.send_port, sending_queue, status_updates_queue))

    try:
        await asyncio.gather(gui_task, reader_task, saver_task, sender_task)
    except gui.TkAppClosed:
        for t in (reader_task, saver_task, sender_task):
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(reader_task, saver_task, sender_task)


if __name__ == "__main__":
    asyncio.run(main())
