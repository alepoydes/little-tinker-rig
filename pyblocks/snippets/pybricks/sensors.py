"""Sensor and timing templates."""


def wait_ms(duration: "ms" = 1000):
    """Подождать указанное число миллисекунд. 1000 мс = 1 секунда."""
    from pybricks.tools import wait

    wait(duration)


def create_color_sensor(name=sensor, port="C"):
    """Подключить датчик цвета к порту хаба."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ColorSensor

    name = ColorSensor(getattr(Port, port))


def reflection_below(sensor: "ColorSensor" = sensor, threshold: "%" = 30):
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
