# API для разработчиков

Ядро находится в `pyblocks.core`. Импорт ядра не загружает Qt, Textual, SDL
или библиотеки связи с хабом. Основной путь интеграции — `Session`; низкоуровневые
преобразования доступны отдельно для автоматизации и тестирования.

## Документ и транзакция

```python
from pyblocks.core.document import Document
from pyblocks.core.interaction import Editor

document = Document("speed = 300\n")
editor = Editor(document)
editor.select(document.syntax.offset(1, 8))
editor.replace("400 + 100")
assert document.state.source == "speed = 400 + 100\n"
editor.undo()
assert document.state.source == "speed = 300\n"
```

`State(source: str, scratch: tuple[str, ...])` неизменяем. `Document.commit(source,
scratch=None)` возвращает `True`, если состояние изменилось. `None` сохраняет
прежний Scratch. Форматирование, разбор и компиляция выполняются до публикации;
при исключении документ и обе истории не меняются. Пустая операция не создаёт
историю и не очищает redo. `undo()`/`redo()` возвращают наличие восстановленного
состояния. Обращайтесь к `Editor.undo/redo`, если используете выделение редактора.

## Координаты и структура

`Syntax(source)` строит индекс валидного Python. `parse(source)` проверяет также
контекст компилятора: одного `ast.parse` недостаточно для `return` вне функции.
Ни одна из этих функций не выполняет код.

| API | Результат / контракт |
| --- | --- |
| `Span(start, end)` | Полуинтервал Unicode-символов, `end` исключён |
| `syntax.offset(line, column=0)` | Строка с 1, столбец с 0 → абсолютная позиция |
| `syntax.position(offset)` | Обратное преобразование |
| `syntax.at(offset)` | Самый глубокий узел в позиции; отступы и комментарии выбирают владеющую инструкцию |
| `syntax.spans[node]` | Диапазон AST-узла с учётом декораторов определения |
| `syntax.owned_spans[node]` | Диапазон выбора с прикреплёнными комментариями и отступом |
| `syntax.parent`, `syntax.children` | Навигация по узлам с исходными позициями |
| `syntax.ancestors(node)` | Сам узел, затем родители до Module |
| `syntax.text(node)` | Срез исходного текста |
| `syntax.block_span(statement)` | Целые строки и прикреплённые комментарии |
| `syntax.suites` | Упорядоченные списки инструкций: body, orelse и т. п. |

AST-узлы и `Target` принадлежат конкретному экземпляру `Syntax`. После commit,
undo или redo нужно получить их заново. UI переводит собственные координаты
на границе: например, Qt считает UTF-16-кодовые единицы.
`Editor.parent()`, `child()` и `sibling(step)` перемещают выделение по этому
дереву. Соседние узлы обходятся циклически; `select(offset)` выбирает по позиции.

## Чистые преобразования

Модуль `edit` возвращает новый текст, не изменяя входной индекс:

- `replace(syntax, node, fragment)` заменяет выражение, инструкцию или модуль.
- `delete(syntax, node)` удаляет инструкцию либо подставляет `None` вместо выражения.
- `Target(suite, index)` обозначает позицию перед инструкцией либо конец списка.
- `insert(syntax, target, fragment)` вставляет текст с нужным отступом.
- `move(syntax, node_or_group, target)` переносит одну или несколько соседних инструкций.
- `targets(syntax)` перечисляет структурные позиции; не все подходят любому фрагменту.
- `target_position(syntax, target)` возвращает смещение и отступ позиции.
- `reindent(text, indent)` переносит отступы, сохраняя содержимое строковых литералов.
- `patches(source, changes)` применяет непересекающиеся замены в исходных координатах.

Высокоуровневый `Editor.begin_move()` проверяет допустимые позиции, затем
`navigate_move(step=±1)` и `navigate_move(depth=±1)` выбирают цель.
`preview_move()` возвращает будущий текст; `commit_move()` фиксирует его;
`cancel_move()` оставляет документ неизменным. Для составных сниппетов используйте
`Session.begin_move()`, который передаёт полную группу инструкций.

## Session и файлы

```python
from pathlib import Path
from pyblocks.core.session import Session

session = Session(Path("main.py"))
snippet = next(s for s in session.snippets if s.identity == "python/basics/display")
session.insert_snippet(snippet, {"value": '"Hello"'})
session.project.save()
```

`Session(path, collections=())` объединяет Project, Editor, библиотеки,
распознавание и анализ имён. `matches` и `analysis` пересчитываются при смене
ревизии. `selected_match()`, `selected_text()`, `destination()` обслуживают
текущее выделение. `edit_python`, `edit_parameters`, `insert_snippet`,
`upgrade_selected`, `to_scratch`, `set_scratch` выполняют общие операции UI.
`toggle_expansion()` переключает составной вид выбранного сниппета;
`visible_matches` исключает раскрытые области. `restore_scratch(index)` возвращает
фрагмент на место выражения либо вставляет инструкции после выделения.

`Project` читает исходную кодировку Python и сохраняет её. `save()` проверяет
изменение исходника и workspace с момента открытия/сохранения и использует атомарную замену
отдельных файлов. `.py` и workspace не являются одной файловой транзакцией:
перед сохранением основного текста записывается резервное объединение Scratch.
При прерывании возможны лишние копии фрагментов; единственная сохранённая копия
не должна пропасть. Путь через символьную ссылку разрешается при открытии.

## Сниппеты и диагностика

`load_module(source, collection, version, historical=False)` и
`load_collection(directory)` читают определения без исполнения.
`instantiate(snippet, bindings, occupied=None)` возвращает
`Expansion(source, imports)`. Binding — строка выражения или `ast.expr`.
`occupied` задаёт занятые имена для гигиенического переименования.
`recognize(syntax, snippets)` возвращает `Match` с шаблоном, диапазоном,
привязками параметров, именами локальных переменных и всеми вхождениями параметров.
`upgrade(match, current, occupied=None)` создаёт совместимое разворачивание.

`manage_imports(source, required=(), retain=())` обслуживает только явно отмеченную секцию.
Использования в обычном, уже не распознаваемом коде тоже удерживают импорт.
`retain` содержит тексты Scratch: упоминания имён в них удерживают зависимости
даже при незавершённом синтаксисе.
`Scopes(tree, positions=None)` строит общий индекс лексических привязок;
`resolve(node, name)` возвращает область определения или `None`.
`Analysis.available(offset)` возвращает имена, `diagnostics()` — предупреждения
с диапазонами. Это лёгкий анализ областей видимости без глубокого вывода типов.

`presentation.regions(syntax, matches=())` возвращает диапазоны, глубину, роль, координаты,
возможность сворачивания/переноса и продолжение фона до края строки.
При передаче совпадений внутренние узлы сниппета заменяются одной составной
областью с открытыми параметрами.
`PALETTE` задаёт общие спокойные RGB-цвета; виджет выбирает способ рисования.

## Pybricks API

`Connection(output=None)` принимает callback `bytes → None` для консоли.
Асинхронные методы: `connect(name=None, transport="ble")`, `run(path, wait=False)`,
`stop()`, `send(ControlState(...))`, `disconnect()`.
В Qt весь объект используется в отдельном asyncio-потоке; TUI использует свой
цикл. Не вызывайте один Connection из разных event loop.

`ControlState` — четыре оси `[-1, 1]`, 16-битная маска кнопок и ползунок `[0, 1]`.
`encode`/`decode` используют кадр `~XXXXXXXXBBBBSS\n`: четыре двухзначных hex-оси
со смещением 100, четыре hex-цифры кнопок и двухзначный hex-ползунок 0…100.
Точность осей — 0,01. Формат не содержит управляющих байтов stdin.

## Ошибки и границы

`SyntaxError` означает недопустимый Python; `ValueError` — недопустимую операцию,
позицию, привязку или конфликт. `OSError` относится к файлам/процессу форматтера.
Ошибки связи остаются исключениями нижележащей библиотеки и отображаются UI.
Изменения исходника при неуспешной операции не публикуются.

Стиль и проверки разработки: [development.md](development.md).
