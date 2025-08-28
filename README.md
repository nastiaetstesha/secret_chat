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