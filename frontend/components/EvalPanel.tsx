"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CareerResult, CompareResponse, ShortRanking } from "@/lib/types";
import { useApp } from "./AppProvider";

const DONE_KEY = "karirfit:v1:eval";

/** Evaluation tasks for study participants (shown only when the backend runs with EVAL_MODE=1):
 *  relevance ratings of the 7 recommended careers (3.6.4), the blind A/B comparison of the normal
 *  ranking vs the ranking without interest fit (3.6.4) and the SUS questionnaire (3.6.6). */
export function EvalPanel({ recommended, ratings }: { recommended: CareerResult[]; ratings: Record<string, number> }) {
  const { t, consent } = useApp();
  const rated = recommended.filter(r => ratings[r.career]).length;

  if (!consent) {
    return (
      <section className="eval">
        <h3>{t.ev_title}</h3>
        <p className="notice">{t.ev_need_consent}</p>
      </section>
    );
  }
  return (
    <section className="eval">
      <h3>{t.ev_title}</h3>
      <p className="hint small">{t.ev_intro}</p>
      <ol className="eval-steps">
        <li>
          <h4>{t.ev_rate_title}</h4>
          <p className={rated === recommended.length ? "ok-line" : "hint small"}>{t.ev_rate_progress(rated, recommended.length)}</p>
        </li>
        <li><Compare /></li>
        <li><Sus /></li>
      </ol>
    </section>
  );
}

function useDone(): [Record<string, boolean>, (k: string) => void] {
  const [done, setDone] = useState<Record<string, boolean>>({});
  useEffect(() => { try { setDone(JSON.parse(localStorage.getItem(DONE_KEY) || "{}")); } catch { /* ignore */ } }, []);
  const mark = (k: string) => setDone(d => {
    const n = { ...d, [k]: true };
    try { localStorage.setItem(DONE_KEY, JSON.stringify(n)); } catch { /* ignore */ }
    return n;
  });
  return [done, mark];
}

function Compare() {
  const { t, profile, session, careerName } = useApp();
  const [data, setData] = useState<CompareResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [done, mark] = useDone();

  const load = () => { setErr(null); api.compare(profile, session).then(setData).catch(e => setErr(String((e as Error).message))); };
  const choose = (c: "A" | "B" | "same") => {
    if (!data) return;
    api.compareChoice(session, data.token, c).then(() => mark("compare")).catch(e => setErr(String((e as Error).message)));
  };
  const Column = ({ label, r }: { label: string; r: ShortRanking }) => (
    <div className="cmp-col">
      <h5>{label}</h5>
      <ol>{r.primary.map(c => <li key={c.career}>{careerName(c)}</li>)}</ol>
      <p className="hint small">{t.r_alt}</p>
      <ol>{r.alternative.map(c => <li key={c.career}>{careerName(c)}</li>)}</ol>
    </div>
  );

  return (
    <>
      <h4>{t.ev_cmp_title}</h4>
      {done.compare ? <p className="ok-line">{t.ev_cmp_done}</p> : (
        <>
          <p className="hint small">{t.ev_cmp_hint}</p>
          {!data && <button className="btn" onClick={load}>{t.ev_cmp_show}</button>}
          {data && (
            <>
              <div className="cmp">
                <Column label={t.ev_cmp_a} r={data.A} />
                <Column label={t.ev_cmp_b} r={data.B} />
              </div>
              {data.same && <p className="hint small">{t.ev_same_note}</p>}
              <div className="cmp-actions">
                <button className="btn" onClick={() => choose("A")}>{t.ev_choose("A")}</button>
                <button className="btn" onClick={() => choose("B")}>{t.ev_choose("B")}</button>
                {data.same && <button className="btn ghost" onClick={() => choose("same")}>{t.ev_same_btn}</button>}
              </div>
            </>
          )}
        </>
      )}
      {err && <p className="notice error">{err}</p>}
    </>
  );
}

function Sus() {
  const { t, lang, session } = useApp();
  const [items, setItems] = useState<string[]>([]);
  const [ans, setAns] = useState<(number | null)[]>(Array(10).fill(null));
  const [msg, setMsg] = useState<string | null>(null);
  const [done, mark] = useDone();

  useEffect(() => { api.susItems(lang).then(r => setItems(r.items)).catch(e => setMsg(String((e as Error).message))); }, [lang]);
  const submit = () => {
    if (ans.some(a => a === null)) { setMsg(t.ev_sus_incomplete); return; }
    api.susSubmit(session, ans as number[]).then(() => { mark("sus"); setMsg(null); }).catch(e => setMsg(String((e as Error).message)));
  };

  return (
    <>
      <h4>{t.ev_sus_title}</h4>
      {done.sus ? <p className="ok-line">{t.ev_sus_done}</p> : (
        <>
          <p className="hint small">{t.ev_sus_hint}</p>
          <ol className="sus">
            {items.map((q, i) => (
              <li key={i}>
                <span>{q}</span>
                <div className="likert" role="radiogroup" aria-label={q}>
                  {[1, 2, 3, 4, 5].map(v => (
                    <button key={v} role="radio" aria-checked={ans[i] === v} aria-label={String(v)}
                      onClick={() => setAns(a => a.map((x, j) => (j === i ? v : x)))}>{v}</button>
                  ))}
                </div>
              </li>
            ))}
          </ol>
          <button className="btn primary" onClick={submit} disabled={!items.length}>{t.ev_sus_submit}</button>
        </>
      )}
      {msg && <p className="notice">{msg}</p>}
    </>
  );
}
