# core/auth.py
import asyncio
import contextlib
import json
import os
import gui
from core.exceptions import InvalidToken


async def _readline_text(reader: asyncio.StreamReader) -> str:
    data = await reader.readline()
    if not data:
        return ""
    return data.decode("utf-8", errors="replace").rstrip("\n")


def _load_token(token_file: str) -> str:
    path = os.path.expanduser(token_file)
    if not os.path.exists(path):
        raise InvalidToken("Токен не найден. Сначала зарегистрируйтесь (register-minechat-user.py).")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("account_hash")
    except Exception as e:
        raise InvalidToken(f"Не удалось прочитать токен: {e}")


async def authorise_or_raise(host: str, port: int, token_file: str, status_queue=None) -> str:
    """Возвращает nickname при успехе, иначе InvalidToken."""
    token = _load_token(token_file)
    reader = writer = None
    try:
        if status_queue:
            await status_queue.put(gui.SendingConnectionStateChanged.INITIATED)

        reader, writer = await asyncio.open_connection(host, port)
        _ = await _readline_text(reader)            # приветствие
        writer.write(f"{token}\n".encode("utf-8"))  # токен
        await writer.drain()
        response = await _readline_text(reader)     # JSON или 'null'

        try:
            payload = json.loads(response) if response else None
        except json.JSONDecodeError:
            payload = None

        if not payload:
            if status_queue:
                await status_queue.put(gui.SendingConnectionStateChanged.CLOSED)
            raise InvalidToken("Неизвестный токен. Проверьте его или зарегистрируйте заново.")

        nickname = payload.get("nickname", "<unknown>")
        if status_queue:
            await status_queue.put(gui.NicknameReceived(nickname))
            await status_queue.put(gui.SendingConnectionStateChanged.ESTABLISHED)
        return nickname

    finally:
        if writer:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()
