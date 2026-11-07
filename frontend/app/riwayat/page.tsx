"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { useApp } from "@/components/AppProvider";
import { deleteAssessment, listAssessments } from "@/lib/supabase";
import type { Assessment } from "@/lib/types";

export default function HistoryPage() {
  return <AuthGate><History /></AuthGate>;
}

function History() {
  const { t, lang, update, careerName } = useApp();
  const router = useRouter();
  const [rows, setRows] = useState<Assessment[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { listAssessments().then(setRows).catch(e => setErr((e as Error).message)); }, []);

  const view = (a: Assessment) => {
    update({ ...a.answers });
    try { sessionStorage.removeItem("karirfit:submit"); } catch { /* ignore */ }   // viewing is not a new test
    router.push("/hasil");
  };
  const remove = async (id: string) => {
    try { await deleteAssessment(id); setRows(r => (r ?? []).filter(x => x.id !== id)); } catch (e) { setErr((e as Error).message); }
  };
  const fmt = (d: string) => new Date(d).toLocaleString(lang === "id" ? "id-ID" : "en-GB", { dateStyle: "medium", timeStyle: "short" });

  return (
    <section className="history">
      <div className="res-head">
        <h2>{t.h_title}</h2>
        <Link className="btn primary" href="/tes">{t.h_new}</Link>
      </div>
      {err && <p className="notice error">{err}</p>}
      {rows === null ? <p className="loading">…</p> : rows.length === 0 ? <p className="hint">{t.h_empty}</p> : (
        <ol className="hist">
          {rows.map(a => (
            <li key={a.id}>
              <div>
                <div className="when">{fmt(a.created_at)}</div>
                <div className="tops">
                  {a.top.slice(0, 3).map((c, i) => (
                    <span key={c.career}>{i + 1}. {careerName(c)} <b>{Math.round(c.fit)}</b></span>
                  ))}
                </div>
              </div>
              <div className="row-actions">
                <button className="btn" onClick={() => view(a)}>{t.h_view}</button>
                <button className="btn ghost" onClick={() => remove(a.id)}>{t.h_delete}</button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
