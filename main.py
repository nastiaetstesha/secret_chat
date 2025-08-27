import asyncio


SERVER_HOST = 'minechat.dvmn.org'
SERVER_PORT = 5000
OUTPUT_FILE = 'chat_messages.txt'


async def read_chat():
    reader, writer = await asyncio.open_connection(SERVER_HOST, SERVER_PORT)
    print(f'Connected to {SERVER_HOST}:{SERVER_PORT}')

    try:
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            while True:
                data = await reader.readline()
                if not data:
                    print("Connection closed by server")
                    break
                message = data.decode().rstrip()
                print(message)
                f.write(message + "\n")
                f.flush()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def main():
    await read_chat()


if __name__ == '__main__':
    asyncio.run(main())
