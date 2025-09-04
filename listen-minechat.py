import asyncio
import contextlib
import datetime as dt
import os
import signal
from typing import Optional

import aiofiles
import logging
from utils import (
    build_parser,
    setup_logging,
    DEFAULT_HOST,
    DEFAULT_LISTEN_PORT,
    DEFAULT_HISTORY,
    RECONNECT_DELAY_START,
    RECONNECT_DELAY_MAX,
)


logger = logging.getLogger("listener")


def _expand_history_path(path: str) -> str:
    path = os.path.expanduser(path)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return path


def _now_ts() -> str:
    """Вернёт отметку времени в формате [DD.MM.YY HH:MM]."""
    return dt.datetime.now().strftime("[%d.%m.%y %H:%M]")


async def log_line(line: str, history_path: str):
    """Пишет строку в stdout и в файл (append) с таймстемпом."""
    stamped = f"{_now_ts()} {line.rstrip()}"
    print(stamped)
    async with aiofiles.open(history_path, mode="a", encoding="utf-8") as f:
        await f.write(stamped + "\n")


async def read_chat_once(host: str, port: int, history_path: str):
    """Один сеанс: подключиться, читать до закрытия/ошибки."""
    reader, writer = await asyncio.open_connection(host, port)
    logger.info(f"Подключились к {host}:{port}")
    await log_line("Установлено соединение", history_path)

    try:
        while True:
            line = await reader.readline()
            if not line:
                await log_line("Соединение закрыто сервером", history_path)
                logger.info("Сервер закрыл соединение")
                break
            text = line.decode("utf-8", errors="replace").rstrip("\n")
            logger.debug(text)
            await log_line(text, history_path)
    finally:
        writer.close()
        with contextlib.suppress(
            asyncio.CancelledError,
            ConnectionResetError,
            BrokenPipeError,
            OSError,
        ):
            await writer.wait_closed()
            logger.info("Сокет закрыт")


async def read_chat_forever(host: str, port: int, history_path: str):
    """Главный цикл: читает чат и переподключается при сбоях."""
    delay = RECONNECT_DELAY_START
    while True:
        try:
            await read_chat_once(host, port, history_path)
            await log_line(f"Повторное подключение через {delay}с…", history_path)
            logger.info(f"Повторное подключение через {delay}с…")
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_DELAY_MAX)
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as e:
            await log_line(f"Ошибка соединения: {type(e).__name__}: {e}", history_path)
            logger.exception("Ошибка соединения")
            await log_line(f"Повторная попытка через {delay}с…", history_path)
            logger.info(f"Повторная попытка через {delay}с…")
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_DELAY_MAX)


def parse_args():
    parser = build_parser(
        "Listen minechat and save history to file.",
        DEFAULT_HOST,
        DEFAULT_LISTEN_PORT,
    )
    parser.add_argument(
        "--history",
        default=os.getenv("MINECHAT_HISTORY", DEFAULT_HISTORY),
    )
    return parser.parse_args()
        

def _install_signal_handlers(loop: asyncio.AbstractEventLoop):
    """Аккуратно завершаем по Ctrl+C (где поддерживается)."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, loop.stop)


async def amain():
    args = parse_args()
    setup_logging(args.log_level)

    host: str = args.host
    port: int = args.port
    history: str = _expand_history_path(args.history)

    await log_line("Скрипт запущен. Наблюдаю за чатом…", history)
    logger.info("Запущен режим наблюдения")
    await read_chat_forever(host, port, history)


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)

    try:
        loop.run_until_complete(amain())
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


if __name__ == "__main__":
    main()
