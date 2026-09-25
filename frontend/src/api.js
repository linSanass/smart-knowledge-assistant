const BASE_URL = "http://127.0.0.1:8000";

async function request(path, options = {}) {

  const response = await fetch(
    BASE_URL + path,
    options
  );

  if (!response.ok) {

    let detail = response.statusText;

    try {

      const data = await response.json();

      detail = data.detail || detail;

    } catch {

      // 响应不是 JSON，保留 statusText
    }

    // 带上状态码：调用方据此区分「业务冲突」(如 409 构建中) 和真正的失败
    const error = new Error(detail);

    error.status = response.status;

    throw error;
  }

  return response.json();
}

function jsonOptions(method, body) {

  return {
    method,
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  };
}

// =========================
// 会话
// =========================

export function listConversations() {

  return request("/conversations");
}

export function createConversation() {

  return request(
    "/conversations",
    jsonOptions("POST", {})
  );
}

export function getConversation(id) {

  return request(`/conversations/${id}`);
}

export function deleteConversation(id) {

  return request(
    `/conversations/${id}`,
    { method: "DELETE" }
  );
}

export function sendMessage(id, message, mode, role) {

  return request(
    `/conversations/${id}/messages`,
    jsonOptions("POST", {
      message,
      mode,
      role
    })
  );
}

// =========================
// 知识库（多文档）
// =========================

export function listDocuments() {

  return request("/documents");
}

export function getIndexStatus() {

  return request("/documents/status");
}

export async function uploadDocument(file) {

  const formData = new FormData();

  formData.append("file", file);

  return request("/documents", {
    method: "POST",
    body: formData
  });
}

export function deleteDocument(id) {

  return request(
    `/documents/${id}`,
    { method: "DELETE" }
  );
}

export function buildRag() {

  return request("/build-rag");
}
