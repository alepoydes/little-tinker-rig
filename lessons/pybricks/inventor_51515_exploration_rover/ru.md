# 51515 · Исследовательский вездеход

<a name="prepare"></a>

## Подготовь модель

Найди моторы вездехода и проверь одну последовательность движений.

Нужны LEGO **51515** и точный механизм из исходного проекта. Одного подходящего хаба недостаточно. Программы открываются как обычный редактируемый Python со стандартными блоками. Модель показана в инструкции по ссылке; этот урок открывается без режима пошаговой 3D-сборки.

- [Видео](https://www.youtube.com/watch?v=3gbAc6iKAJg)
- [Инструкция сборки](https://raw.githubusercontent.com/pybricks/pybricks-projects/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/exploration-rover.pdf)

Подключи устройства по таблицам портов следующих этапов. Сохрани передачи, направления моторов и исходные положения калибровки. Используй актуальную прошивку Pybricks для своего хаба. Нужен настоящий робот: виртуальный хаб не моделирует эти механизмы, пульты и равновесие.

Перед запуском открой и изучи программу. Калибровка может сразу двигать моторы. Отметь этап, когда механизм и подключения готовы. Ссылки на медиа требуют сети; текст, код и зависимости входят в сохранённый проект.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/index.md). Laurens Valk. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Попробуй: программа

[Открой `inventor_51515_exploration_rover.py`](program:inventor_51515_exploration_rover.py). Это копия в твоём проекте; повторное открытие сохраняет изменения.

| Порт | Устройство Python | Имя в коде |
|---|---|---|
| A | `ColorSensor` | `self.sherloc` |
| B | `UltrasonicSensor` | `self.mast_cam` |
| C | `Motor` | `self.left_front_wheel` |
| D | `Motor` | `self.right_front_wheel` |
| E | `Motor` | `self.left_rear_wheels` |
| F | `Motor` | `self.right_rear_wheels` |

Назови механизм каждого порта. При калибровке направь датчик цвета на пол. Сравни красный или голубой камень с препятствием, затем сократи одно движение назад и предскажи место остановки.

Кнопка «Запуск» запускает этот файл, «Остановить» завершает его. Сравни прогноз с поведением робота, затем отметь выполнение.

### Разбери код

Найди создание устройств, затем последовательность действий или цикл управления. Читай комментарии к выбранной программе и меняй один параметр за раз. Библиотека содержит блоки этой программы; «Показать все блоки» снимает ограничение для свободного опыта. Подробное авторское объяснение на английском доступно по ссылке «Источники» ниже.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/index.md). Laurens Valk. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Предскажи, измени, объясни

Назови механизм каждого порта. При калибровке направь датчик цвета на пол. Сравни красный или голубой камень с препятствием, затем сократи одно движение назад и предскажи место остановки.

Сохрани проект, чтобы оставить все программы, черновики и зелёные отметки. Вернись на нужный этап для сравнения результата.

Источники: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/fan-inventions/exploration-rover/index.md). Laurens Valk. [MIT](LICENSE.txt).

