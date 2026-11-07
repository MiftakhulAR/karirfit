"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useApp } from "@/components/AppProvider";
import { api } from "@/lib/api";
import type { KbList } from "@/lib/types";

const TOKEN_KEY = "karirfit:admin-token";
const DOC_TYPES = ["skkni", "occupation_map", "rps", "course", "other"];

/** Administrator page (FR10): manage knowledge-base documents, rebuild the index, export logs.
 *  Every call needs the backend ADMIN_TOKEN; the token stays in this browser tab only. */
export default function AdminPage() {
  const { model, careerName } = useApp();
  const [token, setToken] = useState("");
  const [kb, setKb] = useState<KbList | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ doc_type: "skkni", source: "", access: "public", id_prefix: "", careers: [] as string[] });
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => { try { setToken(sessionStorage.getItem(TOKEN_KEY) || ""); } catch { /* ignore */ } }, []);

  const refresh = useCallback(async (tk = token) => {
    if (!tk) return;
    try { setKb(await api.kbList(tk)); } catch (e) { setKb(null); setMsg((e as Error).message); }
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
    const tk = String(new FormData(e.currentTarget).get("token") || "");
    try { sessionStorage.setItem(TOKEN_KEY, tk); } catch { /* ignore */ }
    setToken(tk);
  };

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file || !form.careers.length) { setMsg("Pilih berkas dan minimal satu karir."); return; }
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

  const exportLog = async () => {
    try {
      const data = await api.exportLog(token);
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url; a.download = `karirfit-log-${new Date().toISOString().slice(0, 10)}.json`; a.click();
      URL.revokeObjectURL(url);
      setMsg(`${data.length} baris log diunduh.`);
    } catch (err) { setMsg((err as Error).message); }
  };

  if (!token || (!kb && msg)) {
    return (
      <section className="admin">
        <h2>Admin KarirFit</h2>
        <section>
          <form onSubmit={login} style={{ gridTemplateColumns: "1fr auto" }}>
            <label>Admin token (ADMIN_TOKEN di backend)<input name="token" type="password" autoComplete="off" required /></label>
            <button className="btn primary" style={{ alignSelf: "end" }}>Masuk</button>
          </form>
          {msg && <p className="notice error">{msg}</p>}
        </section>
      </section>
    );
  }

  return (
    <section className="admin">
      <h2>Admin KarirFit</h2>
      {msg && <p className="notice">{msg}</p>}

      <section>
        <h3>Indeks pengetahuan (RAG)</h3>
        <p>Indeks siap: <strong>{kb?.index_ready ? "ya" : "tidak"}</strong> · Potongan: <strong>{kb?.n_chunks ?? 0}</strong> ·
          Status bangun ulang: <strong>{kb?.rebuild.state}</strong> {kb?.rebuild.message && `(${kb.rebuild.message})`}</p>
        <div className="row-actions">
          <button className="btn primary" onClick={rebuild} disabled={kb?.rebuild.state === "running"}>Bangun ulang indeks</button>
          <button className="btn" onClick={exportLog}>Unduh log evaluasi (JSON)</button>
          <button className="btn ghost" onClick={() => { try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } setToken(""); setKb(null); }}>Keluar</button>
        </div>
        <p className="fine">{kb?.note}</p>
      </section>

      <section>
        <h3>Dokumen ({kb?.documents.length ?? 0})</h3>
        <table className="tbl">
          <thead><tr><th>Berkas</th><th>Jenis</th><th>Karir</th><th>Akses</th><th /></tr></thead>
          <tbody>
            {kb?.documents.map(d => (
              <tr key={d.file}>
                <td>{d.file}{!d.present && <div className="ev">file tidak ada di server</div>}</td>
                <td>{d.doc_type}</td>
                <td className="ev">{d.careers.split("|").join(", ")}</td>
                <td>{d.access}</td>
                <td><button className="btn ghost" onClick={() => remove(d.file)} disabled={busy}>Hapus</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3>Tambah dokumen</h3>
        <form onSubmit={upload}>
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
              <option value="private">private (RPS/kurikulum PNJ)</option>
            </select>
          </label>
          <div className="careers">
            {model?.careers.map(c => (
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
    </section>
  );
}
