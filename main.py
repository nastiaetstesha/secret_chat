# chat_saver.py
import asyncio
import datetime as dt
import signal
from contextlib import asynccontextmanager

import aiofiles


SERVER_HOST = "minechat.dvmn.org"
SERVER_PORT = 5000
HISTORY_FILE = "chat_history.txt"

# стартовая задержка на повторное подключение 
RECONNECT_DELAY_SEC = 2
RECONNECT_DELAY_MAX_SEC = 60


def ts_now() -> str:
    """Вернёт отметку времени в формате [DD.MM.YY HH:MM]."""
    return dt.datetime.now().strftime("[%d.%m.%y %H:%M]")


async def log_line(line: str):
    """Пишет строку и в файл (append), и в stdout - заменю потом на logging"""
    stamped = f"!! {ts_now()} {line.rstrip()}"
    print(stamped)
    async with aiofiles.open(HISTORY_FILE, mode="a", encoding="utf-8") as f:
        await f.write(stamped + "\n")


@asynccontextmanager
async def open_chat_connection(host: str, port: int):
    """Контекстный менеджер для подключения к чату."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        yield reader, writer
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


async def read_chat_once():
    """Один сеанс чтения, до разрыва соединения."""
    reader, writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)
    await log_line("Установлено соединение")
    try:
        while True:
            line = await reader.readline()
            if not line:
                await log_line("Соединение закрыто сервером")
                break
            await log_line(line.decode("utf-8", errors="replace").rstrip("\n"))
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


async def read_chat_forever():
    """Главный цикл: читает чат и переподключается при ошибках/разрывах."""
    delay = RECONNECT_DELAY_SEC
    while True:
        try:
            await read_chat_once()
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_DELAY_MAX_SEC)
            await log_line(f"Повторное подключение через {delay}с…")
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as e:
            await log_line(f"Ошибка соединения: {type(e).__name__}: {e}")
            await log_line(f"Повторная попытка через {delay}с…")
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_DELAY_MAX_SEC)


def install_signal_handlers(loop):
    """Красиво завершаем по Ctrl+C."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, loop.stop)
        except NotImplementedError:
            pass


async def amain():
    # отметим запуск
    await log_line("Скрипт запущен. Наблюдаю за чатом…")
    await read_chat_forever()


if __name__ == "__main__":
    import contextlib

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    install_signal_handlers(loop)
    try:
        loop.run_until_complete(amain())
    finally:
        # корректно закрываем все задачи
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        with contextlib.suppress(Exception):
            loop.run_until_complete(asyncio.gather(*pending))
        loop.close()
