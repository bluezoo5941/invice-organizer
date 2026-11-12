export const $ = (id) => document.getElementById(id);

export function element(tag, text = "", className = "") {
  const node = document.createElement(tag);
  node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

export function button(text, action, className = "button quiet") {
  const node = element("button", text, className);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

export function notice(text, type = "info") {
  const node = element("div", text, `notice ${type}`);
  return node;
}

export function feedback(text, error = false) {
  $("feedback").textContent = text;
  $("feedback").className = `notice ${error ? "error" : "info"}`;
  $("feedback").hidden = !text;
  $("feedback").setAttribute("role", error ? "alert" : "status");
}

export function table(headers, rows) {
  const wrap = element("div", "", "table-wrap");
  const table = element("table");
  const thead = element("thead");
  const tr = element("tr");
  headers.forEach((label) => {
    const th = element("th", label);
    th.scope = "col";
    tr.append(th);
  });
  thead.append(tr);
  const tbody = element("tbody");
  rows.forEach((values) => {
    const row = element("tr");
    values.forEach((value) => row.append(element("td", value ?? "—")));
    tbody.append(row);
  });
  table.append(thead, tbody);
  wrap.append(table);
  return wrap;
}
