import logging
import secrets

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .api import create_routes
from .config import Settings
from .errors import UserError
from .repository import Repository
from .security import install_security
from .services import TaskService


def create_app(settings=None):
    settings = settings or Settings.from_environment()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_bytes(32),
        MAX_CONTENT_LENGTH=settings.max_request_bytes,
        MAX_FORM_MEMORY_SIZE=1024 * 1024,
        MAX_FORM_PARTS=settings.max_pdfs + 5,
        TRUSTED_HOSTS=["127.0.0.1", "localhost"],
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_NAME="invoice_session",
    )
    repository = Repository(settings.data_dir / "records.sqlite3")
    service = TaskService(settings, repository)
    app.extensions.update(repository=repository, task_service=service)
    install_security(app)
    app.register_blueprint(create_routes(service, repository))

    @app.errorhandler(UserError)
    def user_error(exc):
        return jsonify(error=str(exc)), exc.status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        messages = {
            400: "请求格式或访问地址无效。",
            404: "页面或资源不存在。",
            405: "请求方式不支持。",
            413: "文件总大小超过 80 MB，请拆分处理。",
        }
        return jsonify(error=messages.get(exc.code, "请求无法处理。")), exc.code

    @app.errorhandler(Exception)
    def unexpected(exc):
        logging.getLogger(__name__).error("request failed: %s", type(exc).__name__)
        return jsonify(
            error="操作未完成，请检查磁盘空间或重新导入；问题持续时请联系维护人员。"
        ), 500

    return app
