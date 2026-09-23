"""Sensor and timing templates."""


def wait_ms(duration: "ms" = 1000):
    """Подождать указанное число миллисекунд. 1000 мс = 1 секунда."""
    from pybricks.tools import wait

    wait(duration)


def create_color_sensor(name=sensor, port: "Port" = Port.C):
    """Подключить датчик цвета к порту хаба."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ColorSensor

    name = ColorSensor(port)


def reflection_below(sensor: "ColorSensor" = sensor, threshold: "%" = 30) -> "bool":
    """Проверить, что поверхность темнее заданного порога отражения."""
    return sensor.reflection() < threshold


def follow_edge(
    drive: "DriveBase" = drive, sensor: "ColorSensor" = sensor, target: "%" = 50, gain=2
):
    """Следовать вдоль границы линии пропорциональным регулятором.

    drive — заранее созданная DriveBase; sensor — датчик отражения.
    target — отражение на границе светлого и тёмного, gain — сила коррекции.
    Цикл продолжается до остановки программы.
    """
    from pybricks.tools import wait

    while True:
        error = sensor.reflection() - target
        drive.drive(200, gain * error)
        wait(10)


def create_ultrasonic_sensor(name=distance, port: "Port" = Port.D):
    """Подключить ультразвуковой датчик расстояния."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import UltrasonicSensor

    name = UltrasonicSensor(port)


def create_force_sensor(name=button, port: "Port" = Port.E):
    """Подключить датчик силы или аварийную кнопку."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ForceSensor

    name = ForceSensor(port)


def create_color_distance_sensor(name=sensor, port: "Port" = Port.D):
    """Подключить комбинированный датчик цвета и расстояния BOOST."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ColorDistanceSensor

    name = ColorDistanceSensor(port)


def reflection(sensor: "ColorSensor" = sensor) -> "%":
    """Измерить отражение поверхности: от 0 до 100%."""
    return sensor.reflection()


def distance(sensor: "UltrasonicSensor" = distance) -> "mm":
    """Измерить расстояние до препятствия в миллиметрах."""
    return sensor.distance()


def boost_distance(sensor: "ColorDistanceSensor" = sensor) -> "%":
    """Измерить относительное расстояние датчиком BOOST."""
    return sensor.distance()


def force(sensor: "ForceSensor" = button) -> "N":
    """Измерить силу нажатия в ньютонах."""
    return sensor.force()


def pressed(sensor: "ForceSensor" = button) -> "bool":
    """Проверить, нажата ли кнопка датчика силы."""
    return sensor.pressed()


def color(sensor: "ColorSensor" = sensor) -> "Color":
    """Узнать цвет поверхности под датчиком."""
    return sensor.color()
