# 51515 · Задания для Gelo

<a name="prepare"></a>

## Подготовь модель

Исследуй ходьбу, обход препятствий, трюки и управление пультом.

Нужны LEGO **51515** и точный механизм из исходного проекта. Одного подходящего хаба недостаточно. Программы открываются как обычный редактируемый Python со стандартными блоками. Модель показана в инструкции по ссылке; этот урок открывается без режима пошаговой 3D-сборки.

- [Инструкция сборки](https://www.lego.com/cdn/product-assets/product.bi.additional.main.pdf/51515_Gelo.pdf)

Подключи устройства по таблицам портов следующих этапов. Сохрани передачи, направления моторов и исходные положения калибровки. Используй актуальную прошивку Pybricks для своего хаба. Нужен настоящий робот: виртуальный хаб не моделирует эти механизмы, пульты и равновесие.

Перед запуском открой и изучи программу. Калибровка может сразу двигать моторы. Отметь этап, когда механизм и подключения готовы. Ссылки на медиа требуют сети; текст, код и зависимости входят в сохранённый проект.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Попробуй: основная программа

[Открой `inventor_51515_gelo_basic.py`](program:inventor_51515_gelo_basic.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `self.rear_right_leg_motor` |
| B | `Motor` | `self.rear_left_leg_motor` |
| C | `Motor` | `self.front_right_leg_motor` |
| D | `Motor` | `self.front_left_leg_motor` |
| E | `UltrasonicSensor` | `self.distance_sensor` |
| F | `ColorSensor` | `self.color_sensor` |

Объедини два действия Gelo в шаблоне. Оставь общий модуль Gelo рядом с программой. Сравни короткую и длинную прогулку, прежде чем менять саму походку.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.



Начни с исходной стоячей позы. Проследи основную последовательность ходьбы и сравни моменты движения передних и задних ног.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-2"></a>

## Попробуй: пульт

[Открой `inventor_51515_gelo_remote.py`](program:inventor_51515_gelo_remote.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Объедини два действия Gelo в шаблоне. Оставь общий модуль Gelo рядом с программой. Сравни короткую и длинную прогулку, прежде чем менять саму походку.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

Общие модули уже лежат рядом с программой: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).



Запусти программу, затем включи пульт Powered Up. Жёлтый индикатор означает ожидание пульта, зелёный — соединение. Левые +/− меняют скорость, правые +/− — поворот; любая красная кнопка останавливает ходьбу.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-3"></a>

## Попробуй: командная строка

[Открой `inventor_51515_gelo_repl.py`](program:inventor_51515_gelo_repl.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Объедини два действия Gelo в шаблоне. Оставь общий модуль Gelo рядом с программой. Сравни короткую и длинную прогулку, прежде чем менять саму походку.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

Исходное задание с командной строкой требует поддержки REPL прошивкой. Если появился `>>>`, отправляй команды из консоли в построчном режиме, например `gelo.walk()`. Если прошивка просто завершает программу, используй этап с шаблоном: Студия не эмулирует REPL хаба.

Общие модули уже лежат рядом с программой: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).





### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-4"></a>

## Попробуй: обход препятствий

[Открой `inventor_51515_gelo_roam.py`](program:inventor_51515_gelo_roam.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Объедини два действия Gelo в шаблоне. Оставь общий модуль Gelo рядом с программой. Сравни короткую и длинную прогулку, прежде чем менять саму походку.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

Общие модули уже лежат рядом с программой: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).



Следи за датчиком расстояния: препятствие вызывает случайный поворот, затем ходьба продолжается. На малой скорости сравни один порог расстояния.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-5"></a>

## Попробуй: своя программа

[Открой `inventor_51515_gelo_template.py`](program:inventor_51515_gelo_template.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Объедини два действия Gelo в шаблоне. Оставь общий модуль Gelo рядом с программой. Сравни короткую и длинную прогулку, прежде чем менять саму походку.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

Общие модули уже лежат рядом с программой: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).



Шаблон импортирует общий класс Gelo. Добавляй вызовы внутри его контекста: тогда при завершении последовательности моторы будут остановлены.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-6"></a>

## Попробуй: трюки

[Открой `inventor_51515_gelo_tricks.py`](program:inventor_51515_gelo_tricks.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `self.back_right` |
| B | `Motor` | `self.back_left` |
| C | `Motor` | `self.front_right` |
| D | `Motor` | `self.front_left` |
| E | `UltrasonicSensor` | `self.ultrasonic` |
| F | `ColorSensor` | `self.color` |

Объедини два действия Gelo в шаблоне. Оставь общий модуль Gelo рядом с программой. Сравни короткую и длинную прогулку, прежде чем менять саму походку.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

Общие модули уже лежат рядом с программой: [inventor_51515_gelo.py](program:inventor_51515_gelo.py).



Показывай датчику косточки разных цветов и сравни трюки. Выбери поверхность, на которой ноги не скользят.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Предскажи, измени, объясни

Объедини два действия Gelo в шаблоне. Оставь общий модуль Gelo рядом с программой. Сравни короткую и длинную прогулку, прежде чем менять саму походку.

Сохрани проект, чтобы оставить все программы, черновики и зелёные отметки. Вернись на нужный этап для сравнения результата.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/index.md), [basic.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/basic.md), [remote.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/remote.md), [repl.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/repl.md), [roam.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/roam.md), [template.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/template.md), [tricks.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/main-models/gelo/tricks.md). The Lương-Phạm Family, The Pybricks Team. [MIT](LICENSE.txt).

