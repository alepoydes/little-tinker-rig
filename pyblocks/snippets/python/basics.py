"""Small Python building blocks. Functions are static templates."""


def display(value="Hello!"):
    """Показать значение в консоли.

    Значением может быть текст в кавычках, число или имя переменной.
    Консоль помогает увидеть, что происходит в программе.
    """
    print(value)


def assign(name, value=0):
    """Запомнить значение под выбранным именем.

    Имя пишется без кавычек: например, speed или distance.
    Позже это имя можно использовать в других блоках.
    """
    name = value


def repeat(count=10):
    """Повторить действия заданное число раз.

    Замените pass внутри цикла своими действиями через «Edit as Python».
    Счётчик i начинается с нуля.
    """
    for i in range(count):
        pass


def condition(test=True):
    """Выполнить действия, если условие истинно."""
    if test:
        pass


def forever():
    """Повторять действия до остановки программы.

    Добавьте ожидание в цикл управления роботом, чтобы не перегружать хаб.
    """
    while True:
        pass


def compare(value, threshold=0):
    """Проверить, что значение меньше порога."""
    return value < threshold
