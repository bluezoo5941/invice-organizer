import { $, button, element, notice, table } from "./components.js";

export function showStep(current) {
  const ids = ["input", "review", "output"];
  const active = ids.indexOf(current);
  ids.forEach((id, index) => {
    const step = $("step-" + id);
    const done = index < active;
    step.classList.toggle("done", done);
    step.querySelector(".step-number").textContent = done ? "✓" : "0" + (index + 1);
    if (index === active) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });
}

export function filterProjects(issuesOnly) {
  $("filter-all").setAttribute("aria-pressed", String(!issuesOnly));
  $("filter-issues").setAttribute("aria-pressed", String(issuesOnly));
  for (const row of $("groups").children) {
    row.hidden = issuesOnly && !row.hasAttribute("data-issue");
  }
}

function renderProject(group, exportedFile, downloadGroup) {
  const matched = group.items.filter(item => item.status === "matched").length;
  const details = element("details", "", "project-row project");
  if (group.blocked) {
    details.open = true;
    details.setAttribute("data-issue", "");
  }
  const heading = element("summary");
  heading.append(
    element("strong", group.project),
    element("span", exportedFile ? `${exportedFile.pages} 页` :
      group.blocked ? `${matched} / ${group.items.length} 份` : `${matched} 份`, "muted"),
    element("span", group.blocked ? "待处理" : exportedFile ? "已生成" : "可导出",
      `badge ${group.blocked ? "issue" : "ready"}`),
  );
  const detail = element("div", "", "detail");
  detail.append(table(
    ["表格行", "乘机人", "完整票号", "匹配文件 / 异常"],
    group.items.map(item => [item.row, item.name, item.ticket, item.error || item.file]),
  ));
  if (exportedFile) {
    detail.append(button("下载本项目 PDF", () => downloadGroup(exportedFile), "button"));
  }
  details.append(heading, detail);
  return details;
}

export function renderTask(task, downloadGroup) {
  const result = task.result;
  const complete = task.status === "complete";
  const ready = task.status === "ready";
  const pending = task.status === "analyzing" || task.status === "merging";
  $("input-panel").hidden = true;
  $("result-panel").hidden = false;
  $("task-name").textContent = task.name;
  showStep(complete ? "output" : "review");
  $("result-title").textContent = complete ? "导出归集" : "核对匹配";
  $("match-status").hidden = !ready;
  $("completion").hidden = !complete;
  $("refresh-task").hidden = !pending;
  $("summary").hidden = !result || complete;
  $("project-panel").hidden = !result;
  $("export").hidden = !ready;
  $("export").disabled = !result?.summary.ready_groups;
  $("issues-panel").hidden = !result?.issues.length;
  for (const id of ["summary", "groups", "issues-list", "issue-banner"]) $(id).replaceChildren();
  if (!result) {
    $("issue-banner").append(notice(
      task.error || "任务正在处理中，请刷新状态。",
      task.error ? "error" : "info",
    ));
    return;
  }

  const s = result.summary;
  const blocked = s.groups - s.ready_groups;
  if (complete) {
    $("completion-summary").textContent =
      `${result.exports.length} 份项目 PDF${blocked ? ` · ${blocked} 个项目待处理` : ""}`;
  }
  for (const [label, value, tone] of [
    ["账单记录", s.rows, ""],
    ["可导出项目", s.ready_groups, "success"],
    ["待处理项目", blocked, "warning"],
  ]) {
    const box = element("div", "", `metric ${tone}`);
    box.append(element("span", label), element("strong", value));
    $("summary").append(box);
  }

  $("export").textContent = s.ready_groups ? `导出 ${s.ready_groups} 个项目` : "无可导出项目";
  $("filter-all").textContent = `全部 ${s.groups}`;
  $("filter-issues").textContent = `待处理 ${blocked}`;
  $("filter-issues").disabled = blocked === 0;
  $("group-title").textContent = complete ? "归集结果" : "项目清单";
  if (task.error) $("issue-banner").append(notice(task.error, "error"));
  const exportsByGroup = new Map((result.exports || []).map(file => [file.group_id, file]));
  const groups = [...result.groups].sort((a, b) => Number(b.blocked) - Number(a.blocked));
  for (const group of groups) {
    $("groups").append(renderProject(group, exportsByGroup.get(group.id), downloadGroup));
  }
  filterProjects(false);

  const warnings = result.issues.filter(issue => issue.level !== "info");
  const cleaned = result.issues.filter(issue => issue.level === "info");
  $("issues-title").textContent = `异常与清洗记录 · ${warnings.length} 条提醒`;
  if (result.issues.length) {
    $("issues-list").append(table(
      ["类型", "位置", "说明"],
      [...warnings, ...cleaned].map(issue => [
        issue.level === "info" ? "处理说明" : "需留意",
        issue.file || (issue.row ? `Excel 第 ${issue.row} 行` : "—"),
        issue.message,
      ]),
    ));
  }
}
