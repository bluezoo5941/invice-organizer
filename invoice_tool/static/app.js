import { download, downloadFile, json } from "./api.js";
import { $, button, element, feedback } from "./components.js";
import { filterProjects, renderTask, showStep } from "./results.js";

let pdfFiles = [];
let currentTask = null;
let requestKey = crypto.randomUUID();
let busy = false;
let historyOffset = 0;
let historyHasNext = false;
let pdfMode = "pdfs";

async function action(fn) {
  if (busy) return;
  busy = true;
  const controls = [...document.querySelectorAll("button, input")];
  const old = controls.map((node) => node.disabled);
  controls.forEach((node) => {
    node.disabled = true;
  });
  try {
    await fn();
  } catch (error) {
    feedback(
      error.name === "TimeoutError"
        ? "等待超时。请查看历史任务确认处理结果，不要重复提交。"
        : error.message,
      true,
    );
  } finally {
    busy = false;
    controls.forEach((node, index) => {
      node.disabled = old[index];
    });
    $("history-prev").disabled = historyOffset === 0;
    $("history-next").disabled = !historyHasNext;
    if (currentTask && !$("result-panel").hidden) {
      $("export").disabled = !currentTask.result?.summary.ready_groups;
      const summary = currentTask.result?.summary;
      $("filter-issues").disabled = !summary || summary.groups === summary.ready_groups;
    }
  }
}

function render() {
  renderTask(currentTask, (file) =>
    action(async () => {
      await download(currentTask.id, file.filename, file.group_id);
      feedback("文件已交给浏览器下载。");
    }),
  );
}

function setPdfs(files) {
  pdfFiles = [...files].filter((file) =>
    file.name.toLowerCase().endsWith(".pdf"),
  );
  $("pdf-detail").textContent = pdfFiles.length
    ? `${pdfFiles.length} 份 PDF`
    : pdfMode === "folder" ? "未选择文件夹" : "未选择文件";
  requestKey = crypto.randomUUID();
}

function selectMode(mode) {
  pdfMode = mode;
  $("pdf-picker").textContent = mode === "folder" ? "选择文件夹" : "选择 PDF 文件";
  setPdfs($(mode).files);
}

for (const radio of document.querySelectorAll('[name="mode"]')) {
  radio.addEventListener("change", () => selectMode(radio.value));
}
for (const mode of ["pdfs", "folder"]) {
  $(mode).addEventListener("change", () => {
    if (pdfMode === mode) setPdfs($(mode).files);
  });
}
$("pdf-picker").addEventListener("click", () => $(pdfMode).click());
$("workbook").addEventListener("change", (event) => {
  $("workbook-detail").textContent =
    event.target.files[0]?.name || "";
  requestKey = crypto.randomUUID();
});

$("upload-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action(async () => {
    const workbook = $("workbook").files[0];
    if (!workbook || !pdfFiles.length)
      throw new Error("请选择一份 Excel 和至少一份 PDF。");
    if (pdfFiles.length > 300) throw new Error("一次最多选择 300 份 PDF。");
    if ([workbook, ...pdfFiles].some((file) => file.size > 10 * 1024 * 1024))
      throw new Error("单个文件不能超过 10 MB。");
    if (
      [workbook, ...pdfFiles].reduce((n, f) => n + f.size, 0) >
      80 * 1024 * 1024
    )
      throw new Error("文件合计不能超过 80 MB。");
    const form = new FormData();
    form.append("workbook", workbook);
    pdfFiles.forEach((file) => form.append("pdfs", file, file.name));
    feedback("正在读取账单并匹配 PDF，请稍候…");
    $("analyze").textContent = "正在匹配…";
    try {
      currentTask = await json("/api/tasks", {
        method: "POST",
        body: form,
        headers: { "Idempotency-Key": requestKey },
      });
      render();
      feedback("匹配完成，请核对分组和异常");
      $("feedback").classList.replace("info", "success");
    } catch (error) {
      const prompt = "，请填写要使用的工作表名称。";
      if (error.message.startsWith("找到多个数据表（") && error.message.endsWith(prompt)) {
        throw new Error(
          `${error.message.slice(0, -prompt.length)}。请把需要归集的工作表另存为单独的 Excel 文件后重试。`,
          { cause: error },
        );
      }
      throw error;
    } finally {
      $("analyze").textContent = "开始匹配";
    }
  });
});

$("export").addEventListener("click", () =>
  action(async () => {
    feedback("正在合并 PDF 并核对页数，请稍候…");
    currentTask = await json(`/api/tasks/${currentTask.id}/export`, {
      method: "POST",
    });
    render();
    feedback("");
  }),
);
$("download").addEventListener("click", () =>
  action(async () => {
    await download(currentTask.id, "项目发票.zip");
    feedback("ZIP 已交给浏览器下载。");
  }),
);
$("refresh-task").addEventListener("click", () =>
  action(async () => {
    currentTask = await json(`/api/tasks/${currentTask.id}`);
    render();
    feedback("已读取最新任务状态。");
  }),
);
$("workbook-link").addEventListener("click", () =>
  action(async () => {
    await downloadFile(`/api/tasks/${currentTask.id}/workbook`, currentTask.name);
  }),
);
$("filter-all").addEventListener("click", () => filterProjects(false));
$("filter-issues").addEventListener("click", () => filterProjects(true));
$("new-task").addEventListener("click", () => {
  currentTask = null;
  $("input-panel").hidden = false;
  $("result-panel").hidden = true;
  showStep("input");
  feedback("");
});

async function history() {
  const data = await json(`/api/tasks?offset=${historyOffset}`);
  $("history-list").replaceChildren();
  const status = {
    analyzing: "分析中",
    ready: "待导出",
    merging: "合并中",
    complete: "已完成",
    failed: "未完成",
  };
  for (const task of data.tasks) {
    const row = element("div", "", "history-row");
    const info = element("div");
    info.append(
      element("strong", task.name),
      element(
        "p",
        `${new Date(task.created_at).toLocaleString()} · ${status[task.status]}`,
        "muted",
      ),
    );
    row.append(
      info,
      button("查看", () =>
        action(async () => {
          currentTask = await json(`/api/tasks/${task.id}`);
          render();
          feedback("已从本机记录中读取任务。");
        }),
      ),
    );
    $("history-list").append(row);
  }
  if (!data.tasks.length)
    $("history-list").append(
      element("p", "还没有历史任务。", "muted"),
    );
  $("history-page").textContent = `第 ${historyOffset / 50 + 1} 页`;
  $("history-prev").disabled = historyOffset === 0;
  historyHasNext = data.tasks.length === 50;
  $("history-next").disabled = !historyHasNext;
}
$("history-toggle").addEventListener("click", () => {
  $("history").hidden = !$("history").hidden;
  $("history-toggle").setAttribute(
    "aria-expanded",
    String(!$("history").hidden),
  );
  if (!$("history").hidden) action(history);
});
$("refresh-history").addEventListener("click", () => action(history));
$("history-prev").addEventListener("click", () => {
  historyOffset = Math.max(0, historyOffset - 50);
  action(history);
});
$("history-next").addEventListener("click", () => {
  historyOffset += 50;
  action(history);
});
