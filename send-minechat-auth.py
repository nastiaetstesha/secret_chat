import asyncio
import json
import os
import sys
import argparse
import contextlib

DEFAULT_HOST = "minechat.dvmn.org"
DEFAULT_PORT = 5050
DEFAULT_TOKEN_FILE = "minechat_token.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Send messages to minechat with token auth."
        )
    parser.add_argument(
        "--host",
        default=os.getenv("MINECHAT_HOST", DEFAULT_HOST)
        )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MINECHAT_SEND_PORT", DEFAULT_PORT))
        )
    parser.add_argument(
        "--token-file",
        default=os.getenv("MINECHAT_TOKEN_FILE", DEFAULT_TOKEN_FILE),
        help="Where to save/load token (json)."
        )
    parser.add_argument(
        "--message",
        "-m",
        help="Message to send (empty line ends message). do not use double ' "
        )
    return parser.parse_args()


async def register_new_account(reader, writer, token_file):
    writer.write(b"\n")
    await writer.drain()

    await reader.readline()
    nickname = "PythonUser"
    writer.write(f"{nickname}\n".encode())
    await writer.drain()

    token_line = await reader.readline()
    data = json.loads(token_line.decode())
    print("Получен новый токен:", data)
    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data["account_hash"]


async def send_message(host, port, message, token_file):
    reader, writer = await asyncio.open_connection(host, port)

    greeting = await reader.readline()
    print(greeting.decode().strip())

    token = None
    if os.path.exists(token_file):
        with open(token_file, encoding="utf-8") as f:
            data = json.load(f)
            token = data.get("account_hash")

    if token:
        print("Авторизуемся по токену:", token)
        writer.write(f"{token}\n".encode())
        await writer.drain()
    else:
        print("Регистрируем новый аккаунт…")
        token = await register_new_account(reader, writer, token_file)

    while True:
        line = await reader.readline()
        if not line or line.decode().startswith("Welcome"):
            break

    text = message.rstrip("\n") + "\n\n"
    writer.write(text.encode())
    await writer.drain()
    print("Сообщение отправлено!")

    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()


async def amain():
    args = parse_args()
    if not args.message:
        print("Нужно указать сообщение через --message")
        return
    await send_message(args.host, args.port, args.message, args.token_file)


if __name__ == "__main__":
    asyncio.run(amain())
