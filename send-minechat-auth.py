import asyncio
import json
import os
import sys
import argparse
import contextlib
import logging
from utils import (
    build_parser,
    setup_logging,
    expand_path_and_mkdirs,
    DEFAULT_HOST,
    DEFAULT_SEND_PORT,
    DEFAULT_TOKEN_FILE,
)

logger = logging.getLogger("sender")

# DEFAULT_HOST = "minechat.dvmn.org"
# DEFAULT_PORT = 5050
# DEFAULT_TOKEN_FILE = "minechat_token.json"


async def _readline_logged(reader: asyncio.StreamReader) -> str:
    """Читает строку и логирует её на DEBUG."""
    data = await reader.readline()
    text = data.decode("utf-8", errors="replace")
    if text:
        logger.debug(text.rstrip("\n"))
    return text


def parse_args():
    parser = build_parser(
        "Send messages to minechat with token auth.",
        DEFAULT_HOST,
        DEFAULT_SEND_PORT,
        )
    # parser.add_argument(
    #     "--nickname",
    #     default="anonymous",
    #     help="Префикс ника при регистрации (к нему сервер может добавить прилагательное).",
    # )
    parser.add_argument(
        "--token-file",
        default=os.getenv("MINECHAT_TOKEN_FILE", DEFAULT_TOKEN_FILE),
        )
    # parser.add_argument(
    #     "--force",
    #     action="store_true",
    #     help="Перезаписать существующий файл токена.",
    # )
    parser.add_argument(
        "--message",
        "-m",
        help="Message to send (empty line ends message)."
        )
    return parser.parse_args()


async def register_new_account(reader, writer, token_file):
    writer.write(b"\n")
    await writer.drain()
    logger.debug("\\n  (sent)")

    await reader.readline()
    nickname = "PythonUser"
    writer.write(f"{nickname}\n".encode())
    await writer.drain()
    logger.debug(f"{nickname}  (sent)")

    token_line = await reader.readline()
    data = json.loads(token_line.decode())
    redacted = {**data, "account_hash": data.get("account_hash", "")[:6] + "…redacted"}
    logger.info(f"Получен новый токен: {redacted}")
    token_file = expand_path_and_mkdirs(token_file)

    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data["account_hash"]


async def send_message(host, port, message, token_file):
    try:
        reader, writer = await asyncio.open_connection(host, port)
        logger.info(f"Подключились к {host}:{port}")

        await _readline_logged(reader)
        token_path = os.path.expanduser(token_file)
        logger.info(f"Ищем токен в: {token_path}")

        token = None
        if os.path.exists(token_path):
            with open(token_path, encoding="utf-8") as f:
                data = json.load(f)
                token = data.get("account_hash")

        if token:
            logger.info("Авторизуемся по токену ")
            writer.write(f"{token}\n".encode())
            await writer.drain()
            response_line = await reader.readline()
            response_text = response_line.decode().strip()
            try:
                response_json = json.loads(response_text)
            except json.JSONDecodeError:
                response_json = None

            if response_json is None:
                print("Неизвестный токен. Проверьте его или зарегистрируйте заново.")
                logger.error("Сервер отверг токен.")
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()
                return
        else:
            logger.info("Регистрируем новый аккаунт…")
            token = await register_new_account(reader, writer, token_path)

        while True:
            line = await reader.readline()
            if not line or line.decode().startswith("Welcome"):
                break

        text = message.rstrip("\n") + "\n\n"
        writer.write(text.encode())
        await writer.drain()
        logger.debug("(your message)  (sent)")
        logger.info("Сообщение отправлено!")

        # writer.close()
        # with contextlib.suppress(Exception):
        #     await writer.wait_closed()
        # logger.info("Соединение закрыто")
    finally:
        if writer is not None:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()
            logger.info("Соединение закрыто")


async def amain():
    args = parse_args()
    setup_logging(args.log_level)
    # logging.getLogger().setLevel(args.log_level)

    if not args.message:
        print("Нужно указать сообщение через --message")
        return
    await send_message(args.host, args.port, args.message, args.token_file)


if __name__ == "__main__":
    asyncio.run(amain())
