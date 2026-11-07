"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, API_URL, setAuthToken } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";
import { DICTS, type Dict } from "@/lib/i18n";
import type { Answers, Career, Health, Lang, Model, Profile } from "@/lib/types";

const EMPTY: Answers = {
  interests: [], skills: {}, softSkills: {}, major: "", experience: "", expSkills: [], expPhrases: {}, courses: {}, target: "", consent: false,
};

/** Profile sent to the API, built from the answers kept in the browser. */
export function toProfile(a: Answers): Profile {
  return {
    courses: a.courses ?? {}, skills: a.skills ?? {}, soft_skills: a.softSkills ?? {},
    experience_skills: a.expSkills ?? [], interests: a.interests ?? [], target_career: a.target || null, major: a.major || null,
  };
}

export interface AuthUser { id: string; email: string; name: string; consent: boolean }
const KEY = "karirfit:v1";

function readStore<T>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(`${KEY}:${key}`); return v ? (JSON.parse(v) as T) : fallback; } catch { return fallback; }
}
function writeStore(key: string, value: unknown) {
  try { localStorage.setItem(`${KEY}:${key}`, JSON.stringify(value)); } catch { /* storage unavailable */ }
}

interface Ctx {
  lang: Lang; setLang: (l: Lang) => void; t: Dict;
  model: Model | null; modelError: string | null; reloadModel: () => void; waking: boolean;
  health: Health | null;
  answers: Answers; update: (patch: Partial<Answers> | ((a: Answers) => Partial<Answers>)) => void; reset: () => void;
  hydrated: boolean; session: string;
  profile: Profile;
  careerName: (c: Pick<Career, "name_en" | "name_id">) => string;
  skillName: (id: string) => string;
  softName: (id: string) => string;
  // Supabase account (login is required before the test, FR1)
  user: AuthUser | null; authReady: boolean; recovery: boolean; setRecovery: (v: boolean) => void;
  signOut: () => Promise<void>;
  consent: boolean;   // given at registration; required before anything is logged
  // career assistant (shown on every page once logged in)
  chatOpen: boolean; setChatOpen: (v: boolean) => void;
  chatCareer: string | null; setChatCareer: (c: string | null) => void;
}

const AppContext = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("id");
  const [answers, setAnswers] = useState<Answers>(EMPTY);
  const [hydrated, setHydrated] = useState(false);
  const [session, setSession] = useState("anon");
  const [model, setModel] = useState<Model | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [waking, setWaking] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [recovery, setRecovery] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatCareer, setChatCareer] = useState<string | null>(null);

  // Supabase session: keep the access token in the API client so FastAPI can verify the user
  useEffect(() => {
    if (!supabase) { setAuthReady(true); return; }
    const apply = (sess: Session | null) => {
      setAuthToken(sess?.access_token ?? null);
      const m = sess?.user.user_metadata ?? {};
      setUser(sess ? { id: sess.user.id, email: sess.user.email ?? "", name: String(m.name ?? ""), consent: Boolean(m.consent) } : null);
    };
    supabase.auth.getSession().then(({ data }: { data: { session: Session | null } }) => { apply(data.session); setAuthReady(true); });
    const { data: sub } = supabase.auth.onAuthStateChange((event: AuthChangeEvent, sess: Session | null) => {
      if (event === "PASSWORD_RECOVERY") setRecovery(true);
      apply(sess);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const signOut = useCallback(async () => {
    if (supabase) await supabase.auth.signOut();
    setAuthToken(null); setUser(null);
  }, []);

  // restore from localStorage after mount (avoids SSR/client mismatch)
  useEffect(() => {
    setLangState(readStore<Lang>("lang", "id"));
    setAnswers({ ...EMPTY, ...readStore<Partial<Answers>>("answers", {}) });
    let s = readStore<string>("session", "");
    if (!s) { s = Math.random().toString(36).slice(2, 10); writeStore("session", s); }
    setSession(s);
    setHydrated(true);
  }, []);

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const loadModel = useCallback(() => {
    // A sleeping free-tier backend (e.g. Render) needs up to ~1 minute to wake up and may fail the
    // first requests: show a notice after 4 s and retry every 10 s for about 2 minutes.
    setModelError(null);
    let cancelled = false;
    const timer = setTimeout(() => !cancelled && setWaking(true), 4000);
    const attempt = (n: number) => {
      api.model()
        .then(m => {
          if (cancelled) return;
          setModel(m); setWaking(false); clearTimeout(timer);
          api.health().then(h => !cancelled && setHealth(h)).catch(() => {});
        })
        .catch((e: unknown) => {
          if (cancelled) return;
          if (n < 12) { setWaking(true); setTimeout(() => attempt(n + 1), 10000); return; }
          clearTimeout(timer); setWaking(false);
          setModelError(e instanceof ApiError ? e.message : String(e));
        });
    };
    attempt(1);
    return () => { cancelled = true; clearTimeout(timer); };
  }, []);
  useEffect(() => loadModel(), [loadModel]);

  const setLang = useCallback((l: Lang) => { setLangState(l); writeStore("lang", l); }, []);
  const update = useCallback<Ctx["update"]>(patch => {
    setAnswers(prev => {
      const next = { ...prev, ...(typeof patch === "function" ? patch(prev) : patch) };
      writeStore("answers", next);
      return next;
    });
  }, []);
  const reset = useCallback(() => { setAnswers(EMPTY); writeStore("answers", EMPTY); }, []);

  const value = useMemo<Ctx>(() => {
    const skillNames = Object.fromEntries((model?.skills ?? []).map(s => [s.id, s.name]));
    const softNames = Object.fromEntries((model?.soft_skills ?? []).map(s => [s.id, lang === "id" ? s.name_id : s.name_en]));
    return {
      lang, setLang, t: DICTS[lang],
      model, modelError: modelError && DICTS[lang].err_server(API_URL), reloadModel: loadModel, waking, health,
      answers, update, reset, hydrated, session: user?.id ?? session,
      profile: toProfile(answers),
      careerName: c => (lang === "id" ? c.name_id : c.name_en),
      skillName: id => skillNames[id] ?? id,
      softName: id => softNames[id] ?? id,
      user, authReady, recovery, setRecovery, signOut,
      consent: Boolean(user?.consent),
      chatOpen, setChatOpen, chatCareer, setChatCareer,
    };
  }, [lang, setLang, model, modelError, loadModel, waking, health, answers, update, reset, hydrated, session, user, authReady, recovery, signOut, chatOpen, chatCareer]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside <AppProvider>");
  return ctx;
}
