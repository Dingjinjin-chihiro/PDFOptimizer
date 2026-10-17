"""PyInstaller 打包入口（等价于 `python -m pdfoptimizer`）。

带参数时走命令行，无参数时启动图形界面。
"""

from pdfoptimizer.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
