import asyncio
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

    gui_task = asyncio.create_task(gui.draw(messages_queue, sending_queue, status_queue))
    saver_task = asyncio.create_task(save_messages(history_path, save_queue))

    auth_task = asyncio.create_task(authorise_or_raise(args.host, args.send_port, args.token_file, status_queue, watchdog_queue))

    conn_task = asyncio.create_task(handle_connection(
        host=args.host,
        listen_port=args.port,
        send_port=args.send_port,
        token_file=args.token_file,
        gui_queue=messages_queue,
        save_queue=save_queue,
        sending_queue=sending_queue,
        status_queue=status_queue,
        watchdog_queue=watchdog_queue,
        watchdog_timeout=1.0,
        watchdog_alarm_after=10,
        reconnect_delay=1.0,
    ))

    try:
        await asyncio.gather(gui_task, saver_task, auth_task, conn_task)
    except InvalidToken as e:
        try:
            messagebox.showerror("Ошибка авторизации", str(e))
        except Exception:
            print(f"Ошибка авторизации: {e}", flush=True)
        for t in (conn_task, saver_task, gui_task, auth_task):
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(conn_task, saver_task, gui_task, auth_task, return_exceptions=True)
    except gui.TkAppClosed:
        for t in (conn_task, saver_task, auth_task):
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(conn_task, saver_task, auth_task, return_exceptions=True)