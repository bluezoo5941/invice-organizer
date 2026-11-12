# 发票归集

> 导入一份机票账单和一批 PDF，按项目生成可核对的发票包。

发票归集是一个在 Windows 本机运行的小工具。它按**乘机人姓名和完整票号**匹配 Excel 记录与 PDF 文件名，让你先核对缺件、重复和归属冲突，再合并资料齐全的项目。

## 快速开始

需要 **Windows** 和 **Python 3.12 或更新版本**。在项目根目录打开 PowerShell，逐行运行：

```powershell
.\setup.ps1
.\start.cmd
```

首次安装依赖需要联网。安装完成后，日常使用双击 `start.cmd` 即可。浏览器会打开 [本地工作台](http://127.0.0.1:8765/)，关闭启动窗口即可停止服务。

<details>
<summary>手动安装与启动</summary>

在项目根目录打开 PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

</details>

## 准备文件

账单使用 `.xlsx` 格式，包含以下三列。PDF 文件名使用「乘机人姓名-完整票号.pdf」。下面是两条虚构记录：

| 票号 | 乘机人姓名 | 项目名称 | 对应的 PDF 文件名 |
| --- | --- | --- | --- |
| `001-1234567801` | 示例乘机人甲 | 项目 A | `示例乘机人甲-001-1234567801.pdf` |
| `001-1234567802` | 示例乘机人乙 | 项目 A | `示例乘机人乙-001-1234567802.pdf` |

将票号列保存为文本，避免丢失开头的 `0`。表头也支持「电子客票号」「员工姓名」「项目编号」等别名。如果有多张符合条件的工作表，将目标工作表另存为单独的 Excel 再导入。[查看完整匹配规则](docs/requirements.md)

## 从导入到下载

1. **选择资料** · 选一份账单，再选多份 PDF 或整个发票文件夹。
2. **核对匹配** · 点击「开始匹配」，展开项目查看明细。缺件、重复或归属冲突会单独标出。点击账单文件名，可下载该任务保存的 Excel 副本。
3. **导出归集** · 资料齐全的项目各生成一份 PDF，页面顺序跟随账单行顺序。只要一个项目有异常行，该项目就会暂缓导出。

可以单独下载项目 PDF，也可以下载全部结果：

```text
项目发票.zip
├── g001_项目 A.pdf
├── 归集明细.csv
└── 异常与清洗记录.csv
```

## 数据保存在本机

服务只监听本机回环地址。上传副本、SQLite 任务记录和导出结果默认保存在 `data/`，原始文件保留原样。可以从「历史任务」重新打开以前的结果，也可以通过 `INVOICE_DATA_DIR` 指定其他私有数据目录。[查看安全与数据边界](docs/security.md)

## 开发与测试

| 想了解什么 | 从哪里读起 |
| --- | --- |
| Excel 表头、票号和文件名解析 | [parsing.py](invoice_tool/parsing.py) |
| 精确匹配、项目分组和异常判断 | [matching.py](invoice_tool/matching.py) |
| PDF 合并与 CSV、ZIP 生成 | [pdf_service.py](invoice_tool/pdf_service.py) |
| Flask 接口、任务处理和 SQLite 历史 | [api.py](invoice_tool/api.py)、[services.py](invoice_tool/services.py)、[repository.py](invoice_tool/repository.py) |
| 浏览器界面 | [templates](invoice_tool/templates/) 和 [static](invoice_tool/static/) |

测试使用临时生成的账单和 PDF。在完成安装后，从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m unittest discover -v
```
