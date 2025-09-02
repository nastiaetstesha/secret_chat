import asyncio
import json
import logging

logger = logging.getLogger("minechat.api")


async def _readline_text(reader: asyncio.StreamReader) -> str:
    """Считывает строку (bytes) и возвращает str без завершающего \\n."""
    data = await reader.readline()
    if not data:
        return ""
    return data.decode("utf-8", errors="replace").rstrip("\n")


async def register(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, nickname: str) -> dict:
    """
    Регистрация нового пользователя.
    Протокол:
      - сервер просит hash
      - отправляем пустую строку => "режим регистрации"
      - сервер просит nickname
      - отправляем nickname
      - сервер возвращает JSON с токеном: {"nickname": ..., "account_hash": ...}
    Возвращает dict с токеном.
    """
    greet = await _readline_text(reader)
    logger.debug(greet)

    writer.write(b"\n")
    await writer.drain()
    logger.debug("\\n (sent)")

    prompt = await _readline_text(reader)
    logger.debug(prompt)

    writer.write(f"{nickname}\n".encode("utf-8"))
    await writer.drain()
    logger.debug("%s (sent)", nickname)

    token_line = await _readline_text(reader)
    logger.debug(token_line)
    token_data = json.loads(token_line)
    return token_data


async def authorise(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, token: str) -> bool:
    """
    Авторизация по токену.
    Протокол:
      - сервер просит hash
      - отправляем token + \\n
      - сервер возвращает JSON:
          * объект (валидный токен)
          * 'null' (битый токен) -> json.loads(...) == None
    Возвращает True при успехе, False при невалидном токене.
    """
    greet = await _readline_text(reader)
    logger.debug(greet)

    writer.write(f"{token}\n".encode("utf-8"))
    await writer.drain()
    logger.debug("<token> (sent)")

    response = await _readline_text(reader)
    logger.debug(response)

    try:
        payload = json.loads(response) if response else None
    except json.JSONDecodeError:
        payload = None

    return payload is not None


async def submit_message(writer: asyncio.StreamWriter, text: str) -> None:
    """
    Отправляет сообщение. По протоколу каждое сообщение заканчивается пустой строкой.
    """
    # тело + \n + \n
    body = text.rstrip("\n") + "\n\n"
    writer.write(body.encode("utf-8"))
    await writer.drain()
    logger.debug("(message sent)")
