"""Measure complete Qt insertions, including source analysis, layout and repaint."""

import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lines", nargs="+", type=int, default=[1000, 5000])
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QMessageBox

    from pyblocks.core.parameters import default_bindings
    from pyblocks.core.snippets import instantiate
    from pyblocks.core.transfer import Transfer
    from pyblocks.qt.app import Studio

    app = QApplication([])
    with TemporaryDirectory(prefix="pyblocks-benchmark-") as folder:
        root = Path(folder)
        sources = [("courier", Path("examples/courier.py").read_text())]
        sources.extend(
            (
                str(count),
                "from pybricks.parameters import Port\nfrom pybricks.pupdevices import Motor\nmotor = Motor(Port.A)\n"
                + "".join(f"motor.run({i})\n" for i in range(count)),
            )
            for count in args.lines
        )
        settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
        print("document,open_ms,library_to_scratch_ms,program_to_scratch_ms")
        with patch("pyblocks.qt.app.QSettings", return_value=settings):
            for name, source in sources:
                path = root / f"{name}.py"
                path.write_text(source)
                start = perf_counter()
                window = Studio(path)
                window.show()
                app.processEvents()
                opened = perf_counter() - start
                try:
                    session = window.session
                    snippet = next(
                        s
                        for s in session.snippets
                        if s.identity == "pybricks/motors/create_motor"
                    )
                    start = perf_counter()
                    session.set_scratch(
                        None,
                        instantiate(snippet, default_bindings(session, snippet)).source,
                    )
                    window.refresh_views()
                    app.processEvents()
                    library = perf_counter() - start
                    session.editor.select(
                        session.document.state.source.index(
                            "right =" if name == "courier" else "motor.run(0)"
                        )
                    )
                    transfer = Transfer.capture(session)
                    before = session.document.state
                    start = perf_counter()
                    transfer.to_scratch(1)
                    window.refresh_views()
                    app.processEvents()
                    moved = perf_counter() - start
                    assert len(session.document.state.scratch) == 2
                    session.editor.undo()
                    assert session.document.state is before
                    print(
                        f"{name},{opened * 1000:.1f},{library * 1000:.1f},{moved * 1000:.1f}",
                        flush=True,
                    )
                finally:
                    with patch.object(
                        QMessageBox,
                        "question",
                        return_value=QMessageBox.StandardButton.Discard,
                    ):
                        window.close()


if __name__ == "__main__":
    main()
