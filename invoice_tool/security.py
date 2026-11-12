import secrets

from flask import request, session

from .errors import UserError


def install_security(app):
    @app.before_request
    def protect():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            raise UserError("仅支持本机访问。", 403)
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            raise UserError("不允许跨站访问本机工具。", 403)
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            raise UserError("请求来源不匹配，请从本机页面操作。", 403)
        if request.path.startswith("/api/"):
            token = session.get("csrf")
            if not token or not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", ""), token
            ):
                raise UserError("会话已失效，请刷新页面。", 403)

    @app.after_request
    def headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response
