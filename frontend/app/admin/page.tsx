"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { AdminCatalog } from "@/components/AdminCatalog";
import { useApp } from "@/components/AppProvider";
import { api } from "@/lib/api";
import type { KbList } from "@/lib/types";

const TOKEN_KEY = "karirfit:admin-token";
const DOC_TYPES = ["skkni", "occupation_map", "rps", "course", "other"];
type Tab = "overview" | "feedback" | "kb" | "catalog" | "log" | "system";

/** One row of the evaluation log (GET /api/export). Only the fields used here are typed. */
interface LogRow {
  ts: number; kind: string; session: string; career?: string; rating?: number; mode?: string; condition?: string;
  check?: { evidence_support?: number | null }; timings?: { total_ms?: number }; top?: string[];
  question?: string; prefers_normal?: boolean; [k: string]: unknown;
}

const ICONS: Record<Tab, string> = {
  overview: "M3 12l9-9 9 9M5 10v10h14V10",
  feedback: "M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z",
  kb: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  catalog: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  log: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  system: "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12h2M3 12h2M12 3v2M12 19v2",
};
const LABEL: Record<Tab, string> = { overview: "Ringkasan", feedback: "Umpan balik", kb: "Basis pengetahuan", catalog: "Katalog", log: "Log aktivitas", system: "Status sistem" };

const Ico = ({ d }: { d: string }) => (
  <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg>
);
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const fmt = (x: number | null, d = 2) => (x == null ? "—" : x.toFixed(d).replace(".", ","));
const when = (ts: number) => new Date(ts * 1000).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Jakarta" });

function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: "good" | "warn" }) {
  return (
    <div className={"adm-stat" + (tone ? " " + tone : "")}>
      <p>{label}</p><strong>{value}</strong>{hint && <span>{hint}</span>}
    </div>
  );
}

/** Administrator panel (FR10). Layout follows the earlier CareerAI admin: side navigation,
 *  summary cards, feedback per career, knowledge-base management and system status.
 *  Every call needs the backend ADMIN_TOKEN; the token stays in this browser tab only. */
export default function AdminPage() {
  const { model, careerName, health } = useApp();
  const [token, setToken] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [kb, setKb] = useState<KbList | null>(null);
  const [logRows, setLogRows] = useState<LogRow[] | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ doc_type: "skkni", source: "", access: "public", id_prefix: "", careers: [] as string[] });
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => { try { setToken(sessionStorage.getItem(TOKEN_KEY) || ""); } catch { /* ignore */ } }, []);

  const names = useMemo(() => {
    const m: Record<string, string> = {};
    model?.careers.forEach(c => { m[c.id] = careerName(c); });
    return m;
  }, [model, careerName]);
  const nameOf = (id?: string) => (id ? names[id] ?? id : "—");

  const refresh = useCallback(async (tk = token) => {
    if (!tk) return;
    try { setKb(await api.kbList(tk)); setMsg(null); }
    catch { setKb(null); setMsg("Akses admin belum berhasil. Periksa token administrator lalu coba lagi. Kata sandi akun pengguna tidak dapat dipakai sebagai token admin."); return; }
    try { setLogRows(await api.exportLog(tk) as LogRow[]); } catch { setLogRows([]); }
  }, [token]);

  useEffect(() => { if (token) refresh(token); }, [token, refresh]);

  const waitForRebuild = useCallback(async () => {
    for (;;) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const st = await api.kbStatus(token);
        if (st.state !== "running") { setMsg(st.message); await refresh(); return; }
      } catch (e) { setMsg((e as Error).message); return; }
    }
  }, [token, refresh]);

  const login = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const tk = String(new FormData(e.currentTarget).get("token") || "").trim();
    setMsg(null);
    try { sessionStorage.setItem(TOKEN_KEY, tk); } catch { /* ignore */ }
    setToken(tk);
  };
  const logout = () => { try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } setToken(""); setKb(null); setLogRows(null); };

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file || !form.careers.length) { setMsg("Pilih berkas dan minimal satu karier."); return; }
    const fd = new FormData();
    fd.append("file", file);
    fd.append("doc_type", form.doc_type);
    fd.append("careers", form.careers.join("|"));
    fd.append("source", form.source);
    fd.append("access", form.access);
    fd.append("id_prefix", form.id_prefix);
    setBusy(true);
    try { await api.kbUpload(token, fd); setMsg(`${file.name} diunggah. Jalankan "Bangun ulang indeks" agar dipakai.`); setFile(null); await refresh(); }
    catch (err) { setMsg((err as Error).message); }
    setBusy(false);
  };

  const remove = async (f: string) => {
    if (!window.confirm(`Hapus ${f} dari basis pengetahuan?`)) return;
    setBusy(true);
    try { await api.kbDelete(token, f); setMsg(`${f} dihapus. Bangun ulang indeks agar perubahan berlaku.`); await refresh(); }
    catch (err) { setMsg((err as Error).message); }
    setBusy(false);
  };

  const rebuild = async () => {
    try {
      await api.kbRebuild(token);
      setMsg("Membangun ulang indeks… (bisa beberapa menit)");
      await refresh();
      await waitForRebuild();
    } catch (err) { setMsg((err as Error).message); }
  };

  const exportLog = () => {
    if (!logRows) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(logRows, null, 1)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url; a.download = `karirfit-log-${new Date().toISOString().slice(0, 10)}.json`; a.click();
    URL.revokeObjectURL(url);
    setMsg(`${logRows.length} baris log diunduh.`);
  };

  // ------------------------------------------------------------------ summary from the evaluation log
  const s = useMemo(() => {
    const rows = logRows ?? [];
    const by = (k: string) => rows.filter(r => r.kind === k);
    const ratings = by("rating").filter(r => typeof r.rating === "number");
    const perCareer: Record<string, number[]> = {};
    ratings.forEach(r => { (perCareer[r.career ?? "?"] ??= []).push(r.rating as number); });
    const rag = by("explain").map(r => r.check?.evidence_support).filter((x): x is number => typeof x === "number");
    const norag = by("explain_norag").map(r => r.check?.evidence_support).filter((x): x is number => typeof x === "number");
    const times = [...by("explain"), ...by("chat")].map(r => r.timings?.total_ms).filter((x): x is number => typeof x === "number");
    const choices = by("compare_choice");
    const prefersNormal = choices.filter(r => r.prefers_normal === true).length;
    return {
      sessions: new Set(rows.filter(r => r.session !== "admin").map(r => r.session)).size,
      tests: by("recommend").length, explains: by("explain").length, chats: by("chat").length,
      ratings, perCareer: Object.entries(perCareer).map(([c, v]) => ({ c, n: v.length, m: mean(v) as number })).sort((a, b) => b.n - a.n),
      meanRating: mean(ratings.map(r => r.rating as number)), rag: mean(rag), norag: mean(norag), nRag: rag.length, nNorag: norag.length,
      medianMs: times.length ? [...times].sort((a, b) => a - b)[Math.floor(times.length / 2)] : null,
      choices: choices.length, prefersNormal, sus: by("sus").length,
      recent: [...rows].reverse().filter(r => r.kind !== "admin_kb").slice(0, 25),
    };
  }, [logRows]);

  if (!token || !kb) {
    return (
      <section className="adm-login">
        <div className="adm-brand"><span>K</span> KarirFit <em>Admin</em></div>
        <h2>Masuk sebagai administrator</h2>
        <p>Panel ini memakai token administrator, bukan email dan kata sandi akun peserta. Jangan bagikan token kepada siapa pun.</p>
        <form onSubmit={login}>
          <label>Token administrator<input name="token" type="password" autoComplete="off" required /></label>
          <button className="btn primary">Masuk</button>
        </form>
        <p className="hint">Sesi admin hanya berlaku di tab ini.</p>
        {msg && <p className="notice error">{msg}</p>}
      </section>
    );
  }

  const ratingTone = s.meanRating == null ? undefined : s.meanRating >= 3.5 ? "good" : "warn";

  return (
    <div className="adm">
      <aside className="adm-side">
        <div className="adm-brand"><span>K</span> KarirFit <em>Admin</em></div>
        <nav>
          {(Object.keys(LABEL) as Tab[]).map(k => (
            <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)} aria-current={tab === k ? "page" : undefined}>
              <Ico d={ICONS[k]} />{LABEL[k]}
            </button>
          ))}
        </nav>
        <div className="adm-side-foot">
          <button className="btn ghost" onClick={() => refresh()}>Muat ulang data</button>
          <button className="btn ghost" onClick={logout}>Keluar admin</button>
        </div>
      </aside>

      <div className="adm-main">
        <header className="adm-head">
          <p className="crumb">Admin › {LABEL[tab]}</p>
          <h2>{LABEL[tab]}</h2>
        </header>
        {msg && <p className="notice">{msg}</p>}

        {tab === "overview" && (
          <>
            <div className="adm-grid">
              <Stat label="Sesi pengguna" value={s.sessions} hint="akun yang tercatat di log" />
              <Stat label="Tes dijalankan" value={s.tests} />
              <Stat label="Penjelasan AI" value={s.explains} />
              <Stat label="Pertanyaan ke asisten" value={s.chats} />
              <Stat label="Rata-rata rating" value={fmt(s.meanRating)} hint={`target ≥ 3,5 · n = ${s.ratings.length}`} tone={ratingTone} />
              <Stat label="Dukungan bukti (RAG)" value={fmt(s.rag)} hint={`non-RAG ${fmt(s.norag)} · n = ${s.nRag}/${s.nNorag}`} tone={s.rag == null ? undefined : s.rag >= 0.9 ? "good" : "warn"} />
              <Stat label="Median waktu respons AI" value={s.medianMs == null ? "—" : `${fmt(s.medianMs / 1000, 1)} dtk`} hint="penjelasan dan chat" tone={s.medianMs == null ? undefined : s.medianMs <= 30000 ? "good" : "warn"} />
              <Stat label="Mode evaluasi" value={health?.eval_mode ? "aktif" : "nonaktif"} hint={`${s.choices} pilihan A/B · ${s.prefersNormal} memilih peringkat normal`} />
            </div>
            <section className="adm-card">
              <h3>Basis pengetahuan</h3>
              <p>Indeks {kb.index_ready ? "siap" : "belum siap"} · {kb.n_chunks} potongan · {kb.documents.length} dokumen tambahan · bangun ulang: {kb.rebuild.state}</p>
            </section>
          </>
        )}

        {tab === "feedback" && (
          <div className="adm-two">
            <section className="adm-card">
              <h3>Rating per karier</h3>
              {s.perCareer.length === 0 ? <p className="hint">Belum ada rating.</p> : (
                <table className="tbl">
                  <thead><tr><th>Karier</th><th>n</th><th>Rata-rata</th></tr></thead>
                  <tbody>{s.perCareer.map(r => (
                    <tr key={r.c}><td>{nameOf(r.c)}</td><td>{r.n}</td>
                      <td><span className="adm-bar"><i style={{ width: `${(r.m / 5) * 100}%` }} /></span> {fmt(r.m)}</td></tr>
                  ))}</tbody>
                </table>
              )}
            </section>
            <section className="adm-card">
              <h3>Rating terbaru</h3>
              {s.ratings.length === 0 ? <p className="hint">Belum ada rating.</p> : (
                <ul className="adm-list">
                  {[...s.ratings].reverse().slice(0, 12).map((r, i) => (
                    <li key={i}><span>{nameOf(r.career)}</span>
                      <span className="stars" aria-label={`${r.rating} dari 5`}>{"★".repeat(r.rating as number)}<em>{"★".repeat(5 - (r.rating as number))}</em></span>
                      <small>{when(r.ts)}</small></li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}

        {tab === "kb" && (
          <>
            <section className="adm-card">
              <h3>Indeks pengetahuan (RAG)</h3>
              <p>Indeks siap: <strong>{kb.index_ready ? "ya" : "tidak"}</strong> · Potongan: <strong>{kb.n_chunks}</strong> ·
                Status bangun ulang: <strong>{kb.rebuild.state}</strong> {kb.rebuild.message && `(${kb.rebuild.message})`}</p>
              <div className="row-actions">
                <button className="btn primary" onClick={rebuild} disabled={kb.rebuild.state === "running"}>Bangun ulang indeks</button>
              </div>
            </section>
            <section className="adm-card">
              <h3>Dokumen tambahan ({kb.documents.length})</h3>
              {kb.documents.length === 0 ? <p className="hint">Belum ada dokumen tambahan. Basis pengetahuan publik (SKKNI, okupasi, profil karier) sudah terpasang.</p> : (
                <table className="tbl">
                  <thead><tr><th>Berkas</th><th>Jenis</th><th>Karier</th><th>Akses</th><th /></tr></thead>
                  <tbody>
                    {kb.documents.map(d => (
                      <tr key={d.file}>
                        <td>{d.file}{!d.present && <div className="ev">berkas tidak tersedia</div>}</td>
                        <td>{d.doc_type}</td>
                        <td className="ev">{d.careers.split("|").map(c => nameOf(c)).join(", ")}</td>
                        <td>{d.access}</td>
                        <td><button className="btn ghost" onClick={() => remove(d.file)} disabled={busy}>Hapus</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
            <section className="adm-card">
              <h3>Tambah dokumen</h3>
              <p className="hint">Dokumen dan indeks tambahan disimpan di disk server, sehingga hilang saat server di-restart atau tidur (Render gratis). Simpan berkas aslinya dan unggah ulang bila perlu.</p>
              <form onSubmit={upload} className="adm-form">
                <label>Berkas (PDF, DOCX, TXT)<input type="file" accept=".pdf,.docx,.txt,.md" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
                <label>Jenis
                  <select value={form.doc_type} onChange={e => setForm({ ...form, doc_type: e.target.value })}>
                    {DOC_TYPES.map(x => <option key={x} value={x}>{x}</option>)}
                  </select>
                </label>
                <label>Sumber (untuk sitasi)<input value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} placeholder="SKKNI No. 282 Tahun 2016 Bidang Pemrograman" /></label>
                <label>Prefiks ID<input value={form.id_prefix} onChange={e => setForm({ ...form, id_prefix: e.target.value })} placeholder="SKKNI282" /></label>
                <label>Akses
                  <select value={form.access} onChange={e => setForm({ ...form, access: e.target.value })}>
                    <option value="public">public</option>
                    <option value="private" disabled={health?.public_mode}>private (RPS/kurikulum PNJ){health?.public_mode ? " – tidak dipakai di mode publik" : ""}</option>
                  </select>
                </label>
                <div className="careers">
                  {model?.careers.filter(c => c.group !== "non_it").map(c => (
                    <label key={c.id}>
                      <input type="checkbox" checked={form.careers.includes(c.id)}
                        onChange={e => setForm({ ...form, careers: e.target.checked ? [...form.careers, c.id] : form.careers.filter(x => x !== c.id) })} />
                      {careerName(c)}
                    </label>
                  ))}
                </div>
                <button className="btn primary" disabled={busy}>Unggah</button>
              </form>
            </section>
          </>
        )}

        {tab === "catalog" && <AdminCatalog token={token} setMsg={setMsg} />}

        {tab === "log" && (
          <section className="adm-card">
            <div className="adm-card-head">
              <h3>Aktivitas terbaru</h3>
              <button className="btn" onClick={exportLog} disabled={!logRows?.length}>Unduh log evaluasi (JSON)</button>
            </div>
            <p className="hint">{logRows?.length ?? 0} baris tercatat. Log hanya berisi pengguna yang memberi persetujuan; identitas berupa ID akun (pseudonim).</p>
            <table className="tbl">
              <thead><tr><th>Waktu</th><th>Jenis</th><th>Sesi</th><th>Keterangan</th></tr></thead>
              <tbody>{s.recent.map((r, i) => (
                <tr key={i}>
                  <td>{when(r.ts)}</td>
                  <td><span className={"adm-tag " + r.kind}>{r.kind}</span></td>
                  <td className="ev">{String(r.session).slice(0, 8)}</td>
                  <td className="ev">{r.kind === "recommend" ? `teratas: ${(r.top ?? []).slice(0, 3).map(nameOf).join(", ")}`
                    : r.kind === "rating" ? `${nameOf(r.career)} · ${r.rating}/5`
                    : r.kind === "chat" ? String(r.question ?? "").slice(0, 80)
                    : r.career ? `${nameOf(r.career)}${r.check?.evidence_support != null ? ` · dukungan ${fmt(r.check.evidence_support)}` : ""}` : ""}</td>
                </tr>
              ))}</tbody>
            </table>
          </section>
        )}

        {tab === "system" && (
          <div className="adm-two">
            <section className="adm-card">
              <h3>Layanan</h3>
              <dl className="adm-dl">
                <dt>Status</dt><dd>{health?.ok ? "aktif" : "tidak terjangkau"}</dd>
                <dt>Asisten (LLM)</dt><dd>{health?.chat ? "siap" : "kunci API belum diisi"}</dd>
                <dt>Mode publik</dt><dd>{health?.public_mode ? "ya (hanya dokumen publik)" : "tidak"}</dd>
                <dt>Mode evaluasi</dt><dd>{health?.eval_mode ? "aktif" : "nonaktif"}</dd>
              </dl>
            </section>
            <section className="adm-card">
              <h3>Data model</h3>
              <dl className="adm-dl">
                <dt>Sumber permintaan</dt><dd>{health?.demand_source ?? "—"}</dd>
                <dt>Karier</dt><dd>{model?.careers.length ?? "—"}</dd>
                <dt>Keterampilan</dt><dd>{model ? `${model.skills.length} (${model.skills.filter(s => s.source !== "onet").length} kamus + ${model.skills.filter(s => s.source === "onet").length} O*NET)` : "—"}</dd>
                <dt>Potongan RAG</dt><dd>{kb.n_chunks}</dd>
              </dl>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
