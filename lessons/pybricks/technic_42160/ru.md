# 42160 · Audi RS Q e-tron

<a name="prepare"></a>

## Подготовь модель

Сравни пульт Powered Up и аналоговое управление Xbox.

Нужны LEGO **42160** и точный механизм из исходного проекта. Одного подходящего хаба недостаточно. Программы открываются как обычный редактируемый Python со стандартными блоками. Модель показана в инструкции по ссылке; этот урок открывается без режима пошаговой 3D-сборки.

- [Видео](https://www.youtube.com/watch?v=c0KVNdJlAkc)
- [Инструкция сборки](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/6508358.pdf)
- [Видео](https://www.youtube.com/watch?v=fxInp9cutNg)

Подключи устройства по таблицам портов следующих этапов. Сохрани передачи, направления моторов и исходные положения калибровки. Используй актуальную прошивку Pybricks для своего хаба. Нужен настоящий робот: виртуальный хаб не моделирует эти механизмы, пульты и равновесие.

Перед запуском открой и изучи программу. Калибровка может сразу двигать моторы. Отметь этап, когда механизм и подключения готовы. Ссылки на медиа требуют сети; текст, код и зависимости входят в сохранённый проект.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Попробуй: пульт

[Открой `technic_42160_audi_remote.py`](program:technic_42160_audi_remote.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `rear` |
| B | `Motor` | `front` |
| D | `Motor` | `steer` |

С Xbox сравни малые и большие движения стика и курков. В двух вариантах программы найди моменты чтения ввода. Измени один масштаб движения, сохранив калибровку руля.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-2"></a>

## Попробуй: Xbox: вариант из блоков

[Открой `technic_42160_audi_xbox_blocks.py`](program:technic_42160_audi_xbox_blocks.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| D | `Motor` | `steer` |

С Xbox сравни малые и большие движения стика и курков. В двух вариантах программы найди моменты чтения ввода. Измени один масштаб движения, сохранив калибровку руля.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

После запуска включи сопряжение контроллера его кнопкой. На время начальной калибровки руля поставь робота на опору.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

<a name="run-3"></a>

## Попробуй: Xbox: Python

[Открой `technic_42160_audi_xbox_python.py`](program:technic_42160_audi_xbox_python.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `Motor` | `front` |
| B | `Motor` | `rear` |
| D | `Motor` | `steer` |

С Xbox сравни малые и большие движения стика и курков. В двух вариантах программы найди моменты чтения ввода. Измени один масштаб движения, сохранив калибровку руля.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

После запуска включи сопряжение контроллера его кнопкой. На время начальной калибровки руля поставь робота на опору.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Предскажи, измени, объясни

С Xbox сравни малые и большие движения стика и курков. В двух вариантах программы найди моменты чтения ввода. Измени один масштаб движения, сохранив калибровку руля.

Сохрани проект, чтобы оставить все программы, черновики и зелёные отметки. Вернись на нужный этап для сравнения результата.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/powered-up-remote/index.md), [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/technic/42160-audi-rs-q-e-tron/xbox-controller/index.md). Geoff Stearns, The Pybricks Team. [MIT](LICENSE.txt).

