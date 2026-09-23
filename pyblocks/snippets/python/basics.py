"""Small Python building blocks. Functions are static templates."""


def display(value="Hello!"):
    """Показать значение в консоли.

    Значением может быть текст в кавычках, число или имя переменной.
    Консоль помогает увидеть, что происходит в программе.
    """
    print(value)


def assign(name=value, value=0):
    """Запомнить значение под выбранным именем.

    Имя пишется без кавычек: например, speed или distance.
    Позже это имя можно использовать в других блоках.
    """
    name = value


def repeat(count: "number" = 10):
    """Повторить действия заданное число раз.

    Замените pass внутри цикла своими действиями через «Edit as Python».
    Счётчик i начинается с нуля.
    """
    for i in range(count):
        pass


def condition(test: "bool" = True):
    """Выполнить действия, если условие истинно."""
    if test:
        pass


def forever():
    """Повторять действия до остановки программы.

    Добавьте ожидание в цикл управления роботом, чтобы не перегружать хаб.
    """
    while True:
        pass


def compare(value: "number" = 0, threshold: "number" = 0) -> "bool":
    """Проверить, что значение меньше порога."""
    return value < threshold


def condition_else(test: "bool" = True):
    """Выбрать одно из двух действий по условию."""
    if test:
        pass
    else:
        pass


def while_condition(test: "bool" = True):
    """Повторять действия, пока условие истинно."""
    while test:
        pass


def add_to(name=value, amount: "number" = 1):
    """Увеличить значение переменной."""
    name += amount


def equal(left=0, right=0) -> "bool":
    """Проверить, равны ли два значения."""
    return left == right


def both(left: "bool" = True, right: "bool" = True) -> "bool":
    """Проверить, что оба условия истинны."""
    return left and right


def either(left: "bool" = True, right: "bool" = False) -> "bool":
    """Проверить, что хотя бы одно условие истинно."""
    return left or right


def opposite(test: "bool" = True) -> "bool":
    """Изменить условие на противоположное."""
    return not test
