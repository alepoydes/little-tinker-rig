"""Drive-base and clock building blocks."""


def create_drive(
    name=drive,
    left: "Motor" = left,
    right: "Motor" = right,
    wheel: "mm" = 56,
    track: "mm" = 112,
):
    """Создать двухколёсного робота из левого и правого моторов."""
    from pybricks.robotics import DriveBase

    name = DriveBase(left, right, wheel_diameter=wheel, axle_track=track)


def drive(drive: "DriveBase" = drive, speed: "mm/s" = 180, turn: "deg/s" = 0):
    """Ехать с заданной скоростью и поворотом."""
    drive.drive(speed, turn)


def brake(drive: "DriveBase" = drive):
    """Затормозить оба колеса робота."""
    drive.brake()


def create_clock(name=clock):
    """Создать секундомер для измерения времени."""
    from pybricks.tools import StopWatch

    name = StopWatch()


def elapsed(clock: "StopWatch" = clock) -> "ms":
    """Узнать, сколько миллисекунд прошло на секундомере."""
    return clock.time()


def reset_clock(clock: "StopWatch" = clock):
    """Начать отсчёт времени заново."""
    clock.reset()
