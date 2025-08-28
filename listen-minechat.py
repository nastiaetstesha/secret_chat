import asyncio
import contextlib
import datetime as dt
import os
import signal
from typing import Optional

import aiofiles

DEFAULT_HOST = "minechat.dvmn.org"
DEFAULT_PORT = 5000
DEFAULT_HISTORY = "chat_history.txt"

RECONNECT_DELAY_START = 2
RECONNECT_DELAY_MAX = 60


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
    await log_line("Установлено соединение", history_path)

    try:
        while True:
            line = await reader.readline()
            if not line:
                await log_line("Соединение закрыто сервером", history_path)
                break
            text = line.decode("utf-8", errors="replace").rstrip("\n")
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


async def read_chat_forever(host: str, port: int, history_path: str):
    """Главный цикл: читает чат и переподключается при сбоях."""
    delay = RECONNECT_DELAY_START
    while True:
        try:
            await read_chat_once(host, port, history_path)
            await log_line(f"Повторное подключение через {delay}с…", history_path)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_DELAY_MAX)
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as e:
            await log_line(f"Ошибка соединения: {type(e).__name__}: {e}", history_path)
            await log_line(f"Повторная попытка через {delay}с…", history_path)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_DELAY_MAX)


def _parse_args():

    try:
        import configargparse as cap

        parser = cap.ArgumentParser(
            description="Listen minechat and save history to file.",
            default_config_files=[os.path.expanduser("~/.minechat.conf"), "./minechat.conf"],
            formatter_class=cap.ArgumentDefaultsHelpFormatter,
        )
        parser.add(
            "-c", "--config",
            is_config_file=True,
            help="Путь к конфиг-файлу (ini). Значения из него можно переопределять CLI/ENV."
        )
        parser.add(
            "--host",
            env_var="MINECHAT_HOST",
            default=DEFAULT_HOST,
            help="Адрес сервера чата (ENV: MINECHAT_HOST).",
        )
        parser.add(
            "--port",
            env_var="MINECHAT_PORT",
            type=int,
            default=DEFAULT_PORT,
            help="Порт сервера чата (ENV: MINECHAT_PORT).",
        )
        parser.add(
            "--history",
            env_var="MINECHAT_HISTORY",
            default=DEFAULT_HISTORY,
            help="Путь к файлу истории (ENV: MINECHAT_HISTORY). Поддерживает ~.",
        )
        return parser.parse_args()

    except ImportError:
        import argparse

        parser = argparse.ArgumentParser(
            description="Listen minechat and save history to file.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument(
            "--host",
            default=os.getenv("MINECHAT_HOST", DEFAULT_HOST),
            help="Адрес сервера чата (ENV: MINECHAT_HOST).",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("MINECHAT_PORT", DEFAULT_PORT)),
            help="Порт сервера чата (ENV: MINECHAT_PORT).",
        )
        parser.add_argument(
            "--history",
            default=os.getenv("MINECHAT_HISTORY", DEFAULT_HISTORY),
            help="Путь к файлу истории (ENV: MINECHAT_HISTORY). Поддерживает ~.",
        )
        return parser.parse_args()


def _install_signal_handlers(loop: asyncio.AbstractEventLoop):
    """Аккуратно завершаем по Ctrl+C (где поддерживается)."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, loop.stop)


async def amain():
    args = _parse_args()
    host: str = args.host
    port: int = args.port
    history: str = _expand_history_path(args.history)

    await log_line("Скрипт запущен. Наблюдаю за чатом…", history)
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
