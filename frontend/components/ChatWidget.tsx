"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import type { ChatTurn } from "@/lib/types";
import { useApp } from "./AppProvider";

const KEY = "karirfit:v1:chat";

/** Career assistant (Groq via FastAPI /api/chat), available on every page once logged in.
 *  It receives the user's answers and, on the results page, the career being viewed, so its answers
 *  are grounded in their computed results. Before the test it answers general career questions. */
export function ChatWidget() {
  const { t, lang, profile, session, consent, health, user, chatOpen: open, setChatOpen: setOpen, chatCareer, answers } = useApp();
  const path = usePathname();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => { try { setTurns(JSON.parse(sessionStorage.getItem(KEY) || "[]")); } catch { /* ignore */ } }, []);
  useEffect(() => {
    try { sessionStorage.setItem(KEY, JSON.stringify(turns.slice(-30))); } catch { /* ignore */ }
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns, open, busy]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, setOpen]);

  if (!user || path?.startsWith("/masuk") || path?.startsWith("/admin")) return null;

  const off = health?.chat === false;
  const tested = answers.interests.length > 0;

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || busy || off) return;
    const next: ChatTurn[] = [...turns, { role: "user", content: q }];
    setTurns(next); setInput(""); setBusy(true); setErr(null);
    try {
      const r = await api.chat(next, profile, chatCareer, lang, session, consent);
      setTurns([...next, { role: "assistant", content: r.reply }]);
    } catch (e) {
      setErr(t.chat_error + (e as Error).message);
    }
    setBusy(false);
  };
  const submit = (e: FormEvent<HTMLFormElement>) => { e.preventDefault(); send(input); };

  if (!open) {
    return (
      <button className="chat-fab" onClick={() => setOpen(true)} aria-label={t.chat_open}>
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.2 3.6c-.5.4-1.3 0-1.3-.6V16A2.5 2.5 0 0 1 4 13.5v-8Z" fill="currentColor" />
          <circle cx="8.5" cy="9.5" r="1.2" fill="var(--ink)" /><circle cx="12" cy="9.5" r="1.2" fill="var(--ink)" /><circle cx="15.5" cy="9.5" r="1.2" fill="var(--ink)" />
        </svg>
        <span>{t.chat_fab}</span>
      </button>
    );
  }
  const suggestions = tested ? t.chat_suggestions : t.chat_suggestions_general;
  return (
    <>
      <div className="chat-scrim" onClick={() => setOpen(false)} aria-hidden="true" />
      <aside className="chat" role="dialog" aria-label={t.chat_title}>
        <header>
          <div>
            <strong>{t.chat_title}</strong>
            <span className="chat-sub">Groq · KarirFit</span>
          </div>
          <div className="chat-tools">
            {turns.length > 0 && <button className="linkbtn" onClick={() => { setTurns([]); setErr(null); }}>{t.chat_reset}</button>}
            <button className="chat-x" onClick={() => setOpen(false)} aria-label={t.chat_close}>×</button>
          </div>
        </header>
        <div className="chat-body">
          {off && <p className="notice">{t.chat_off}</p>}
          {turns.length === 0 && !off && (
            <div className="chat-empty">
              <p>{tested ? t.chat_intro : t.chat_intro_general}</p>
              {suggestions.map(sug => <button key={sug} className="chip" onClick={() => send(sug)}>{sug}</button>)}
            </div>
          )}
          {turns.map((m, i) => <div key={i} className={"msg " + m.role}>{m.content}</div>)}
          {busy && <div className="msg assistant pending"><span className="dots"><i /><i /><i /></span>{t.chat_thinking}</div>}
          {err && <p className="notice error">{err}</p>}
          <div ref={endRef} />
        </div>
        <form onSubmit={submit}>
          <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)} placeholder={t.chat_placeholder}
            maxLength={1000} aria-label={t.chat_placeholder} disabled={off} />
          <button className="btn primary" disabled={busy || off || !input.trim()}>{t.chat_send}</button>
        </form>
        <p className="fine">{t.chat_disclaimer}</p>
      </aside>
    </>
  );
}
