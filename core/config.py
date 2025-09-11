import os
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
