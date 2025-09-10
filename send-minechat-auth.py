import asyncio
import json
import os
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
from minechat_api import authorise as mc_authorise, submit_message as mc_submit


logger = logging.getLogger("sender")


def parse_args():
    parser = build_parser(
        "Send messages to minechat with token auth.",
        DEFAULT_HOST,
        DEFAULT_SEND_PORT,
        )
    parser.add_argument(
        "--token-file",
        default=os.getenv("MINECHAT_TOKEN_FILE", DEFAULT_TOKEN_FILE),
        )
    parser.add_argument(
        "--message",
        "-m",
        required=True,
        help="Message to send (empty line ends message)."
        )
    
    return parser.parse_args()


async def amain():
    args = parse_args()
    setup_logging(args.log_level)

    token_path = os.path.expanduser(args.token_file)
    if not os.path.exists(token_path):
        print("Токен не найден. Сначала зарегистрируйтесь (register-minechat-user.py).")
        return

    with open(token_path, encoding="utf-8") as f:
        data = json.load(f)
        token = data.get("account_hash")

    reader = writer = None
    try:
        reader, writer = await asyncio.open_connection(args.host, args.port)
        ok = await mc_authorise(reader, writer, token)
        if not ok:
            print("Неизвестный токен. Проверьте его или зарегистрируйте заново.")
            return

        await mc_submit(writer, args.message)
        logger.info("Сообщение отправлено!")
    finally:
        if writer:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(amain())
