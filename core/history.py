import os
import datetime as dt
import aiofiles
from utils import expand_path_and_mkdirs


def _now_ts() -> str:
    return dt.datetime.now().strftime("[%d.%m.%y %H:%M]")


async def preload_history(filepath: str, gui_queue):
    """Читает файл построчно и кладёт строки в очередь GUI."""
    path = os.path.expanduser(filepath)
    if not os.path.exists(path):
        return
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        async for line in f:
            await gui_queue.put(line.rstrip("\n"))


async def save_messages(filepath: str, save_queue):
    """Берёт строки из очереди и дописывает в историю с таймстемпом."""
    path = expand_path_and_mkdirs(filepath)
    async with aiofiles.open(path, "a", encoding="utf-8") as f:
        while True:
            msg = await save_queue.get()
            stamped = f"{_now_ts()} {msg.rstrip()}"
            await f.write(stamped + "\n")
            await f.flush()
