import asyncio
import contextlib
import logging
import os
import datetime as dt
import json

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
    DEFAULT_TOKEN_FILE
)
from minechat_api import (
    authorise as mc_authorise,
    submit_message as mc_submit
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
    parser.add_argument(
        "--token-file",
        default=os.getenv("MINECHAT_TOKEN_FILE", DEFAULT_TOKEN_FILE),
        help="Путь к файлу токена (ENV: MINECHAT_TOKEN_FILE)",
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
                    token_file: str, status_queue: asyncio.Queue | None = None):
    """
    Реальная отправка: держим соединение на порту отправки,
    авторизуемся токеном и шлём каждую строку из очереди.
    Переподключаемся при сбоях с экспоненциальной задержкой.
    """
    token_path = os.path.expanduser(token_file)
    if not os.path.exists(token_path):
        print("Токен не найден. Сначала зарегистрируйтесь (register-minechat-user.py).")
        return
    try:
        with open(token_path, encoding="utf-8") as f:
            token = json.load(f).get("account_hash")
    except Exception as e:
        print(f"Не удалось прочитать токен из {token_path}: {e}")
        return

    delay = RECONNECT_DELAY_START
    while True:
        reader = writer = None
        try:
            if status_queue:
                await status_queue.put(gui.SendingConnectionStateChanged.INITIATED)

            reader, writer = await asyncio.open_connection(host, port)
            ok = await mc_authorise(reader, writer, token)
            if not ok:
                print("Неизвестный токен. Проверьте его или зарегистрируйте заново.")
                if status_queue:
                    await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
                return

            if status_queue:
                await status_queue.put(gui.SendingConnectionStateChanged.ESTABLISHED)
            delay = RECONNECT_DELAY_START

            while True:
                text = (await queue.get() or "").strip()
                if not text:
                    continue
                await mc_submit(writer, text)
                logger.info("Отправлено на сервер: %r", text)

        except asyncio.CancelledError:
            if status_queue:
                await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
            if writer:
                with contextlib.suppress(Exception):
                    writer.close()
                    await writer.wait_closed()
            raise
        except Exception as e:
            logger.exception("Ошибка отправки: %s", e)
        finally:
            if writer:
                with contextlib.suppress(Exception):
                    writer.close()
                    await writer.wait_closed()
            if status_queue:
                await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)

        await asyncio.sleep(delay)
        delay = min(delay * 2, RECONNECT_DELAY_MAX)


async def _readline_text(reader: asyncio.StreamReader) -> str:
    data = await reader.readline()
    if not data:
        return ""
    return data.decode("utf-8", errors="replace").rstrip("\n")


async def authorise_and_report(host: str, port: int, token_file: str,
                               status_queue: asyncio.Queue | None = None) -> bool:
    token_path = os.path.expanduser(token_file)
    if not os.path.exists(token_path):
        print("Токен не найден. Сначала зарегистрируйтесь (register-minechat-user.py).")
        return False

    try:
        with open(token_path, encoding="utf-8") as f:
            token = json.load(f).get("account_hash")
    except Exception as e:
        print(f"Не удалось прочитать токен из {token_path}: {e}")
        return False

    reader = writer = None
    try:
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.INITIATED)

        reader, writer = await asyncio.open_connection(host, port)
        # 1) сервер шлёт приветствие
        _ = await _readline_text(reader)
        # 2) отправляем токен
        writer.write(f"{token}\n".encode("utf-8"))
        await writer.drain()
        # 3) ответ — JSON-объект при успехе, 'null' при неверном токене
        response = await _readline_text(reader)

        try:
            payload = json.loads(response) if response else None
        except json.JSONDecodeError:
            payload = None

        if not payload:
            print("Неизвестный токен. Проверьте его или зарегистрируйте заново.")
            if status_queue:
                await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
            return False

        nickname = payload.get("nickname", "<unknown>")
        print(f"Выполнена авторизация. Пользователь {nickname}.")
        if status_queue:
            await status_queue.put(gui.NicknameReceived(nickname))
            await status_queue.put(gui.SendingConnectionStateChanged.ESTABLISHED)
        return True

    finally:
        if writer:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()


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
    sender_task = asyncio.create_task(send_msgs(args.host, args.send_port, sending_queue, args.token_file, status_updates_queue))
    auth_task = asyncio.create_task(authorise_and_report(args.host, args.send_port, args.token_file, status_updates_queue))

    try:
        await asyncio.gather(gui_task, reader_task, saver_task, sender_task, auth_task)
    except gui.TkAppClosed:
        for t in (reader_task, saver_task, sender_task, auth_task):
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(reader_task, saver_task, sender_task, auth_task)


if __name__ == "__main__":
    asyncio.run(main())
