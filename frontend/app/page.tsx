"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type CSSProperties } from "react";
import { toProfile, useApp } from "@/components/AppProvider";
import { ServerError } from "@/components/Header";
import { api } from "@/lib/api";
import { listAssessments } from "@/lib/supabase";
import type { Assessment, CareerGroup, CareerResult } from "@/lib/types";
import { reqLabel } from "@/lib/reference";

const HOME_PAGE_SIZE = 24;

export default function Home() {
  const { user, authReady } = useApp();
  if (!authReady) return <p className="loading">…</p>;
  return user ? <Dashboard /> : <Landing />;
}

/* ------------------------------------------------------------------ landing (logged out) */

function Landing() {
  const { t, lang, model, careerName } = useApp();
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<"all" | CareerGroup>("all");
  const [limit, setLimit] = useState(HOME_PAGE_SIZE);
  const careers = model?.careers ?? [];
  const groups: ("all" | CareerGroup)[] = ["all", "primary", "alternative", "non_it"];
  const filtered = careers.filter(c =>
    (group === "all" || c.group === group) &&
    `${c.name_id} ${c.name_en} ${c.field_id ?? ""}`.toLowerCase().includes(query.trim().toLowerCase())
  );
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-copy">
          <p className="badge">{t.land_badge}</p>
          <h1>{t.hero_title}</h1>
          <p className="lead">{t.hero_lead}</p>
          <div className="hero-actions">
            <Link className="btn primary big" href="/masuk?tab=daftar">{t.land_cta}</Link>
            <Link className="btn ghost big" href="/karier">{t.land_cta2}</Link>
          </div>
          <p className="fine">{t.land_login} <Link className="link" href="/masuk">{t.nav_login}</Link></p>
          <ServerError />
        </div>
        <SampleCard />
      </section>

      <section className="band" aria-labelledby="how-h">
        <h2 id="how-h">{t.how_h}</h2>
        <ol className="steps3">
          {t.how_steps.map((s, i) => (
            <li key={s.t}><span className="n">{i + 1}</span><h3>{s.t}</h3><p>{s.d}</p></li>
          ))}
        </ol>
      </section>

      <section className="band split" aria-labelledby="who-h">
        <div>
          <h2 id="who-h">{t.who_h}</h2>
          <p className="hint">{t.hero_fine}</p>
        </div>
        <ul className="who-list">
          {t.who_items.map(w => <li key={w.t}><h3>{w.t}</h3><p>{w.d}</p></li>)}
        </ul>
      </section>

      <section className="band" aria-labelledby="get-h">
        <h2 id="get-h">{t.get_h}</h2>
        <ul className="get-grid">
          {t.get_items.map(g => <li key={g.t}><h3>{g.t}</h3><p>{g.d}</p></li>)}
        </ul>
      </section>

      {careers.length > 0 && (
        <section className="band" aria-labelledby="band-h">
          <h2 id="band-h">{t.band_h}</h2>
          <div className="ex-tools">
            <input type="search" value={query} aria-label={t.ex_search} placeholder={t.ex_search}
              onChange={e => { setQuery(e.target.value); setLimit(HOME_PAGE_SIZE); }} />
            <div className="cats" role="tablist" aria-label={t.band_h}>
              {groups.filter(g => g === "all" || careers.some(c => c.group === g)).map(g => (
                <button key={g} role="tab" aria-selected={group === g}
                  onClick={() => { setGroup(g); setLimit(HOME_PAGE_SIZE); }}>{t.ex_groups[g]}</button>
              ))}
            </div>
          </div>
          <p className="picked">{t.ex_count(filtered.length)}</p>
          <div className="career-cloud" id="home-careers">
            {filtered.slice(0, limit).map(c => (
              <Link key={c.id} href={`/karier#${c.id}`} className={"cc " + c.group}>{careerName(c)}</Link>
            ))}
          </div>
          {filtered.length === 0 && <p className="hint">{t.ex_none}</p>}
          {filtered.length > HOME_PAGE_SIZE && (
            <div className="ex-more">
              <p className="hint small">{lang === "id"
                ? `Menampilkan ${Math.min(limit, filtered.length)} dari ${filtered.length} karir.`
                : `Showing ${Math.min(limit, filtered.length)} of ${filtered.length} careers.`}</p>
              {limit < filtered.length && (
                <>
                  <button className="btn ghost" aria-controls="home-careers"
                    onClick={() => setLimit(n => n + HOME_PAGE_SIZE)}>{lang === "id" ? "Tampilkan lebih banyak" : "Show more"}</button>
                  <button className="btn ghost" aria-controls="home-careers"
                    onClick={() => setLimit(filtered.length)}>{lang === "id" ? "Tampilkan semua" : "Show all"}</button>
                </>
              )}
              {limit > HOME_PAGE_SIZE && (
                <button className="btn ghost" aria-controls="home-careers"
                  onClick={() => setLimit(HOME_PAGE_SIZE)}>{lang === "id" ? "Sembunyikan" : "Hide"}</button>
              )}
            </div>
          )}
        </section>
      )}

      <section className="final">
        <h2>{t.final_h}</h2>
        <p>{t.final_p}</p>
        <Link className="btn kunyit big" href="/masuk?tab=daftar">{t.land_cta}</Link>
      </section>
    </div>
  );
}

/** A static example of the result screen: shows visitors what they will get before signing up. */
function SampleCard() {
  const { t } = useApp();
  const fit = 82;
  return (
    <figure className="sample" aria-label={t.land_sample}>
      <figcaption>{t.land_sample}</figcaption>
      <div className="sample-head">
        <h3>{t.land_sample_career}</h3>
        <div className="ring" style={{ "--p": fit } as CSSProperties}><b>{fit}</b><small>/100</small></div>
      </div>
      <ul>
        {t.land_sample_skills.map(([name, have], i) => (
          <li key={name}>
            <span>{name}</span>
            <span className="bar"><i style={{ width: `${78 - i * 14}%` }} /></span>
            <span className={"tag " + (have ? "ok" : "gap")}>{have ? t.land_have : t.land_learn}</span>
          </li>
        ))}
      </ul>
      <p className="fine">{t.land_sample_note}</p>
    </figure>
  );
}

/* ------------------------------------------------------------------ dashboard (logged in) */

function Dashboard() {
  const { t, lang, user, model, answers, update, careerName, skillName, setChatOpen, session } = useApp();
  const router = useRouter();
  const [hist, setHist] = useState<Assessment[] | null>(null);
  const [top, setTop] = useState<CareerResult | null>(null);

  useEffect(() => { listAssessments().then(setHist).catch(() => setHist([])); }, []);
  const last = hist?.[0];

  // recompute the latest result to show the next skills to learn for the top career
  useEffect(() => {
    if (!last || !model) return;
    api.recommend(toProfile(last.answers), session, false).then(r => setTop(r.top[0] ?? null)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [last?.id, model]);

  const viewLast = () => {
    if (!last) return;
    update({ ...last.answers });
    try { sessionStorage.removeItem("karirfit:submit"); } catch { /* ignore */ }
    router.push("/hasil");
  };
  const inProgress = answers.interests.length > 0 && (!last || JSON.stringify(last.answers) !== JSON.stringify(answers));

  return (
    <div className="dash">
      <header className="dash-head">
        <h1>{t.dash_hello((user?.name || user?.email || "").split(" ")[0])}</h1>
        <p className="lead">{t.dash_sub}</p>
      </header>
      <ServerError />

      <div className="dash-grid">
        <section className="dash-main">
          {hist === null ? <p className="loading">…</p> : last ? (
            <>
              <h2>{t.dash_last}</h2>
              <ol className="podium">
                {last.top.slice(0, 3).map((c, i) => (
                  <li key={c.career} className={i === 0 ? "first" : ""}>
                    <span className="pos">{i + 1}</span>
                    <span className="nm">{careerName(c)}</span>
                    <span className="sc">{Math.round(c.fit)}</span>
                    <span className="bar"><i style={{ width: `${Math.max(3, c.fit)}%` }} /></span>
                  </li>
                ))}
              </ol>
              <div className="dash-actions">
                <button className="btn kunyit" onClick={viewLast}>{t.dash_view}</button>
                <Link className="btn on-dark" href="/tes">{inProgress ? t.continue_test : t.dash_retake}</Link>
              </div>
            </>
          ) : (
            <>
              <h2>{inProgress ? t.dash_progress_h : t.dash_new_h}</h2>
              <p>{inProgress ? t.dash_progress_p : t.dash_new_p}</p>
              <ol className="mini-steps">{t.steps.map(s => <li key={s}>{s}</li>)}</ol>
              <Link className="btn kunyit big" href="/tes">{inProgress ? t.continue_test : t.start}</Link>
            </>
          )}
        </section>

        {top && (
          <section className="dash-next">
            <h2>{t.dash_next_h}</h2>
            {top.gaps.length ? (
              <>
                <p className="hint small">{t.dash_next_p(careerName(top))}</p>
                <ul>
                  {[...top.gaps].sort((a, b) => b.weight - a.weight).slice(0, 4).map(g => (
                    <li key={g.skill}>
                      <span>{skillName(g.skill)}</span>
                      <span className="pctl">{reqLabel(g, lang)}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : <p className="hint small">{t.dash_next_none}</p>}
          </section>
        )}

        <button className="tile chat-tile" onClick={() => setChatOpen(true)}>
          <h3>{t.dash_chat_t}</h3><p>{t.dash_chat_d}</p>
        </button>
        <Link className="tile" href="/karier">
          <h3>{t.dash_explore_t}</h3><p>{t.dash_explore_d(model?.careers.length ?? 30)}</p>
        </Link>
        <Link className="tile" href="/riwayat">
          <h3>{t.dash_hist_t}</h3><p>{t.dash_hist_d(hist?.length ?? 0)}</p>
        </Link>
      </div>
    </div>
  );
}
