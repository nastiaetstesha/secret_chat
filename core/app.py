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


logger = logging.getLogger("app")


async def run_app():
    args = parse_args()
    setup_logging(args.log_level)

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_queue = asyncio.Queue()
    save_queue = asyncio.Queue()

    history_path = expand_path_and_mkdirs(args.history)
    await preload_history(history_path, messages_queue)

    gui_task = asyncio.create_task(gui.draw(messages_queue, sending_queue, status_queue))
    reader_task = asyncio.create_task(read_msgs(args.host, args.port, messages_queue, save_queue, status_queue))
    saver_task = asyncio.create_task(save_messages(history_path, save_queue))
    auth_task = asyncio.create_task(authorise_or_raise(args.host, args.send_port, args.token_file, status_queue))
    sender_task = asyncio.create_task(send_msgs(args.host, args.send_port, sending_queue, args.token_file, status_queue))

    try:
        await asyncio.gather(gui_task, reader_task, saver_task, auth_task, sender_task)
    except InvalidToken as e:
        try:
            messagebox.showerror("Ошибка авторизации", str(e))
        except Exception:
            print(f"Ошибка авторизации: {e}", flush=True)
        for t in (reader_task, saver_task, sender_task, gui_task):
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(reader_task, saver_task, sender_task, gui_task, return_exceptions=True)
    except gui.TkAppClosed:
        for t in (reader_task, saver_task, sender_task, auth_task):
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(reader_task, saver_task, sender_task, auth_task, return_exceptions=True)
