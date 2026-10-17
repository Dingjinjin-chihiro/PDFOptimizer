# PDFelement 新版 libPdfCore.dll —— PDF 优化 / 压缩业务管线逆向分析记录

> 目标：逆向 PDFelement **新版无符号** `libPdfCore.dll` 的「PDF 优化 / 压缩」**产品级业务管线**（不是 zlib/libpng 原语）。
> 方法：仅使用 Trae 自带 `ida-pro-mcp`（不再使用 REA），自导出 `CreateFactory` 自顶向下追。
> 说明：旧版逆向产物只作为「符号名字索引」，所有结论均落到**新版地址证据**。

---

## 0. 目标与环境

| 项 | 值 |
|---|---|
| 目标文件 | `C:\Users\DINGJINJIN\Desktop\PDFelement\App\PDFelement\libPdfCore.dll` |
| sha256 | `edd753f42dd2c43e20facdeaf21166b3e73fd3fb8e8cdce8719a4deeb3d2a505` |
| 镜像基址 | `0x180000000` |
| 镜像大小 | `0x3534000` |
| 工具 | IDA Pro 9.4 + ida-pro-mcp（RPC `127.0.0.1:13337`）|
| 符号情况 | **无符号、RTTI 已剥离**（无 `. ?AV*Pdf` / `nsPdfCore` / `*Optimizer` 类型串；`"katana"` 属 Skia/Blink CSS，与本产品无关）|

**排除的死路（勿再挖）**：`sub_180C8D9E0` = libpng `zstream`（`IDAT 0x49444154`，zlib 1.2.11）；`sub_180E32330/sub_180E31330` = Ghostscript 风格流过滤器。二者是底层原语，**不属于**本任务范围。

---

## 1. 重要纠正：接口对象不是「IPDFOptimizer 的 16 个方法」

早期（上一轮上下文）曾推断：文档 QI 命中 IID `{28AE50E8-3608-4918-84D1-239E0A18E244}` 返回的 32B 对象（vtable `off_18201E3B0`，20 槽）就是旧版 `IPDFOptimizer`，且 7~14 槽一一对应 `ReduceImagesSize / ReduceContentStream / ...`。

**本轮逐槽反编译后证明该推断错误**。实际槽位语义如下（全部有反编译证据）：

| 槽 | 地址 | 语义（证据） |
|---|---|---|
| 0 | `0x18005C310` | 析构：`*a1=off_18201E3B0`；析构 `+16` 引擎(352B)、Release `+24` |
| 1 | `0x180001140` | QueryInterface 返回 0 的桩 |
| 2 | `0x180002960` | AddRef |
| 3 | `0x180002970` | Release |
| 4 | `0x18005C3C0` | **SetDoc / Init**：校验实参 `vf+40()!=0`，AddRef 存 `+24`(文档 COM)，释放旧引擎后 `new 352B` → `sub_180089510` 构造 → `sub_18008CDF0`；返回 `*(*(+16)+88)!=0` |
| 5 | `0x18005A4C0` | **OptimizePages(1-based 页数组)**：把入参 `a3[a4]` 复制并对每项 **减 1**（1-based→0-based），再 `(vf+120)(=槽15)(...)` 转发 |
| 6 | `0x18005C4C0` | **Optimize(整文档)**：取 `+24` 文档→内部文档，`sub_18008D170(engine,&doc,0,0, 0,1,0, cb)` → **opcode 6** |
| 7 | `0x18005C620` | 元数据 `Author`（worker 里 `sub_18002F7D0(&v9,"Author")`）|
| 8 | `0x18005C700` | 元数据 `CreationDate` |
| 9 | `0x18005C7E0` | 元数据 `Creator` |
| 10 | `0x18005C8C0` | 元数据 `Keywords` |
| 11 | `0x18005C9A0` | 元数据 `ModDate` |
| 12 | `0x18005CA80` | 元数据 `Producer` |
| 13 | `0x18005CB60` | 元数据 `Subject`（worker `sub_1800E3E00`）|
| 14 | `0x18005CC40` | 元数据 `Title`（worker `sub_1800E3EE0`）|
| 15 | `0x18005CD20` | **OptimizePages(0-based 页索引区间) 核心**：逐页循环调用 `sub_18008D170`（opcode 6）|
| 16 | `0x1800172D0` | nullsub |
| 17 | `0` | nullsub |
| 18 | `0x18005D210` | 某字体辅助对象（vtbl `off_18201E440`）的构造/析构 |
| 19 | `0x18005D260` | 转发 `(*(a1+8))->vf()`，返回子对象结果（字体相关查询）|

> 结论：该 32B 对象是一个**「优化 + 信息字典（元数据）」复合接口**。真正的优化动作在槽 4/5/6/15，元数据管理在槽 7~14，槽 18/19 为字体相关。旧版 16 个 `IPDFOptimizer` 业务方法并不能直接与这 20 个槽硬对应。

---

## 2. 完整调用链（自顶向下，逐层地址证据）

```
[导出] CreateFactory              0x180002730
  └─ 单例 qword_183383C38，调 vtable+16(AddRef)，返回 &qword_183383C38
      对象 @0x183383C38，vtable = off_18201A000（工厂，33 槽）
      [5] = CreateDocument        0x1800012D0
        └─ alloc 360B(sub_181FBD43C(360,&unk_18201B640))，refcount@+8=1
           文档对象 = 360B，vtable = off_18201A0F0
           [1] = QI               0x18005A1A0
             └─ 比较 16B IID 与 xmmword_18201E4C0
                IID@0x18201E4C0 = {28AE50E8-3608-4918-84D1-239E0A18E244}
                命中 → new 32B(sub_181FBD400(32))，refcount@+8=1
                        vtable = off_18201E3B0（优化+元数据接口，见 §1）
                        +16 = 引擎(352B)，初值 0；+24 = 文档 COM
```

### 2.1 引擎（352B）与驱动
- 引擎构造：`sub_180089510` → 352B；`sub_18008CDF0` → 建全局 map(键 `+88`) 及 200B/208B/16B 子对象（`sub_1804801FB0` / `sub_18018013F830`…）。
- **核心驱动 `sub_18008D170(engine, out, opts, a4, a5, a6, a7, progress)`**：
  - `engine+88 != 0` 时取内部文档 `v11 = *(engine+88)+72`；
  - **操作码**：`opcode = 4 + a5 + 2*a6 + 8*a7`（范围 4~15）；若 `(opcode&1) && doc+25==0` 则 `opcode &= 7`；
  - 建 **152B 写上下文** `sub_1804EC7D0(ctx[152], …, &out)`；
  - `opts` 非空且 `*(opts+40)==1` 时按图像采样参数分支：`sub_1804EF660` / `sub_1804EF710` / `sub_1804F0190`（判据含 `*(opts+16)==2 && w==2 && h==32 && *(opts+20)==32` = 灰度 32bpp 路径）；
  - `sub_1804EEDA0(ctx, opcode)` 写入操作码/标志；
  - 步进循环 `sub_1804EF5C0(ctx)`，进度 1.0(`0x3F800000`) 起、步长 0.2、上限 99.8；
  - 结束 `sub_1804ECAA0(ctx)` 析构上下文。

### 2.2 写上下文布局（`sub_1804EC7D0` 建）
| 偏移 | 含义 |
|---|---|
| +0 | `a2`（输出/引擎上下文）|
| +8 | `*(a2+72)` → 目标文档 |
| +16 | `sub_18011E200()` 结果（页管理对象）|
| +24/+32 | 子对象（引用计数对象）|
| +48 | 当前对象计数（`*(*(+0)+8)`）|
| **+56** | **输出字节流 helper**（vtbl `off_1821337A0`），带 32KB（`0x8000`）缓冲，缓冲由 `sub_1801B4490(0x8000,1)` 申请 |
| +72 | **相态计数器**（0..100，见 §2.3）|
| +88 / +96 | 对象节点树（root）|
| +104 | 已登记节点数 |
| +112 / +120 | **页索引向量** `vector<int>`（begin/end）|
| +149 | 标志 A = `opcode & 1`（由 `sub_1804EEDA0` 写）|
| +150 | 标志 B = `!(opcode & 2)` |

### 2.3 相态状态机（`sub_1804EF5C0`）
按 `ctx+72` 分段派发，返回下一相态，循环直到 `>=100`：

| 相态 | 处理函数 | 职责（证据）|
|---|---|---|
| 0–19 | `sub_1804ED270` | 读 catalog（`*(*(ctx+0)+80)`）与 **`/Metadata`**（`sub_18002F7D0(&v,"Metadata")`）；写 **PDF 头/版本**（前缀比较 `sub_1801C5510`，`unk_182F8074C` 9 字节）；按需复制源流；**枚举页**（`sub_18011B8F0` 页数 / `sub_18011B9A0` 取页 / `sub_18011BA00` 存在性），构建 48B 页索引节点树 |
| 20–79 | `sub_1804ED740` | 逐页调度对象图：`sub_1804ECDB0`/`sub_1804ECF70` 遍历依赖并登记节点，**每对象调用 `sub_1804ECBD0` 写出**；节点 `+40` 记录输出字节偏移 |
| 80–89 | `sub_1804EDA40` | 写 **xref 表 + trailer**：`"xref\r\n"`、`"0 %d\r\n0000000000 65535 f\r\n"`、`"%010d 00000 n\r\n"`（偏移取自节点 `+40`）|
| 90–100 | `sub_1804EE190` | 收尾（trailer / 完成）|

### 2.4 单对象写出（`sub_1804ECBD0`）—— 压缩落点
```
sub_1804ECBD0(ctx, objNum, objEntity):
  out = (*(ctx[7]->vf + 16))()            # 输出流
  if out->vf+..(objNum) && write(" N 0 obj\r\n"):     # sub_1801C55C0 / sub_1801C5510
      tctx = alloc(16); sub_1806AB870(tctx, params, objNum)   # {params, objNum}
      ok   = (*(objEntity->vf + 312))(objEntity, out, tctx)   # ★ 对象自身序列化虚拟
      if ok: write("\r\nendobj\r\n")
```
- `+312`（vtable 偏移 `0x138`）即对象的 **WriteTo / serialize** 虚函数，**图像重编码、内容流重压、对象流生成都在各自的 `vf+312` 里完成**。
- 序列化上下文构造器 `sub_1806AB870` 仅初始化 `{ptr=params, int=objNum}` 共 16B（无独立压缩逻辑）。

### 2.5 公开 API 层（opcode 判定实例）
| 函数 | 形态 | 调用 |
|---|---|---|
| `sub_18001D300` | `(impl, doc, cb)` | 校验 `doc->vf+40()!=0` → 内部文档 → 建进度回调对象（`off_18201BC98`/`off_18201BCB0`，用户对象在 `a3`）→ `sub_18008D170(impl+56,&page,0,0, **a5=1,a6=0,a7=1**, cb)` ⇒ **opcode 13**（标志 A=1「重写」、B=1「复制」），即「优化并重写＝另存／压缩」路径 |
| `sub_18001CAE0` | 变参 `(impl,…,a6,…)` | 同样走 `sub_18008D170`（x 引用 `0x18001CC54`）|
| `sub_1800911C0` | `(a1,a2,a3,a4)` | 条件分支后走 `sub_18008D170`（x 引用 `0x180091222` / `0x180091410`）|

> opcode 语义（由 `sub_1804EEDA0` 决定）：
> - 标志 A(`opcode&1`)=1 → **重写**（重新分配对象号、写新文件）；
> - 标志 B(`!(opcode&2)`)=1（即 `opcode&2==0`）→ **复制源内容**；
> - `opcode&4` 恒置位（基值 4）。
> 例：`6 = 0b110`（A=0,B=0）＝ 整文档 Optimize；`13 = 0b1101`（A=1,B=1）＝ 优化后另存。

### 2.6 `vf+312` 序列化器逐一展开（PDF 值节点写出机制）

**值节点模型**：每种 PDF 值类型是一个独立小对象（40–80B），在对象体解析 `sub_180160D80` 内由若干构造器建立；`*(obj+0)` = vtable、`*(obj+8)` = refcount、`*(obj+24)` = 对象号(objNum)。**`obj->vtable[39]`（字节偏移 `+0x138`）即该类型的序列化器**；字典/数组序列化器会**递归**调用子值的 `+312`。

**构造器 / vtable 族（`sub_180160D80` 的被调）**：

| 构造器 | 大小 | 初始化器（写 vtable）| vtable |
|---|---|---|---|
| `sub_180161B50` / `sub_180127010` | 56B | `sub_18013F310` | `off_182026B40` |
| `sub_180161D00` | 80B | `sub_1801298F0` | `off_1820261E0` |
| `sub_180161BE0` | 40B | `sub_1804F0C50` | `off_182133930` |
| `sub_180161C60` | 56B | `sub_180143110` | `off_182026DE0` |
| `sub_180161D80` | 48B | `sub_180128380` | `off_182026020` |
| `sub_180161E20` | 80B | `sub_180125CA0` | `off_182025ED0` |

**`slot[39] = +312` 解码**（base `0x180000000`）：

| vtable | 大小 | `+312` | 语义（证据）|
|---|---|---|---|
| `off_182026020` | 48B | **`0x180127940`** | **字典**：写 `<<` → 逐键写 `/k` + 值 → `>>`；子值走 `+312` |
| `off_182026B40` | 56B | **`0x18013F730`** | **间接引用**：写 `" N 0 R "`（N=`*(a1+48)`）|
| `off_182026DE0` | 56B | **`0x1804F0B20`** | 包装：读 `*(a1+24)`=objNum → 建 56B ref 对象再写 |
| `off_182025ED0` | 80B | **`0x180125D10`** | 红黑树容器复制/重建（遍历 `a1+56..a1+64`，对子调 `+320`）|
| `off_182133930` | 40B | `0x180001140` | 纯虚 stub（`return 0`）|
| `off_1820261E0` | 80B | *（dump 被截断，待补读）* | `slot[1]` 类型码 getter = `sub_180129A30` |

**字典序列化器 `sub_180127940`（递归派发核心）**：
```
v26[0] = "<<", v26[1] = 2;   sub_1801C5510(a2, v26)        // 写 "<<"
  v11 = v9[5];                                             // 值对象
  ... 写 "/" + 键名 ...
  v17 = (v8 != 0 && sub_180030A00(v9+4, "Contents") != 0) ? 0 : a3;   // ★ /Contents 键强制 params=0
  v18 = (*(*(v11) + 312))(v11, a2, v17);                    // ★ 递归调用子值的 +312 序列化器
v29[0] = ">>", v29[1] = 2;   sub_1801C5510(a2, v29)        // 写 ">>"
```
→ 证实 **`+312` 就是逐值序列化器**；且 **`/Contents`（内容流）不接收优化参数**（内容流重压缩不挂在该键上，见下）。

**引用序列化器 `sub_18013F730`**：
```
v6[0] = " ", v6[1] = 1;                                     // 先写空格
sub_1801C5510(a2, v6);  sub_1801C55C0(a2, *(u32*)(a1+48))    // 写对象号（十进制）
v5[0] = " 0 R ", v5[1] = 5;  sub_1801C5510(a2, v5)          // 写 " 0 R "
```

**通用值→字符串序列化器 `sub_1804F2860`**（`a1`=字符串 builder，`sub_1800E9710`=append）：
`switch ((*(*a2+8))(a2))`：`1|2`→`" "`+…；`4`→`"/"+名`；`5`→`[`…`]`（元素 `objNum!=0` 写 `" N 0 R"`，否则递归）；`6`→`<<`…`>>`；`7`→字典 + `"stream\r\n"` + 数据 + `"\r\nendstream"`；`8`/0→`" null"`；`9`→`" N 0 R "`。

**流对象序列化器 `sub_1801C5100`（0x1801C5100）——含 `/Length` 修正与优化参数重编码**：
```
v6 = *(a1+48);                                        // 流对象关联的字典
取 /Type；若 Type==Metadata 再判 /Subtype==XML → 认定「元数据流」
v9 = v8 ^ 1;   sub_1807069C0(&v23, a1, v9);
v10/v11 = 流数据 ptr/len;
if ((v8 | (a3==0)) == 0)  sub_1806AB880(a3, &v28, {v25,v24});   // ★ 非 XML 且 a3(tctx)!=0 → 重编码流数据
r = sub_1807074C0(&v23);
if (流数据长度 != /Length) { ... 改写 /Length ... }              // ★ 长度不符则改 /Length
v16 = sub_180127940(sub_1807074C0(&v23), a2, a3);              // 调字典序列化器写 <<..>>
if (v16 && sub_1801C5510(a2, "stream\r\n")) { (**a2)(a2, v11, v10); sub_1801C5510(a2, "\r\nendstream"); }
```
→ **流写出 = 字典（可能改 /Length）+ `"stream\r\n"` + 原始/重编码字节 + `"\r\nendstream"`**；`a3` = 序列化上下文 `tctx={params, objNum}`（见 §2.4）。
> 另有分块写出器 `sub_18015CCE0`（内存型，尾部 `"\nendstream\nendobj\n\n"`）与 `sub_18015CF70`（`sub_1801A5910` 按 4KB 分块读流）；两者均先校验对象类型码 `(*(*obj+8))() == 6`（=流）。

**优化参数对象的重编码派发 `sub_1806AB880`（0x1806AB880）**：
```
a2 清零；v5 = *a1;                                 // *a1 = params 对象（tctx[0]）
v6 = (*(*v5 + 8))(v5, v10);                        // ★ params->vtable[1] 过滤流数据，返回新长度
sub_180163850(a2, v6);                             // 按新长度调整输出缓冲
guard_dispatch_icall(v7, *((u32*)a1 + 2));         // params 参数的第二次虚调用
```
→ **真正的流/图重编码是 `params` 对象的虚方法 `vtable[1]`（+8）**；`params` 由写目标文档 `*(targetDoc+56)`（写上下文 `ctx+32` = `a1[4]`）的 `vtable+40` 方法提供（见 §2.4）。
- 「是否已压缩」判据：`sub_180170850` 遍历 `/Filter` 数组元素，用 `sub_180170990("FlateDecode", elem)` 判断该流是否**已是 FlateDecode-only**。

**排除项（重要，勿误归因）**：`0x180E30xxx` 簇（`sub_180E31280` → `sub_180E31330`；`sub_180E32330`）是 **PDF→PostScript（打印）图像输出**：自带 `"\nsave\n/im/initmatrix load def\n…"` PS prolog、`"currentfile/ASCII85Decode filter "`、`"false 1 colorimage\n"` 等 PS 算子。其中 JPEG 质量是**硬编码常量 75**（`sub_180E31330` 调 `(*(*(a1+88)+24))(&v88,&v83,&v82,75)`）；`sub_180E32330` 按 `*(a1+8)∈{1,2}` 选 `/FlateDecode filter`、否则 `/RunLengthDecode filter`，且仅当 **输入 ≥ 1024B 且压缩后更小**才采用。**此簇属于打印/PS 转换路径，不属于 PDF 文件写出的压缩管线**，须与新文件写出路径区分。

### 2.7 PDF 侧图像质量参数定位（★本会话核心成果）

**结论：PDF 侧图像质量参数 = 图像对象偏移 `+364` 的 float 字段**，经 `sub_180502530` 四舍五入取整，最终流入 `sub_180CA529E`（内嵌 libtiff/libjpeg 的 JPEG 质量）。

证据链（自底向上）：

1. **内嵌编码库确认**：`"Copyright (C) 1991-2021 The libjpeg-turbo Project"` @`0x182eeebec` → **libjpeg-turbo**；libtiff JPEG codec 方法名 `JPEGSetupEncode`@`0x182da8240`、`JPEGPreEncode`@`0x182da8250`、`JPEGEncode`@`0x182f30642`、`JPEGSetupDecode`@`0x182f30860` 齐全。**导入表无 libJpeg/libTiff 导入** → 二者均静态内嵌。

2. **MIF 图像库 JPG 编码器 `sub_181727DD0`**（注册于 `sub_1813029D0` 的 codec 表 `id=6 "jpg"`，desc `"JPEG (ISO/IEC 10918-1)"`）：
   - 解析 option 字符串，命中 `"quality"`（表 `unk_1833767F0` 的 `+8` 指向 `"quality"` 字符串 @`0x182eda99b`）时 `%d` 解析质量到 `v50`；
   - `sub_180CA529E(v55, v50, 1)` 设置质量；
   - `"ignoring bad quality specifier %s\n"` @`0x182f7502e` 即此处的解析失败消息（x 引用 → `sub_181727DD0`）。

3. **质量设置函数 `sub_180CA529E`**，4 个调用者：`sub_1805FC5B0`、`sub_180BE0400`（JPEG 编码）、`sub_181727DD0`（MIF JPG）、`sub_18173C640`。

4. **JPEG 编码器 `sub_180BE0400`**（图像对象 → JPEG，`sub_1805063D0` 的 `case 3` 调用）：
   ```
   v10 = sub_180502530(a1);          // 质量 getter
   sub_180CA529E(v33, v10, v9 & 1);  // 设置质量（v9 = sub_180502430(a1,3) 标志）
   ```

5. **质量 getter `sub_180502530`（★最终落点）**：
   ```c
   return (unsigned int)(int)(float)(*(float *)(a1 + 364) + 0.5);  // +364 float 质量，四舍五入
   ```

6. **图像编码格式调度器 `sub_1805063D0`**：`switch(a3)`，`case 1/2/3/4/6/11`，**`case 3 = JPEG`**（`sub_180BE0400`）；`default` → `"Encode: Unknown format"`。其封装：`sub_180506250`（编码到文件）、`sub_180506330`（编码到流）、`sub_180506790`（编码到内存缓冲）。

7. **标志 getter/setter（+420 区）**：`sub_180502430`（getter，读 `a1 + 4*qword_182134318[v2] + 420`）/ `sub_1805024C0`（setter，写同式）；索引表 `qword_182134318`=`[1,2,3,4,6,5,6,6,6,6,1]`、`qword_182134370`=`[1,2,3,4,0,0,5,…]`，有效 index 掩码 `1071=0b10000101111`。质量 float 在 **+364**，标志区在 **+420**。

8. **40B 图像节点类 `off_1821346A0`**（ctor `sub_1805081D0`，析构 `sub_180508D50` 释放 40B）：字段 `+16/+24/+32` 三个对象引用（`+32`=图像流对象）；27 个虚方法，**`slot[7]=sub_180507930`（GetImageType2**，读 `/Filter` 判 DCT/JPX 返回 1/2），`slot[14..16]` 处理 `Mask`/`SMask`。

**尚未定位（下一步）**：
- 写 `+364` 的质量 **setter**（用户质量选项入口）；
- 旧版公式 `((q/100)^2*0.3+0.001)*100` 的浮点常量 `0.3f=0x3E99999A` / `0.001f=0x3A83126F` / `100.0f=0x42C80000` 在新版**尚未找到**（质量 float 可能已按 0–100 或 0–1 归一化存储，未复现旧版非线性映射）。

---

## 3. 旧版符号 ↔ 新版地址映射（仅作名字索引）

| 旧版（macOS nsPdfCore，仅符号名） | 新版地址（本 IDB 证据） | 说明 |
|---|---|---|
| `NewPdfOptimizer(CBaseDocument*)` | `CreateFactory 0x180002730` → QI `0x18005A1A0` → 接口对象 vtbl `off_18201E3B0` | 工厂创建 |
| `CPdfOptimizerImpl` ctor | `sub_180089510`（352B 引擎）+ `sub_18008CDF0` | 引擎构造 |
| `CPdfUnknown<IPDFOptimizer>::QI/AddRef/Release` | `0x18005A1A0` / `0x180002960` / `0x180002970` | COM 样板 |
| `CPdfDocPageImpl::Optimize(ulong)` | `sub_18005CD20`（槽15，逐页）→ `sub_18008D170` | 单页优化驱动 |
| `CBaseOptimizer::ReduceImagesSize` | `sub_18008D170` 的 `opts(+40)==1` 分支；图像/流对象 `vf+312`(`sub_1801C5100`) 的 `sub_1806AB880` 重编码 | 部分实证 |
| `CBaseOptimizer::ReduceContentStream` | 每对象 `vf+312`（`sub_1804ECBD0` → `sub_1801C5100`）；`/Contents` 键 params 强制 0，是否重压由 `params->vtable[1]` 决定 | 部分实证 |
| `CBaseOptimizer::RemoveMetadata` | 相态 0–19 `sub_1804ED270` 的 `/Metadata`；且 `sub_1801C5100` 对 `/Type==Metadata & /Subtype==XML` 流**跳过重编码** | 实证 |
| `BaseContentStreamOptimizer::Compress` | 流序列化器 `sub_1801C5100` 内 `sub_1806AB880` → `params->vtable[1]`（`+8`） | 实证（入口）|
| `CImageUtil::{AdjustQuality,AdjustEncodeMode,downSample,CompressBitmap}` | **图像质量参数已定位**：图像对象 `+364` float（getter `sub_180502530`）；JPEG 编码 `sub_180BE0400` → 调度 `sub_1805063D0(case 3)`；质量 setter 尚未定位；`0x180E31330` 的 DCTDecode(q=75) 属 **PS 打印路径**，非本管线 | 质量 getter 实证，setter 待续 |
| `XRef/trailer 生成` | `sub_1804EDA40`（相态 80–89） | 已确认 |

---

## 4. 局限与待办

1. **值节点 `vf+312` 序列化器已展开**：字典 `sub_180127940` / 引用 `sub_18013F730` / 流 `sub_1801C5100` / 通用值 `sub_1804F2860`（见 §2.6）。**剩余**：`off_1820261E0` 的 `slot[39]` dump 被截断待补读；`sub_180161EA0` 用途待定。
2. **PDF 写出侧的图像质量→编码器映射已部分定位**（见 §2.7）：质量 = 图像对象 `+364` float，getter `sub_180502530`，JPEG 编码 `sub_180BE0400` → 调度 `sub_1805063D0(case 3)` → 质量设置 `sub_180CA529E`。`0x180E31330` 的 DCTDecode 质量固定 `75` 属 **PS 打印输出**（非本管线）。**剩余**：写 `+364` 的质量 setter（用户选项入口）未定位；旧版公式 `((q/100)^2*0.3+0.001)*100`、面积阈值 `10001`、DPI 阈值在新版**尚未找到常量**。
3. **旧版滑窗常量缺证据**：`100.0f=0x42C80000`、`-1.0f=0xBF800000`、`0.3f=0x3E99999A`、`0.001f=0x3A83126F` 在本簇**尚未复现**（质量 float 或已归一化 0–100/0–1，未走旧版非线性映射）。
4. 字体：槽 18/19 的字体接口（`GetCancelableEmbeddedFonts` / `CancelFontsEmbedded`）未展开；子集锚点 `"--- subset:\nSRC font %s\n..."`@`0x182f79053` → `sub_181B2CF80` → 调用者 `sub_1817F06C0`。
5. **下一步关键**：反编译提供 `params->vtable[1]`（流过滤）的 **优化参数对象类**（由 `*(targetDoc+56)` 的 `vtable+40` 方法返回，见 §2.4/§2.6），即可定位 PDF 图像/内容流重编码与质量参数；并补读 `off_1820261E0` 的 `slot[39]`。

---

## 5. 地址速查表

| 地址 | 名称 | 作用 |
|---|---|---|
| `0x180002730` | CreateFactory | 唯一导出 |
| `0x18201A000` | 工厂 vtable | 33 槽，[5]=CreateDocument |
| `0x1800012D0` | CreateDocument | 建 360B 文档 |
| `0x18201A0F0` | 文档 vtable | [1]=QI |
| `0x18005A1A0` | 文档 QI | IID `28AE50E8-…-18E244` |
| `0x18201E3B0` | 优化+元数据接口 vtable | 20 槽 |
| `0x18005C3C0` | 接口槽4 SetDoc/Init | 绑文档 + 建 352B 引擎 |
| `0x18005A4C0` | 接口槽5 OptimizePages(1-based) | → 槽15 |
| `0x18005C4C0` | 接口槽6 Optimize(整文档) | opcode 6 |
| `0x18005CD20` | 接口槽15 OptimizePages 核心 | 逐页驱动 |
| `0x180089510` | 引擎构造 | 352B |
| `0x18008D170` | **核心驱动** | opcode=4+a5+2a6+8a7 |
| `0x1804EC7D0` | 建 152B 写上下文 | 32KB 输出缓冲@+56 |
| `0x1804EEDA0` | 设 opcode/标志 | +149/+150 |
| `0x1804EF5C0` | 相态状态机 | 0-19/20-79/80-89/90-100 |
| `0x1804ED270` | 相态0-19 | Metadata / 头 / 页表 |
| `0x1804ED740` | 相态20-79 | 逐页对象图 |
| `0x1804EDA40` | 相态80-89 | xref + trailer |
| `0x1804EE190` | 相态90-100 | 收尾 |
| `0x1804ECBD0` | 写单对象 | 派发 obj `vf+312` |
| `0x1806AB870` | 序列化上下文 init | {params,objNum} |
| `0x18001D300` | API Optimize/另存 | opcode 13 |
| `0x180160D80` | 对象体解析 | 生成值节点族 |
| `0x180127940` | **字典序列化器 `+312`** | `<<k v …>>`，递归子值；`/Contents` params=0 |
| `0x18013F730` | **引用序列化器 `+312`** | `" N 0 R "` |
| `0x1804F0B20` | 引用包装 `+312`(off_182026DE0) | 读 `+24`→建 ref |
| `0x180125D10` | 树容器复制 `+312`(off_182025ED0) | 子节点调 `+320` |
| `0x1804F2860` | 通用值→串序列化器 | `switch(obj 类型码)` |
| `0x1801C5100` | **流序列化器** | 字典+`stream\r\n`+数据+`\r\nendstream`；改 `/Length`；`a3` 重编码 |
| `0x18015CCE0` / `0x18015CF70` | 流分块写出器 | 尾部 `\nendstream\nendobj\n\n`；类型码须 ==6 |
| `0x1806AB880` | **优化参数重编码派发** | `(*(params->vtbl+8))(params,…)` |
| `0x180170850` | 流「已 FlateDecode」判据 | `sub_180170990("FlateDecode",…)` |
| `0x180E31280`/`0x180E31330` | (PS 打印) 图像编码 | DCTDecode `q=75`；**非本管线** |
| `0x180E32330` | (PS 打印) 流过滤器 | Flate/RunLength；≥1024B 且更小才用；**非本管线** |
| `0x180502530` | **质量 getter** | `(int)(*(float*)(a1+364)+0.5)` |
| `0x180BE0400` | **JPEG 编码器** | 读质量 `sub_180502530` → `sub_180CA529E` |
| `0x1805063D0` | **图像编码调度器** | `switch(a3)`，`case 3`=JPEG |
| `0x180CA529E` | **质量设置** | `(ctx, quality, flag)`，流入 libtiff/libjpeg |
| `0x180502430` / `0x1805024C0` | 标志 getter / setter | 写 `+420` 区，索引表 `qword_182134318/370` |
| `0x181727DD0` | MIF 库 JPG 编码器 | 解析 `"quality"` option → `sub_180CA529E` |
| `0x1813029D0` | 图像 codec 注册表 | id=6 `"jpg"` → `sub_181727DD0` |
| `0x180507930` | GetImageType2 | 40B 图像节点 `off_1821346A0` slot[7]，读 `/Filter` 判 DCT/JPX |
| `0x182eeebec` | libjpeg-turbo 版权串 | 内嵌 libjpeg-turbo 证据 |
| `0x182f7502e` | `"ignoring bad quality specifier %s\n"` | `sub_181727DD0` 的质量解析失败消息 |

---

## 6. 本轮补充确认（2026-10-17，Windows x64 库 · 导出驱动视角）

> 本轮从**唯一导出** `CreateFactory` 重新自顶向下核对，并把“外部可达路径”作为重点。所有地址均落在 `libPdfCore.dll`（sha256 `edd753f4…3d2a505`，基址 `0x180000000`）。

### 6.1 单例与工厂 vtable（核实）

| 项 | 结论 |
|---|---|
| `CreateFactory` @ `0x180002730` | `lea rsi, gFactory` → 读 `cs:qword_183383C38`(=对象首=qword vtable 指针) → `call [rax+0x10]`(slot 2 = `sub_180001150`) → 返回 `&gFactory` |
| 单例对象 | `gFactory` @ **`0x183383C38`**（`.data`；**静态镜像读为 0**，vtable 指针由运行期初始化器写入） |
| 工厂 vtable | `off_18201A000`；`[5]=sub_1800012D0`（**分配 360B**，vtable `off_18201A0F0`）|
| 观察到的“重叠” | `off_18201A0F0 = off_18201A000 + 0xF0`，工厂 vtable 的 `[30..]` 与 360B 对象 vtable 的 `[0..]` 为同一段内存（`sub_180002930` 等）→ 属同一 `??_7` COMDAT 组内的多个子对象 vtable |

### 6.2 文档实现对象（528B）——与 mac `CPdfDocumentImpl` 对应

| 项 | 结论 |
|---|---|
| 创建者 | **工厂 vtable slot 18 = `sub_180001250`**：`sub_181FBD43C(528, &unk_18201B640)` → `sub_180019450` 构造 → 返回对象 |
| 构造 `sub_180019450` | `*(+32)=1`(引用计数)；`+0/ +8/ +16/ +24` 四个 vtable = `off_18201B900 / 18201BB70 / 18201BBD0 / 18201BC50`；`+48 = new(24)`；**`sub_180089510(+56)`** = 内嵌“引擎”（352B，对应 mac `CBaseDocument` 位）；`+88 = this`；`+408=0`、`+416=0`、`+472=0`、`+520=0`；随后 `sub_1800924A0` 等绑定回调/子对象 |
| 析构 | vtable#1 slot0 = `sub_180023910` → `sub_180019900()` 复位 + `sub_181FBD458(this,528)`；另有 `sub_1800239B0 / 180023A40 / 180023B90`（其余 3 个 vtable 的析构）|
| 其它 vtable | `off_18201BB70`（IO/Pages 类，slot1=`sub_180019390`）、`off_18201BBD0`、`off_18201BC50` |

### 6.3 优化器接口（32B）与 opcode 驱动（核实 + 细化）

- QI `sub_18005A1A0`（IID `xmmword_18201E4C0` = `{28AE50E8-3608-4918-84D1-239E0A18E244}`）→ `new(32)`、`*(+8)=1`、vtable `off_18201E3B0`、`*(+16)=0`。
- `off_18201E3B0` 布局：`+16` = 引擎(352B)、`+24` = 文档 COM；`[4]=sub_18005C3C0`(SetDoc/Init：new 352B → `sub_180089510` → `sub_18008CDF0`，返回 `*(*(+16)+88)!=0`)；`[6]=sub_18005C4C0`(Optimize 整文档)。
- `sub_18005C4C0` 实证：`sub_180033B80(&v15, a1+24)` 取内部文档 → `sub_18008D170(*(a1+16), &doc, 0, 0, **a5=0,a6=1,a7=0**, 0)` ⇒ **opcode = 4+0+2+0 = 6**；随后销毁引擎(352)。
- **核心驱动 `sub_18008D170(engine, out, opts=a3, a4, a5, a6, a7, cb=a8)`**：
  - `opcode = 4 + a5 + 2*a6 + 8*a7`（范围 4–15）；
  - `if (a3==0 || *(BYTE*)(a3+40)!=1)` → 直接按 opcode 执行；
  - 否则：若 `*(BYTE*)(a3+24)==1` → `sub_1804EF660`（简单分支）；否则读 `*(int*)(a3+16)`、`*(int*)(a3+20)`，并用 `v11 = *(engine+72)` 的 `+56` 对象两个虚函数取值，判据 `*(a3+16)==2 && v==2 && v==32 && *(a3+20)==32`（**灰度/32bpp 路径**）→ `sub_1804F0190(ctx,…,2,32,*(a3+28),*(a3+25),*(a3+36))`；否则 `sub_1804EF710(ctx,…,*(a3+16),*(a3+20),*(a3+28),*(a3+25),*(a3+36))`；
  - 之后 `sub_1804EEDA0(ctx, opcode)` 写操作码/标志，`sub_1804EF5C0(ctx)` 相态步进（进度 1.0 起、步长 0.2、上限 99.8），结束 `sub_1804ECAA0(ctx)`。
  - **`a3` 即“图像采样参数”结构：`+16` 颜色类型、`+20` 位深、`+24`/`+25` 标志、`+28` 质量、`+36` DPI、`+40` 使能、`+8` 子串。已知 5 个调用者（`sub_18001D300` / `sub_18001CAE0` / `sub_1800911C0` / `sub_18005C4C0` / `sub_18005CD20`）**全部传 a3 = 0**。**
- opcode-13「优化并另存」= `sub_18001D300(impl, doc, cb)` → `sub_18008D170(impl+56, &doc, 0, 0, **1,0,1**, cb)`；外部可达路径 = `sub_180022340`（**528B 文档实现 vtable `off_18201B900` slot 24**，即 `+0xC0`）。
- 写上下文 `sub_1804EC7D0(ctx, engine, &out)`：`+0 = engine`；`+8 = *(engine+72)`；`+16 = sub_18011E200()`(页管理)；**`+32 = *(*(engine+72)+56)`**；`+56 = 输出流 helper（vtable `off_1821337A0`，32KB 缓冲 `sub_1801B4490(0x8000,1)`）**。`sub_1804ECBD0` 通过 `(*(*(ctx+32)+0x28))(ctx+32)`（slot 5）取序列化用的 **params 对象**，该对象的 `vtable[1](+8)` 就是流/图重编码落点（§2.6）。

### 6.4 本轮新增地址速查（追加）

| 地址 | 名称 | 作用 |
|---|---|---|
| `0x183383C38` | `gFactory` 单例 | 首 qword = vtable 指针（运行期写入）|
| `0x180001250` | 工厂 slot 18 | **CreateDocument → 528B 文档实现** |
| `0x180019450` | 528B 构造 | 4 vtable + 引擎@+56 + 子对象绑定 |
| `0x180019900` | 528B 复位/清理 | 写回 4 vtable 并释放所持对象 |
| `0x180023910` | 528B 析构(vtbl#1 slot0) | `sub_180019900` + free 528 |
| `0x18201B900` | 528B vtable#1 | 77 槽；slot 24 = `sub_180022340`（优化并另存）|
| `0x18201BB70` | 528B vtable#2 | IO/页相关（slot1 = `sub_180019390` 析构）|
| `0x18201BBD0` | 528B vtable#3 | — |
| `0x18201BC50` | 528B vtable#4 | — |
| `0x180022340` | 528B vtable#1 slot24 | → `sub_18001D300`（opcode 13）|
| `0x1800911C0` | 带 opts 候选优化 API | 两处调用 `sub_18008D170`，opcode 15 |
| `0x1800012D0` | 工厂 slot 5 | 分配 360B（vtable `off_18201A0F0`）|

### 6.5 结论

1. `sub_180022340`（528B 文档实现 slot 24）是从**导出驱动的对象**上唯一可直达 “opcode 13 优化并另存” 的槽位，`sub_18001D300` 的 `doc` 入参即“要写出的文档”。
2. 参数（图像质量/编码、DPI/下采样、内容流压缩、去元数据）**不在** `sub_18008D170` 的 `opts` 形参上（调用者恒传 0），而是落在 **`*(*(engine+72)+56)` 的 params 对象**（序列化期经其 `vtable[1]` 生效）。→ 下一步应定位该对象的类与其 setter 槽位。
3. 文档“加载 PDF / 写出”的槽位待定位（528B 四个 vtable 已列出，尚未逐一展开）。

---

## 7. 另一套可用引擎：SolidFramework（`SolidFramework\Win64\`）

> 本轮在安装目录下发现的**第二套、且符号完整**的 PDF 压缩引擎。记录备选，未作为主目标。

| 文件 | 形态 | 关键 API |
|---|---|---|
| `SolidFramework\Win64\PDFLibTool.dll` | x64 原生，**5267 个 MSVC 完整命名导出** | `CPdfWriter::WritePdfFile(const wchar_t*, const IPdfDataBaseOptimizer*, IProgress*, const IPdfEncryptionExportOptions*)`；`CPdfWriter::CreateOptimizer(const std::vector<CPdfObjectID>&, bool, bool)`；`CompressStreams` / `CompressStream` / `ContentStreamCompression` / `ImageStreamCompression` / `DoStreamCompression`；`SetPdfExportOptions(CPdfExportOptions)`；`CPdfCompressor::EncoderTypeByName` / `ImageEncoderTypeByName`；`CPdfMerger::LoadPdfFile(const wchar_t*)`；`CPdfDataBaseCleaner`；`CPdfExportOptions::AutoEncoderColorImage/GrayscaleImage/MonoImage` |
| `SolidFramework\Win64\SolidFrameworkNative.dll` | x64 原生，**4380 个 SWIG C 导出** | `SolidFramework_Plumbing_Document_Create/Open__SWIG_0/1/SaveOptimizedAs__SWIG_0/1/SaveOptimized__SWIG_0/1`；`SolidFramework_Model_Export_ExportOptions_*`；`SolidFramework_Imaging_Image_DCTCompressionQuality_get`；`SolidFramework_Converters_PdfToPdfConverter_*` |
| `SolidFramework\Win64\PDFLibTool.dll` 之 `CPdfExportOptions` | — | `SPdfDocumentInfo@CPdfExportOptions`、`SPdfViewerPreferences@CPdfExportOptions`、`CPdfExportOptions* vtable` 含 `IPdfOpenActionOptions`/`IPdfFontExport` 等 |

**归属核查（UTF-8 + UTF-16 双编码扫描）**：
- `PDFCore.dll`（AnyCPU 托管，2.9MB，3.1MB 级）**只从 `libPdfCore.dll` 导入 `CreateFactory`**（`#Strings` 堆中 `libPdfCore.dll` + `CreateFactory` 相邻），其余全部经工厂 vtable 驱动。
- `PDFelement.exe`（AnyCPU 托管）**不含** `libPdfCore` / `PDFLibTool` / `SolidFrameworkNative` 任一模块名；仅含 `PDFCore`、`CreateFactory`、`CreateOptimizer` 等字符串。
- `SolidFrameworkNative.dll` 含 `PDFLibTool` + `SolidCore` + `CreateOptimizer` + `SaveOptimizedAs` + `IPdfDataBaseOptimizer` → Solid 自成一系，由 `libSolidEngine.dll` / `SolidFrameworkNative.dll` 使用。

**SWIG 入口签名（反汇编初判）**：SWIG 的 `self` 形参在 `rcx` 且先 `mov rbx,[rcx]`（指针的指针）；`SaveOptimizedAs__SWIG_0(self, path, …)` 内为 `wchar_t*` 转换；`SaveOptimized__SWIG_0(self)` 走 `self->vf[0x40]`。

---

## 8. 托管侧还原（PDFCore.dll / PDFToolbox.exe，dnSpy 反编译，2026-10-17）

> 用 dnSpy 反编译 `PDFCore.dll`（AnyCPU 托管，2.9MB）与其消费方 `PDFToolbox.exe`（20MB），**绕过原生符号缺失**，直接取得「接口方法 → 原生 vtable 槽位」的精确映射与全部可选参数语义。
> 注意：PDFCore.dll 经 Dotfuscator 混淆（类/方法名如 `mwv`/`m9a`/`b8i`），但**接口的方法顺序未打乱**，且结构体字段顺序 = 方法顺序。

### 8.1 互操作机制（关键）

`PDFCore/PDFCore/bwz.cs`（泛型代理基类）：

```csharp
public unsafe bwz(IntPtr A_0) {
    this.m = A_0;
    IntPtr intPtr = *(IntPtr*)(void*)A_0;          // ★ 读原生对象首 qword = vtable 指针
    if (intPtr != IntPtr.Zero)
        this.f = (b)this.m(intPtr, out flag);       // ★ Marshal.PtrToStructure(vtable, b)
}
// m(IntPtr vtable, out bool)：Marshal.PtrToStructure(vtable, new b())  —— b 为「槽位表」结构体
```

`bwd`（所有槽位表的基类）恰好 4 个委托字段：

| 字段 | 委托签名 | 原生槽 |
|---|---|---|
| `lb` | `void (IntPtr)` | **0** |
| `li` | `int (IntPtr, Guid, ref IntPtr)` = QueryInterface | **1** |
| `lp` | `nint (IntPtr)` = AddRef | **2** |
| `lw` | `nint (IntPtr)` = Release | **3** |

→ **结论：托管接口的第 i 个方法 = 原生 vtable 第 `i+4` 槽**（原生对象前 4 槽为 dtor/QI/AddRef/Release）。
（验证：`mwv[14] b8i()` → 工厂槽 18 = `sub_180001250`，正是 §6.2 实证的 528B 文档实现构造。）

### 8.2 工厂接口 `mwv`（`CreateFactory` 返回值）

`mbg.cs`: `[DllImport("libPdfCore.dll", EntryPoint="CreateFactory")] private static extern mwv m();` → 托管入口即 `mwv`。

| idx | 方法 | →原生槽 | 结果类型 |
|---|---|---|---|
| 0 | `b1s(m4o)` | 4 | bool |
| 2 | `b86(m33,bool,m4a,int,int,m4w,bool)` | 6 | m3i |
| 3 | `b8d(byte[],nint)` | 7 | m3i |
| **14** | **`b8i()`** | **18** | **m9a = 文档**（CreateDocument = `sub_180001250`）|
| 15 | `b8p()` | 19 | mfw |
| 20 | `b8o()` | 24 | m4h |
| 25 | `b8n()` | 29 | bool |

### 8.3 文档接口 `m9a`（63 方法，槽位表 `q63`）

对象 = §6.2 的 528B 文档实现（首 qword vtable = `off_18201B900`，77 槽；m9a 用 **槽 4..66**）。

| idx | 方法 | 原生槽 | 原生地址 | 语义 |
|---|---|---|---|---|
| 0 | `qwb()` | 4 | `sub_180019A20` | — |
| **1** | **`qwi(mav, byte[], nint)`** | **5** | **`sub_180019A90`** | **打开（入参 = 输入流 + 口令字节 + 长度）** |
| 2 | `qwp()` | 6 | `sub_180019FC0` | — |
| **3** | **`qww(mav, m3s)`** | **7** | `sub_18001A560` | **另存到流** |
| **4** | **`qw3(mav, m9b, m3s)`** | **8** | `sub_18001CA80` | 另存（带参数） |
| 5 | `qwa()` | 9 | `sub_18001D520` | 取流 |
| 18 | `qwt()` | 22 | `sub_18001DCC0` | **取优化器 (`m9m`)** |
| 20 | `qw7(mav, m3s)` | 24 | `sub_180022340` | **优化并另存（opcode 13）** |

### 8.4 流接口 `mav`（9 方法，槽位表 `btt`/`bt1`）

托管实现 `mae`（`mae.cs`）包裹任意 `System.IO.Stream`。mav 的槽 4..12：

| idx | 方法 | 原生槽 | 语义 |
|---|---|---|---|
| 0 | `bq4()` | 4 | CanRead |
| 1 | `bqb()` | 5 | CanWrite |
| 2 | `bqi()` | 6 | Flush |
| 3 | `bqp()` | 7 | Length |
| 4 | `bqw(long)` | 8 | SetLength |
| 5 | `bq3(byte[], nint)` | 9 | **Read** |
| 6 | `bqa(long, ma2)` | 10 | **Seek**（0/1/2 = Begin/Current/End）|
| 7 | `bqh()` | 11 | Tell |
| 8 | `bqo(byte[], nint)` | 12 | **Write** |

> 含义：**输入/输出流由调用方实现并回调**。纯原生 loader 必须自建一个实现该 vtable 的流对象。

### 8.5 优化器接口 `m9m`（21 方法，槽位表 `qdd`；= 旧版 `IPDFOptimizer`）

| idx | 方法 | 原生槽 | 语义（与 mac 对应）|
|---|---|---|---|
| 0 | `qhz()` | 4 | — |
| 1 | `qh6(m3s)` | 5 | 进度回调（mac `sub_1804EEDA0`/进度）|
| **2** | **`qhd(m9t,int,int,m90,m9e)`** | **6** | **图像采样参数组 1**（≈ mac `+48` 块 / setter `0x550c0`）|
| **3** | **`qhk(...)`** | **7** | **图像采样参数组 2**（≈ `+80` 块 / `0x55140`）|
| **4** | **`qhr(...)`** | **8** | **图像采样参数组 3**（≈ `+112` 块 / `0x551c0`）|
| 5 | `qhy(m9y,bool)` | 9 | 逐页内容流处理 |
| 6 | `qh5()→int` | 10 | — |
| 7 | `qhc()→float` | 11 | — |
| **8** | **`qhj()→bool`** | **12** | **去元数据（mac `RemoveMetadata`）** |
| 9 | `qhq(m9y,bool)→bool` | 13 | 逐页内容流压缩 |
| **10** | **`qhx(bool)`** | **14** | **压缩内嵌字体** |
| **11** | **`qh4(bool)`** | **15** | 字体相关 |
| 12 | `qhb(m9l)` | 16 | 采样/回调节点 |
| 13 | `qhi(int)` | 17 | 设 int（质量）|
| 14 | `qhp(int)` | 18 | 设 int（DPI）|
| 15 | `qhw(m97)` | 19 | 设参数 |
| **16** | **`qh3(m9s)→bool`** | **20** | **去书签/附件/批注/缩略图（按位掩码）** |
| 17 | `qha()→mab` | 21 | 取字体集合 |
| 18 | `qhh(mab)→bool` | 22 | 字体子集/去内嵌 |
| **19** | **`qho()→bool`** | **23** | **去未引用节点（mac `RemoveInvalidateNodes`）** |

### 8.6 可选参数（用户提问的「它提供的可选参数」）

**用户级选项类 = `PDFToolbox/jzh.cs`**（`public class jzh`，`jzh()` 默认值）：

| 属性 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `ImageResolution` | int | 0 | **目标图像 DPI（下采样）**，0 = 不降采样 |
| `RemoveDuplicateResources` | bool | true | 去重复资源 |
| `CompressContentStreams` | bool | true | **内容流压缩** |
| `UnembedFonts` | bool | false | 去内嵌字体 |
| `CompressEmbeddedFonts` | bool | true | **压缩内嵌字体** |
| `RemoveMetadata` | bool | true | **去元数据** |
| `RemoveAttachments` | bool | false | 去附件 |
| `RemoveBookmarks` | bool | false | 去书签 |
| `RemoveComments` | bool | false | 去批注 |
| `RemoveThumbnail` | bool | false | 去缩略图 |
| `RemoveUnreferenced` | bool | true | **去未引用对象** |

另：`jzh.f()` 依 `jzo.Details` 预设表把 `ImageResolution` 映射为 `ImageQuality`（取第一个 `ImageResolution ≤ 目标` 的预设质量，否则 100）。
预设管理 `jz2`：`jzh u()/j()/y()/n()/c()`（5 档质量档位）+ `m(ud4, m9e)`。

**选项 → 原生调用 的翻译器 = `PDFToolbox/jz9.cs`**（`internal class jz9 : f0c`，`y0c` 为主流程）：

```
m9m opt = this.m.Optimizer;                 // u1c.Optimizer → doc.qwt()
this.b(opt);  this.q(opt);  this.m(opt);    // 字体 / 图像 / 清理三类
this.m(opt, 0.3);                           // 进度段
this.m(opt, this.b.j(), 30.0);
```
- `q(m9m)` → `opt.qhd(组1…)`, `opt.qhk(组2…)`, `opt.qhr(组3…)`, `opt.qhi(int)`, `opt.qhp(int)`, `opt.qhw(m97)`
- `m(m9m)` → `opt.qh3(掩码)`、`opt.qhj()`（RemoveMetadata）、`opt.qho()`（RemoveUnreferenced）
- `b(m9m)` → `opt.qhx(true)`, `opt.qh4(true)`（字体压缩/子集），`opt.qhh(mab)`
- `m(m9m, bool, double)` → 逐页 `opt.qhq(page.Core, true)` / `opt.qhy(page.Core, true)`（内容流压缩，`flag = this.b.y().CompressContentStreams`）

### 8.7 打开/保存的托管封装 `PDFCore/m9v.cs`（可直接照抄成 loader）

```csharp
// 打开
new mae(File.Open(path,4,1,1), true)  →  doc.qwi(stream, Encoding.UTF8.GetBytes(pwd), len)  → OpenResult
// 另存
new mae(File.Create(path), true)      →  doc.qww(stream, saveOptions)     // 或
                                      →  doc.qw3(stream, m9b, saveOptions)
```
`mae : m3z, mwn, mav`（`mae.cs`）——托管侧用 `System.IO.Stream` 实现 `mav` 的 9 个方法。

### 8.8 结论（loader 可用的最小调用链）

```
CreateFactory()                                   [导出]
  doc = ((fn*)factory_vt[18])(&gFactory)          [CreateDocument → 528B]
  ((fn*)doc_vt[5])(doc, in_stream, pwd, len)      [qwi Open]
  opt = ((fn*)doc_vt[22])(doc)                    [qwt GetOptimizer]
  ((fn*)opt_vt[6/7/8])(opt, a,b,c,d,e)            [qhd/qhk/qhr 三组图像参数]
  ((fn*)opt_vt[20])(opt, mask)                    [qh3 去书签/附件/缩略图]
  ((fn*)opt_vt[12])(opt)                          [qhj 去元数据]
  ((fn*)opt_vt[23])(opt)                          [qho 去未引用]
  ((fn*)opt_vt[14/15])(opt, true)                 [qhx/qh4 字体]
  ((fn*)doc_vt[7])(doc, out_stream, save_opts)    [qww 另存]  或 doc_vt[24]（opcode 13）
其中 in_stream/out_stream 需自建一个实现 mav vtable（槽 4..12：CanRead/CanWrite/Flush/Length/SetLength/Read/Seek/Tell/Write）的对象。
```

---

## 9. 二次会话突破（2026-10-17）：参数通道解码 + 图像重编码总开关

> 本轮用 `ctypes` loader 直接驱动 `libPdfCore.dll`，并用**内存探针**逐字段 fuzz 优化器参数块，最终使参数真正生效。

### 9.1 地址更正

| 项 | 值 |
|---|---|
| 文档槽 **22** = `qwt()` GetOptimizer | **`sub_18001DC40`**（§8.3 表内误写成 `sub_18001DCC0`；后者是槽 23） |
| `sub_18001DC40` 行为 | `sub_180089F00(engine)` 校验 → `sub_1800F0100(&obj, engine)` 建优化器 → 返回 `obj` |
| 优化器对象 | **128 B**，vtable `off_182024700`；`sub_1800F0100` 分配 → `sub_1800EF400(obj, engine)` 初始化 |
| 优化器 vtable（自槽 4 起，RVA） | [4]`ef580`(qhz) [5]`ef590`(qh6) **[6]`ef620`(qhd)** **[7]`ef690`(qhk)** **[8]`ef700`(qhr)** **[9]`ef770`(qhy)** [10]`ef880` [11]`ef8f0` **[12]`ef960`(qhj)** **[13]`ef9b0`(qhq)** **[14]`efaa0`(qhx)** **[15]`efae0`(qh4)** **[16]`efb20`(qhb)** **[17]`efb90`(qhi)** **[18]`efba0`(qhp)** **[19]`efbb0`(qhw)** **[20]`efbc0`(qh3)** [21]`efc30`(qha) [22]`efee0`(qhh) **[23]`f00b0`(qho)**；表尾 `0x200000000`/`0x300000004` 为 vtable 终止标记 |
| 唯一能体现优化器改动的写出槽 | `doc[43]`（应用层 `jy2` 另存）；`doc[7]`(qww) 实测只写 306 B 残档，`doc[8]/doc[24]` 不消费参数 |

### 9.2 优化器 128 B 布局

| 偏移 | 含义 |
|---|---|
| +0 | vtable `off_182024700` |
| +8 | 引用计数 |
| **+16** | `sub_180635C90(obj80, engine)` 新建的 **80 B「优化器」**（其 `+72` = `sub_180CC6270` 新建的 **40 B 编码器**） |
| +24 | engine |
| **+32 / +64 / +96** | **三组 32 B 图像参数块**（组 1 彩色 / 组 2 灰度 / 组 3 单色），`sub_1800EF400` 初始化 |

**32 B 参数块字段（本轮 fuzz 实测解码，见 §9.4 数据）**

| dword | 偏移 | 语义 | 对应 setter |
|---|---|---|---|
| 0 | +0 | **下采样使能**（0 = 关闭，>0 = 启用） | qhd/qhk/qhr 的 `a2` |
| 1 | +4 | **目标 DPI-X**（计算新尺寸：`new = dword1 * 原尺寸 / 当前DPI`） | `a3` |
| 2 | +8 | **目标 DPI-Y**（与当前 DPI 比较，`当前 ≤ 目标` 则不下采样） | `a4` |
| 3 | +12 | **编码模式**（**2 = DCT/JPEG**，8 = 另一编码器，其余 = 不重编码） | `a5` |
| 4 | +16 | 保留 | `a6` |
| 5 (float) | +20 | **质量 0..100**（`-1`＝用默认回调值） | **qhi**(组1) / **qhp**(组2) / 组3 无 setter |
| 6 | +24 | 保留（字节） | — |
| 7 | +28 | **1 = 启用图像重编码**（对象初始值是 **2 = 关闭**） | **`qhw`** |

> **根因**：图像重编码的总开关是 `dword7`，而 `qhw` 默认传 2/3 ⇒ 参数永远不生效。**必须 `qhw(1)`**。

### 9.3 图像重编码管线（qhy）

```
opt[9] qhy(page, flag) = sub_1800EF770
  ├ sub_1801D36E0(page) = QI(IID {732EB1B3-83BE-4294-847D-B7C1DA8B6095})
  ├ sub_1800C42F0(v6)   → img
  └ sub_18063A130(*(opt+16), img, flag, opt+32, opt+64, opt+96)   // 80B 对象 + 三组参数指针
       └ sub_180CC62B0(40Bobj, img, flag, g1, g2, g3)
            ├ sub_180CC6380(img+16, 0, &vec)                    // 取图像（16B 条目向量）
            └ sub_180CC6660(40Bobj, flag, g1, g2, g3, &vec)      // 逐图像
                 └ sub_180CC6EB0(40Bobj, flag, g1, g2, g3, entry)  // ★ 参数消费点
                      ├ sub_180CC8AF0 → 图像类型码 v15
                      │    switch(v15): 0→组1(彩色) 1→组2(灰度) 2→组3 其他→直接复制组1
                      ├ sub_180CC89D0 → 当前 DPI(X=v105.d0, Y=v96)
                      │    if (当前X <= dword2 || 当前Y <= dword2) 不下采样
                      ├ new_w/h = dword1 * 原尺寸 / max(当前X,当前Y)
                      │    if (new_area >= src_area || (dword3==1 && src_area < 10001)) 不缩放
                      ├ sub_180CCE310(...) → 缩放
                      └ dword3==1 时质量套旧版公式 ((q/100)^2*0.3+0.001)*100
                           （常量 0.3f/0.001f/100.0f 实证出现于该函数）
                      └ sub_180CC9930(img, ?, ?, flag, dword3, quality, dword7) → 实际编码
opt[13] qhq(page, flag) = sub_1800EF9B0 → sub_18063A200(*(opt+16), img, flag, 0, -2)  // 纯内容流压缩，不消费参数块
```

### 9.4 内存探针实测（doc3.pdf：11 051 B，1 张 364×140 DeviceRGB/DCTDecode，8591 B）

固定 `dword0=1, dword1=2, dword3=2, dword7=1`，仅 qhy：

| 变量 | 取值 → 输出字节 | 结论 |
|---|---|---|
| `dword5` 质量 | 1→3787, 10→4429, 25→5339, 45→6159, 60→6728, 75→7719, 90→10716, 100→11021 | **质量单调生效** |
| `dword3` 模式 | 2→6159, 8→5983，其余 →11021 | 只有 2/8 会重编码 |
| `dword1/2` DPI | 0→7604, 10→4105, 36→4334, 72→6159, ≥96→7604 | **下采样生效**（原图有效 DPI≈96） |
| `dword0` | 0→7604, 1/2→6159 | 缩放使能 |
| `dword7` | 0/2/3/8→11021，**1→6159** | **总开关** |

### 9.5 loader 实测（已修参数映射）

`python PDF优化压缩_libPdfCore调用器.py <in> <out> 43 <level>`：

| level | 预设(DPI/质量) | doc3 输出 |
|---|---|---|
| 0 | 72 / 45 | **4 815 B**（图像 364→**273**，DCTDecode 重编码，实证 `Width 273`） |
| 1 | 96 / 55 | 6 696 B |
| 2 | 120 / 70 | 8 371 B |
| 3–6 | ≥150 / 85–100 | 9 676 B（原图 DPI ≤150 ⇒ 不下采样，仅清理元数据/去重） |

（修复前：全档位恒为 9 676 B，参数完全无效）

### 9.6 成品 CLI（`PDF优化压缩_libPdfCore调用器.py`）

```
python PDF优化压缩_libPdfCore调用器.py <源.pdf> <输出.pdf> [选项]

图像压缩（有损）
  -l/--level 0..6        质量档位预设（给出时覆盖下两项）：
                         0=72dpi/45  1=96/55  2=120/70  3=150/85  4=300/95  5=600/100  6=1200/100
  --dpi N                目标图像 DPI（>=0，默认 120；0 = 一律不降采样）→ ReduceSampleData.targetDpi (+4)
  --dpi-min N            降采样阈值 DPI（默认 = --dpi）→ ReduceSampleData.thresholdDpi (+8)
                         当前 PPI ≤ N 的图像直接跳过降采样
  --quality N            重编码质量 0..100（默认 70；仅 --encoder 2 生效）→ ReduceSampleData.quality (+20 float)
  --encoder 2|8          2 = DCTDecode/JPEG 有损（默认）    8 = FlateDecode/zlib 无损 → encodeMode (+12)
结构清理（默认全部开启；想保留哪类就加对应的 --keep-*）
  --keep-pieceinfo       保留 /PieceInfo 应用私有数据        [默认删除]  掩码位 0x01
  --keep-thumbnail       保留 /Thumb 页面缩略图              [默认删除]  掩码位 0x02
  --keep-bookmarks       保留 /Outlines 书签 / 大纲          [默认删除]  掩码位 0x04
  --keep-attachments     保留 /Names/EmbeddedFiles 附件      [默认删除]  掩码位 0x08
  --keep-annotations     保留 /Annots 批注 + /AcroForm/Fields 表单字段  [默认删除]  掩码位 0x10
  --keep-metadata        保留元数据（XMP/Info）  [默认删除]  （qhj）
  --keep-unreferenced    保留未被引用的对象      [默认删除]  （槽 23：清理 Dests/OpenAction/AA）
  --remove-flags N       直接给删除掩码，覆盖上面五项 --keep-*（默认 0x1F；0 = 全保留）
逐页优化开关（默认全开）
  --no-image             跳过 qhy（图像重编码）
  --no-content-compress  跳过 qhq（内容流压缩）
  --no-font-compress     不压缩内嵌字体（槽 14 EnableFontMerge / 槽 15 EnableFontSplite）
  --unembed-fonts        取消内嵌字体（槽 21 GetCancelableEmbeddedFonts → 槽 22 CancelFontsEmbedded）
其它
  --slot N               另存槽位（默认 43）        -q/--quiet  不打印流回调细节
```
**无需界面、无需登录**，只经 `CreateFactory` 一个导出入口驱动 `libPdfCore.dll`。
`--quality` 越界 / `--dpi` 为负 / `--encoder` 非 2|8 均会直接报错。

#### 9.6.1 每个参数的取值实测确认

| 参数 | 实测证据 |
|---|---|
| `--encoder 2` | 输出图像为 **DCTDecode/JPEG**（`doc3`：`/Filter /DCTDecode`，流头 `\xff\xd8\xff\xe0 JFIF`）|
| `--encoder 8` | 输出图像为 **FlateDecode/zlib**（`fz2_H08.pdf` 中 DCTDecode 计数归零，图像流头 `x\x9c`）→ 无损，`--quality` 无效 |
| `--quality` | doc3 单调：1→3787、10→4429、25→5339、45→6159、75→7719、100→11021 B |
| `--dpi` | doc3：0→7604、10→4105、36→4334、72→6159、≥96→7604 B；**仅当图像自带 DPI > 目标值**才降采样 |
| 掩码位 `0x02` | 符号 `RemoveUnimportantNodes::sThumb` → **`/Thumb`**。`simple_thumbnail.pdf`（4642 B）：掩码 2 → **491 B**；加 `--keep-thumbnail` → 4551 B |
| 掩码位 `0x04` | 符号 `::sOutlines` → **`/Outlines`**。`page_labels.pdf`（10080 B）：掩码 4 → `/Outlines` 从 1 变 0，8266→8037 B；`--keep-bookmarks` → 保留 |
| 掩码位 `0x08` | 符号 `::sNames` + `::sEmbeddedFiles` → **`/Names`(`/EmbeddedFiles`)**，并额外删页面上 `CBaseAnnot::GetKind()==17`（FileAttachment）批注。`embedded_attachments.pdf`（10447 B）：掩码 8 → **5670 B** |
| 掩码位 `0x10` | 符号 `::sAcroForm` + `::sFields` → **`/AcroForm/Fields`**（数组 clear），并删页面 `/Annots`。`redact_annot.pdf`（739 B）：掩码 16 → **586 B** |
| 掩码位 `0x01` | 符号 `::sPieceInfo` → **`/PieceInfo`**（应用私有数据）。样本中没有该键，故此前实测"无可观测效果"——**先前"重复资源去重"的归类是错的** |

#### 9.6.1b mac 版符号 ↔ Windows 版结构交叉验证（2026-10-17）

> 依据用户指引：`PDFelement 11.4.22\...\libPdfCore.dylib.i64`（同一份跨平台代码，保留 126 821 个 C++ 符号）。**仅用符号名做"命名"，结构一致性一律用字段偏移与调用形态验证**（未使用哈希/字符串匹配）。

**完整槽位对照表**（mac Itanium vtable 的 `_ZTVN9nsPdfCore17CPdfOptimizerImplE` @ `0x32ad308`；19 个接口方法**逐槽偏移恒为 −3**：Windows 槽 = mac 槽 − 3）

| Windows 槽 | Windows RVA | mac 符号（11.4.22）| 结构一致性证据（参数个数 / 字段偏移 / 调用形态）|
|---|---|---|---|
| 4 | `ef580` | `CPdfOptimizerImpl::RemoveUnlessObjects()` | 同为无参函数；**Windows 版实现为空桩**（直接返回错误码，无任何转发）|
| 5 | `ef590` | `RemoveInvalidateResource(IPDFProgress*)` | 同为 1 个指针参数；Windows 把入参包成 `{off_18201BCB0, arg}` 再调 `sub_180636670`（`off_18201BCB0` 与 §2 的进度回调用同族 vtable）|
| 6 | `ef620` | `SetColorImageParameter(OptmDownSampleModeEnum,int,int,OptmImgEncodeModeEnum,OptmImgQualityEnum)` | **5 个参数**；写组 1 的 `+32..+48`（dword0..4）|
| 7 | `ef690` | `SetGrayImageParameter(...)` | 同形 5 参；写组 2 的 `+64..+80` |
| 8 | `ef700` | `SetMonoImageParameter(...)` | 同形 5 参；写组 3 的 `+96..+112` ⇒ **组 3 = 单色**（此前只是推测）|
| 9 | `ef770` | `ReduceImagesSize(IPDFDocPage*,bool)` | 2 参；转发 `(*(opt+16), page, flag, opt+32, opt+64, opt+96)` |
| 10 | `ef880` | `CountUnlessObjects()` | 无参 → 返回计数（`sub_180635E90`）|
| 11 | `ef8f0` | `CalcMiddleImageDPI()` | 无参 → 返回 **double** 型 DPI（`sub_18063A580`）|
| 12 | `ef960` | `RemoveMetadata()` | 无参 → bool |
| 13 | `ef9b0` | `ReduceContentStream(IPDFDocPage*,bool)` | 2 参 |
| 14 | `efaa0` | `EnableFontMerge(bool)` | 1 个 bool |
| 15 | `efae0` | `EnableFontSplite(bool)` | 1 个 bool |
| 16 | `efb20` | `RemoveInvalidateNodes(OptmRemoveInvalidateNodesEnum)` | 1 个枚举参数；`sub_18063ADE0` 内 `(mask & 1)` 门控并处理 `Root` / `AcroForm` / `Fields` |
| 17 | `efb90` | `SetColorImageQuality(int)` | 同为 `*(float*)(+52)=(float)a2` |
| 18 | `efba0` | `SetGrayImageQuality(int)` | 同为 `*(float*)(+84)=(float)a2` |
| 19 | `efbb0` | `SetImageJpegEncodeMode(OptImgEncodeJpegModeEnum)` | 同为 `a[15]=a[23]=a[31]=a2` → `+60/+92/+124` |
| 20 | `efbc0` | `RemoveUnimportantNodes(OptmRemoveUnimportantNodesEnum)` | 同 5 位掩码（1/2/4/8/0x10）+ 同 `GetKind()==17` + 同 `is_dict` 前置校验 |
| 21 | `efc30` | `GetCancelableEmbeddedFonts()` | 无参 → 构造并返回字体集合对象 |
| 22 | `efee0` | `CancelFontsEmbedded(IPDFReadOnlyCollection<IPDFCancelableEmbeddedFont*,IPDFIterator>*)` | 1 个集合参数；内部以 `(*(*a2+40))(a2)` / `(*(*v5+32))(v5)` 遍历 |
| 23 | `f00b0` | **12.x 新增，11.4.22 无此槽** | 无参 → bool；调用 `sub_18063E490`，其中出现 `"Dests"` `"OpenAction"` `"AA"` `"A"` `"Dest"` ⇒ 清理不可达的**导航/动作节点**。托管接口中它就是 `qho()`「去未引用」|

> 说明：`RemoveUnlessObjects`（mac 槽 7）在 Windows 12.x 里槽 4 只剩空桩，而槽 23 的无参方法承担了「移除无用/不可达节点」的职责；托管 `m9m` 的第 0 个方法（`qhz()`）对应这个空桩，故其返回值恒为错误码——这也解释了早前实测 `qho()` 返回 0 的现象并非失败。

#### 9.6.1c `CBaseImageOptimizer::ReduceSampleData`（32 B）字段定名

证据来源（全部为 mac 符号签名 + 反编译 + Windows 侧实际读取）：
- `CPdfOptimizerImpl::Set{Color,Gray,Mono}ImageParameter(OptmDownSampleModeEnum, int, int, OptmImgEncodeModeEnum, OptmImgQualityEnum)` —— 前 5 个 dword 的**类型名**由符号直接给出；
- `CImageUtil::AdjustQuality(ImageEncodeMode, ImageQuality)` @ `0x335760` 与内置质量表；
- `CImageUtil::AdjustEncodeMode(ReduceSampleData const&, ImageType, int)` @ `0x335fb0`；
- `CImageUtil::GetImagePpi(CPDF_FormObject*, float&, float&)` @ `0x335880`；
- `CBaseImageOptimizer::compressSingleImage` @ `0x334720`（只读 `+16`/`+20`/`+24`）；
- Windows 侧 `sub_180CC6EB0` 的实际读取路径。

| 偏移 | 字段 | 类型（mac 符号）| 语义 / 证据 |
|---|---|---|---|
| +0 | `downSampleMode` | `IPDFOptimizer::OptmDownSampleModeEnum` | 0 = 不降采样；实测 1/2 会触发降采样 |
| +4 | `targetDpi` | int | 新尺寸 = `targetDpi × 原尺寸 ÷ 当前PPI`（`sub_180CC6EB0` 用 dword1 广播后乘） |
| +8 | `thresholdDpi` | int | 当前 PPI(X 与 Y) ≤ 此值则**跳过**降采样（同函数 `*(float*)curX <= (float)dword2` / `curY <= dword2`）；实践中与 +4 取同一数值 |
| +12 | `encodeMode` | `IPDFOptimizer::OptmImgEncodeModeEnum` | 实测 2 = DCTDecode/JPEG，8 = FlateDecode，其余不重编码 |
| +16 | `qualityEnum` | `IPDFOptimizer::OptmImgQualityEnum` | **0..6 档位枚举**（`AdjustQuality` 内先 `min(q,6)` 再查表）；仅在 +20 未设置时参与 |
| +20 | `quality`（float）| — | 显式质量值，默认 `-1.0f` = 未设置。`SetColorImageQuality/SetGrayImageQuality(int)` 直接写此字段 → CLI 的 `--quality 0..100` 就是它 |
| +24 | `reserved` | int | `compressSingleImage` 从 +24 起读 8 字节，但只提取**高 dword**（= +28），**+24 从未被使用** |
| +28 | `jpegEncodeMode` | `IPDFOptimizer::OptImgEncodeJpegModeEnum` | `SetImageJpegEncodeMode` 写此字段；库对象初值 2 = 不重编码 JPEG ⇒ 这就是 CLI 新增 `--jpeg-mode` 的原因 |

**内置质量档位表**（`AdjustQuality` 以 `ImageQuality` 枚举 0..6 索引）：

| 表（mac RVA）| 7 档取值 | 适用 |
|---|---|---|
| `unk_247A3F0` | `[45, 55, 65, 75, 85, 95, 100]` | 图像**不是** DCT/JPX 时（`GetImageType2()==0`）|
| `flt_247A410` | `[23, 33, 43, 53, 66, 86, 100]` | 其他情形 |

且内部 `ImageEncodeMode`（与公开的 `OptmImgEncodeModeEnum` 不是同一枚举）在 `AdjustQuality` 中取 1/2/4：1 → 查表并做 `>=6 → 100` 特判；2 → 查表；4 → 返回 `-5.0`（其余返回 `0.0`）。

**当前 PPI 计算 `GetImagePpi`**：`PPI = 图像像素宽(高) ÷ (放置 bbox 宽(高) pt ÷ 72)`；先置 `*x = *y = 0.0`，无 bbox 时回退用图像自身 —— 与 Windows `sub_180CC89D0` 同构，这正是"当前 PPI ≤ 阈值就跳过降采样"判据的数据来源。


> 结论：Windows 128 B 优化器与 mac `CPdfOptimizerImpl` **逐字段、逐参数同构**。此前我把 `qhw` 称作"图像重编码总开关"并不准确——它其实是 `SetImageJpegEncodeMode`，只是**库对象初值为 2（不重编码 JPEG）**，所以必须显式设成 1 才会重编码。CLI 已新增 `--jpeg-mode`（默认 1）暴露该参数。


#### 9.6.2 实测（真实中文扫描/合并文档 `入职材料合并版丁金金.pdf`：9 372 601 B / 17 页 / 21 张图）

| 命令 | 输出 | 压缩率 |
|---|---|---|
| `--level 0` | **862 215 B** | **−90.8 %** |
| `--level 2` | 2 217 522 B | −76.3 % |
| `--level 6` | 9 368 755 B | ≈0（原图 DPI 未超阈值，不下采样） |

doc3.pdf（11 051 B，1 张 364×140 DeviceRGB/DCTDecode）对照：

| 命令 | 输出 |
|---|---|
| `--level 0` | 4 815 B（图像 364→273 px，DCTDecode 重编码）|
| `--level 0 --remove-flags 0` | 4 815 B（同上：图像部分与清理无关）|
| `--dpi 150 --quality 85` | 9 676 B（150dpi 不触发降采样）|
| `--dpi 0 --encoder 8` | 8 079 B（无损 Flate 重编码，不降采样）|
| `--no-image`（其余默认） | 9 676 B（仅结构清理）|
| 全部 `--keep-*` + `--remove-flags 0` + 三个 `--no-*` | 11 021 B（≈原样另存）|

产物校验：把 `--level 0` 的输出再喂回本工具 → `OpenResult = 1`、页数 17 一致、体积 862 215 → 863 189 B（幂等，输出文件有效）。

### 9.7 遗留问题

- **`SolidOCR.pdf`（1 页 / 398 张 2bpp DeviceGray Flate 图，17.8 MB）**：在模式 {2,4,6,8} × 质量 {1,45} × DPI {10,72} 全组合下输出**逐字节不变**（17 820 396 B）。该文件的图像未被 `sub_180CC6660` 枚举到（疑似 2bpp/图集型图像在类型分类或条目枚举分支上不覆盖）。说明：该文件的 `/Type/Catalog` 与 398 个 `/Type/XObject` 在明文里可见，但**页树与 `/Resources` 经过压缩**（明文里搜不到 `/Type/Page`、`/Resources` 计数为 0），是 SolidFramework 生成的 OCR 样张。普通连续调图像（doc3 的 DCT 图、真实扫描件的 JPEG 页）均正常。
- `doc[7]`(qww) 在当前 loader 的流实现下只写出 306 B 残档，原因未查（可能流回调约定或该槽前置状态不同）。

---

*记录同步时间：2026-10-17（含托管侧还原 + 二次会话参数解码）｜ 依据 IDB 快照 sha256 `edd753f4…3d2a505` ｜ 工具：ida-multi-mcp（实例 `4r7q`）+ capstone + dnSpy.Console + ctypes 内存探针*
