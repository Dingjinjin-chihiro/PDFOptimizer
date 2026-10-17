"""主窗口：文件队列 + 参数面板 + 进度 / 日志。"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)

from ..core import ENCODER_FLATE, ENCODER_JPEG, PRESETS, OptimizeOptions, suggest_dst
from ..dllfinder import remember, resolve_dll
from .theme import CUSTOM_LABEL, LEVEL_LABELS, QSS
from .worker import BatchWorker

PDF_FILTER = "PDF 文件 (*.pdf);;所有文件 (*.*)"


def human_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)
    return frame, layout


def section(title: str) -> QLabel:
    label = QLabel(title)
    label.setObjectName("SectionTitle")
    return label


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.HLine)
    return line


class FileDropList(QListWidget):
    """支持拖入 PDF 的列表。"""

    def __init__(self, on_added) -> None:
        super().__init__()
        self._on_added = on_added
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DropOnly)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setMinimumHeight(180)
        self.setToolTip("把 PDF 拖到这里，或点「添加文件」")

    def dragEnterEvent(self, event) -> None:            # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:             # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:                 # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        pdfs = [p for p in paths if p.lower().endswith(".pdf")]
        if pdfs:
            self._on_added(pdfs)
        event.acceptProposedAction()


class SliderRow(QWidget):
    """标签 + 滑块 + 数字框 同步控件。"""

    def __init__(self, title: str, minimum: int, maximum: int, value: int,
                 suffix: str = "", on_change=None) -> None:
        super().__init__()
        self._on_change = on_change
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        label = QLabel(title)
        label.setFixedWidth(74)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setValue(value)
        self.spin.setFixedWidth(84)
        if suffix:
            self.spin.setSuffix(f" {suffix}")

        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.spin.valueChanged.connect(self._changed)

        row.addWidget(label)
        row.addWidget(self.slider, 1)
        row.addWidget(self.spin)

    def _changed(self, _value: int) -> None:
        if self._on_change:
            self._on_change()

    def value(self) -> int:
        return self.spin.value()

    def set_value(self, value: int) -> None:
        """程序化赋值（同时屏蔽信号，避免被当成自定义改动）。"""
        for widget in (self.spin, self.slider):
            widget.blockSignals(True)
        self.spin.setValue(value)
        self.slider.setValue(value)
        for widget in (self.spin, self.slider):
            widget.blockSignals(False)

    def set_enabled(self, enabled: bool) -> None:
        self.slider.setEnabled(enabled)
        self.spin.setEnabled(enabled)


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("PDFOptimizer · PDF 优化压缩")
        self.resize(1080, 720)

        self._files: list[str] = []
        self._job_names: list[str] = []
        self._worker: BatchWorker | None = None
        self._ready = False          # 构建期不把控件初始化误判为“自定义”
        self._dll_path: str | None = resolve_dll()

        self._build_ui()
        self.setStyleSheet(QSS)
        self._refresh_dll_state()
        self._sync_advanced_state()
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        # 标题
        head = QVBoxLayout()
        head.setSpacing(2)
        title = QLabel("PDFOptimizer")
        title.setObjectName("Title")
        subtitle = QLabel("直接驱动 PDFelement 的 libPdfCore.dll 原生优化压缩流水线 · 无需界面登录")
        subtitle.setObjectName("Subtitle")
        head.addWidget(title)
        head.addWidget(subtitle)
        root.addLayout(head)

        # 主体：左文件 / 右参数
        main = QHBoxLayout()
        main.setSpacing(14)
        main.addWidget(self._build_files_card(), 5)
        main.addWidget(self._build_options_card(), 6)
        root.addLayout(main, 1)

        root.addWidget(self._build_action_card())

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(112)
        self.log.setPlaceholderText("运行日志…")
        root.addWidget(self.log)

    def _build_files_card(self) -> QFrame:
        frame, layout = card()
        layout.addWidget(section("待处理文件"))

        self.file_list = FileDropList(self._add_files)
        layout.addWidget(self.file_list, 1)

        buttons = QHBoxLayout()
        add = QPushButton("添加文件")
        add.clicked.connect(self._pick_files)
        remove = QPushButton("移除选中")
        remove.setObjectName("Ghost")
        remove.clicked.connect(self._remove_selected)
        clear = QPushButton("清空")
        clear.setObjectName("Ghost")
        clear.clicked.connect(self._clear_files)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(clear)
        layout.addLayout(buttons)

        self.files_hint = QLabel("尚未添加文件")
        self.files_hint.setObjectName("Hint")
        layout.addWidget(self.files_hint)
        return frame

    def _build_options_card(self) -> QFrame:
        frame, outer = card()
        outer.addWidget(section("压缩参数"))

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        # 质量档位
        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("质量档位"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(list(LEVEL_LABELS) + [CUSTOM_LABEL])
        self.level_combo.setCurrentIndex(2)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        level_row.addWidget(self.level_combo, 1)
        layout.addLayout(level_row)

        layout.addWidget(divider())
        layout.addWidget(section("图像"))

        self.dpi_row = SliderRow("目标 DPI", 0, 600, PRESETS[2][0], "dpi",
                                 self._mark_custom)
        self.dpi_min_row = SliderRow("阈值 DPI", 0, 600, PRESETS[2][0], "dpi",
                                     self._mark_custom)
        self.quality_row = SliderRow("质量", 0, 100, PRESETS[2][1], "",
                                     self._mark_custom)
        layout.addWidget(self.dpi_row)
        layout.addWidget(self.dpi_min_row)
        layout.addWidget(self.quality_row)

        encoder_row = QHBoxLayout()
        encoder_row.addWidget(QLabel("编码格式"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["JPEG（有损，质量生效）", "Flate / zlib（无损）"])
        self.encoder_combo.currentIndexChanged.connect(self._mark_custom)
        encoder_row.addWidget(self.encoder_combo, 1)
        layout.addLayout(encoder_row)

        dpi_hint = QLabel("目标 DPI = 0 时不降采样；当前 PPI ≤ 阈值 DPI 的图像会跳过降采样。")
        dpi_hint.setObjectName("Hint")
        dpi_hint.setWordWrap(True)
        layout.addWidget(dpi_hint)

        layout.addWidget(divider())
        layout.addWidget(section("结构清理（勾选 = 删除，取消勾选 = 保留）"))

        self.clean_checks: dict[str, QCheckBox] = {}
        for key, text in (
            ("pieceinfo", "应用私有数据 /PieceInfo"),
            ("thumbnail", "页面缩略图 /Thumb"),
            ("bookmarks", "书签 / 大纲 /Outlines"),
            ("attachments", "附件与嵌入文件 /Names"),
            ("annotations", "批注与表单 /Annots + /AcroForm"),
            ("metadata", "文档元数据（XMP / Info）"),
            ("unreferenced", "未被引用的对象"),
        ):
            box = QCheckBox(text)
            box.setChecked(True)
            box.stateChanged.connect(self._mark_custom)
            self.clean_checks[key] = box
            layout.addWidget(box)

        layout.addWidget(divider())
        layout.addWidget(section("高级"))

        self.font_check = QCheckBox("压缩内嵌字体")
        self.font_check.setChecked(True)
        self.font_check.stateChanged.connect(self._mark_custom)
        self.unembed_check = QCheckBox("取消内嵌字体（体积可能变大）")
        self.unembed_check.stateChanged.connect(self._mark_custom)
        self.content_check = QCheckBox("内容流压缩")
        self.content_check.setChecked(True)
        self.content_check.stateChanged.connect(self._mark_custom)
        self.image_check = QCheckBox("图像重编码")
        self.image_check.setChecked(True)
        self.image_check.stateChanged.connect(self._mark_custom)
        for box in (self.font_check, self.unembed_check,
                    self.content_check, self.image_check):
            layout.addWidget(box)

        jpeg_row = QHBoxLayout()
        jpeg_row.addWidget(QLabel("JPEG 编码模式"))
        self.jpeg_spin = QSpinBox()
        self.jpeg_spin.setRange(0, 8)
        self.jpeg_spin.setValue(1)
        self.jpeg_spin.setFixedWidth(84)
        self.jpeg_spin.valueChanged.connect(self._mark_custom)
        jpeg_row.addWidget(self.jpeg_spin)
        jpeg_hint = QLabel("库内部初值为 2（不重编码 JPEG），必须为 1 才启用图像重编码")
        jpeg_hint.setObjectName("Hint")
        jpeg_row.addWidget(jpeg_hint, 1)
        layout.addLayout(jpeg_row)

        self.dll_hint = QLabel()
        self.dll_hint.setObjectName("Hint")
        self.dll_hint.setWordWrap(True)
        layout.addWidget(divider())
        layout.addWidget(section("引擎"))
        layout.addWidget(self.dll_hint)
        pick_dll = QPushButton("手动选择 libPdfCore.dll")
        pick_dll.setObjectName("Ghost")
        pick_dll.clicked.connect(self._pick_dll)
        layout.addWidget(pick_dll)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inner)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        # 控件全部就绪后，把档位复位到推荐档（其值即当前各控件默认值）
        self._ready = True
        self.level_combo.setCurrentIndex(2)
        return frame

    def _build_action_card(self) -> QFrame:
        frame, layout = card()
        row = QHBoxLayout()
        row.setSpacing(12)

        self.same_dir_check = QCheckBox("输出到源文件同目录（追加 _optimized）")
        self.same_dir_check.setChecked(True)
        self.same_dir_check.stateChanged.connect(self._sync_output_state)
        row.addWidget(self.same_dir_check, 1)

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("输出目录…")
        self.out_edit.setEnabled(False)
        row.addWidget(self.out_edit, 2)
        self.out_button = QPushButton("选择目录")
        self.out_button.setObjectName("Ghost")
        self.out_button.setEnabled(False)
        self.out_button.clicked.connect(self._pick_out_dir)
        row.addWidget(self.out_button)
        layout.addLayout(row)

        progress_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        progress_row.addWidget(self.progress, 1)
        self.run_button = QPushButton("开始压缩")
        self.run_button.setObjectName("Primary")
        self.run_button.clicked.connect(self._start)
        progress_row.addWidget(self.run_button)
        layout.addLayout(progress_row)

        self.status = QLabel("就绪")
        self.status.setObjectName("Hint")
        layout.addWidget(self.status)
        return frame

    # -------------------------------------------------------------- 状态联动 --
    def _mark_custom(self, *_args) -> None:
        if not self._ready:
            return
        if self.level_combo.currentText() != CUSTOM_LABEL:
            self.level_combo.blockSignals(True)
            self.level_combo.setCurrentText(CUSTOM_LABEL)
            self.level_combo.blockSignals(False)
        self._sync_advanced_state()

    def _on_level_changed(self, index: int) -> None:
        if index >= len(PRESETS):
            return
        dpi, quality = PRESETS[index]
        for row, value in ((self.dpi_row, dpi), (self.dpi_min_row, dpi),
                           (self.quality_row, quality)):
            row.set_value(value)
        self._sync_advanced_state()

    def _sync_advanced_state(self) -> None:
        has_dpi = self.dpi_row.value() > 0
        self.dpi_min_row.set_enabled(has_dpi)
        self.quality_row.set_enabled(self.encoder_combo.currentIndex() == 0)
        if self.jpeg_spin.value() != 1:
            self.image_check.setToolTip("JPEG 编码模式不为 1 时，图像不会被重编码")
        else:
            self.image_check.setToolTip("")

    def _sync_output_state(self) -> None:
        same = self.same_dir_check.isChecked()
        self.out_edit.setEnabled(not same)
        self.out_button.setEnabled(not same)

    def _refresh_dll_state(self) -> None:
        if self._dll_path:
            self.dll_hint.setText(f"已找到引擎：{self._dll_path}")
            self.run_button.setEnabled(True)
        else:
            self.dll_hint.setText("未找到 libPdfCore.dll —— 请手动选择 PDFelement 安装目录下的该文件")
            self.run_button.setEnabled(False)

    # -------------------------------------------------------------- 文件队列 --
    def _add_files(self, paths: list[str]) -> None:
        added = 0
        for path in paths:
            path = os.path.abspath(path)
            if path.lower().endswith(".pdf") and path not in self._files:
                self._files.append(path)
                item = QListWidgetItem(f"{os.path.basename(path)}   ·   "
                                       f"{human_size(os.path.getsize(path))}")
                item.setData(Qt.UserRole, path)
                item.setToolTip(path)
                self.file_list.addItem(item)
                added += 1
        self._update_files_hint(added)

    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择 PDF 文件", "", PDF_FILTER)
        if paths:
            self._add_files(paths)

    def _remove_selected(self) -> None:
        for item in self.file_list.selectedItems():
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
            self._files.pop(row)
        self._update_files_hint()

    def _clear_files(self) -> None:
        self.file_list.clear()
        self._files.clear()
        self._update_files_hint()

    def _update_files_hint(self, added: int = 0) -> None:
        total = sum(os.path.getsize(p) for p in self._files if os.path.isfile(p))
        if self._files:
            text = f"共 {len(self._files)} 个文件 · {human_size(total)}"
            if added:
                text = f"已添加 {added} 个 · " + text
        else:
            text = "尚未添加文件（可直接把 PDF 拖进左侧列表）"
        self.files_hint.setText(text)

    def _pick_out_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.out_edit.setText(folder)

    def _pick_dll(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 libPdfCore.dll", "",
                                              "libPdfCore.dll (libPdfCore.dll);;所有文件 (*.*)")
        if not path:
            return
        remember(path)
        self._dll_path = path
        self._refresh_dll_state()
        self._log(f"已记住引擎路径：{path}")

    # ------------------------------------------------------------------ 参数 --
    def _options(self) -> OptimizeOptions:
        encoder = ENCODER_JPEG if self.encoder_combo.currentIndex() == 0 else ENCODER_FLATE
        keep = {key: not box.isChecked() for key, box in self.clean_checks.items()}
        return OptimizeOptions(
            dpi=self.dpi_row.value(),
            dpi_min=self.dpi_min_row.value(),
            quality=self.quality_row.value(),
            encoder=encoder,
            jpeg_mode=self.jpeg_spin.value(),
            keep_pieceinfo=keep["pieceinfo"],
            keep_thumbnail=keep["thumbnail"],
            keep_bookmarks=keep["bookmarks"],
            keep_attachments=keep["attachments"],
            keep_annotations=keep["annotations"],
            keep_metadata=keep["metadata"],
            keep_unreferenced=keep["unreferenced"],
            compress_fonts=self.font_check.isChecked(),
            unembed_fonts=self.unembed_check.isChecked(),
            compress_content=self.content_check.isChecked(),
            compress_images=self.image_check.isChecked(),
        )

    # ------------------------------------------------------------------ 执行 --
    def _start(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        if not self._files:
            QMessageBox.information(self, "提示", "请先添加要压缩的 PDF 文件。")
            return
        if not self._dll_path:
            QMessageBox.warning(self, "缺少引擎", "请先选择 libPdfCore.dll。")
            return

        out_dir = None if self.same_dir_check.isChecked() else (self.out_edit.text().strip() or None)
        if out_dir and not os.path.isdir(out_dir):
            QMessageBox.warning(self, "输出目录无效", f"目录不存在：{out_dir}")
            return

        jobs: list[tuple[str, str]] = []
        for src in self._files:
            dst = suggest_dst(src, out_dir)
            if os.path.normcase(dst) == os.path.normcase(src):
                dst = suggest_dst(src, out_dir, "_optimized2")
            jobs.append((src, dst))

        self.log.clear()
        self.progress.setValue(0)
        self._job_names = [os.path.basename(src) for src, _ in jobs]
        self.run_button.setEnabled(False)
        self.run_button.setText("压缩中…")
        self.status.setText(f"正在处理 {len(jobs)} 个文件…")

        self._worker = BatchWorker(jobs, self._options(), self._dll_path, self)
        self._worker.file_progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_progress(self, index: int, total: int, stage: str,
                     fraction: float) -> None:
        overall = (index + fraction) / max(total, 1)
        self.progress.setValue(int(overall * 1000))
        name = self._job_names[index] if index < len(self._job_names) else ""
        self.status.setText(f"[{index + 1}/{total}] {name} · {stage}")

    def _on_file_done(self, result) -> None:
        if result.ok:
            self._log(f"✓ {os.path.basename(result.src)}  "
                      f"{human_size(result.src_size)} → {human_size(result.dst_size)} "
                      f"（-{result.ratio * 100:.1f}%，{result.pages} 页）\n"
                      f"    输出：{result.dst}")
        else:
            self._log(f"✗ {os.path.basename(result.src)}  失败：{result.error}")

    def _on_all_done(self, results: list) -> None:
        ok = [r for r in results if r.ok]
        src_total = sum(r.src_size for r in ok)
        dst_total = sum(r.dst_size for r in ok)
        gain = (1 - dst_total / src_total) * 100 if src_total else 0.0
        self.progress.setValue(1000)
        self.status.setText(f"完成 {len(ok)}/{len(results)} 个 · "
                            f"{human_size(src_total)} → {human_size(dst_total)} · "
                            f"共节省 {gain:.1f}%")
        self._log(f"\n———— 全部完成：成功 {len(ok)}/{len(results)}，"
                  f"{human_size(src_total)} → {human_size(dst_total)}（-{gain:.1f}%）")
        self.run_button.setEnabled(True)
        self.run_button.setText("开始压缩")
        self._worker = None

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    # ------------------------------------------------------------ 关闭时收尾 --
    def closeEvent(self, event) -> None:                # noqa: N802
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)
        event.accept()
