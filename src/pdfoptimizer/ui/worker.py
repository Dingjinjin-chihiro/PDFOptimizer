"""后台压缩工作线程（避免阻塞 Qt 事件循环）。"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QThread, Signal

from ..core import OptimizeOptions, OptimizeResult, PdfCoreEngine


class BatchWorker(QThread):
    """按队列串行压缩多个文件；每个文件一条进度信号。"""

    #: (文件序号 0-based, 文件总数, 阶段描述, 0.0~1.0)
    file_progress = Signal(int, int, str, float)
    #: 单个文件完成
    file_done = Signal(object)                 # OptimizeResult
    #: 全部完成
    all_done = Signal(list)                    # list[OptimizeResult]

    def __init__(self, jobs: list[tuple[str, str]], options: OptimizeOptions,
                 dll_path: str | None, parent=None) -> None:
        super().__init__(parent)
        self._jobs = list(jobs)
        self._options = options
        self._dll_path = dll_path
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:                      # noqa: D102
        engine = PdfCoreEngine(self._dll_path)
        results: list[OptimizeResult] = []
        total = len(self._jobs)
        for index, (src, dst) in enumerate(self._jobs):
            if self._cancel:
                break
            self.file_progress.emit(index, total, "准备", 0.0)

            def on_progress(stage: str, fraction: float, _i=index) -> None:
                self.file_progress.emit(_i, total, stage, fraction)

            result = engine.optimize(src, dst, self._options, on_progress)
            results.append(result)
            self.file_done.emit(result)
        self.all_done.emit(results)


def options_with_overrides(options: OptimizeOptions, **overrides) -> OptimizeOptions:
    """便于界面按需覆盖个别参数。"""
    return replace(options, **overrides)
