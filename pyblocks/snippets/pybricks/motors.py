"""Motor templates for Pybricks hubs."""


def create_motor(name, port="A"):
    """Подключить мотор к порту хаба.

    name — имя мотора без кавычек, например left_motor.
    port — буква порта в кавычках: "A", "B", "C" или "D".
    Набор доступных портов зависит от хаба.
    """
    from pybricks.parameters import Port
    from pybricks.pupdevices import Motor

    name = Motor(getattr(Port, port))


def run_motor(motor: "Motor", speed: "deg/s" = 500):
    """Вращать мотор с заданной скоростью.

    Скорость задаётся в градусах в секунду. Отрицательное число меняет направление.
    Мотор продолжает вращаться после этого блока до следующей команды.
    """
    motor.run(speed)


def stop_motor(motor: "Motor"):
    """Остановить мотор с торможением."""
    motor.brake()


def turn_motor(motor: "Motor", angle: "deg" = 90, speed: "deg/s" = 300):
    """Повернуть мотор на заданный угол и дождаться завершения."""
    motor.run_angle(speed, angle)
