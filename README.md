listen-minechat.py —  для чата minechat:
- Подключается к серверу и построчно читает сообщения.
- Дублирует вывод в консоль и пишет историю в файл (append) с таймстемпами.
- При обрыве сети — переподключается с экспоненциальной задержкой.
- Имеет CLI и поддержку переменных окружения (и конфигов, если есть ConfigArgParse).

## Использование:
     python3 listen-minechat.py \
        --host minechat.dvmn.org \
        --port 5000 \
        --history ~/minechat.history

### Переменные окружения (дублируют параметры):
    `MINECHAT_HOST`, `MINECHAT_PORT`, `MINECHAT_HISTORY`

### Если установлен пакет `configargparse`, доступны:
```
--config PATH     # файл конфигурации (по умолчанию: ~/.minechat.conf, ./minechat.conf)
 ```
В файле можно писать, например:
    ```
    host = minechat.dvmn.org
    port = 5000
    history = ~/minechat.history
    ```

## запуск (CLI):

`python3 listen-minechat.py --host minechat.dvmn.org --port 5000 --history ~/minechat.history`


### через переменные окружения:

```
export MINECHAT_HOST=minechat.dvmn.org
export MINECHAT_PORT=5000
export MINECHAT_HISTORY=~/minechat.history
python3 listen-minechat.py
```

пример конфиг-файла (~/.minechat.conf):

```
host = minechat.dvmn.org
port = 5000
history = ~/minechat.history
```

Можно запустить так:

`python3 listen-minechat.py --config ~/.minechat.conf`

И подменить что-то на лету:

`python3 listen-minechat.py --config ~/.minechat.conf --history ./today.history`

## Все доступные CLI-команды и аргументы


`listen-minechat.py` — слушатель чата;

`register-minechat-user.py` — регистрация нового пользователя;

`send-minechat-auth.py` — отправка сообщений.

### 1. Слушатель чата
`python3 listen-minechat.py [OPTIONS]`
Аргументы и переменные окружения:


#### `--config PATH`	–	путь к ini-файлу конфигурации (работает только если установлен configargparse)	~/.minechat.conf, ./minechat.conf
#### `--host HOST`	MINECHAT_HOST	адрес сервера чата	minechat.dvmn.org
#### `--port PORT`	MINECHAT_PORT	порт сервера чата	5000
#### `--history FILE`	MINECHAT_HISTORY	путь к файлу истории сообщений	chat_history.txt
#### `--log-level LEVEL`	MINECHAT_LOG_LEVEL	уровень логирования	DEBUG
### Примеры:
```
python3 listen-minechat.py
python3 listen-minechat.py --history ./today.history
python3 listen-minechat.py --host minechat.dvmn.org --port 5000 --log-level INFO
python3 listen-minechat.py --config ~/.minechat.conf
```
### Регистрация пользователя
`python3 register-minechat-user.py [OPTIONS]`


Аргументы и ENV:


#### `--host HOST`	MINECHAT_HOST	адрес сервера чата	minechat.dvmn.org
#### `--port PORT`	MINECHAT_PORT	порт сервера чата (отправка)	5050
#### `--nickname NAME`	–	префикс ника (сервер добавит эпитет)	"anonymous"
#### `--token-file FILE`	MINECHAT_TOKEN_FILE	путь для сохранения токена	./minechat_token.json (в директории проекта)
#### `--force`	–	перезаписать существующий токен	False
#### `--log-level` LEVEL	MINECHAT_LOG_LEVEL	уровень логирования	DEBUG

### Примеры:
```
python3 register-minechat-user.py
python3 register-minechat-user.py --nickname egor
python3 register-minechat-user.py --token-file ./secrets/token.json
python3 register-minechat-user.py --force --log-level INFO
```
### Отправка сообщений
`python3 send-minechat-auth.py [OPTIONS] --message "TEXT"`


Аргументы и ENV:

#### `--host HOST`	MINECHAT_HOST	адрес сервера чата	minechat.dvmn.org
#### `--port PORT`	MINECHAT_PORT	порт сервера чата (отправка)	5050
#### `--token-file` FILE	MINECHAT_TOKEN_FILE	путь к файлу с токеном	./minechat_token.json
#### `--message`, -m TEXT	–	текст сообщения (обязательно)	–
#### -`-log-level` LEVEL	MINECHAT_LOG_LEVEL	уровень логирования	DEBUG

#### Примеры:
```
python3 send-minechat-auth.py -m 'Привет всем'
python3 send-minechat-auth.py --message 'Это я со старым токеном'
python3 send-minechat-auth.py --token-file ./secrets/token.json -m 'Секретное сообщение'
python3 send-minechat-auth.py --host minechat.dvmn.org --port 5050 -m 'Через другой порт'
python3 send-minechat-auth.py --log-level INFO -m 'Меньше логов'
```

python main.py --host minechat.dvmn.org --port 5000 --send-port 5050 \
  --token-file ~/minechat_token.json --log-level INFO


python main.py --host minechat.dvmn.org --port 5000

python main.py --host minechat.dvmn.org --port 5000 --history ~/chat_history.txt