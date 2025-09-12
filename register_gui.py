import asyncio
import json
import os
import contextlib
import logging
from dataclasses import dataclass
from typing import Optional

import anyio
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

from utils import (
    DEFAULT_HOST,
    DEFAULT_SEND_PORT,
    DEFAULT_TOKEN_FILE,
    expand_path_and_mkdirs,
)
from minechat_api import register as mc_register


class TkAppClosed(Exception):
    """Поднимается, когда окно уничтожено (чтобы корректно остановить TaskGroup)."""
    pass


@dataclass
class RegisterRequest:
    host: str
    port: int
    nickname: str
    token_path: str


async def update_tk(root: tk.Misc, interval: float = 1 / 120):
    while True:
        try:
            root.update()
        except tk.TclError:
            raise TkAppClosed()
        await anyio.sleep(interval)


def build_gui():
    root = tk.Tk()
    root.title("Minechat — регистрация пользователя")

    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    row = 0

    tk.Label(frame, text="Сервер (host):").grid(row=row, column=0, sticky="w")
    host_var = tk.StringVar(value=DEFAULT_HOST)
    host_entry = tk.Entry(frame, textvariable=host_var, width=36)
    host_entry.grid(row=row, column=1, sticky="we", padx=(6, 0))
    row += 1

    tk.Label(frame, text="Порт отправки:").grid(row=row, column=0, sticky="w")
    port_var = tk.StringVar(value=str(DEFAULT_SEND_PORT))
    port_entry = tk.Entry(frame, textvariable=port_var, width=10)
    port_entry.grid(row=row, column=1, sticky="w", padx=(6, 0))
    row += 1

    tk.Label(frame, text="Ник:").grid(row=row, column=0, sticky="w")
    nick_var = tk.StringVar(value="")
    nick_entry = tk.Entry(frame, textvariable=nick_var, width=36)
    nick_entry.grid(row=row, column=1, sticky="we", padx=(6, 0))
    row += 1

    tk.Label(frame, text="Файл токена:").grid(row=row, column=0, sticky="w")
    token_var = tk.StringVar(value=os.path.expanduser(DEFAULT_TOKEN_FILE))
    token_entry = tk.Entry(frame, textvariable=token_var, width=36)
    token_entry.grid(row=row, column=1, sticky="we", padx=(6, 0))

    def browse_token():
        initial = os.path.dirname(token_var.get()) or os.getcwd()
        path = filedialog.asksaveasfilename(
            parent=root,
            title="Куда сохранить токен",
            initialdir=initial,
            initialfile=os.path.basename(token_var.get() or "minechat_token.json"),
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Любой файл", "*.*")],
        )
        if path:
            token_var.set(path)
    browse_btn = tk.Button(frame, text="Обзор…", command=browse_token)
    browse_btn.grid(row=row, column=2, sticky="w", padx=(6, 0))
    row += 1

    btns = tk.Frame(frame, pady=6)
    btns.grid(row=row, column=0, columnspan=3, sticky="we")
    register_btn = tk.Button(btns, text="Зарегистрироваться")
    quit_btn = tk.Button(btns, text="Выход", command=root.destroy)
    register_btn.pack(side="left")
    quit_btn.pack(side="right")
    row += 1

    log = ScrolledText(frame, height=10, wrap="word", state="disabled")
    log.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
    frame.grid_columnconfigure(1, weight=1)
    frame.grid_rowconfigure(row, weight=1)

    widgets = {
        "root": root,
        "host_var": host_var,
        "port_var": port_var,
        "nick_var": nick_var,
        "token_var": token_var,
        "register_btn": register_btn,
        "log": log,
    }
    return widgets


async def log_consumer(log_widget: ScrolledText, queue: asyncio.Queue):
    while True:
        line = await queue.get()
        try:
            log_widget["state"] = "normal"
            if log_widget.index("end-1c") != "1.0":
                log_widget.insert("end", "\n")
            log_widget.insert("end", line)
            log_widget.yview(tk.END)
            log_widget["state"] = "disabled"
        except tk.TclError:
            raise TkAppClosed()


def push_log(queue: asyncio.Queue, text: str):
    queue.put_nowait(text)


async def perform_registration(req: RegisterRequest, log_q: asyncio.Queue) -> dict:
    """
    Подключается к серверу отправки, выполняет регистрацию и возвращает token_data dict.
    """
    reader = writer = None
    push_log(log_q, f"Подключаюсь к {req.host}:{req.port}…")
    try:
        reader, writer = await asyncio.open_connection(req.host, req.port)

        # minechat_api.register выполнит протокол регистрации:
        #   - сервер просит hash → отправляем пустую строку
        #   - сервер просит nickname → отправляем ник
        #   - сервер шлёт JSON с {"nickname":..., "account_hash":...}
        token_data = await mc_register(reader, writer, req.nickname)

        nick = token_data.get("nickname") or req.nickname or "anonymous"
        push_log(log_q, f"Пользователь зарегистрирован: {nick}")
        return token_data

    except Exception as e:
        push_log(log_q, f"Ошибка регистрации: {type(e).__name__}: {e}")
        raise
    finally:
        if writer:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()


def save_token_file(path: str, data: dict, overwrite_ok: bool = False):
    full = expand_path_and_mkdirs(path)
    if os.path.exists(full) and not overwrite_ok:
        raise FileExistsError(full)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


async def register_controller(
    widgets: dict,
    cmd_queue: asyncio.Queue,
    log_q: asyncio.Queue,
):
    root: tk.Tk = widgets["root"]
    register_btn: tk.Button = widgets["register_btn"]

    while True:
        req: RegisterRequest = await cmd_queue.get()

        overwrite_ok = False
        if os.path.exists(os.path.expanduser(req.token_path)):
            try:
                overwrite_ok = messagebox.askyesno(
                    "Файл существует",
                    f"Файл уже существует:\n{req.token_path}\n\nПерезаписать?",
                    parent=root,
                )
            except tk.TclError:
                raise TkAppClosed()
            if not overwrite_ok:
                push_log(log_q, "Сохранение отменено пользователем.")
                with contextlib.suppress(tk.TclError):
                    register_btn["state"] = "normal"
                continue

        try:
            register_btn["state"] = "disabled"
        except tk.TclError:
            raise TkAppClosed()

        try:
            token_data = await perform_registration(req, log_q)

            save_token_file(req.token_path, token_data, overwrite_ok=overwrite_ok)
            push_log(log_q, f"Токен сохранён: {os.path.abspath(req.token_path)}")
            try:
                messagebox.showinfo("Готово", "Токен успешно сохранён.", parent=root)
            except tk.TclError:
                raise TkAppClosed()

        except Exception as e:
            push_log(log_q, f"Ошибка: {type(e).__name__}: {e}")
            with contextlib.suppress(tk.TclError):
                messagebox.showerror("Ошибка", str(e), parent=root)
        finally:
            with contextlib.suppress(tk.TclError):
                register_btn["state"] = "normal"


async def run_app():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    w = build_gui()
    root: tk.Tk = w["root"]

    cmd_queue: asyncio.Queue[RegisterRequest] = asyncio.Queue()
    log_queue: asyncio.Queue[str] = asyncio.Queue()

    def on_register():
        if w["register_btn"]["state"] == "disabled":
            return

        host = (w["host_var"].get() or "").strip() or DEFAULT_HOST
        try:
            port = int((w["port_var"].get() or "").strip() or DEFAULT_SEND_PORT)
        except ValueError:
            messagebox.showerror("Некорректный порт", "Введите номер порта (число).", parent=w["root"])
            return
        nickname = (w["nick_var"].get() or "").strip() or "anonymous"
        token_path = (w["token_var"].get() or "").strip() or DEFAULT_TOKEN_FILE

        w["register_btn"]["state"] = "disabled"
        req = RegisterRequest(host=host, port=port, nickname=nickname, token_path=token_path)
        cmd_queue.put_nowait(req)
        push_log(log_queue, f"Запрошена регистрация пользователя «{nickname}».")

    w["register_btn"]["command"] = on_register

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(update_tk, root)
            tg.start_soon(log_consumer, w["log"], log_queue)
            tg.start_soon(register_controller, w, cmd_queue, log_queue)
    except* TkAppClosed:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        pass
