import os
import argparse
import logging

DEFAULT_HOST = "minechat.dvmn.org"
DEFAULT_LISTEN_PORT = 5000
DEFAULT_SEND_PORT = 5050
DEFAULT_HISTORY = "chat_history.txt"
DEFAULT_TOKEN_FILE = "minechat_token.json"
RECONNECT_DELAY_START = 2
RECONNECT_DELAY_MAX = 60


def setup_logging(level: str = "DEBUG"):
    logging.basicConfig(
        level=getattr(logging, level, logging.DEBUG),
        format="%(levelname)s:%(name)s:%(message)s",
    )


def expand_path_and_mkdirs(path: str) -> str:
    """Раскрывает ~ и создаёт родительскую папку, если её нет."""
    full = os.path.expanduser(path)
    parent = os.path.dirname(full)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return full


try:
    import configargparse
    HAS_CAP = True
except ImportError:
    HAS_CAP = False


def build_parser(description: str, default_host: str, default_port: int):

    if HAS_CAP:
        parser = configargparse.ArgumentParser(
            description=description,
            default_config_files=[os.path.expanduser("~/.minechat.conf"), "./minechat.conf"],
            formatter_class=configargparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add(
            "-c", "--config", is_config_file=True, help="Путь к конфиг-файлу."
        )

        parser.add(
            "--host",
            env_var="MINECHAT_HOST",
            default=default_host,
            help="Адрес сервера (ENV: MINECHAT_HOST)"
        )
        parser.add(
            "--port",
            env_var="MINECHAT_PORT",
            type=int,
            default=default_port,
            help="Порт сервера (ENV: MINECHAT_PORT)"
        )
        parser.add(
            "--log-level",
            env_var="MINECHAT_LOG_LEVEL",
            default="DEBUG",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Уровень логирования (ENV: MINECHAT_LOG_LEVEL)"
        )
    else:
        parser = argparse.ArgumentParser(
            description=description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument(
            "--host",
            default=os.getenv("MINECHAT_HOST", default_host),
            help="Адрес сервера (ENV: MINECHAT_HOST)"
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("MINECHAT_PORT", default_port)),
            help="Порт сервера (ENV: MINECHAT_PORT)"
        )
        parser.add_argument(
            "--log-level",
            default=os.getenv("MINECHAT_LOG_LEVEL", "DEBUG"),
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Уровень логирования (ENV: MINECHAT_LOG_LEVEL)"
        )
    return parser
