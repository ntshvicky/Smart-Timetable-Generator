export type AuthResponse = {
  access_token: string;
  school_id: number;
  user_id: number;
  school_name: string;
  role: string;
};

export type UserProfile = {
  id: number;
  email: string;
  full_name: string;
  school_id: number;
  school_name: string;
  role: string;
};

export type MasterData = {
  sections: { id: number; name: string; display_name: string }[];
  subjects: { id: number; code: string; name: string; category: string }[];
  teachers: { id: number; code: string; name: string }[];
};

export type Constraint = {
  id?: number;
  rule_type: string;
  target_type: string;
  target_values: string[];
  day_scope: string[];
  period_scope: number[];
  priority: string;
  parsed_description: string;
  confidence_score: number;
};

export type Conflict = { code: string; message: string; context?: Record<string, unknown> };
export type Cell = {
  id: number | null;
  day: string;
  period_number: number;
  section_id: number;
  subject_id: number | null;
  subject_code: string | null;
  subject_name: string | null;
  teacher_id: number | null;
  teacher_code: string | null;
  teacher_name: string | null;
  is_break: boolean;
  is_manual: boolean;
  notes: string;
};
export type Timetable = {
  timetable_id: number;
  name: string;
  status: string;
  days: string[];
  periods: number[];
  entries: Cell[];
  conflicts: Conflict[];
};

export type AdminOverview = {
  stats: { schools: number; users: number; uploads: number; timetables: number; manual_edits: number };
  schools: { id: number; name: string; created_at: string; users: number; uploads: number; timetables: number }[];
  users: { id: number; school_id: number; school_name: string; email: string; full_name: string; role: string; created_at: string }[];
  activity: { id: number; school_id: number | null; school_name: string | null; user_id: number | null; user_email: string | null; action: string; entity_type: string; entity_id: string; detail: string; created_at: string }[];
};

const API_BASE =
  import.meta.env.VITE_API_BASE ??
  (globalThis.location?.hostname === "localhost" || globalThis.location?.hostname === "127.0.0.1" ? "http://127.0.0.1:8000" : "");

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

function token() {
  return localStorage.getItem("token");
}

async function download(path: string, filename: string): Promise<void> {
  const headers = new Headers();
  if (token()) headers.set("Authorization", `Bearer ${token()}`);
  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (!response.ok) {
    const detail = await response.text();
    if (response.status === 401) throw new AuthError(detail || "Not authenticated");
    throw new Error(detail || response.statusText);
  }
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token()) headers.set("Authorization", `Bearer ${token()}`);
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const detail = await response.text();
    if (response.status === 401) throw new AuthError(detail || "Not authenticated");
    throw new Error(detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  register: (payload: { school_name: string; full_name: string; email: string; password: string }) =>
    request<AuthResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    request<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  me: () => request<UserProfile>("/api/auth/me"),
  adminOverview: () => request<AdminOverview>("/api/admin/overview"),
  summary: () => request<Record<string, number>>("/api/data/summary"),
  masters: () => request<MasterData>("/api/data/masters"),
  upload: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<{ batch_id: number; status: string; errors: unknown[] }>("/api/data/upload", { method: "POST", body: data });
  },
  parseRules: (text: string) => request<{ constraints: Constraint[]; provider: string }>("/api/rules/parse", { method: "POST", body: JSON.stringify({ text }) }),
  saveRule: (constraint: Constraint) => request<Constraint>("/api/rules", { method: "POST", body: JSON.stringify(constraint) }),
  rules: () => request<Constraint[]>("/api/rules"),
  generate: (name: string) => request<Timetable>("/api/timetables/generate", { method: "POST", body: JSON.stringify({ name }) }),
  timetables: () => request<{ id: number; name: string; status: string; created_at: string }[]>("/api/timetables"),
  latestTimetable: (sectionId?: number, teacherId?: number) => {
    const params = new URLSearchParams();
    if (sectionId) params.set("section_id", String(sectionId));
    if (teacherId) params.set("teacher_id", String(teacherId));
    const suffix = params.toString();
    return request<Timetable>(`/api/timetables/latest${suffix ? `?${suffix}` : ""}`);
  },
  timetable: (id: number, sectionId?: number, teacherId?: number) => {
    const params = new URLSearchParams();
    if (sectionId) params.set("section_id", String(sectionId));
    if (teacherId) params.set("teacher_id", String(teacherId));
    return request<Timetable>(`/api/timetables/${id}?${params}`);
  },
  editEntry: (id: number, payload: { section_id: number; day: string; period_number: number; subject_id: number | null; teacher_id: number | null; notes?: string }) =>
    request<Conflict[]>(`/api/timetables/${id}/entries`, { method: "PUT", body: JSON.stringify(payload) }),
  downloadTemplate: () => download("/api/data/template", "smart_timetable_template.xlsx"),
  exportTimetable: (id: number) => download(`/api/timetables/${id}/export`, `timetable_${id}.xlsx`),
};
