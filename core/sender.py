import asyncio
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


def _read_token(token_file: str) -> str:
    path = os.path.expanduser(token_file)
    if not os.path.exists(path):
        raise InvalidToken("Токен не найден. Сначала зарегистрируйтесь (register-minechat-user.py).")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("account_hash")
    except Exception as e:
        raise InvalidToken(f"Не удалось прочитать токен: {e}")


async def send_msgs(host, port, sending_queue, token_file, status_queue=None, watchdog_queue=None):
    """
    ОДНА сессия. Авторизация + отправка.
    На любой сетевой сбой бросает ConnectionError (для внешнего перезапуска).
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

        while True:
            text = (await sending_queue.get() or '').strip()
            if not text:
                continue
            await mc_submit(writer, text)
            if watchdog_queue:
                await watchdog_queue.put(WD.MSG_SENT)

    except asyncio.CancelledError:
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
        raise
    except InvalidToken:
        # фатально — пусть наружу
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
        raise
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

