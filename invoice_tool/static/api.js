const csrf = document.querySelector('meta[name="csrf-token"]').content;

export async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "X-CSRF-Token": csrf, ...options.headers },
    signal: AbortSignal.timeout(120000),
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ error: `请求失败（${response.status}）` }));
    throw new Error(body.error || `请求失败（${response.status}）`);
  }
  return response;
}

export async function json(path, options) {
  return (await request(path, options)).json();
}

export async function download(taskId, filename, groupId) {
  const suffix = groupId ? `?group=${encodeURIComponent(groupId)}` : "";
  await downloadFile(`/api/tasks/${taskId}/download${suffix}`, filename);
}

export async function downloadFile(path, filename) {
  const response = await request(path);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
