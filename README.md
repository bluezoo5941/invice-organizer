# 发票归集

把机票 Excel 账单与 PDF 发票匹配，按项目导出合并后的 PDF。支持在本机浏览器核对缺件、重复和归属冲突，查看历史任务并下载原始账单副本。

## 在 Windows 上运行

安装 Python 3.12 或更新版本。在项目根目录打开 PowerShell，执行：

```powershell
./setup.ps1
./start.cmd
```

首次安装依赖需要联网。启动后访问 [本地工作台](http://127.0.0.1:8765/)，关闭启动窗口可停止服务。

也可以通过 PowerShell 手动创建环境并启动：

```powershell
py -3 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run.py
```

## 文件格式和使用流程

1. 准备一份 `.xlsx` 账单，包含「票号」「乘机人姓名」「项目名称」三列。票号按文本保存，以保留前导零。
2. 选择若干 PDF 或一个发票文件夹。文件名格式为「乘机人姓名-完整票号.pdf」，例如 `示例乘机人-123-4567890123.pdf`。
3. 点击「开始匹配」。工具按姓名和完整票号精确查找 PDF，按项目归组。展开项目或异常清单可以核对结果，点击账单名可下载该任务保存的 Excel。
4. 导出可归集的项目。一个项目中有任意一行异常时，该项目整体暂缓导出。其他匹配完整的项目可以继续。
5. 下载单个项目 PDF，或下载包含项目 PDF、归集明细及异常与清洗记录的 ZIP。

Excel 表头支持别名，如「电子客票号」「员工姓名」「项目编号」。如果发现多张符合条件的工作表，把需要处理的那张单独另存再导入。详细规则见 [匹配规则](docs/requirements.md)。

## 数据位置

服务只监听本机回环地址。上传副本、SQLite 数据库和生成结果默认保存在项目的 `data/` 目录。可通过 `INVOICE_DATA_DIR` 环境变量选择其他私有目录。源文件保持原样。详见 [安全与数据边界](docs/security.md)。

## 源码和测试

- `invoice_tool/parsing.py` 读取 Excel 并规范化票号与文件名。
- `invoice_tool/matching.py` 执行精确匹配，汇总项目和异常。
- `invoice_tool/pdf_service.py` 使用 pypdf 合并并校验 PDF，生成 CSV 和 ZIP。
- `invoice_tool/api.py` 提供 Flask 接口，`services.py` 管理任务，`repository.py` 保存历史。
- `invoice_tool/templates/` 和 `invoice_tool/static/` 包含浏览器界面。

测试会临时生成账单和 PDF，可以直接在没有业务数据的环境运行：

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m unittest discover -v
```
