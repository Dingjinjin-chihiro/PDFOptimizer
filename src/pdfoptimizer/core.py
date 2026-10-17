"""libPdfCore 原生优化压缩引擎封装（ctypes 驱动，无 GUI / 无 argparse 依赖）。

调用链（逆向结论见 docs/PDF优化压缩_逆向分析记录.md §8/§9）：
    CreateFactory -> factory[18] CreateDocument -> doc[5] Open
      -> doc[22] GetOptimizer -> 设置参数 -> 逐页 qhy/qhq -» doc[43] 另存

原生对象布局要点：
  * mav 流接口（实现给原生回调）：槽 0..12 = dtor/QI/AddRef/Release/CanRead/CanWrite/
    Flush/Length/SetLength/Read/Seek/Tell/Write
  * 优化器 128 B：+16 = 内部 80 B 优化对象，+24 = engine，
    +32/+64/+96 = 三组 32 B ReduceSampleData（彩色 / 灰度 / 单色）
  * ReduceSampleData: +0 downSampleMode, +4 targetDpi, +8 thresholdDpi,
    +12 encodeMode, +16 qualityEnum, +20 quality(float), +24 保留, +28 jpegEncodeMode
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from typing import Callable, Optional

from .dllfinder import resolve_dll

# --------------------------------------------------------------------------- #
# 常量与预设
# --------------------------------------------------------------------------- #

#: 质量档位预设：(目标 DPI, 质量)，索引 0..6 与 PDFelement 一致（0 压缩最狠）
PRESETS: tuple[tuple[int, int], ...] = (
    (72, 45), (96, 55), (120, 70), (150, 85), (300, 95), (600, 100), (1200, 100)
)

#: 图像编码模式（OptmImgEncodeModeEnum）：2 = DCTDecode/JPEG 有损，8 = FlateDecode 无损
ENCODER_JPEG = 2
ENCODER_FLATE = 8

#: RemoveUnimportantNodes 删除掩码位（mac 符号定名）
MASK_PIECEINFO = 0x01    # /PieceInfo 应用私有数据
MASK_THUMBNAIL = 0x02    # /Thumb 页面缩略图
MASK_BOOKMARKS = 0x04    # /Outlines 书签 / 大纲
MASK_ATTACHMENTS = 0x08  # /Names(/EmbeddedFiles) 附件 + FileAttachment 批注
MASK_ANNOTATIONS = 0x10  # /Annots 批注 + /AcroForm(/Fields) 表单字段
MASK_ALL = 0x1F

#: 是否在每次任务结束后释放原生对象（减少长批量任务的内存占用）
RELEASE_OBJECTS = True

#: native Stream 回调是否打印（调试用）
TRACE_STREAMS = False

ProgressFn = Callable[[str, float], None]      # (阶段描述, 0.0~1.0)


# --------------------------------------------------------------------------- #
# 参数与结果
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class OptimizeOptions:
    """界面端「优化压缩」的全部可选参数。"""

    # —— 图像（ReduceSampleData）——
    dpi: int = 120                       # targetDpi；0 = 完全不降采样
    dpi_min: Optional[int] = None        # thresholdDpi；None = 同 dpi
    quality: int = 70                    # +20 显式质量 0..100（仅 JPEG 编码生效）
    encoder: int = ENCODER_JPEG          # +12 编码模式
    jpeg_mode: int = 1                   # +28 OptImgEncodeJpegModeEnum；库初值 2 = 不重编码

    # —— 结构清理（默认全部执行，keep_* 为 True 表示保留）——
    keep_pieceinfo: bool = False
    keep_thumbnail: bool = False
    keep_bookmarks: bool = False
    keep_attachments: bool = False
    keep_annotations: bool = False
    keep_metadata: bool = False
    keep_unreferenced: bool = False
    remove_mask: Optional[int] = None    # 直接给定掩码（优先级高于上面 5 个 keep_*）

    # —— 字体 / 内容流 / 图像 ——
    compress_fonts: bool = True          # 槽 14 EnableFontMerge + 槽 15 EnableFontSplite
    unembed_fonts: bool = False          # 槽 21 GetCancelableEmbeddedFonts -> 槽 22 CancelFontsEmbedded
    compress_content: bool = True        # 逐页 qhq（内容流）
    compress_images: bool = True         # 逐页 qhy（图像重编码）

    slot: int = 43                       # 另存槽位（43 = 唯一体现优化器改动的写出路径）

    @property
    def mask(self) -> int:
        if self.remove_mask is not None:
            return self.remove_mask
        m = 0
        if not self.keep_pieceinfo:
            m |= MASK_PIECEINFO
        if not self.keep_thumbnail:
            m |= MASK_THUMBNAIL
        if not self.keep_bookmarks:
            m |= MASK_BOOKMARKS
        if not self.keep_attachments:
            m |= MASK_ATTACHMENTS
        if not self.keep_annotations:
            m |= MASK_ANNOTATIONS
        return m

    @property
    def effective_dpi_min(self) -> int:
        return self.dpi if self.dpi_min is None else self.dpi_min

    @property
    def down_sample_enabled(self) -> bool:
        return self.dpi > 0

    @classmethod
    def from_preset(cls, level: int, **overrides) -> "OptimizeOptions":
        level = max(0, min(level, len(PRESETS) - 1))
        dpi, quality = PRESETS[level]
        return cls(dpi=dpi, quality=quality, **overrides)


@dataclass
class OptimizeResult:
    src: str
    dst: str
    ok: bool = False
    src_size: int = 0
    dst_size: int = 0
    pages: int = 0
    error: str = ""

    @property
    def ratio(self) -> float:
        """压缩率：正数表示变小。"""
        if not self.src_size or not self.dst_size:
            return 0.0
        return 1.0 - self.dst_size / self.src_size


# --------------------------------------------------------------------------- #
# ctypes 基础设施
# --------------------------------------------------------------------------- #

def _vtbl(ptr: int) -> int:
    return ctypes.cast(ctypes.c_void_p(ptr), ctypes.POINTER(ctypes.c_void_p)).contents.value


def _slot(ptr: int, index: int) -> int:
    vt = _vtbl(ptr)
    return ctypes.cast(ctypes.c_void_p(vt + index * 8),
                       ctypes.POINTER(ctypes.c_void_p)).contents.value


def _call(ptr: int, index: int, restype, argtypes=(), args=()):
    """按原生 vtable 槽位调用（第 0 参数恒为 this）。"""
    fn = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(_slot(ptr, index))
    return fn(ptr, *args)


def _release(obj: int) -> None:
    """调用原生对象槽 3 = Release（失败不影响主流程）。"""
    if not obj or not RELEASE_OBJECTS:
        return
    try:
        _call(obj, 3, ctypes.c_size_t)
    except Exception:
        pass


class Stream:
    """实现原生 mav 接口（槽 0..12），把文件映射成回调。"""

    NAMES = ("dtor", "qi", "addref", "release", "canread", "canwrite", "flush",
             "length", "setlength", "read", "seek", "tell", "write")

    def __init__(self, path: str, mode: str) -> None:
        self.path = path
        self.mode = mode
        self.file = open(path, mode)
        self._callbacks: list = []
        self.calls: list[str] = []

        vt = (ctypes.c_void_p * 13)()

        def put(index: int, restype, argtypes, impl) -> None:
            name = self.NAMES[index]

            def wrapper(*args):
                if name not in ("addref", "release"):
                    self.calls.append(name)
                    if TRACE_STREAMS:
                        print(f"      [stream] {name}")
                return impl(*args)

            cb = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(wrapper)
            self._callbacks.append(cb)
            vt[index] = ctypes.cast(cb, ctypes.c_void_p).value

        put(0, None, [], lambda t: None)                                        # dtor
        put(1, ctypes.c_int, [ctypes.c_void_p, ctypes.c_void_p], self._qi)      # QI
        put(2, ctypes.c_size_t, [], lambda t: 2)                                # AddRef
        put(3, ctypes.c_size_t, [], lambda t: 1)                                # Release
        put(4, ctypes.c_int, [], lambda t: 1)                                   # CanRead
        put(5, ctypes.c_int, [], self._can_write)                               # CanWrite
        put(6, ctypes.c_int, [], self._can_write)                               # Flush
        put(7, ctypes.c_int64, [], self._length)                                # Length
        put(8, None, [ctypes.c_int64], self._set_length)                        # SetLength
        put(9, ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_size_t], self._read)
        put(10, ctypes.c_int64, [ctypes.c_int64, ctypes.c_int], self._seek)
        put(11, ctypes.c_int64, [], self._tell)
        put(12, ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_size_t], self._write)

        self._vt = vt
        self._buf = ctypes.create_string_buffer(ctypes.sizeof(ctypes.c_void_p))
        ctypes.cast(self._buf, ctypes.POINTER(ctypes.c_void_p))[0] = \
            ctypes.cast(vt, ctypes.c_void_p).value
        self.ptr: int = ctypes.cast(self._buf, ctypes.c_void_p).value

    # —— 回调实现 ——
    def _qi(self, t, iid, ppv):
        ctypes.cast(ctypes.c_void_p(ppv), ctypes.POINTER(ctypes.c_void_p))[0] = 0
        return -2147467262                # E_NOINTERFACE

    def _can_write(self, t) -> int:
        return 1 if ("w" in self.mode or "+" in self.mode) else 0

    def _length(self, t) -> int:
        pos = self.file.tell()
        self.file.seek(0, 2)
        size = self.file.tell()
        self.file.seek(pos)
        return size

    def _set_length(self, t, size: int) -> None:
        self.file.truncate(size)

    def _read(self, t, buf, count: int) -> int:
        data = self.file.read(count)
        if data:
            ctypes.memmove(buf, data, len(data))
        return len(data)

    def _seek(self, t, offset: int, origin: int) -> int:
        return self.file.seek(offset, origin)

    def _tell(self, t) -> int:
        return self.file.tell()

    def _write(self, t, buf, count: int) -> int:
        self.file.write(ctypes.string_at(buf, count))
        return count

    def close(self) -> None:
        try:
            self.file.flush()
        except Exception:
            pass
        try:
            self.file.close()
        except Exception:
            pass


class SaveOptions:
    """实现另存槽 43 需要的 mgy 对象（槽 4..10）。"""

    def __init__(self, flags: int = 1, big: int = 100) -> None:
        self._callbacks: list = []
        vt = (ctypes.c_void_p * 11)()

        def put(index: int, restype, argtypes, impl) -> None:
            cb = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(impl)
            self._callbacks.append(cb)
            vt[index] = ctypes.cast(cb, ctypes.c_void_p).value

        put(0, None, [], lambda t: None)
        put(1, ctypes.c_int, [ctypes.c_void_p, ctypes.c_void_p], self._qi)
        put(2, ctypes.c_size_t, [], lambda t: 1)                       # AddRef
        put(3, ctypes.c_size_t, [], lambda t: 1)                       # Release
        put(4, ctypes.c_int, [], lambda t: 3)                          # qh2
        put(5, ctypes.c_int, [], lambda t: flags)                      # qh9
        put(6, ctypes.c_int, [], lambda t: flags)                      # qhg
        put(7, ctypes.c_int, [], lambda t: flags)                      # qhn
        put(8, ctypes.c_int, [], lambda t: big)                        # qhu
        put(9, None, [ctypes.c_void_p, ctypes.c_void_p], self._q1)     # qh1(out,out)
        put(10, ctypes.c_int, [], lambda t: flags)                     # qh8

        self._vt = vt
        self._buf = ctypes.create_string_buffer(ctypes.sizeof(ctypes.c_void_p))
        ctypes.cast(self._buf, ctypes.POINTER(ctypes.c_void_p))[0] = \
            ctypes.cast(vt, ctypes.c_void_p).value
        self.ptr: int = ctypes.cast(self._buf, ctypes.c_void_p).value

    def _qi(self, t, iid, ppv):
        ctypes.cast(ctypes.c_void_p(ppv), ctypes.POINTER(ctypes.c_void_p))[0] = 0
        return -2147467262

    def _q1(self, t, a, b):
        ctypes.cast(ctypes.c_void_p(a), ctypes.POINTER(ctypes.c_int))[0] = 1
        ctypes.cast(ctypes.c_void_p(b), ctypes.POINTER(ctypes.c_int))[0] = 7


# --------------------------------------------------------------------------- #
# 引擎
# --------------------------------------------------------------------------- #

class PdfCoreEngine:
    """libPdfCore.dll 的薄封装（线程内串行使用）。"""

    _dll: Optional[ctypes.WinDLL] = None
    _dll_path: Optional[str] = None

    def __init__(self, dll_path: Optional[str] = None) -> None:
        self.dll_path = dll_path or resolve_dll()

    # —— DLL ——
    def _load(self) -> ctypes.WinDLL:
        cls = type(self)
        if cls._dll is not None and (self.dll_path is None or cls._dll_path == self.dll_path):
            return cls._dll
        if not self.dll_path or not os.path.isfile(self.dll_path):
            raise FileNotFoundError(f"找不到 libPdfCore.dll：{self.dll_path!r}")
        dll = ctypes.WinDLL(self.dll_path, winmode=0x8)
        dll.CreateFactory.restype = ctypes.c_void_p
        dll.CreateFactory.argtypes = []
        cls._dll = dll
        cls._dll_path = self.dll_path
        return dll

    # —— 主流程 ——
    def optimize(self, src: str, dst: str, options: OptimizeOptions,
                 progress: Optional[ProgressFn] = None) -> OptimizeResult:
        def report(stage: str, fraction: float) -> None:
            if progress:
                progress(stage, max(0.0, min(fraction, 1.0)))

        result = OptimizeResult(src=src, dst=dst)
        try:
            result.src_size = os.path.getsize(src)
        except OSError as exc:
            result.error = f"源文件不可读：{exc}"
            return result

        report("加载引擎", 0.02)
        try:
            dll = self._load()
        except Exception as exc:                       # noqa: BLE001
            result.error = str(exc)
            return result

        factory = doc = pages = optimizer = 0
        stream_in = stream_out = None
        try:
            factory = dll.CreateFactory()
            if not factory:
                result.error = "CreateFactory 返回空"
                return result

            doc = _call(factory, 18, ctypes.c_void_p)
            if not doc:
                result.error = "CreateDocument 返回空"
                return result

            report("打开文档", 0.06)
            stream_in = Stream(src, "rb")
            pwd = ctypes.create_string_buffer(1)        # 口令指针必须非空
            open_res = _call(doc, 5, ctypes.c_int,
                             (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64),
                             (stream_in.ptr, ctypes.addressof(pwd), 0))
            if open_res != 1:
                names = {0: "Failed", 1: "Success", 2: "FormatError",
                         3: "SecurityError", 4: "NeedPassword"}
                result.error = f"打开失败：{names.get(open_res, open_res)}"
                return result

            optimizer = _call(doc, 22, ctypes.c_void_p)
            pages = _call(doc, 10, ctypes.c_void_p)
            page_count = _call(pages, 4, ctypes.c_size_t) if pages else 0
            result.pages = int(page_count)

            if optimizer:
                report("设置优化参数", 0.12)
                self._apply_options(optimizer, options)

                report("逐页优化", 0.20)
                self._process_pages(doc, optimizer, pages, page_count, options,
                                    lambda i, n: report(f"逐页优化 {i}/{n}",
                                                        0.20 + 0.55 * (i / max(n, 1))))
            else:
                report("跳过优化参数（引擎未提供优化器）", 0.5)

            report("写出文件", 0.82)
            stream_out = Stream(dst, "w+b")
            ok = self._save(doc, stream_out, options)
            stream_out.close()
            if not ok:
                result.error = f"另存槽 {options.slot} 返回失败"
                if os.path.exists(dst) and os.path.getsize(dst) < 1024:
                    os.remove(dst)
                return result

            result.dst_size = os.path.getsize(dst) if os.path.exists(dst) else 0
            result.ok = result.dst_size > 0
            if not result.ok:
                result.error = "输出文件为空"
            report("完成", 1.0)
        except Exception as exc:                        # noqa: BLE001
            result.error = f"{type(exc).__name__}: {exc}"
        finally:
            # 先释放原生对象（其析构可能回调我们的流对象），再关闭 Python 文件句柄
            _release(optimizer)
            _release(pages)
            _release(doc)
            _release(factory)
            if stream_in is not None:
                stream_in.close()
        return result

    # —— 参数装配 ——
    @staticmethod
    def _apply_options(optimizer: int, o: OptimizeOptions) -> None:
        scale = 1 if o.down_sample_enabled else 0
        dpi_min = o.effective_dpi_min
        # 槽 6/7/8 = SetColor/Gray/MonoImageParameter(下采样模式, 目标DPI, 阈值DPI, 编码模式, 质量档位)
        for slot in (6, 7, 8):
            _call(optimizer, slot, ctypes.c_int, (ctypes.c_int,) * 5,
                  (scale, o.dpi, dpi_min, o.encoder, 0))
        # 槽 17/18 = SetColor/GrayImageQuality(显式质量浮点)
        _call(optimizer, 17, None, (ctypes.c_int,), (o.quality,))
        _call(optimizer, 18, None, (ctypes.c_int,), (o.quality,))
        # 槽 19 = SetImageJpegEncodeMode（库初值 2 = 不重编码 JPEG，必须显式设 1）
        _call(optimizer, 19, None, (ctypes.c_int,), (o.jpeg_mode,))
        # 槽 16 = RemoveInvalidateNodes 的档位
        _call(optimizer, 16, None, (ctypes.c_int,), (0,))
        # 槽 23 = 清理不可达导航/动作节点（Dests/OpenAction/AA）
        if not o.keep_unreferenced:
            _call(optimizer, 23, ctypes.c_int)
        # 槽 12 = RemoveMetadata
        if not o.keep_metadata:
            _call(optimizer, 12, ctypes.c_int)
        # 槽 20 = RemoveUnimportantNodes(掩码)
        if o.mask:
            _call(optimizer, 20, ctypes.c_int, (ctypes.c_int,), (o.mask,))
        # 槽 14/15 = EnableFontMerge / EnableFontSplite
        if o.compress_fonts:
            _call(optimizer, 14, None, (ctypes.c_int,), (1,))
            _call(optimizer, 15, None, (ctypes.c_int,), (1,))
        # 槽 21 -> 槽 22 = 取消内嵌字体
        if o.unembed_fonts:
            fonts = _call(optimizer, 21, ctypes.c_void_p)
            if fonts:
                _call(optimizer, 22, ctypes.c_int, (ctypes.c_void_p,), (fonts,))

    @staticmethod
    def _process_pages(doc: int, optimizer: int, pages: int, page_count: int,
                       o: OptimizeOptions, tick: Callable[[int, int], None]) -> None:
        for index in range(page_count):
            page = _call(pages, 6, ctypes.c_void_p, (ctypes.c_size_t,), (index,))
            if page:
                if o.compress_images:      # 槽 9  = ReduceImagesSize
                    _call(optimizer, 9, ctypes.c_int,
                          (ctypes.c_void_p, ctypes.c_int), (page, 1))
                if o.compress_content:     # 槽 13 = ReduceContentStream
                    _call(optimizer, 13, ctypes.c_int,
                          (ctypes.c_void_p, ctypes.c_int), (page, 1))
            tick(index + 1, page_count)

    @staticmethod
    def _save(doc: int, stream_out: Stream, o: OptimizeOptions) -> bool:
        if o.slot == 43:
            save_options = _call(doc, 11, ctypes.c_void_p)     # qwo() 保存选项对象
            mgy = SaveOptions()
            return bool(_call(doc, 43, ctypes.c_int, (ctypes.c_void_p,) * 4,
                              (stream_out.ptr, mgy.ptr, save_options, None)))
        if o.slot == 7:
            return bool(_call(doc, 7, ctypes.c_int,
                              (ctypes.c_void_p, ctypes.c_void_p), (stream_out.ptr, None)))
        if o.slot == 8:
            return bool(_call(doc, 8, ctypes.c_int, (ctypes.c_void_p,) * 3,
                              (stream_out.ptr, None, None)))
        if o.slot == 24:
            return bool(_call(doc, 24, ctypes.c_int,
                              (ctypes.c_void_p, ctypes.c_void_p), (stream_out.ptr, None)))
        raise ValueError(f"未知另存槽位：{o.slot}")


# --------------------------------------------------------------------------- #
# 便捷函数
# --------------------------------------------------------------------------- #

def optimize(src: str, dst: str, options: Optional[OptimizeOptions] = None,
             dll_path: Optional[str] = None,
             progress: Optional[ProgressFn] = None) -> OptimizeResult:
    """单文件优化压缩（同步调用；界面端请放在工作线程里）。"""
    return PdfCoreEngine(dll_path).optimize(src, dst, options or OptimizeOptions(), progress)


def suggest_dst(src: str, out_dir: Optional[str] = None, suffix: str = "_optimized") -> str:
    """默认输出路径：<原名><suffix>.pdf（可指定输出目录）。"""
    base, _ = os.path.splitext(os.path.basename(src))
    folder = out_dir or os.path.dirname(os.path.abspath(src))
    return os.path.join(folder, f"{base}{suffix}.pdf")
