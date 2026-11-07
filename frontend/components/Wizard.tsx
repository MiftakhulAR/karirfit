"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Grade, Interest, Level } from "@/lib/types";
import { useApp } from "./AppProvider";
import { ServerError } from "./Header";

const LEVELS: Level[] = ["beginner", "intermediate", "advanced"];
// Peraturan Pendidikan PNJ 2023/2024 Pasal 10; e(s) = points / 4 (model.json params.grade_points)
const GRADES: Grade[] = ["A", "A-", "B+", "B", "B-", "C+", "C", "D", "E"];

export function Wizard() {
  const { t, model, answers } = useApp();
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [warn, setWarn] = useState(false);

  const goto = (n: number) => {
    if (n > 1 && !answers.interests.length) { setWarn(true); return; }
    setWarn(false); setStep(n); window.scrollTo({ top: 0 });
  };
  const LAST = 6;
  const finish = () => {
    try { sessionStorage.setItem("karirfit:submit", "1"); } catch { /* ignore */ }   // results page saves this test to history
    router.push("/hasil");
  };
  const next = () => (step < LAST ? goto(step + 1) : answers.interests.length ? finish() : setWarn(true));

  if (!model) return <ServerError />;

  return (
    <section className="wizard">
      <div className="progress-m" aria-hidden="true">
        <span>{t.step_of(step, LAST)} · <b>{t.steps[step - 1]}</b></span>
        <div className="bar"><i style={{ width: `${(step / LAST) * 100}%` }} /></div>
      </div>
      <ol className="progress" aria-label="Steps">
        {t.steps.map((name, i) => {
          const n = i + 1;
          return (
            <li key={n} className={n < step ? "done" : n === step ? "now" : ""} aria-current={n === step ? "step" : undefined}>
              <button onClick={() => goto(n)}><b>{n}</b><span>{name}</span></button>
            </li>
          );
        })}
      </ol>

      {step === 1 && <StepInterests />}
      {step === 2 && <StepSkills />}
      {step === 3 && <StepSoft />}
      {step === 4 && <StepExperience />}
      {step === 5 && <StepCourses />}
      {step === 6 && <StepSummary />}

      {warn && <p className="notice" role="alert">{t.need_interest}</p>}

      <nav className="wiz-nav">
        <button className="btn ghost" style={{ visibility: step === 1 ? "hidden" : "visible" }} onClick={() => goto(step - 1)}>{t.back}</button>
        <button className="btn primary" onClick={next}>{step === LAST ? t.see : t.next}</button>
      </nav>
    </section>
  );
}

function StepHead({ title, hint }: { title: string; hint: string }) {
  return (<><h2>{title}</h2><p className="hint">{hint}</p></>);
}

function StepInterests() {
  const { t, model, answers, update, careerName, lang } = useApp();
  const careers = Object.fromEntries(model!.careers.map(c => [c.id, c]));
  const toggle = (id: string) => update(a => ({
    interests: a.interests.includes(id) ? a.interests.filter(x => x !== id) : [...a.interests, id],
  }));
  // an area counts as "general" when most of its careers are non-IT
  const isGeneral = (cs: string[]) => cs.filter(c => careers[c]?.group === "non_it").length * 2 > cs.length;
  const groups: [string, Interest[]][] = [
    [t.s1_it, model!.interests.filter(i => !isGeneral(i.careers))],
    [t.s1_general, model!.interests.filter(i => isGeneral(i.careers))],
  ];
  return (
    <div className="step">
      <StepHead title={t.s1_title} hint={t.s1_hint} />
      <p className="picked sticky-count" aria-live="polite">{t.s1_count(answers.interests.length)}</p>
      {groups.map(([label, items]) => items.length > 0 && (
        <div key={label} className="group">
          <h3 className="group-h">{label}</h3>
          <div className="chips interests">
            {items.map(i => (
              <button key={i.id} className="chip" aria-pressed={answers.interests.includes(i.id)} onClick={() => toggle(i.id)}>
                <span className="tick" aria-hidden="true" />
                <span className="chip-nm">{lang === "id" ? i.name_id : i.name_en}</span>
                <small>{i.careers.map(c => careerName(careers[c])).join(", ")}</small>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function StepSkills() {
  const { t, model, answers, update } = useApp();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const hard = useMemo(() => model!.skills.filter(s => s.kind !== "soft"), [model]);   // soft skills have their own step
  const cats = useMemo(() => ["all", ...new Set(hard.map(s => s.category))], [hard]);
  const list = hard.filter(s => (cat === "all" || s.category === cat) && (!q || s.name.toLowerCase().includes(q.toLowerCase())));
  const setLevel = (id: string, l: Level) => update(a => {
    const skills = { ...a.skills };
    if (skills[id] === l) delete skills[id]; else skills[id] = l;
    return { skills };
  });
  return (
    <div className="step">
      <StepHead title={t.s2_title} hint={t.s2_hint} />
      <div className="skill-tools">
        <input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder={t.s2_search} aria-label={t.s2_search} />
        <div className="cats" role="tablist">
          {cats.map(c => (
            <button key={c} role="tab" aria-selected={c === cat} onClick={() => setCat(c)}>{c === "all" ? t.all : c}</button>
          ))}
        </div>
      </div>
      <div className="skill-list">
        {list.map(s => {
          const lv = answers.skills[s.id];
          return (
            <div key={s.id} className={"skill" + (lv ? " on" : "")}>
              <span className="nm">{s.name}</span>
              <div className="levels" role="group" aria-label={s.name}>
                {LEVELS.map(l => (
                  <button key={l} aria-pressed={lv === l} onClick={() => setLevel(s.id, l)}>{t.lv[l]}</button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <p className="picked">{t.picked(Object.keys(answers.skills).length)}</p>
    </div>
  );
}

function StepSoft() {
  const { t, model, answers, update, lang } = useApp();
  const setLevel = (id: string, l: Level) => update(a => {
    const soft = { ...(a.softSkills ?? {}) };
    if (soft[id] === l) delete soft[id]; else soft[id] = l;
    return { softSkills: soft };
  });
  return (
    <div className="step">
      <StepHead title={t.s_soft_title} hint={t.s_soft_hint} />
      <div className="skill-list">
        {(model!.soft_skills ?? []).map(s => {
          const lv = answers.softSkills?.[s.id];
          const name = lang === "id" ? s.name_id : s.name_en;
          return (
            <div key={s.id} className={"skill" + (lv ? " on" : "")}>
              <span className="nm">{name}</span>
              <div className="levels" role="group" aria-label={name}>
                {LEVELS.map(l => <button key={l} aria-pressed={lv === l} onClick={() => setLevel(s.id, l)}>{t.lv[l]}</button>)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StepExperience() {
  const { t, answers, update, skillName } = useApp();
  const [busy, setBusy] = useState(false);
  const [via, setVia] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const extract = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.extractSkills(answers.experience);
      update({ expSkills: [...new Set(r.skills.map(s => s.skill))], expPhrases: Object.fromEntries(r.skills.map(s => [s.skill, s.phrase])) });
      setVia(r.model);
    } catch (e) {
      setErr(String((e as Error).message));
    } finally { setBusy(false); }
  };
  const remove = (id: string) => update(a => ({ expSkills: a.expSkills.filter(x => x !== id) }));

  return (
    <div className="step">
      <StepHead title={t.s3_title} hint={t.s3_hint} />
      <textarea rows={6} maxLength={1500} value={answers.experience} placeholder={t.s3_placeholder}
        aria-label={t.s3_title} onChange={e => update({ experience: e.target.value })} />
      <div className="row">
        <span className="counter">{answers.experience.length}/1500</span>
        <button className="btn" onClick={extract} disabled={busy || !answers.experience.trim()}>{busy ? t.s3_extracting : t.s3_extract}</button>
      </div>
      {err && <p className="notice error">{err}</p>}
      {answers.expSkills.length > 0 ? (
        <div className="found">
          <h4>{t.s3_found}</h4>
          <p className="hint small">{t.s3_confirm}</p>
          <div className="chips">
            {answers.expSkills.map(id => (
              <button key={id} className="chip" aria-pressed="true" onClick={() => remove(id)}>
                {skillName(id)} ×
                {answers.expPhrases[id] && <q>{answers.expPhrases[id]}</q>}
              </button>
            ))}
          </div>
          {via && <p className="meta">{t.s3_via(via)}</p>}
        </div>
      ) : via && <p className="notice">{t.s3_none}</p>}
    </div>
  );
}

function StepCourses() {
  const { t, model, answers, update, lang } = useApp();
  const cats = model!.course_categories ?? [];
  const [cat, setCat] = useState<string>(() => {
    const taken = model!.courses.find(c => answers.courses[c.id]);
    return taken?.category ?? cats[0]?.id ?? "it";
  });
  const [q, setQ] = useState("");
  const setGrade = (id: string, g: string) => update(a => {
    const courses = { ...a.courses };
    if (g) courses[id] = g as Grade; else delete courses[id];
    return { courses };
  });
  const name = (c: { name_id: string; name_en: string }) => (lang === "id" ? c.name_id : c.name_en);
  const list = model!.courses.filter(c => (q ? name(c).toLowerCase().includes(q.toLowerCase()) : (c.category ?? "it") === cat));
  const count = (id: string) => model!.courses.filter(c => (c.category ?? "it") === id && answers.courses[c.id]).length;
  return (
    <div className="step">
      <StepHead title={t.s4_title} hint={t.s4_hint} />
      <label className="field">
        <span>{t.f_major_wiz}</span>
        <input value={answers.major ?? ""} onChange={e => update({ major: e.target.value })} placeholder={t.f_major_ph} />
      </label>
      <div className="skill-tools">
        <input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder={t.search_course} aria-label={t.search_course} />
        {!q && (
          <div className="cats" role="tablist">
            {cats.map(c => (
              <button key={c.id} role="tab" aria-selected={c.id === cat} onClick={() => setCat(c.id)}>
                {name(c)}{count(c.id) ? ` (${count(c.id)})` : ""}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="courses">
        {list.map(c => {
          const g = answers.courses[c.id] ?? "";
          return (
            <label key={c.id} className={"course" + (g ? " on" : "")}>
              <span>{name(c)}</span>
              <select value={g} onChange={e => setGrade(c.id, e.target.value)} aria-label={name(c)}>
                <option value="">{t.grade_none}</option>
                {GRADES.map(x => <option key={x} value={x}>{x}</option>)}
              </select>
            </label>
          );
        })}
      </div>
    </div>
  );
}

function StepSummary() {
  const { t, model, answers, update, careerName, skillName, softName, lang } = useApp();
  const join = (a: string[]) => (a.length ? a.join(", ") : t.empty);
  const interests = model!.interests.filter(i => answers.interests.includes(i.id)).map(i => (lang === "id" ? i.name_id : i.name_en));
  const courses = model!.courses.filter(c => answers.courses[c.id]).map(c => `${lang === "id" ? c.name_id : c.name_en} (${answers.courses[c.id]})`);
  return (
    <div className="step">
      <StepHead title={t.s5_title} hint={t.s5_hint} />
      <label className="field">
        <span>{t.s5_target}</span>
        <select value={answers.target} onChange={e => update({ target: e.target.value })}>
          <option value="">{t.none}</option>
          {model!.careers.map(c => <option key={c.id} value={c.id}>{careerName(c)}</option>)}
        </select>
      </label>
      <div className="summary">
        <dl>
          <dt>{t.sum_interests}</dt><dd>{join(interests)}</dd>
          <dt>{t.sum_skills}</dt><dd>{join(Object.entries(answers.skills).map(([s, l]) => `${skillName(s)} (${t.lv[l]})`))}</dd>
          <dt>{t.sum_soft}</dt><dd>{join(Object.entries(answers.softSkills ?? {}).map(([s, l]) => `${softName(s)} (${t.lv[l]})`))}</dd>
          <dt>{t.sum_exp}</dt><dd>{join(answers.expSkills.map(skillName))}</dd>
          <dt>{t.sum_major}</dt><dd>{answers.major || t.empty}</dd>
          <dt>{t.sum_courses}</dt><dd>{join(courses)}</dd>
        </dl>
      </div>
      <p className="fine">{t.consent_note}</p>
    </div>
  );
}
