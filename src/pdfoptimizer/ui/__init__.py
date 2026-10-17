"""图形界面入口：``python -m pdfoptimizer`` 或控制台脚本 ``pdfoptimizer-gui``。"""

from __future__ import annotations

import sys


def run(argv: list[str] | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("PDFOptimizer")
    app.setApplicationDisplayName("PDFOptimizer · PDF 优化压缩")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


__all__ = ["run"]
