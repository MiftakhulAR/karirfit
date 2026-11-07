"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent, type MouseEvent } from "react";
import { useApp } from "@/components/AppProvider";
import { supabase } from "@/lib/supabase";

type Tab = "login" | "register";

/** Sign in / create account with Supabase Auth (email + password). Registration records the
 *  consent and the profile fields of thesis Table 3.9 (name, status, major, cohort, semester) in the
 *  user's metadata; the password is hashed by Supabase. */
export default function LoginPage() {
  const { t, user, recovery, setRecovery } = useApp();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("login");
  useEffect(() => { if (new URLSearchParams(window.location.search).get("tab") === "daftar") setTab("register"); }, []);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [consent, setConsent] = useState(false);

  const next = () => {
    const n = new URLSearchParams(window.location.search).get("next");
    return n && n.startsWith("/") && !n.startsWith("//") ? n : "/";
  };

  useEffect(() => { if (user && !recovery) router.push(next()); }, [user, recovery, router]);

  if (!supabase) return <section className="auth"><p className="notice error">{t.supabase_missing}</p></section>;

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setMsg(null);
    try { await fn(); } catch (e) { setMsg({ text: (e as Error).message, error: true }); }
    setBusy(false);
  };

  const login = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    run(async () => {
      const { error } = await supabase!.auth.signInWithPassword({ email: String(f.get("email")), password: String(f.get("password")) });
      if (error) throw error;
    });
  };

  const register = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!consent) { setMsg({ text: t.need_consent_reg, error: true }); return; }
    const f = new FormData(e.currentTarget);
    run(async () => {
      const { data, error } = await supabase!.auth.signUp({
        email: String(f.get("email")), password: String(f.get("password")),
        options: {
          emailRedirectTo: `${window.location.origin}/masuk`,
          data: {
            name: String(f.get("name") || ""), status: String(f.get("status") || ""), major: String(f.get("major") || ""),
            cohort: String(f.get("cohort") || ""), semester: String(f.get("semester") || ""),
            consent: true, consent_at: new Date().toISOString(),
          },
        },
      });
      if (error) throw error;
      if (!data.session) { setMsg({ text: t.check_email }); setTab("login"); }
    });
  };

  const forgot = (e: MouseEvent) => {
    e.preventDefault();
    const email = (document.querySelector<HTMLInputElement>('input[name="email"]')?.value || "").trim();
    if (!email) { setMsg({ text: t.f_email, error: true }); return; }
    run(async () => {
      const { error } = await supabase!.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/masuk` });
      if (error) throw error;
      setMsg({ text: t.reset_sent });
    });
  };

  const setPassword = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const pw = String(new FormData(e.currentTarget).get("password"));
    run(async () => {
      const { error } = await supabase!.auth.updateUser({ password: pw });
      if (error) throw error;
      setRecovery(false); setMsg({ text: t.password_updated });
    });
  };

  if (recovery) {
    return (
      <section className="auth">
        <h2>{t.new_password}</h2>
        <form onSubmit={setPassword} className="auth-form">
          <label>{t.new_password}<input name="password" type="password" minLength={8} required autoComplete="new-password" /></label>
          <button className="btn primary" disabled={busy}>{t.btn_set_password}</button>
        </form>
        {msg && <p className={"notice" + (msg.error ? " error" : "")}>{msg.text}</p>}
      </section>
    );
  }

  return (
    <section className="auth">
      <h2>{t.auth_title}</h2>
      <p className="hint">{t.auth_intro}</p>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "login"} onClick={() => { setTab("login"); setMsg(null); }}>{t.tab_login}</button>
        <button role="tab" aria-selected={tab === "register"} onClick={() => { setTab("register"); setMsg(null); }}>{t.tab_register}</button>
      </div>

      {tab === "login" ? (
        <form onSubmit={login} className="auth-form">
          <label>{t.f_email}<input name="email" type="email" required autoComplete="email" /></label>
          <label>{t.f_password}<input name="password" type="password" required autoComplete="current-password" /></label>
          <button className="btn primary" disabled={busy}>{t.btn_login}</button>
          <a href="#" className="link" onClick={forgot}>{t.forgot}</a>
        </form>
      ) : (
        <form onSubmit={register} className="auth-form">
          <label>{t.f_name}<input name="name" required autoComplete="name" /></label>
          <label>{t.f_email}<input name="email" type="email" required autoComplete="email" /></label>
          <label>{t.f_password}<input name="password" type="password" minLength={8} required autoComplete="new-password" /></label>
          <label>{t.f_status}
            <select name="status" defaultValue="university">
              {Object.entries(t.status_opts).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label>{t.f_major}<input name="major" placeholder={t.f_major_ph} /></label>
          <div className="two">
            <label>{t.f_cohort}<input name="cohort" inputMode="numeric" placeholder="2022" /></label>
            <label>{t.f_semester}<input name="semester" inputMode="numeric" placeholder="7" /></label>
          </div>
          <label className="consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /> <span>{t.consent_register}</span></label>
          <button className="btn primary" disabled={busy}>{t.btn_register}</button>
        </form>
      )}
      {msg && <p className={"notice" + (msg.error ? " error" : "")} role="status">{msg.text}</p>}
    </section>
  );
}
