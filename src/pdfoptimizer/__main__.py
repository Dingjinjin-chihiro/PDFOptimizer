"""``python -m pdfoptimizer``：无参数启动图形界面，带参数等价于命令行。"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        from .cli import main as cli_main
        return cli_main(args)
    from .ui import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
