"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useApp } from "@/components/AppProvider";
import { ServerError } from "@/components/Header";
import type { CareerGroup } from "@/lib/types";
import { refNote, reqBar, reqLabel } from "@/lib/reference";

const PAGE = 24;   // O*NET has 896 occupations: render in pages so the catalogue stays light

type Filter = "all" | CareerGroup;
const FILTERS: Filter[] = ["all", "primary", "alternative", "non_it"];

/** Public career catalogue: every career with its most requested skills (from model.json). */
export default function CareersPage() {
  const { t, lang, model, careerName, skillName, softName, user } = useApp();
  const [limit, setLimit] = useState(PAGE);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<string | null>(null);

  // /karier#data_analyst opens that career
  useEffect(() => {
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (id) { setOpen(id); setTimeout(() => document.getElementById(id)?.scrollIntoView({ block: "center" }), 50); }
  }, [model]);

  const list = useMemo(() => (model?.careers ?? []).filter(c =>
    (filter === "all" || c.group === filter) &&
    (!q || `${c.name_id} ${c.name_en} ${c.field_id ?? ""}`.toLowerCase().includes(q.toLowerCase()))), [model, filter, q]);
  useEffect(() => setLimit(PAGE), [filter, q]);
  // IT careers always shown; O*NET occupations in pages ("Tampilkan lebih banyak" / "Sembunyikan")
  const it = list.filter(c => c.group !== "non_it");
  const ref = list.filter(c => c.group === "non_it");
  const visible = [...it, ...ref.slice(0, limit)];

  if (!model) return <ServerError />;

  return (
    <section className="explore">
      <header className="ex-head">
        <h1>{t.ex_title}</h1>
        <p className="lead">{t.ex_lead}</p>
      </header>
      <div className="ex-tools">
        <input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder={t.ex_search} aria-label={t.ex_search} />
        <div className="cats" role="tablist">
          {FILTERS.filter(f => f !== "non_it" || (model?.careers ?? []).some(c => c.group === "non_it")).map(f => (
            <button key={f} role="tab" aria-selected={filter === f} onClick={() => setFilter(f)}>{t.ex_groups[f]}</button>
          ))}
        </div>
      </div>
      <p className="picked">{t.ex_count(list.length)}</p>

      {list.length === 0 ? <p className="hint">{t.ex_none}</p> : (
        <ul className="ex-grid">
          {visible.map(c => {
            const isOpen = open === c.id;
            const reqs = [...c.requirements].sort((a, b) => b.weight - a.weight);
            return (
              <li key={c.id} id={c.id} className={"ex-card " + c.group + (isOpen ? " open" : "")}>
                <button className="ex-top" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : c.id)}>
                  <span className="grp">{t.ex_groups[c.group]}</span>
                  <h2>{careerName(c)}</h2>
                  <span className="ex-preview">{reqs.slice(0, 3).map(r => skillName(r.skill)).join(" · ")}</span>
                  <span className="ex-n">{t.ex_n_skills(c.n_requirements ?? reqs.length)}</span>
                  {c.group === "non_it" && <span className="ex-n">{refNote(c, lang)}</span>}
                </button>
                {isOpen && (
                  <div className="ex-body">
                    <h3>{t.ex_skills}</h3>
                    <ul className="ex-skills">
                      {reqs.slice(0, 10).map(r => (
                        <li key={r.skill}>
                          <span>{skillName(r.skill)}</span>
                          <span className="bar"><i style={{ width: `${reqBar(r)}%` }} /></span>
                          <span className="pctl">{reqLabel(r, lang)}</span>
                        </li>
                      ))}
                    </ul>
                    {(c.soft_skills?.length ?? 0) > 0 && (
                      <>
                        <h3>{t.ex_soft}</h3>
                        <div className="chips small">
                          {c.soft_skills!.slice(0, 6).map(s => <span key={s.skill} className="chip static">{softName(s.skill)}</span>)}
                        </div>
                      </>
                    )}
                    <Link className="btn primary" href={user ? "/tes" : "/masuk?tab=daftar&next=%2Ftes"}>{t.ex_cta}</Link>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {ref.length > PAGE && (
        <div className="ex-more">
          <p className="hint small">{lang === "id"
            ? `Menampilkan ${Math.min(limit, ref.length)} dari ${ref.length} okupasi O*NET 31.0 (profil acuan, belum divalidasi untuk Indonesia; sumber: O*NET 31.0 Database, U.S. DOL/ETA, CC BY 4.0).`
            : `Showing ${Math.min(limit, ref.length)} of ${ref.length} O*NET 31.0 occupations (reference profiles, not validated for Indonesia; source: O*NET 31.0 Database, U.S. DOL/ETA, CC BY 4.0).`}</p>
          {limit < ref.length && <button className="btn ghost" onClick={() => setLimit(l => l + 96)}>{lang === "id" ? "Tampilkan lebih banyak" : "Show more"}</button>}
          {limit < ref.length && <button className="btn ghost" onClick={() => setLimit(ref.length)}>{lang === "id" ? `Tampilkan semua (${ref.length})` : `Show all (${ref.length})`}</button>}
          {limit > PAGE && <button className="btn ghost" onClick={() => setLimit(PAGE)}>{lang === "id" ? "Sembunyikan" : "Hide"}</button>}
        </div>
      )}
    </section>
  );
}
