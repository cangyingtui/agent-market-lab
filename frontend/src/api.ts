export type JsonObject = Record<string, unknown>;

const API_BASE = import.meta.env.VITE_API_BASE || "";
const TOKEN_KEY = "agentsim_token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await response.text();
  let data: JsonObject | null = null;
  if (text) {
    try {
      data = JSON.parse(text) as JsonObject;
    } catch {
      data = { detail: text };
    }
  }
  if (!response.ok) {
    const detail = data?.message || data?.detail || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (data && typeof data === "object" && "code" in data && "data" in data) {
    return data.data as T;
  }
  return data as T;
}

export const api = {
  register: (payload: JsonObject) => request<JsonObject>("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: JsonObject) => request<JsonObject>("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  me: () => request<JsonObject>("/api/auth/me"),
  profile: () => request<JsonObject>("/api/user/profile"),
  updateProfile: (payload: JsonObject) => request<JsonObject>("/api/user/profile", { method: "PUT", body: JSON.stringify(payload) }),
  upgrade: () => request<JsonObject>("/api/user/upgrade", { method: "POST", body: JSON.stringify({ reason: "frontend_upgrade" }) }),
  categories: () => request<JsonObject>("/api/categories"),
  fields: (categoryId: string | number) => request<JsonObject>(`/api/categories/${categoryId}/fields`),
  marketTemplates: () => request<JsonObject>("/api/market/templates"),
  products: (query: string) => request<JsonObject>(`/api/products?${query}`),
  assistantChat: (payload: JsonObject) => request<JsonObject>("/api/assistant/chat", { method: "POST", body: JSON.stringify(payload) }),
  listProjects: (query = "page=1&page_size=20") => request<JsonObject>(`/api/simulations?${query}`),
  createProject: (project_name: string) =>
    request<JsonObject>("/api/simulations", { method: "POST", body: JSON.stringify({ project_name }) }),
  getProject: (id: string | number) => request<JsonObject>(`/api/simulations/${id}`),
  deleteProject: (id: string | number) => request<JsonObject>(`/api/simulations/${id}`, { method: "DELETE" }),
  saveStep1: (id: string | number, product_definition: JsonObject) =>
    request<JsonObject>(`/api/simulations/${id}/step1`, { method: "PUT", body: JSON.stringify({ product_definition }) }),
  saveStep2: (id: string | number, market_config: JsonObject) =>
    request<JsonObject>(`/api/simulations/${id}/step2`, { method: "PUT", body: JSON.stringify({ market_config }) }),
  submit: (id: string | number) => request<JsonObject>(`/api/simulations/${id}/submit`, { method: "POST", body: JSON.stringify({}) }),
  run: (id: string | number) => request<JsonObject>(`/api/simulations/${id}/run`, { method: "POST" }),
  progress: (id: string | number) => request<JsonObject>(`/api/simulations/${id}/progress`),
  logs: (id: string | number, limit = 100) => request<JsonObject>(`/api/simulations/${id}/logs?limit=${limit}`),
  queueStatus: () => request<JsonObject>("/api/debug/queue/status"),
  report: (id: string | number) => request<JsonObject>(`/api/simulations/${id}/report`),
  cancel: (id: string | number) => request<JsonObject>(`/api/simulations/${id}/cancel`, { method: "POST" }),
  exportReport: (id: string | number, format: "json" | "markdown" | "excel" | "pdf") =>
    request<JsonObject>(`/api/simulations/${id}/exports`, { method: "POST", body: JSON.stringify({ format }) }),
  exportStatus: (exportTaskId: string | number) => request<JsonObject>(`/api/exports/${exportTaskId}`),
  shareReport: (id: string | number, expires_in_hours = 72) =>
    request<JsonObject>(`/api/simulations/${id}/share-tokens`, {
      method: "POST",
      body: JSON.stringify({ expires_in_hours })
    }),
  getShare: (token: string) => request<JsonObject>(`/api/share/${token}`),
  getPrintReport: (token: string) => request<JsonObject>(`/api/exports/render/${token}`)
};

export async function downloadWithAuth(path: string, filename: string): Promise<void> {
  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const url = /^https?:\/\//i.test(path) ? path : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, { headers });
  if (!response.ok) {
    const text = await response.text();
    let detail = response.statusText || "下载失败";
    if (text) {
      try {
        const payload = JSON.parse(text);
        detail = payload?.message || payload?.detail || detail;
      } catch {
        detail = text;
      }
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
