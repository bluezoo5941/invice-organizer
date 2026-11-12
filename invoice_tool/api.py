import secrets

from flask import Blueprint, jsonify, render_template, request, send_file, session

from .errors import UserError


def create_routes(service, repository):
    routes = Blueprint("app", __name__)

    @routes.get("/")
    def home():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return render_template("index.html", csrf=session["csrf"])

    @routes.get("/api/tasks")
    def history():
        try:
            offset = int(request.args.get("offset", "0"))
        except ValueError as exc:
            raise UserError("分页参数无效。") from exc
        if offset < 0 or offset > 100000:
            raise UserError("分页参数超出范围。")
        return jsonify(tasks=repository.list(50, offset))

    @routes.get("/api/tasks/<task_id>")
    def get_task(task_id):
        return jsonify(repository.get(task_id))

    @routes.post("/api/tasks")
    def create_task():
        if set(request.form) - {"sheet"} or set(request.files) - {"workbook", "pdfs"}:
            raise UserError("请求包含不支持的字段。")
        if len(request.files.getlist("workbook")) != 1 or len(request.form.getlist("sheet")) > 1:
            raise UserError("请提交一份账单。")
        task = service.create(
            request.files.get("workbook"),
            request.files.getlist("pdfs"),
            request.form.get("sheet", "").strip(),
            request.headers.get("Idempotency-Key"),
        )
        return jsonify(task), 201

    @routes.post("/api/tasks/<task_id>/export")
    def export(task_id):
        if request.get_data():
            raise UserError("导出请求无需提交额外字段。")
        return jsonify(service.export(task_id))

    @routes.get("/api/tasks/<task_id>/workbook")
    def download_workbook(task_id):
        path, name = service.workbook_download(task_id)
        return send_file(path, as_attachment=True, download_name=name)

    @routes.get("/api/tasks/<task_id>/download")
    def download(task_id):
        if set(request.args) - {"group"}:
            raise UserError("下载参数无效。")
        path = service.download(task_id, request.args.get("group"))
        return send_file(path, as_attachment=True, download_name=path.name)

    return routes
