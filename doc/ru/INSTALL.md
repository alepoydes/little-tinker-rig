# Установка и запуск

Исходный код доступен на [GitHub](https://github.com/alepoydes/little-tinker-rig):

```sh
git clone https://github.com/alepoydes/little-tinker-rig.git
cd little-tinker-rig
```

Настройки PyBlocks, пользовательские блоки и загруженный кеш сохраняются.
При новой установке данные и кеш используют каталог `little-tinker-rig`
в стандартных пользовательских каталогах ОС. Новые проекты уроков имеют
расширение `.ltr`; прежние `.pyblocks` и рабочие файлы `.pyblocks.json`
по-прежнему читаются.

LittleTinker Rig работает на компьютере. Программу для робота он передаёт на хаб
с установленной прошивкой Pybricks. Для знакомства с редактором робот не нужен.

При первом запуске интерфейс английский. **View → Language → Русский**
переключает интерфейс и справку. Выбор сохраняется; прежняя русская настройка
остаётся в силе после обновления.

## Из исходников с uv

Установите [uv](https://docs.astral.sh/uv/getting-started/installation/), скачайте
проект и откройте терминал в его каталоге. uv создаёт изолированное окружение
`.venv`; системные Python-пакеты не меняются.

Графический редактор:

```sh
uv sync --extra qt
uv run --extra qt little-tinker-rig-qt examples/first.py
```

Терминальный редактор:

```sh
uv sync --extra tui
uv run --extra tui little-tinker-rig-tui examples/first.py
```

Для работы с хабом добавьте `--extra pybricks` при установке и запуске:

```sh
uv sync --extra qt --extra pybricks
uv run --extra qt --extra pybricks little-tinker-rig-qt examples/motor.py
```

Физический геймпад требует ещё `--extra gamepad`. Установка терминального
интерфейса не устанавливает Qt; установка ядра не устанавливает Pybricks.
`uv sync --all-extras` устанавливает все возможности сразу.

Виртуальные Inventor/Prime, BOOST и Technic входят в базовый пакет и не требуют
`--extra pybricks`. В Qt нажмите «Подключить хаб», выберите «Виртуальный хаб»
и модель. Руководство находится в режиме «Помощь» и работает без сети.

Версии зависимостей зафиксированы в `uv.lock`. Добавьте `--locked`, если нужно
запретить uv менять этот файл. `--no-dev` исключает инструменты разработки.

## Обычное виртуальное окружение

Поддерживается Python 3.11 и новее. В корне проекта:

```sh
python -m venv .venv
```

Активируйте окружение: `source .venv/bin/activate` в Linux/macOS либо
`.venv\Scripts\activate` в Windows. Затем:

```sh
python -m pip install '.[qt,pybricks]'
little-tinker-rig-qt examples/first.py
```

## Если запуск не удался

- `No module named PySide6` / `textual` / `pybricksdev`: соответствующая опция
  установки отсутствует. При использовании uv укажите её в `uv run`.
- Qt сообщает об отсутствии платформенного плагина: проверьте графическую
  сессию и системные библиотеки Qt для своей ОС. Без графического окружения
  используйте TUI; `QT_QPA_PLATFORM=offscreen` предназначен для тестов.
- Bluetooth-хаб не найден: включите Bluetooth, запустите хаб с прошивкой Pybricks
  и закройте другое приложение, которое уже подключено к нему.
- USB недоступен: проверьте кабель передачи данных и права доступа к USB.

Дальше: [первое знакомство](tutorial/first.md), [управление редактором](usage.md),
[подключение робота](robotics.md).
