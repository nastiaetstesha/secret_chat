import asyncio
import async_timeout
import socket
import contextlib
import json
import os
import logging
import gui

from utils import RECONNECT_DELAY_START, RECONNECT_DELAY_MAX
from minechat_api import authorise as mc_authorise, submit_message as mc_submit
from core.exceptions import InvalidToken
from core.watchdog import WD


logger = logging.getLogger("sender")


HEARTBEAT_IDLE_S = 5.0  # если нет сообщений столько секунд — шлём пинг
PING_ACK_TIMEOUT_S = 2.0


def _read_token(token_file: str) -> str:
    path = os.path.expanduser(token_file)
    if not os.path.exists(path):
        raise InvalidToken("Токен не найден. Сначала зарегистрируйтесь (register-minechat-user.py).")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("account_hash")
    except Exception as e:
        raise InvalidToken(f"Не удалось прочитать токен: {e}")


async def _readline_text(reader: asyncio.StreamReader) -> str:
    data = await reader.readline()
    return data.decode("utf-8", errors="replace").rstrip("\n") if data else ""


async def send_msgs(host, port, sending_queue, token_file, status_queue=None, watchdog_queue=None):
    """
    ОДНА сессия «отправителя»: авторизуется, затем либо отправляет пользовательские
    сообщения, либо регулярно шлёт пустой пинг и ждёт ПРОМПТ от сервера.
    На сетевых сбоях/таймаутах поднимает ConnectionError.
    """
    token = _read_token(token_file)
    reader = writer = None
    try:
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.INITIATED)

        reader, writer = await asyncio.open_connection(host, port)
        ok = await mc_authorise(reader, writer, token)
        if not ok:
            if status_queue:
                await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
            raise InvalidToken("Неизвестный токен. Проверьте его или зарегистрируйте заново.")

        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.ESTABLISHED)
        if watchdog_queue:
            await watchdog_queue.put(WD.SEND_OK)

        try:
            async with async_timeout.timeout(PING_ACK_TIMEOUT_S):
                _ = await _readline_text(reader)
        except asyncio.TimeoutError:
            raise ConnectionError("no initial prompt after auth")

        while True:
            try:
                async with async_timeout.timeout(HEARTBEAT_IDLE_S) as cm:
                    text = await sending_queue.get()
            except asyncio.TimeoutError:
                await mc_submit(writer, "")
                if watchdog_queue:
                    await watchdog_queue.put(WD.MSG_SENT)

                try:
                    async with async_timeout.timeout(PING_ACK_TIMEOUT_S):
                        _ = await _readline_text(reader)
                    if watchdog_queue:
                        await watchdog_queue.put(WD.CHAT_RX)
                except asyncio.TimeoutError:
                    raise ConnectionError("ping ack timeout")
                continue

            text = (text or "").strip()
            if not text:
                continue

            await mc_submit(writer, text)
            if watchdog_queue:
                await watchdog_queue.put(WD.MSG_SENT)

            try:
                async with async_timeout.timeout(PING_ACK_TIMEOUT_S):
                    _ = await _readline_text(reader)
                if watchdog_queue:
                    await watchdog_queue.put(WD.CHAT_RX)
            except asyncio.TimeoutError:
                raise ConnectionError("no prompt after message")

    except asyncio.CancelledError:
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
        raise

    except InvalidToken:
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
        raise

    except (socket.gaierror, OSError) as e:
        logger.debug("sender OS error: %s", e)
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
        raise ConnectionError(str(e))
    
    except Exception as e:
        logger.debug("sender error: %s", e)
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
        raise ConnectionError(str(e))
    
    finally:
        if writer:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()