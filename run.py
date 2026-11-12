"""Loopback-only launcher. Hold a socket first to prevent multiple writers/recovery races."""

import argparse
import logging
import socket
import webbrowser

from waitress import serve

from invoice_tool.app import create_app
from invoice_tool.config import Settings


def main():
    parser = argparse.ArgumentParser(description="发票归集：本机 Excel/PDF 工具")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", 8765))
        listener.listen(128)
    except OSError:
        listener.close()
        print(
            "端口 8765 已被使用。若工具已启动，请打开 http://127.0.0.1:8765；否则先关闭占用端口的程序。",
            flush=True,
        )
        return 1
    try:
        app = create_app(Settings.from_environment())
        app.extensions["repository"].recover_interrupted()
        print("发票归集已启动：http://127.0.0.1:8765（关闭此窗口将停止服务）", flush=True)
        if not args.no_browser:
            webbrowser.open("http://127.0.0.1:8765")
        serve(
            app,
            sockets=[listener],
            threads=4,
            channel_timeout=120,
            max_request_body_size=80 * 1024 * 1024,
        )
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
