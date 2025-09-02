import asyncio
import json
import os
import logging
import contextlib

from utils import (
    build_parser,
    setup_logging,
    DEFAULT_HOST,
    DEFAULT_SEND_PORT,
    expand_path_and_mkdirs,
)
from minechat_api import register as mc_register


logger = logging.getLogger("registrar")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TOKEN_PATH = os.path.join(PROJECT_DIR, "minechat_token.json")


def parse_args():
    parser = build_parser(
        "Register a new minechat user and save token to file.",
        DEFAULT_HOST,
        DEFAULT_SEND_PORT,
    )
    parser.add_argument(
        "--nickname",
        default="anonymous",
        help="Префикс ника при регистрации (к нему сервер может добавить прилагательное).",
    )
    parser.add_argument(
        "--token-file",
        default=os.getenv("MINECHAT_TOKEN_FILE", DEFAULT_TOKEN_PATH),
        help="Куда сохранить токен (по умолчанию в директорию проекта).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Перезаписать существующий файл токена.",
    )
    return parser.parse_args()


# async def register_and_save(host: str, port: int, nickname_prefix: str, token_file: str):
#     reader = writer = None
#     try:
#         logger.info(f"Подключаемся к {host}:{port}")
#         reader, writer = await asyncio.open_connection(host, port)

#         greet = await reader.readline()
#         logger.debug(greet.decode(errors="replace").rstrip("\n"))

#         writer.write(b"\n")
#         await writer.drain()
#         logger.debug("\\n  (sent)")

#         req_nick = await reader.readline()
#         logger.debug(req_nick.decode(errors="replace").rstrip("\n"))

#         nickname = f"{nickname_prefix}"
#         writer.write(f"{nickname}\n".encode("utf-8"))
#         await writer.drain()
#         logger.debug(f"{nickname}  (sent)")

#         token_line = await reader.readline()
#         token_text = token_line.decode("utf-8", errors="replace").strip()
#         logger.debug(token_text)

#         data = json.loads(token_text)
#         print(json.dumps(data, ensure_ascii=False, indent=4))

#         token_path = expand_path_and_mkdirs(token_file)
#         with open(token_path, "w", encoding="utf-8") as f:
#             json.dump(data, f, ensure_ascii=False)
#         logger.info(f"Токен сохранён: {token_path}")

#     finally:
#         if writer is not None:
#             with contextlib.suppress(Exception):
#                 writer.close()
#                 await writer.wait_closed()
#             logger.info("Соединение закрыто")


async def amain():
    args = parse_args()
    setup_logging(args.log_level)

    token_path = os.path.expanduser(args.token_file)
    if os.path.exists(token_path) and not args.force:
        logger.warning(f"Файл уже существует: {token_path}. Используйте --force для перезаписи.")
        print(token_path)
        return

    reader = writer = None
    try:
        reader, writer = await asyncio.open_connection(args.host, args.port)
        token_data = await mc_register(reader, writer, args.nickname)
        print(json.dumps(token_data, ensure_ascii=False, indent=4))

        token_path = expand_path_and_mkdirs(args.token_file)

        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(token_data, f, ensure_ascii=False)
        logger.info(f"Токен сохранён: {token_path}")

    finally:
        if writer:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(amain())
