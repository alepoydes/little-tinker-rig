# 42099 · Внедорожник X-treme

<a name="prepare"></a>

## Подготовь модель

Сравни автономную поездку, клавиатуру, пульт и обнаружение препятствий.

Нужны LEGO **42099** и точный механизм из исходного проекта. Одного подходящего хаба недостаточно. Программы открываются как обычный редактируемый Python со стандартными блоками. Модель показана в инструкции по ссылке; этот урок открывается без режима пошаговой 3D-сборки.

- [Инструкция сборки](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6314518.pdf)
- [Видео](https://www.youtube.com/watch?v=kN47P6mksj4)

Подключи устройства по таблицам портов следующих этапов. Сохрани передачи, направления моторов и исходные положения калибровки. Используй актуальную прошивку Pybricks для своего хаба. Нужен настоящий робот: виртуальный хаб не моделирует эти механизмы, пульты и равновесие.

Перед запуском открой и изучи программу. Калибровка может сразу двигать моторы. Отметь этап, когда механизм и подключения готовы. Ссылки на медиа требуют сети; текст, код и зависимости входят в сохранённый проект.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Попробуй: автономное движение

[Открой `technic_42099_off_roader.py`](program:technic_42099_off_roader.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| C | `Motor` | `steer` |

В программе для цифровой клавиатуры 7/8/9 едут вперёд, 1/2/3 — назад, 5 останавливает. Для обхода препятствий нужен датчик, указанный в программе. Измени один параметр руля или расстояния и предскажи результат.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-2"></a>

## Попробуй: клавиатура

[Открой `technic_42099_keyboard.py`](program:technic_42099_keyboard.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| C | `Motor` | `steer` |

В программе для цифровой клавиатуры 7/8/9 едут вперёд, 1/2/3 — назад, 5 останавливает. Для обхода препятствий нужен датчик, указанный в программе. Измени один параметр руля или расстояния и предскажи результат.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

Открой консоль, поставь курсор в поле ввода хаба и включи **Отправлять клавиши сразу**. Клавиши уходят на настоящий хаб, пока фокус в этом поле. Escape выключает этот режим; «Остановить» завершает программу.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-3"></a>

## Попробуй: чтение клавиш

[Открой `technic_42099_keyboard_monitor.py`](program:technic_42099_keyboard_monitor.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.



В программе для цифровой клавиатуры 7/8/9 едут вперёд, 1/2/3 — назад, 5 останавливает. Для обхода препятствий нужен датчик, указанный в программе. Измени один параметр руля или расстояния и предскажи результат.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

Открой консоль, поставь курсор в поле ввода хаба и включи **Отправлять клавиши сразу**. Клавиши уходят на настоящий хаб, пока фокус в этом поле. Escape выключает этот режим; «Остановить» завершает программу.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-4"></a>

## Попробуй: обход препятствий

[Открой `technic_42099_obstacle_avoidance.py`](program:technic_42099_obstacle_avoidance.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| C | `Motor` | `steer` |
| D | `ColorDistanceSensor` | `sensor` |

В программе для цифровой клавиатуры 7/8/9 едут вперёд, 1/2/3 — назад, 5 останавливает. Для обхода препятствий нужен датчик, указанный в программе. Измени один параметр руля или расстояния и предскажи результат.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-5"></a>

## Попробуй: пульт

[Открой `technic_42099_off_roader_remote.py`](program:technic_42099_off_roader_remote.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| C | `Motor` | `steer` |

В программе для цифровой клавиатуры 7/8/9 едут вперёд, 1/2/3 — назад, 5 останавливает. Для обхода препятствий нужен датчик, указанный в программе. Измени один параметр руля или расстояния и предскажи результат.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Предскажи, измени, объясни

В программе для цифровой клавиатуры 7/8/9 едут вперёд, 1/2/3 — назад, 5 останавливает. Для обхода препятствий нужен датчик, указанный в программе. Измени один параметр руля или расстояния и предскажи результат.

Сохрани проект, чтобы оставить все программы, черновики и зелёные отметки. Вернись на нужный этап для сравнения результата.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/driving/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/keyboard-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/obstacle-avoidance/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42099-off-roader/powered-up-remote/index.md). The Pybricks Team. [MIT](LICENSE.txt).

