"""PDFOptimizer —— 基于 PDFelement 的 libPdfCore.dll 的优化压缩工具。

对外暴露的公共接口：

    from pdfoptimizer import OptimizeOptions, optimize, PRESETS

    result = optimize("in.pdf", "out.pdf", OptimizeOptions.from_preset(0))
"""

from .core import (
    ENCODER_FLATE,
    ENCODER_JPEG,
    MASK_ALL,
    MASK_ANNOTATIONS,
    MASK_ATTACHMENTS,
    MASK_BOOKMARKS,
    MASK_PIECEINFO,
    MASK_THUMBNAIL,
    PRESETS,
    OptimizeOptions,
    OptimizeResult,
    PdfCoreEngine,
    optimize,
    suggest_dst,
)
from .dllfinder import resolve_dll

__version__ = "1.0.0"

__all__ = [
    "PRESETS", "OptimizeOptions", "OptimizeResult", "PdfCoreEngine",
    "optimize", "suggest_dst", "resolve_dll",
    "ENCODER_JPEG", "ENCODER_FLATE",
    "MASK_PIECEINFO", "MASK_THUMBNAIL", "MASK_BOOKMARKS",
    "MASK_ATTACHMENTS", "MASK_ANNOTATIONS", "MASK_ALL",
    "__version__",
]
