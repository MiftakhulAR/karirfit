"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Catalog, CatalogKind } from "@/lib/types";

/** FR10: the administrator adds, edits or removes careers, skills, interest areas and course templates.
 *  Changes are stored by the backend on top of the evaluated catalogue (model.json) and can be reset. */

const KINDS: { k: CatalogKind; label: string }[] = [
  { k: "careers", label: "Karier" }, { k: "skills", label: "Keterampilan" },
  { k: "interests", label: "Bidang minat" }, { k: "courses", label: "Mata kuliah" },
];
const ACTION = { add: "baru", edit: "diubah", delete: "dihapus" } as const;
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 60);

type Draft = Record<string, unknown> & { id: string; isNew: boolean };
interface Opt { id: string; label: string }

/** Search + chips: picks several ids from a long list (skills, careers). */
function Picker({ options, value, onChange, placeholder }: { options: Opt[]; value: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [q, setQ] = useState("");
  const label = useMemo(() => Object.fromEntries(options.map(o => [o.id, o.label])), [options]);
  const hits = q.trim().length < 2 ? [] : options.filter(o => !value.includes(o.id) && `${o.label} ${o.id}`.toLowerCase().includes(q.toLowerCase())).slice(0, 8);
  return (
    <div className="picker">
      <input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder={placeholder} />
      {hits.length > 0 && <div className="chips">{hits.map(o => <button type="button" key={o.id} className="chip" onClick={() => { onChange([...value, o.id]); setQ(""); }}>+ {o.label}</button>)}</div>}
      {value.length > 0 && <div className="chips">{value.map(id => <button type="button" key={id} className="chip" aria-pressed="true" onClick={() => onChange(value.filter(x => x !== id))}>{label[id] ?? id} ×</button>)}</div>}
    </div>
  );
}

export function AdminCatalog({ token, setMsg }: { token: string; setMsg: (m: string | null) => void }) {
  const [data, setData] = useState<Catalog | null>(null);
  const [kind, setKind] = useState<CatalogKind>("careers");
  const [q, setQ] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setData(await api.catalog(token)); } catch (e) { setMsg((e as Error).message); }
  }, [token, setMsg]);
  useEffect(() => { load(); }, [load]);

  const skillOpts = useMemo(() => (data?.skills ?? []).map(s => ({ id: s.id, label: s.name })), [data]);
  const careerOpts = useMemo(() => (data?.careers ?? []).map(c => ({ id: c.id, label: c.name_id })), [data]);
  const skillName = useMemo(() => Object.fromEntries(skillOpts.map(o => [o.id, o.label])), [skillOpts]);
  if (!data) return <p className="hint">Memuat katalog…</p>;

  const change = (id: string) => data.changes.find(c => c.kind === kind && c.id === id);
  const items = (data[kind] as { id: string; name?: string; name_id?: string; name_en?: string; group?: string }[])
    .filter(x => (q ? `${x.name ?? ""} ${x.name_id ?? ""} ${x.name_en ?? ""} ${x.id}`.toLowerCase().includes(q.toLowerCase())
      : kind !== "careers" || x.group !== "non_it"));
  const deleted = data.changes.filter(c => c.kind === kind && c.action === "delete");

  const edit = (id: string | null) => {
    const x = id ? (data[kind] as unknown as Record<string, unknown>[]).find(i => i.id === id) : null;
    if (kind === "careers") {
      const c = x as Catalog["careers"][number] | null;
      setDraft({ id: id ?? "", isNew: !id, name_id: c?.name_id ?? "", name_en: c?.name_en ?? "", group: c?.group ?? "alternative",
        reqs: (c?.requirements ?? []).map(r => ({ skill: r.skill, pct: r.demand == null ? "" : String(Math.round(r.demand * 1000) / 10) })) });
    } else if (kind === "skills") {
      const s = x as Catalog["skills"][number] | null;
      setDraft({ id: id ?? "", isNew: !id, name: s?.name ?? "", name_id: s?.name_id ?? "", name_en: s?.name_en ?? "", category: s?.category ?? "",
        kind: s?.kind ?? "hard", patterns: (s?.patterns ?? []).join("\n") });
    } else if (kind === "interests") {
      const i = x as Catalog["interests"][number] | null;
      setDraft({ id: id ?? "", isNew: !id, name_id: i?.name_id ?? "", name_en: i?.name_en ?? "", careers: i?.careers ?? [] });
    } else {
      const c = x as Catalog["courses"][number] | null;
      setDraft({ id: id ?? "", isNew: !id, name_id: c?.name_id ?? "", name_en: c?.name_en ?? "", semester: c?.semester ?? 1,
        credits: c?.credits ?? 2, category: c?.category ?? "prodi", skills: c?.skills ?? [] });
    }
  };

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try { await fn(); setMsg(ok); setDraft(null); await load(); } catch (e) { setMsg((e as Error).message); }
    setBusy(false);
  };
  const save = () => {
    if (!draft) return;
    const d = draft;
    const id = d.isNew ? slug(String(d.id || d.name_en || d.name || d.name_id)) : d.id;
    const body = kind === "careers"
      ? { name_id: d.name_id, name_en: d.name_en, group: d.group,
          requirements: (d.reqs as { skill: string; pct: string }[]).map(r => ({ skill: r.skill, demand: Number(r.pct) / 100 })) }
      : kind === "skills" ? { ...d, patterns: String(d.patterns).split("\n").map(p => p.trim()).filter(Boolean) }
      : d;
    run(() => api.catalogSave(token, kind, id, body), `${id} disimpan. Peringkat berikutnya memakai katalog baru.`);
  };
  const remove = (id: string) => {
    if (!window.confirm(`Hapus ${id}? Item asli bisa dikembalikan dengan "Kembalikan"; item baru hilang permanen.`)) return;
    run(() => api.catalogDelete(token, kind, id), `${id} dihapus dari katalog.`);
  };
  const reset = (id: string) => run(() => api.catalogReset(token, kind, id), `${id} dikembalikan ke versi asli.`);

  const set = (k: string, v: unknown) => setDraft(d => (d ? { ...d, [k]: v } : d));
  const field = (k: string, label: string, props: Record<string, unknown> = {}) => (
    <label>{label}<input value={String(draft?.[k] ?? "")} onChange={e => set(k, e.target.value)} {...props} /></label>
  );
  const onet = kind === "careers" && draft?.group === "non_it";

  return (
    <>
      <section className="adm-card">
        <p className="hint">Perubahan berlaku langsung untuk semua pengguna dan tersimpan di database. Evaluasi skripsi memakai katalog asli
          (15 karier TI, 135 keterampilan kamus); item yang diubah bisa dikembalikan ke versi asli. Bobot permintaan karier baru dihitung
          dengan Persamaan 3.2 dari persentase iklan yang diisi.</p>
        <div className="cats" role="tablist">
          {KINDS.map(x => (
            <button key={x.k} role="tab" aria-selected={kind === x.k} onClick={() => { setKind(x.k); setDraft(null); setQ(""); }}>
              {x.label} ({(data[x.k] as unknown[]).length})
            </button>
          ))}
        </div>
        <div className="row-actions">
          <input type="search" value={q} onChange={e => setQ(e.target.value)}
            placeholder={kind === "careers" ? "Cari karier (kosong = 15+ karier TI; ketik untuk mencari O*NET)" : "Cari"} />
          <button className="btn primary" onClick={() => edit(null)} disabled={busy}>+ Tambah</button>
        </div>
      </section>

      {draft && (
        <section className="adm-card">
          <h3>{draft.isNew ? "Tambah" : `Ubah ${draft.id}`}</h3>
          <div className="adm-form">
            {draft.isNew && field("id", "ID (huruf kecil, angka, _; kosong = dari nama)", { placeholder: "game_developer" })}
            {kind === "skills" ? (<>
              {field("name", "Nama")}
              {field("category", "Kategori", { placeholder: "Bahasa Pemrograman" })}
              <label>Jenis<select value={String(draft.kind)} onChange={e => set("kind", e.target.value)}><option value="hard">hard (teknis)</option><option value="soft">soft</option></select></label>
              {draft.kind === "soft" && <>{field("name_id", "Nama Indonesia")}{field("name_en", "Nama Inggris")}</>}
              <label>Pola regex untuk deteksi di teks pengalaman (satu per baris)
                <textarea rows={3} value={String(draft.patterns)} onChange={e => set("patterns", e.target.value)} placeholder={"\\bunity\\b"} /></label>
            </>) : (<>
              {field("name_id", "Nama Indonesia")}
              {field("name_en", "Nama Inggris")}
            </>)}
            {kind === "careers" && (onet ? <p className="hint">Profil acuan O*NET: hanya nama yang bisa diubah; syaratnya berasal dari O*NET.</p> : (<>
              <label>Kelompok<select value={String(draft.group)} onChange={e => set("group", e.target.value)}>
                <option value="primary">Profil lulusan</option><option value="alternative">Alternatif TI</option></select></label>
              <div className="reqs">
                <p>Keterampilan yang diminta (% iklan lowongan yang memintanya)</p>
                {(draft.reqs as { skill: string; pct: string }[]).map((r, i) => (
                  <div key={r.skill} className="req-row">
                    <span>{skillName[r.skill] ?? r.skill}</span>
                    <input type="number" min={1} max={100} step={0.1} value={r.pct} aria-label={`Persentase ${skillName[r.skill] ?? r.skill}`}
                      onChange={e => set("reqs", (draft.reqs as { skill: string; pct: string }[]).map((x, j) => (j === i ? { ...x, pct: e.target.value } : x)))} />
                    <span>%</span>
                    <button type="button" className="btn ghost small" onClick={() => set("reqs", (draft.reqs as unknown[]).filter((_, j) => j !== i))}>Hapus</button>
                  </div>
                ))}
                <Picker options={skillOpts} value={[]} placeholder="Tambah keterampilan yang diminta…"
                  onChange={v => set("reqs", [...(draft.reqs as { skill: string; pct: string }[]), { skill: v[v.length - 1], pct: "20" }])} />
              </div>
            </>))}
            {kind === "interests" && <Picker options={careerOpts} value={draft.careers as string[]} onChange={v => set("careers", v)} placeholder="Tambah karier ke bidang ini…" />}
            {kind === "courses" && (<>
              {field("semester", "Semester", { type: "number", min: 1, max: 8 })}
              {field("credits", "SKS", { type: "number", min: 1, max: 8 })}
              <label>Kelompok<select value={String(draft.category)} onChange={e => set("category", e.target.value)}>
                {data.course_categories.map(c => <option key={c.id} value={c.id}>{c.name_id}</option>)}</select></label>
              <Picker options={skillOpts} value={draft.skills as string[]} onChange={v => set("skills", v)} placeholder="Tambah keterampilan yang diajarkan…" />
            </>)}
            <div className="row-actions">
              <button type="button" className="btn ghost" onClick={() => setDraft(null)}>Batal</button>
              <button type="button" className="btn primary" onClick={save} disabled={busy}>Simpan</button>
            </div>
          </div>
        </section>
      )}

      <section className="adm-card">
        <h3>{KINDS.find(x => x.k === kind)?.label} ({items.length}{items.length > 60 ? ", 60 ditampilkan" : ""})</h3>
        <table className="tbl">
          <thead><tr><th>Nama</th><th>ID</th><th>Status</th><th /></tr></thead>
          <tbody>
            {items.slice(0, 60).map(x => {
              const ch = change(x.id);
              return (
                <tr key={x.id}>
                  <td>{x.name ?? x.name_id}{x.group === "non_it" && <div className="ev">O*NET</div>}</td>
                  <td className="ev">{x.id}</td>
                  <td>{ch ? ACTION[ch.action] : "asli"}</td>
                  <td className="row-actions">
                    <button className="btn ghost small" onClick={() => edit(x.id)} disabled={busy}>Ubah</button>
                    <button className="btn ghost small" onClick={() => remove(x.id)} disabled={busy}>Hapus</button>
                    {ch?.action === "edit" && <button className="btn ghost small" onClick={() => reset(x.id)} disabled={busy}>Kembalikan</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {deleted.length > 0 && (<>
          <h3>Item asli yang dihapus ({deleted.length})</h3>
          <ul className="adm-list">{deleted.map(d => (
            <li key={d.id}>{d.id} <button className="btn ghost small" onClick={() => reset(d.id)} disabled={busy}>Kembalikan</button></li>
          ))}</ul>
        </>)}
      </section>
    </>
  );
}
