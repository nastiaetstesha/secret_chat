import asyncio
import time
import contextlib
import gui


async def generate_msgs(messages_queue: asyncio.Queue):
    """Каждую секунду добавляет тестовое сообщение с текущим Unix timestamp."""
    while True:
        ts = int(time.time())
        await messages_queue.put(f"Ping {ts}")
        await asyncio.sleep(1)


async def main():
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()

    await messages_queue.put('Иван: Привет всем в этом чатике!')

    gui_task = asyncio.create_task(gui.draw(messages_queue, sending_queue, status_updates_queue))
    gen_task = asyncio.create_task(generate_msgs(messages_queue))

    try:
        await asyncio.gather(gui_task, gen_task)
    except gui.TkAppClosed:
        gen_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await gen_task


if __name__ == "__main__":
    asyncio.run(main())
