import asyncio
import time
import json
import os
import contextlib
import logging

import gui
from utils import (
    build_parser,
    setup_logging,
    DEFAULT_HOST,
    DEFAULT_LISTEN_PORT,
    DEFAULT_SEND_PORT,
    DEFAULT_TOKEN_FILE,
    # HAS_CAP,
)

logger = logging.getLogger("runner")


def parse_args():
    parser = build_parser(
        "Run minechat GUI with configurable settings.",
        DEFAULT_HOST,
        DEFAULT_LISTEN_PORT,
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


async def generate_msgs(messages_queue: asyncio.Queue):
    """Каждую секунду добавляет тестовое сообщение с текущим Unix timestamp."""
    while True:
        await messages_queue.put(f"Ping {int(time.time())}")
        await asyncio.sleep(1)


async def main():
    args = parse_args()
    setup_logging(args.log_level)

    token = None
    token_path = os.path.expanduser(args.token_file)
    if os.path.exists(token_path):
        try:
            with open(token_path, encoding="utf-8") as f:
                token = json.load(f).get("account_hash")
        except Exception as e:
            logger.warning("Не удалось прочитать токен из %s: %s", token_path, e)

    logger.info(
        "Config: host=%s listen_port=%s send_port=%s token_file=%s token=%s",
        args.host,
        args.port,
        args.send_port,
        args.token_file,
        "present" if token else "absent",
    )

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()

    await messages_queue.put("Иван: Привет всем в этом чатике!")

    gui_task = asyncio.create_task(
        gui.draw(messages_queue, sending_queue, status_updates_queue)
    )
    gen_task = asyncio.create_task(generate_msgs(messages_queue))

    try:
        await asyncio.gather(gui_task, gen_task)
    except gui.TkAppClosed:
        gen_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await gen_task


if __name__ == "__main__":
    asyncio.run(main())
