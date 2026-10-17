# PDFOptimizer

直接驱动 **PDFelement** 的原生 PDF 引擎 `libPdfCore.dll` 做**优化压缩**的桌面工具与命令行工具。
不需要打开 PDFelement，也不需要登录账号 —— 只用到它自带的那个唯一导出入口 `CreateFactory`。

* 图形界面：PySide6（深色主题、拖拽多文件批处理、进度与日志）
* 命令行：`python -m pdfoptimizer …`
* 参数全部可调：目标/阈值 DPI、重编码质量、编码格式（JPEG 有损 / Flate 无损）、结构清理项、字体与内容流开关

> ⚠️ **本项目不包含也不分发 `libPdfCore.dll`。** 该文件是 Wondershare PDFelement 的商业组件，
> 你需要自行安装 PDFelement（或已有其安装包），本工具会在运行期自动定位它；
> 这是为了与你自己已授权的软件互操作。请自行确认符合你所在地法律与软件许可协议。

---

## 1. 效果

| 输入 | 参数 | 输出 |
|---|---|---|
| 中文扫描合并件 9 372 601 B / 17 页 | `--level 0` | **862 215 B（−90.8 %）** |
| 同上 | `--level 2` | 2 217 309 B（−76.3 %） |
| 小样本 11 051 B / 1 张 JPEG | `--level 0` | 4 815 B（−56.4 %，图像 364→273 px 重编码） |

---

## 2. 环境要求

* Windows 10/11 x64
* Python **3.12 ~ 3.14**（本项目在 3.14.6 上验证）
* 已安装 PDFelement（提供 `libPdfCore.dll`）

依赖被**精确锁定**在 `pyproject.toml`：

```
PySide6==6.11.2                    # 唯一支持 Python 3.14 的稳定线
pyinstaller==6.11.0                # 可选，仅打包 exe 时需要
```

## 3. 安装

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

若你在国内网络下安装缓慢，可临时加代理：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7897"; $env:HTTPS_PROXY="http://127.0.0.1:7897"
```

## 4. 使用

### 图形界面

```powershell
.venv\Scripts\pythonw.exe -m pdfoptimizer
```

左栏拖入 PDF（可多选批量），右栏选档位或自定义参数，底部选输出位置后点「开始压缩」。

### 命令行

```powershell
.venv\Scripts\python -m pdfoptimizer <源.pdf> [输出.pdf] [选项]
```

省略输出时写到源文件同目录的 `<原名>_optimized.pdf`。

#### 质量档位 `-l/--level 0..6`

| 档位 | 目标 DPI | 质量 | 说明 |
|---|---|---|---|
| 0 | 72 | 45 | 极致压缩 |
| 1 | 96 | 55 | 强压缩 |
| 2 | 120 | 70 | 推荐（默认） |
| 3 | 150 | 85 | 轻压缩 |
| 4 | 300 | 95 | 高质量 |
| 5 | 600 | 100 | 近无损 |
| 6 | 1200 | 100 | 仅结构清理 |

#### 全部可选参数

| 参数 | 取值 | 默认 | 效果 |
|---|---|---|---|
| `--dpi N` | ≥0 | 120 | 目标图像 DPI；**仅当图像自带 PPI 大于 N 才降采样**；`0` = 一律不降采样 |
| `--dpi-min N` | ≥0 | = `--dpi` | 降采样阈值 DPI：当前 PPI ≤ N 的图像直接跳过降采样 |
| `--quality N` | 0–100 | 70 | 图像重编码质量，越小文件越小；仅 `--encoder 2` 生效 |
| `--encoder 2\|8` | 2 / 8 | 2 | `2` = DCTDecode/JPEG 有损；`8` = FlateDecode/zlib 无损（此时质量无效） |
| `--jpeg-mode N` | 整数 | 1 | 引擎内部 JPEG 编码模式；**库初值为 2（不重编码），必须为 1 图像参数才生效** |
| `--keep-pieceinfo` | 开关 | 删除 | 保留 `/PieceInfo`（应用私有数据） |
| `--keep-thumbnail` | 开关 | 删除 | 保留 `/Thumb` 页面缩略图 |
| `--keep-bookmarks` | 开关 | 删除 | 保留 `/Outlines` 书签/大纲 |
| `--keep-attachments` | 开关 | 删除 | 保留 `/Names`(`/EmbeddedFiles`) 附件与 FileAttachment 批注 |
| `--keep-annotations` | 开关 | 删除 | 保留 `/Annots` 批注与 `/AcroForm`(`/Fields`) 表单字段 |
| `--remove-flags N` | 位掩码 | `0x1F` | 直接给删除掩码（`0x01` `/PieceInfo`、`0x02` `/Thumb`、`0x04` `/Outlines`、`0x08` `/Names`、`0x10` `/Annots`+`/AcroForm`）；`0` = 全保留 |
| `--keep-metadata` | 开关 | 删除 | 保留 XMP / Info 元数据 |
| `--keep-unreferenced` | 开关 | 删除 | 保留不可达的导航/动作节点（`Dests`/`OpenAction`/`AA`） |
| `--no-font-compress` | 开关 | 压缩 | 不压缩内嵌字体 |
| `--unembed-fonts` | 开关 | 否 | 取消内嵌字体（体积可能变大） |
| `--no-content-compress` | 开关 | 压缩 | 跳过逐页内容流压缩 |
| `--no-image` | 开关 | 重编码 | 跳过逐页图像重编码 |
| `--slot N` | 整数 | 43 | 另存槽位（43 是唯一体现优化器改动的写出路径） |
| `--dll 路径` | 路径 | 自动 | 显式指定 `libPdfCore.dll` |
| `-q/--quiet` | 开关 | 详细 | 只输出结果行 |

#### 常用示例

```powershell
# 最大压缩
python -m pdfoptimizer in.pdf out.pdf --level 0

# 降到 150dpi、质量 85，其余默认
python -m pdfoptimizer in.pdf out.pdf --dpi 150 --quality 85

# 无损重压（zlib），不降采样
python -m pdfoptimizer in.pdf out.pdf --dpi 0 --encoder 8

# 只清结构，完全不动图像与内容流
python -m pdfoptimizer in.pdf out.pdf --no-image --no-content-compress --no-font-compress

# 原样另存（取基准体积）
python -m pdfoptimizer in.pdf out.pdf --remove-flags 0 --keep-metadata \
    --keep-unreferenced --no-image --no-content-compress --no-font-compress
```

### 在 Python 里当库用

```python
from pdfoptimizer import OptimizeOptions, optimize

result = optimize("in.pdf", "out.pdf", OptimizeOptions.from_preset(0))
print(result.ok, result.src_size, result.dst_size, f"{-result.ratio:.1%}")
```

---

## 5. 引擎定位（不需要手工配路径）

运行期按以下顺序找 `libPdfCore.dll`：

1. 环境变量 `PDFOPTIMIZER_DLL`
2. 上次记住的路径 `%APPDATA%\PDFOptimizer\settings.json`（界面里手动选一次即记住）
3. 程序自身目录 / `vendor` 子目录（自己打包分发时用）
4. 注册表 `Wondershare\PDFElement` 的安装路径
5. `Program Files` / 桌面 / 下载 下的 `PDFelement*` 目录

都找不到时，界面会提示并允许你手动选择该 DLL。

---

## 6. 项目结构

```
pyproject.toml                    依赖锁定
docs/PDF优化压缩_逆向分析记录.md    完整的逆向分析记录（见下）
src/pdfoptimizer/
  core.py                         ctypes 驱动内核：Stream/SaveOptions/PdfCoreEngine/OptimizeOptions
  dllfinder.py                    libPdfCore.dll 运行期定位
  cli.py                          命令行入口
  __main__.py                     无参启动界面，带参走命令行
  ui/theme.py                     深色现代主题（QSS）
  ui/worker.py                    QThread 批量工作线程（信号回传进度）
  ui/main_window.py               主窗口
```

---

## 7. 实现原理（简述，完整过程见 docs）

`libPdfCore.dll` 是**无符号**的，只有一个导出 `CreateFactory`。整个调用链靠逆向得到：

```
CreateFactory
  └─ factory[18]  CreateDocument            → 文档对象
       ├─ doc[5]  Open(输入流, 口令, 0)       → OpenResult
       ├─ doc[22] GetOptimizer               → 128 B 优化器
       │    ├─ 三组 32 B 参数块 @ +32/+64/+96（彩色/灰度/单色）
       │    ├─ 槽 6/7/8  Set{Color,Gray,Mono}ImageParameter(下采样模式,目标DPI,阈值DPI,编码模式,质量档位)
       │    ├─ 槽 17/18 Set{Color,Gray}ImageQuality(显式质量浮点)
       │    ├─ 槽 19    SetImageJpegEncodeMode(库初值 2 = 不重编码)
       │    ├─ 槽 12    RemoveMetadata      槽 23 清理 Dests/OpenAction/AA
       │    ├─ 槽 20    RemoveUnimportantNodes(掩码)
       │    └─ 槽 14/15 EnableFontMerge / EnableFontSplite
       ├─ 逐页 doc[10] → pages[6] → opt[9] ReduceImagesSize / opt[13] ReduceContentStream
       └─ doc[43] ApplyOptimizedAndSave(输出流, mgy, 保存选项, 进度)
```

关键坑（详见 docs 文档第 9 节）：

* 图像重编码的总开关其实是 `SetImageJpegEncodeMode`，**库对象初值为 2（不重编码）**；
  不把它设成 `1`，任何 DPI/质量参数都不会生效 —— 这是最初"参数怎么调都没反应"的根因。
* 参数字段语义、26 个 vtable 槽位、删除掩码五位的键名，全部通过 macOS 版
  `libPdfCore.dylib`（同一份跨平台代码，保留 126k 个 C++ 符号）做**结构对齐**确认，
  而不是靠函数哈希或字符串匹配。

---

## 8. 许可与免责

* 本项目代码（`src/`、`pyproject.toml`、本文档）可自由使用。
* **不含**任何 Wondershare 的二进制、图标、字体或商标。
* 依赖用户本机已授权的 PDFelement 提供的 `libPdfCore.dll` 才能工作。
* `docs/` 中是互操作性目的所做的逆向分析记录，仅供学习与自行研究使用。
