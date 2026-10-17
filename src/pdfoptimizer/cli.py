"""命令行入口：pdfoptimizer <源.pdf> <输出.pdf> [选项]"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from .core import (ENCODER_FLATE, ENCODER_JPEG, MASK_ALL, PRESETS,
                   OptimizeOptions, PdfCoreEngine, suggest_dst)
from .dllfinder import resolve_dll


def _quality(text: str) -> int:
    value = int(text)
    if not 0 <= value <= 100:
        raise argparse.ArgumentTypeError("质量必须在 0..100 之间")
    return value


def _dpi(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("DPI 不能为负数")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdfoptimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="用 libPdfCore.dll 的原生优化压缩流水线处理 PDF（无需界面 / 无需登录）。",
        epilog="""质量档位（--level）：0=72dpi/45  1=96/55  2=120/70  3=150/85  4=300/95  5=600/100  6=1200/100

示例
  pdfoptimizer in.pdf out.pdf --level 0
  pdfoptimizer in.pdf out.pdf --dpi 150 --quality 85
  pdfoptimizer in.pdf out.pdf --dpi 0 --encoder 8          # 无损 zlib 重压
  pdfoptimizer in.pdf out.pdf --dll "D:\\PDFelement\\libPdfCore.dll"
""")
    parser.add_argument("src", metavar="源.pdf")
    parser.add_argument("dst", nargs="?", metavar="输出.pdf",
                        help="缺省时输出到源目录下 <原名>_optimized.pdf")
    parser.add_argument("-l", "--level", type=int, choices=range(len(PRESETS)),
                        metavar="0..6", help="质量档位预设（覆盖 --dpi / --quality）")
    parser.add_argument("--dpi", type=_dpi, metavar="N", help="目标图像 DPI（默认 120；0 = 不降采样）")
    parser.add_argument("--dpi-min", type=_dpi, metavar="N",
                        help="降采样阈值 DPI（默认 = --dpi）：当前 PPI ≤ N 的图像跳过降采样")
    parser.add_argument("--quality", type=_quality, metavar="N", help="重编码质量 0..100（默认 70）")
    parser.add_argument("--encoder", type=int, choices=(ENCODER_JPEG, ENCODER_FLATE), default=ENCODER_JPEG,
                        metavar="2|8", help="2 = DCTDecode/JPEG 有损（默认）；8 = FlateDecode 无损")
    parser.add_argument("--jpeg-mode", type=int, default=1, metavar="N",
                        help="SetImageJpegEncodeMode（默认 1；库初值 2 = 不重编码 JPEG）")
    parser.add_argument("--keep-pieceinfo", action="store_true", help="保留 /PieceInfo（默认删除）")
    parser.add_argument("--keep-thumbnail", action="store_true", help="保留 /Thumb 缩略图（默认删除）")
    parser.add_argument("--keep-bookmarks", action="store_true", help="保留 /Outlines 书签（默认删除）")
    parser.add_argument("--keep-attachments", action="store_true", help="保留 /Names 附件（默认删除）")
    parser.add_argument("--keep-annotations", action="store_true", help="保留 /Annots + /AcroForm（默认删除）")
    parser.add_argument("--remove-flags", type=int, metavar="N",
                        help=f"直接给删除掩码，覆盖上面五项（默认 {MASK_ALL:#x}；0 = 全保留）")
    parser.add_argument("--keep-metadata", action="store_true", help="保留元数据（默认删除）")
    parser.add_argument("--keep-unreferenced", action="store_true", help="保留未引用对象（默认删除）")
    parser.add_argument("--no-font-compress", action="store_true", help="不压缩内嵌字体")
    parser.add_argument("--unembed-fonts", action="store_true", help="取消内嵌字体")
    parser.add_argument("--no-content-compress", action="store_true", help="跳过内容流压缩")
    parser.add_argument("--no-image", action="store_true", help="跳过图像重编码")
    parser.add_argument("--slot", type=int, default=43, metavar="N", help="另存槽位（默认 43）")
    parser.add_argument("--dll", metavar="路径", help="显式指定 libPdfCore.dll")
    parser.add_argument("-q", "--quiet", action="store_true", help="只输出结果行")
    return parser


def options_from_args(args: argparse.Namespace) -> OptimizeOptions:
    base = OptimizeOptions(
        encoder=args.encoder,
        jpeg_mode=args.jpeg_mode,
        keep_pieceinfo=args.keep_pieceinfo,
        keep_thumbnail=args.keep_thumbnail,
        keep_bookmarks=args.keep_bookmarks,
        keep_attachments=args.keep_attachments,
        keep_annotations=args.keep_annotations,
        remove_mask=args.remove_flags,
        keep_metadata=args.keep_metadata,
        keep_unreferenced=args.keep_unreferenced,
        compress_fonts=not args.no_font_compress,
        unembed_fonts=args.unembed_fonts,
        compress_content=not args.no_content_compress,
        compress_images=not args.no_image,
        slot=args.slot,
    )
    if args.level is not None:
        dpi, quality = PRESETS[args.level]
        base = replace(base, dpi=dpi, quality=quality)
    else:
        base = replace(base,
                       dpi=120 if args.dpi is None else args.dpi,
                       quality=70 if args.quality is None else args.quality)
    if args.dpi_min is not None:
        base = replace(base, dpi_min=args.dpi_min)
    return base


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src = args.src
    dst = args.dst or suggest_dst(src)
    options = options_from_args(args)

    dll = resolve_dll(args.dll)
    if not dll:
        print("找不到 libPdfCore.dll，请用 --dll 指定，或设置环境变量 PDFOPTIMIZER_DLL",
              file=sys.stderr)
        return 2

    engine = PdfCoreEngine(dll)
    if not args.quiet:
        print(f"引擎: {dll}")
        print(f"参数: dpi={options.dpi} dpi_min={options.effective_dpi_min} "
              f"quality={options.quality} encoder={options.encoder} "
              f"jpeg_mode={options.jpeg_mode} mask={options.mask:#x}")

    def progress(stage: str, fraction: float) -> None:
        if not args.quiet:
            print(f"  [{fraction * 100:5.1f}%] {stage}")

    result = engine.optimize(src, dst, options, progress)
    if result.ok:
        print(f"完成: {dst}  {result.src_size} -> {result.dst_size} 字节 "
              f"(-{result.ratio * 100:.1f}%)  共 {result.pages} 页")
        return 0
    print(f"失败: {result.error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
