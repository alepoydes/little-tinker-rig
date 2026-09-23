"""Motor actions and values for Pybricks hubs; parsed as static templates."""


def create_motor(name=motor, port: "Port" = Port.A):
    """Подключить мотор к порту хаба.

    Выберите порт и задайте имя мотора без кавычек, например left_motor.
    Доступные порты зависят от модели хаба.
    """
    from pybricks.parameters import Port
    from pybricks.pupdevices import Motor

    name = Motor(port)


def create_oriented_motor(
    name=motor,
    port: "Port" = Port.A,
    direction: "Direction" = Direction.COUNTERCLOCKWISE,
):
    """Подключить мотор и выбрать положительное направление вращения."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor

    name = Motor(port, direction)


def run_motor(motor: "Motor" = motor, speed: "deg/s" = 500):
    """Вращать мотор с заданной скоростью.

    Скорость задаётся в градусах в секунду. Отрицательное число меняет направление.
    Мотор продолжает вращаться после этого блока до следующей команды.
    """
    motor.run(speed)


def stop_motor(motor: "Motor" = motor):
    """Остановить мотор с торможением."""
    motor.brake()


def turn_motor(motor: "Motor" = motor, angle: "deg" = 90, speed: "deg/s" = 300):
    """Повернуть мотор на заданный угол и дождаться завершения."""
    motor.run_angle(speed, angle)


def motor_target(motor: "Motor" = motor, angle: "deg" = 0, speed: "deg/s" = 300):
    """Повернуть мотор в заданное положение и дождаться завершения."""
    motor.run_target(speed, angle)


def motor_time(motor: "Motor" = motor, duration: "ms" = 1000, speed: "deg/s" = 300):
    """Вращать мотор заданное время, затем остановить."""
    motor.run_time(speed, duration)


def reset_motor_angle(motor: "Motor" = motor, angle: "deg" = 0):
    """Назначить текущему положению мотора выбранный угол."""
    motor.reset_angle(angle)


def motor_angle(motor: "Motor" = motor) -> "deg":
    """Узнать текущий угол мотора."""
    return motor.angle()


def motor_speed(motor: "Motor" = motor) -> "deg/s":
    """Узнать текущую скорость мотора."""
    return motor.speed()
