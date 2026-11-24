# KarirFit — Competency-Based IT Career Recommendation

KarirFit helps D4 Informatics Engineering students at Politeknik Negeri Jakarta (PNJ) find the IT careers that best fit their **courses, skills, experience and interests**. The weight of each skill comes from Indonesian job advertisements. An AI explanation cites its sources from a knowledge base, using retrieval-augmented generation (RAG).

> ⚠️ **Not a final decision.** Results are input for career planning, not an official assessment. O*NET careers are United States reference profiles and have not been validated for Indonesia.

- Web app: https://karirfit.vercel.app
- API: https://karirfit.onrender.com (status: `/api/health`)

This app was developed as a final-year project for the Bachelor in Computer Science (MSU–PNJ).

---

## Features

- **Account and consent.** Register with an e-mail address, read how your data are processed, then give consent. Each browser tab has its own session.
- **Step-by-step test:**
  - interests (more than one area can be chosen);
  - technical and soft skills with a level;
  - an experience text with **skill suggestions** from the dictionary, which are added only after you confirm them;
  - courses and grades, or your own courses with their category and credits (1–8 SKS);
  - a target career, searchable across the whole catalogue.
- **Results:**
  - competency and interest fit for the 15 IT careers;
  - an education-level filter (SMA/SMK to S2) for the O*NET reference careers;
  - every requirement with the share of advertisements that ask for it, its evidence source and its status;
  - the skills to improve, with advice.
- **AI explanation with sources.** When no source is relevant enough, the system says the evidence is insufficient instead of making something up.
- **Career assistant.** Free questions about careers; answers never change the ranking.
- **History** of earlier tests and a **relevance rating** (1–5) for each career.
- **Admin panel:** evaluation overview, catalogue management (careers, skills, interest areas, courses), knowledge-base documents and re-indexing, activity log and system status.
- **Two languages:** Indonesian and English.

## How to Use

1. Open https://karirfit.vercel.app, then **register** or **sign in**.
2. Tap **Start the test** and complete each step. You are told if a step is incomplete.
3. In the summary, check your answers, then tap **See results**.
4. On the results page:
   - choose your education level;
   - open a career to see its details and the AI explanation;
   - rate its relevance.
5. Open **History** to see earlier tests.

**The first request can take about one minute.** The free server goes to sleep after a period without use. Once it is awake, an explanation appears in about 4 seconds.

## Common Problems

| Problem | Solution |
|---|---|
| "The server is starting up" appears | Wait up to one minute; the page continues on its own once the server is awake. |
| The explanation says "Insufficient evidence in the knowledge base" | Expected for careers without documents in the knowledge base, such as O*NET careers or careers newly added by the administrator. |
| Signing out in one tab only | Sessions are per tab; other tabs are not signed out. |

## Structure

```
KarirFit_Web/
├─ backend/        FastAPI: scoring, LLM, RAG, claim checks, catalogue, evaluation (tests: backend/tests)
├─ frontend/       Next.js: step-by-step test, results, history, admin
├─ pipeline-data/  Colab notebooks and modules that produce model.json, demand and the knowledge base
└─ docs/           Local setup, hosting, replacing data, change notes (in Indonesian)
```

## Running Locally

Backend (Python 3.12):

```
cd backend
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```

To enable RAG, install `requirements-rag.txt`; it needs more than 512 MB of RAM.

Frontend (Node.js):

```
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. Environment variables and hosting are described in [docs/PANDUAN.md](docs/PANDUAN.md). Never commit `.env` files.

Backend unit tests:

```
cd backend
python -m unittest discover -s tests
```
