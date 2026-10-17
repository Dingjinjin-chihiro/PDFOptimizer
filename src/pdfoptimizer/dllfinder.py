"""运行期定位 libPdfCore.dll（不硬编码任何机器路径）。

搜索顺序：
  1. 环境变量 ``PDFOPTIMIZER_DLL``
  2. 上次记住的路径（%APPDATA%\\PDFOptimizer\\settings.json，界面里可选文件后写入）
  3. 程序自身所在目录 / vendor 子目录（打包分发时随 exe 一起放）
  4. 注册表（HKLM/HKCU）Wondershare\\PDFelement 的安装路径
  5. 常见安装目录与 Program Files 下的 PDFelement* 目录
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

DLL_NAME = "libPdfCore.dll"
ENV_VAR = "PDFOPTIMIZER_DLL"

_SETTINGS_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "PDFOptimizer"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"


# --------------------------------------------------------------------------- #
# 记住的路径
# --------------------------------------------------------------------------- #

def load_remembered() -> Optional[str]:
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        return None
    path = data.get("dll_path")
    return path if path and os.path.isfile(path) else None


def remember(path: str) -> None:
    if not path:
        return
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        data = {}
        if _SETTINGS_FILE.is_file():
            try:
                data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:                           # noqa: BLE001
                data = {}
        data["dll_path"] = os.path.abspath(path)
        _SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    except Exception:                                   # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
# 候选路径
# --------------------------------------------------------------------------- #

def _app_dir() -> Path:
    """打包后 = exe 目录；源码运行 = 项目根目录。"""
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def _registry_dirs() -> list[str]:
    dirs: list[str] = []
    try:
        import winreg
    except ImportError:
        return dirs
    keys = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wondershare\PDFelement"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Wondershare\PDFelement"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Wondershare\PDFelement"),
    )
    value_names = ("InstallPath", "InstallDir", "Path", "AppPath", "InstallLocation")
    for root, sub in keys:
        try:
            with winreg.OpenKey(root, sub) as handle:
                count = winreg.QueryInfoKey(handle)[1]
                for i in range(count):
                    name, value, _ = winreg.EnumValue(handle, i)
                    if name in value_names and isinstance(value, str):
                        dirs.append(value)
        except OSError:
            continue
    return dirs


def _pf_dirs() -> list[str]:
    dirs: list[str] = []
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.environ.get(env)
        if not root:
            continue
        base = Path(root)
        for pattern in ("Wondershare/PDFelement*", "Wondershare/PDFelement*/*",
                        "PDFelement*", "PDFelement*/*"):
            try:
                dirs.extend(str(p) for p in base.glob(pattern) if p.is_dir())
            except OSError:
                continue
    # 便携版常见落点：桌面 / 下载
    for env in ("USERPROFILE",):
        root = os.environ.get(env)
        if not root:
            continue
        for sub in ("Desktop", "Downloads"):
            base = Path(root) / sub
            if not base.is_dir():
                continue
            for pattern in ("*PDFelement*", "*PDFelement*/*", "*PDFelement*/*/*"):
                try:
                    dirs.extend(str(p) for p in base.glob(pattern) if p.is_dir())
                except OSError:
                    continue
    return dirs


def candidates() -> list[str]:
    """按优先级给出所有候选 DLL 路径。"""
    out: list[str] = []

    env = os.environ.get(ENV_VAR)
    if env:
        out.append(env)

    saved = load_remembered()
    if saved:
        out.append(saved)

    app = _app_dir()
    out.extend([str(app / DLL_NAME), str(app / "vendor" / DLL_NAME),
                str(app / "resources" / DLL_NAME)])

    for folder in _registry_dirs() + _pf_dirs():
        p = Path(folder)
        out.extend([str(p / DLL_NAME), str(p / "lib" / DLL_NAME),
                    str(p / "PDFelement" / DLL_NAME),
                    str(p / "App" / "PDFelement" / DLL_NAME)])

    seen: set[str] = set()
    unique: list[str] = []
    for path in out:
        norm = os.path.normcase(os.path.abspath(path))
        if norm not in seen:
            seen.add(norm)
            unique.append(os.path.abspath(path))
    return unique


def resolve_dll(explicit: Optional[str] = None) -> Optional[str]:
    """返回第一个真实存在的候选路径；都找不到返回 None。"""
    if explicit and os.path.isfile(explicit):
        return os.path.abspath(explicit)
    for path in candidates():
        if os.path.isfile(path):
            return path
    return None
