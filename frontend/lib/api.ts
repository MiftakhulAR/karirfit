import type {
  ChatResponse, ChatTurn, CompareResponse, ExplainResponse, ExtractResponse, Health, KbList, KbStatus, Lang, Model,
  Profile, RecommendResponse,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

// Supabase access token of the signed-in user, sent to FastAPI as "Authorization: Bearer ..."
let authToken: string | null = null;
export function setAuthToken(token: string | null) { authToken = token; }

async function request<T>(path: string, body?: unknown, init: RequestInit = {}): Promise<T> {
  if (authToken) init = { ...init, headers: { Authorization: `Bearer ${authToken}`, ...(init.headers || {}) } };
  let res: Response;
  const opts: RequestInit = body === undefined
    ? { cache: "no-store", ...init }
    : body instanceof FormData
      ? { method: "POST", body, ...init }
      : { method: "POST", body: JSON.stringify(body), ...init, headers: { "Content-Type": "application/json", ...(init.headers || {}) } };
  try {
    res = await fetch(API_URL + path, opts);
  } catch {
    throw new ApiError(0, `Cannot reach the server at ${API_URL}`);
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail ?? ""; } catch { /* not JSON */ }
    throw new ApiError(res.status, `${path} returned ${res.status}${detail ? `: ${detail}` : ""}`);
  }
  return res.json() as Promise<T>;
}

const admin = (token: string): RequestInit => ({ headers: { "X-Admin-Token": token } });

export const api = {
  model: () => request<Model>("/api/model"),
  extractSkills: (text: string) => request<ExtractResponse>("/api/extract-skills", { text }),
  // α is fixed by the backend (0.5, thesis Section 3.5.2); users cannot change it.
  recommend: (profile: Profile, session: string, consent: boolean) =>
    request<RecommendResponse>("/api/recommend", { profile, session, consent, include_all: true }),
  explain: (profile: Profile, career: string, lang: Lang, session: string, consent: boolean) =>
    request<ExplainResponse>("/api/explain", { profile, career, lang, session, consent }),
  rate: (session: string, career: string, rating: number) =>
    request<{ ok: boolean }>("/api/rating", { session, career, rating }),
  health: () => request<Health>("/api/health"),
  chat: (messages: ChatTurn[], profile: Profile, career: string | null, lang: Lang, session: string, consent: boolean) =>
    request<ChatResponse>("/api/chat", { messages, profile, career, lang, session, consent }),

  // user evaluation (backend EVAL_MODE=1, thesis Sections 3.6.4-3.6.6)
  compare: (profile: Profile, session: string) =>
    request<CompareResponse>("/api/compare", { profile, session, consent: true }),
  compareChoice: (session: string, token: string, choice: "A" | "B" | "same") =>
    request<{ ok: boolean }>("/api/compare/choice", { session, token, choice }),
  susItems: (lang: Lang) => request<{ items: string[] }>(`/api/sus?lang=${lang}`),
  susSubmit: (session: string, answers: number[]) => request<{ ok: boolean }>("/api/sus", { session, answers }),

  // administrator (FR10)
  kbList: (token: string) => request<KbList>("/api/admin/kb", undefined, admin(token)),
  kbUpload: (token: string, form: FormData) => request<{ ok: boolean; file: string }>("/api/admin/kb/upload", form, admin(token)),
  kbDelete: (token: string, file: string) =>
    request<{ ok: boolean }>(`/api/admin/kb/${encodeURIComponent(file)}`, undefined, { ...admin(token), method: "DELETE" }),
  kbRebuild: (token: string) => request<{ ok: boolean }>("/api/admin/kb/rebuild", {}, admin(token)),
  kbStatus: (token: string) => request<KbStatus>("/api/admin/kb/status", undefined, admin(token)),
  exportLog: (token: string) => request<unknown[]>("/api/export", undefined, admin(token)),
};
