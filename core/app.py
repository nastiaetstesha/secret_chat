import asyncio
import anyio
import contextlib
import logging
from tkinter import messagebox

import gui
from utils import setup_logging, expand_path_and_mkdirs
from core.config import parse_args
from core.history import preload_history, save_messages
from core.reader import read_msgs
from core.sender import send_msgs
from core.auth import authorise_or_raise
from core.exceptions import InvalidToken
from core.watchdog import watch_for_connection
from core.connection import handle_connection

logger = logging.getLogger("app")


async def run_app():
    args = parse_args()
    setup_logging(args.log_level)

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_queue = asyncio.Queue()
    save_queue = asyncio.Queue()
    watchdog_queue = asyncio.Queue()

    history_path = expand_path_and_mkdirs(args.history)
    await preload_history(history_path, messages_queue)

    wd_handler = logging.StreamHandler()
    wd_handler.setFormatter(logging.Formatter("%(message)s"))
    wlog = logging.getLogger("watchdog")
    wlog.propagate = False
    wlog.setLevel(logging.INFO)
    wlog.handlers = [wd_handler]

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(gui.draw, messages_queue, sending_queue, status_queue)

            tg.start_soon(save_messages, history_path, save_queue)

            tg.start_soon(authorise_or_raise, args.host, args.send_port, args.token_file,
                          status_queue, watchdog_queue)

            tg.start_soon(
                handle_connection, args.host,
                args.port,
                args.send_port,
                args.token_file,
                messages_queue,
                save_queue,
                sending_queue,
                status_queue,
                watchdog_queue,
                5.0,
                5,
                1.0,
            )
    except* gui.TkAppClosed:
        pass

    except* asyncio.CancelledError:
        pass

    except* InvalidToken as eg:
        try:
            msg = str(eg.exceptions[0]) if eg.exceptions else "Invalid token"
            messagebox.showerror("Ошибка авторизации", msg)
        finally:
            pass
