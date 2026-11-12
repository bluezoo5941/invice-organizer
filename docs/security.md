# 安全与数据边界

## 信任边界

面向单个 Windows 登录用户的本机工具，监听 127.0.0.1:8765。没有多人共享或远程鉴权承诺。任何能控制本机用户进程/磁盘的人都可访问数据，这是操作系统账户边界，不由随机任务 ID 隔离。

本地页面建立随机签名会话；所有 API（含 GET 下载）验证会话与 X-CSRF-Token。Host 白名单、Origin 同源检查、Sec-Fetch-Site 检查、SameSite=Strict、禁止跨域与嵌入降低其他网页访问本机工具的风险。会话签名密钥每次启动随机生成，不写入代码；重启需刷新页面重新建立会话。HTTP 仅限回环，因此不设置只适用于 HTTPS 的 Secure Cookie。不得直接改成 0.0.0.0 部署。

## 输入与文件

上传数量、扩展名、大小、文件头、XLSX ZIP 解压体积、行列数及 PDF 页数均校验。安装 defusedxml 防 XML 实体扩展。PDF 上传副本用随机内部 ID 存储，拒绝路径和控制字符，客户端不能指定服务器读取路径。导出下载查已完成任务的清单。账单下载校验任务 ID 后返回对应任务的 Excel 副本。

解析、合并在独立子进程执行，90 秒超时；最多同时两项处理。子进程不执行文件提供的脚本、SQL、命令或链接。当前没有 OS 级内存配额，不应作为接收任意互联网恶意文档的公共服务。实际处理本机业务文件，异常文件需人工检查。

## 数据与事务

SQLite WAL、参数化查询、唯一 request_key、BEGIN IMMEDIATE 和条件状态更新防止同次重试/并发重复处理。相同请求键若文件内容不同返回 409。同内容新建任务被允许，不静默删除历史。

迁移文件由工程控制，不拼接外部值。任务数据与文件均在 data/，不在 static。导出先生成 .part ZIP，再原子改名；只有数据库 complete 才能下载。故障或强制关机后保留源副本，启动将中断任务显式标失败，不伪造完成。

日志仅记录错误类别，不含个人字段、文件正文或完整异常堆栈。界面采用 textContent 和模板自动转义，无 innerHTML；CSV 对危险公式前缀加文本保护。

## 依赖来源

- Flask 配置与安全：https://flask.palletsprojects.com/en/stable/web-security/
- Flask 3.1 配置：https://flask.palletsprojects.com/en/stable/config/
- Waitress：https://docs.pylonsproject.org/projects/waitress/en/stable/
- openpyxl 安全提示：https://openpyxl.readthedocs.io/en/stable/
- pypdf 合并 API：https://pypdf.readthedocs.io/en/6.21.4/user/merging-pdfs.html

运行依赖固定在 requirements.txt。安装后运行 `python -m pip check` 检查依赖兼容性，发布前可使用 `pip-audit` 查询已知漏洞。

