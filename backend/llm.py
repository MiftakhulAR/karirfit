"""
LLM tasks (thesis Section 3.5.3). The LLM never computes or changes a score, and experience-skill
suggestions come from the dictionary (career_model/extract.py), not from the LLM.

  explain(career, ..., passages) -> four-part explanation citing passage ids (temperature 0, versioned prompt)
  chat(messages, results, passages) -> answer of the career assistant

Provider order for explanations: Gemini (GEMINI_API_KEY) first, then Groq (GROQ_API_KEY); the assistant uses Groq
first. The thesis deployment sets only GROQ_API_KEY (openai/gpt-oss-120b, thesis Table 3.17), so both tasks use
Groq. Setting GEMINI_API_KEY changes the explanation model; every log row records the model used.
No name / e-mail / student number is ever sent (NFR5): only experience text, scores, skill
lists and retrieved passages.
Uses only the standard library (urllib) so no SDK is required.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

PROMPT_VERSION = "v1.2"   # v1.1: career source line (IT job ads vs O*NET reference)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_REASONING = os.getenv("GROQ_REASONING_EFFORT", "low")   # gpt-oss only: low | medium | high
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT = 30


class LLMUnavailable(RuntimeError):
    pass


def _post(url, payload, headers):
    # Groq sits behind Cloudflare, which answers 403 to Python's default "Python-urllib" user agent
    headers = {"User-Agent": "KarirFit/1.0 (+https://karirfit-ecru.vercel.app)", "Accept": "application/json", **headers}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:   # surface the provider's message (e.g. invalid key, unknown model)
        detail = e.read().decode("utf-8", "ignore")[:300]
        raise LLMUnavailable(f"HTTP {e.code}: {detail}") from None


def _groq_body(messages: list[dict], temperature: float, max_tokens: int) -> dict:
    body = {"model": GROQ_MODEL, "temperature": temperature, "messages": messages, "max_completion_tokens": max_tokens}
    if GROQ_MODEL.startswith("openai/gpt-oss"):
        # reasoning tokens count towards max_completion_tokens; keep the answer clean of the reasoning text
        body["reasoning_effort"] = GROQ_REASONING
        body["include_reasoning"] = False
    return body


def _gemini(prompt: str, json_mode: bool) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise LLMUnavailable("GEMINI_API_KEY not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    cfg = {"temperature": 0}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    out = _post(url, {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg},
                {"Content-Type": "application/json", "x-goog-api-key": key})   # header, not URL: keeps the key out of logs
    return out["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt: str, json_mode: bool) -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise LLMUnavailable("GROQ_API_KEY not set")
    body = _groq_body([{"role": "user", "content": prompt}], 0, 3000)
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    out = _post(GROQ_URL, body,
                {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    return out["choices"][0]["message"]["content"]


def complete(prompt: str, json_mode=False) -> tuple[str, str]:
    """Returns (text, model_id). Raises LLMUnavailable if no provider works."""
    errors = []
    for name, fn, model in (("gemini", _gemini, GEMINI_MODEL), ("groq", _groq, GROQ_MODEL)):
        try:
            return fn(prompt, json_mode), f"{name}:{model}"
        except Exception as e:  # network, quota, missing key
            errors.append(f"{name}: {e}")
    raise LLMUnavailable("; ".join(errors))


# --------------------------------------------------------------------------- task 2
EXPLAIN_PROMPT = """You are a career guidance assistant. Write in {language}.
Explain why the career "{career}" was recommended to this person. Use ONLY the facts below and
the CONTEXT passages. Cite passages with their id in square brackets, e.g. [{example_id}].
If something is not supported by the facts or context, do not say it.

FACTS (computed by the system, do not change them):
- Fit score: {fit:.0f}/100 (competency fit {k:.0%}, interest match: {interest})
- Career source: {career_source}
- Matched skills (skill: demand in job ads or O*NET importance, evidence): {matched}
- Skill gaps ordered by importance (skill: demand in job ads or O*NET importance): {gaps}
- Soft skills often requested for this career that the person has not marked as strong (development checklist; required soft skills already contribute to the computed score): {soft}

CONTEXT:
{context}

Answer in exactly four short sections with these headings:
1. {h1}
2. {h2}
3. {h3}
4. {h4}
"""

HEADINGS = {
    "id": ("Dasar kecocokan", "Kompetensi yang sudah sesuai", "Kompetensi yang perlu ditingkatkan", "Saran pengembangan"),
    "en": ("Basis of fit", "Matched competencies", "Competencies to improve", "Development advice"),
}


def explain(result: dict, names: dict, passages: list[dict], lang="id", soft_names: dict | None = None) -> tuple[str, str]:
    fmt = lambda r: (f"{names.get(r['skill'], r['skill'])}: {r['demand']:.0%}" if r.get("demand") is not None else
                     f"{names.get(r['skill'], r['skill'])}: O*NET importance {r.get('importance', 0):.1f}/{r.get('scale', 5)}")
    matched = "; ".join(f"{fmt(r)}, {r['evidence']['source']}" for r in result["matched"]) or "none"
    gaps = "; ".join(fmt(r) for r in result["gaps"][:6]) or "none"
    soft_names = soft_names or {}
    soft = ", ".join(soft_names.get(r["skill"], r["skill"]) for r in result.get("soft", []) if not r.get("have"))[:300] or "none"
    context = "\n\n".join(f"[{p['id']}] ({p['source']}) {p['text']}" for p in passages) or "(no passages)"
    h = HEADINGS.get(lang, HEADINGS["en"])
    prompt = EXPLAIN_PROMPT.format(
        language="Indonesian" if lang == "id" else "English",
        career=result["name_id"] if lang == "id" else result["name_en"],
        example_id=passages[0]["id"] if passages else "P1",
        fit=result["fit"], k=result["K"], interest="yes" if result["M"] else "no",
        career_source=("O*NET 31.0 reference profile (United States), not validated for Indonesia; requirements are "
                       "O*NET importance ratings, NOT job-ad demand - never state job-ad percentages for it"
                       if result.get("group") == "non_it" else "Indonesian IT job ads (demand = share of job ads)"),
        matched=matched, gaps=gaps, soft=soft, context=context, h1=h[0], h2=h[1], h3=h[2], h4=h[3])
    return complete(prompt)


_BRACKET_RE = re.compile(r"\[([^\[\]\n]{1,120})\]")


def _looks_like_citation(token: str) -> bool:
    """Passage ids look like 'skkni-00385'; invented markers look like 'FACT-SQL', 'FACTS', 'P1'.
    Plain words in brackets (e.g. '[Python]') are left alone."""
    return bool(re.fullmatch(r"[A-Za-z0-9_\-:.]+", token)) and (
        any(ch.isdigit() for ch in token) or "-" in token or "_" in token or token.isupper())


def strip_unknown_citations(text: str, passages: list[dict]) -> tuple[str, list[str]]:
    """Remove citation markers that do not point to a retrieved passage (e.g. '[FACT-SQL]').
    Only the text shown to the user is cleaned; the raw text is still checked and logged,
    so the evidence-support metric keeps counting these markers as unsupported."""
    known = {p["id"] for p in passages}
    removed: list[str] = []

    def repl(m: re.Match) -> str:
        parts = [x.strip() for x in m.group(1).split(",")]
        if not all(_looks_like_citation(x) for x in parts):
            return m.group(0)
        keep = [x for x in parts if x in known]
        removed.extend(x for x in parts if x not in known)
        return f"[{', '.join(keep)}]" if keep else ""

    clean = _BRACKET_RE.sub(repl, text)
    clean = re.sub(r"[ \t]+([.,;:])", r"\1", clean)
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    return clean, sorted(set(removed))


# --------------------------------------------------------------------------- career assistant chat
CHAT_SYSTEM = """You are KarirFit's career assistant. Answer in {language}, briefly and concretely.
Help the person understand their career test results and plan how to learn the skills they lack.
Rules:
- Use the RESULTS and CONTEXT below for anything about their scores, skills or job-ad demand. Never
  invent scores, percentages, salaries or statistics; if the data is not here, say you do not know.
- When you use a CONTEXT passage, cite its id in square brackets, e.g. [{example_id}].
- You may give general study advice (what to learn first, project ideas, kinds of courses or
  certifications) but do not claim specific prices, dates or that a particular course exists.
- Stay on careers, skills, learning and job searching. Politely decline unrelated requests.
- The ranking was computed by a fixed formula; you cannot change it. Recommendations are
  suggestions to explore, not decisions.

RESULTS (computed by the system):
{results}

CONTEXT:
{context}"""


def chat(messages: list[dict], results_text: str, passages: list[dict], lang: str = "id") -> tuple[str, str]:
    """Groq chat completion (GROQ_MODEL); falls back to Gemini if Groq is unavailable."""
    context = "\n\n".join(f"[{p['id']}] ({p['source']}) {p['text'][:900]}" for p in passages) or "(no passages)"
    system = CHAT_SYSTEM.format(language="Indonesian" if lang == "id" else "English",
                                example_id=passages[0]["id"] if passages else "P1",
                                results=results_text, context=context)
    history = [{"role": m["role"], "content": str(m["content"])[:2000]}
               for m in messages[-12:] if m.get("role") in ("user", "assistant")]
    key = os.getenv("GROQ_API_KEY")
    if key:
        for attempt in range(2):   # one retry: free-tier 429s and empty gpt-oss replies are usually transient
            try:
                out = _post(GROQ_URL, _groq_body([{"role": "system", "content": system}] + history, 0.3, 2500),
                            {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
                text = (out["choices"][0]["message"].get("content") or "").strip()
                if not text:
                    raise LLMUnavailable("empty reply (reasoning used all tokens)")
                return text, f"groq:{GROQ_MODEL}"
            except Exception as e:
                err = e
                if attempt == 0:
                    time.sleep(2)
    else:
        err = LLMUnavailable("GROQ_API_KEY not set")
    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    try:   # fallback keeps the assistant available
        text = _gemini(system + "\n\nCONVERSATION:\n" + transcript + "\nASSISTANT:", json_mode=False)
        return text, f"gemini:{GEMINI_MODEL}"
    except Exception as e2:
        raise LLMUnavailable(f"groq: {err}; gemini: {e2}")
