# clipgrep v1 — Design

**Date:** 2026-09-24
**Status:** proposed, awaiting review
**Supersedes:** the generic "YouTube AI Workspace" framing in `README.md`

---

## 1. Problem

This repo contains a stronger engine than its positioning admits, and nobody can see
either one.

**Positioning problem.** The surface is add-sources → chat-with-citations → summary,
which is NotebookLM's exact shape. Competing there is unwinnable: NotebookLM is free
and needs zero setup, and `Tencent/WeKnora` already holds the "open-source RAG knowledge
platform" position with ~29k stars and corporate backing.

An earlier draft of this spec claimed the differentiator was cross-source disagreement
analysis, on the theory that NotebookLM is structurally credulous and cannot surface
conflict. **That claim was tested and is false.** Google's own launch post frames
NotebookLM as "great for comparing perspectives across multiple sources," it ingests
YouTube URLs directly, it caps at 50 sources on the free tier, its citations link to the
exact transcript span, it embeds a YouTube player, and users already run prompts like
*"where do these sources disagree, and cite the specific source for each position."*
The "presents everything positively" complaint in the reviews is about **tone, not
capability**, and the earlier draft over-read it.

Similarly, "skip the filler" is better served than an LLM can serve it for popular
videos: `SponsorBlock` is crowdsourced, free, instant, and has a "highlight" feature that
jumps to the point, distributed across Tubular, LibreTube, SkipVids, ReVanced, NewPipe and
FreeTube.

**What survives falsification** — four gaps, ordered by how hard they are to copy:

| # | Gap | Why it holds |
|---|---|---|
| 1 | **NotebookLM requires YouTube captions**, and videos must be ≥1 day old. Older lectures and niche topics frequently lack auto-captions. | This repo downloads audio and transcribes it itself (Whisper / Gemini, see `README.md:9`). **It works on videos NotebookLM cannot ingest at all.** A capability gap, not a framing one — and expensive for Google to close at their scale. |
| 2 | Your sources and queries go to Google. | `core/llm.py:12` supports Ollama — "no key, no limits, no cost." A fully local pipeline, which Google structurally cannot offer. |
| 3 | 50 sources on the free tier, plus invisible daily and weekly query caps. | Self-hosted has no caps. |
| 4 | NotebookLM is a web UI and cannot be automated. | CLI + API: scriptable, batchable, pipeable, CI-able, exportable to `SKILL.md` (v2). |

The verification machinery (`claim_extractor`'s chunk_id validation; the verbatim-substring
rule in §3.2) is an architectural guarantee rather than a prompt request. That earns trust
with engineers, but a casual user cannot perceive it — it is a credibility asset, not a
consumer hook, and the README should not lead with it.

**Visibility problem, and this is the binding constraint.** Path to first output today:
Python venv → two requirements files → a Gemini key → install Deno → run a Docker
PO-token sidecar → ffmpeg → wait minutes for transcription. Roughly 30 minutes with a
real failure rate. For comparison, `bilawalsidhu/gods-eye-view` earned ~41k stars in
thirty days running entirely in a browser. No positioning work matters while the output
is invisible.

**Validated user pain** (research, 2026-09-24):

| Pain | Evidence |
|---|---|
| Padding — wanting one formula, finding 20-minute videos, "skip through to find the exact moment it was mentioned" | Medium, developer accounts of tutorial use |
| Triage — "searching a topic returns an infinite list where training videos get mixed with entertainment" | Medium, YouTube learning UX analysis |
| Can't detect outdated/incorrect advice | Medium; JMIR Infodemiology (Oct 2025), 33 studies on fitness misinformation |
| Abandonment — a "graveyard of half-used notebooks" when setup cost exceeds payoff | Medium, NotebookLM workflow accounts |
| Tedious setup — each video is a separate source; a 20-lecture playlist means 20 individual links | NotebookLM usage guides |

**Not** validated: nobody asked whether a creator contradicts themselves. That idea is a
marketing asset, not a daily-use feature. It moves to v3.

**Category precedent.** `scite.ai` built a 2M-user business on supporting/contrasting
citation classification for papers. `transcriptintelligence.com` sells contradiction
detection ("Clash Finder") for TV transcripts.

**Star-formula precedent, and this is the model to copy.** Neither of the two most
comparable trending repos claims novel capability. `VoiceStudio` — "open-source,
fully-local ElevenLabs alternative" — has ~34.8k stars. `open-seo` — "open source
alternative to Semrush and Ahrefs" — has ~20.5k. **Both win on sovereignty and the
absence of limits, not on doing something nobody else does.** That is the position here.

## 2. What we are building

> **clipgrep — NotebookLM for the videos it can't read, on hardware you own, at a scale
> it won't allow.**

The claim is deliberately smaller than "we do something unique," because that claim did
not survive §1. Four user-facing capabilities:

0. **Works on any video** — no captions required, no 24-hour wait. This is gap #1 and the
   sharpest demo: a URL that visibly fails in NotebookLM and succeeds here.
1. **Density** — one URL, no question. **MEASURED OUTCOME (2026-09-24): the
   claim-bearing percentage does not discriminate.** Across 7 real videos from 6 creators
   it ranged 87-100%, because chunks are ~180 words and nearly every chunk yields a claim,
   so the figure tracks chunk size rather than substance. `claims_per_minute` does vary
   (1.63-3.67) but n=7 is too small to call that signal rather than speaking pace. Shipped
   as a diagnostic with the saturation disclosed in its own output; **not** a headline and
   not a way to rank videos. Original rationale below, kept for the record. "At least 3 minutes of this 24-minute video contain
   checkable claims. Here they are." Zero user input, ~60 seconds to value. Honest scope:
   `SponsorBlock`'s crowdsourced highlight already serves *popular* videos better. Density's
   real edge is that it needs no crowd data and is semantic rather than
   popularity-based — so it works on the long tail, which is also where captions are
   missing. It is a useful signal, **not** the headline.
2. **Clips** — a question over N videos. Ranked timestamped clips that *answer* it,
   conflicts between them flagged, and a report of which videos to skip.
3. **Fully local, uncapped, scriptable** — gaps #2, #3 and #4. Runs end-to-end on Ollama
   with no API key and no per-day limits; driven by CLI and API rather than a web UI, so it
   batches and pipes. Promoted from a footnote to a headline, and **measured** rather than
   asserted (§3.5).
4. **A static browser demo** — precomputed real output on GitHub Pages with embedded
   YouTube players seeking to each timestamp. No install, no key, no backend.

### Non-goals for v1

- **`SKILL.md` export** → v2. Agent skills are where GitHub stars currently concentrate
  (`archify` 55,857/month; `i-have-adhd` 27,477/month; `scientific-agent-skills` 46k
  total), and `FUTURE_IDEAS.md:40` already identified it. It ships second because the
  answer gate is what makes an exported skill trustworthy — "AI summarized 10 videos into
  a skill file" is a weekend with no moat.
- **Self-contradiction detection (drift)** → v3, as a launch hook.
- **Staleness / recency labeling** → v3. "Stale" is a strong assertion; v1 shows publish
  dates and lets the reader judge.
- **Sub-chunk clip trimming.** Chunk granularity (~60-75s) is close enough to the promise.
  Sentence-level times are computed in `ingestion/chunker.py` but not persisted;
  persisting them is a separate change.
- **Multi-user auth, hosted service, horizontal scaling.** See `atpes/Auth Refactor
  Decision.md` and `atpes/Backend Worker Decision.md` — both explicitly single-node.

## 3. Architecture

Everything below reuses the existing pipeline. No existing module is restructured.

```
                    ┌──────────────── EXISTING, UNCHANGED ────────────────┐
YouTube URL ──▶ scraper ──▶ ingest ──▶ index ──▶ extract-claims
                    │        chunks   Qdrant     claims.json
                    └─────────────────────────────────────────────────────┘
                                 │                      │
              ┌──────────────────┘                      └──────────────┐
              ▼                                                        ▼
   ┌──────────────────────┐                            ┌────────────────────────┐
   │ NEW knowledge/       │                            │ NEW retrieval/clips.py │
   │     density.py       │                            │                        │
   │                      │                            │ 1. hybrid retrieve +   │
   │ per video:           │                            │    rerank  (EXISTING)  │
   │  interval-union of   │                            │ 2. ANSWER GATE  ← core │
   │  claim-bearing       │                            │ 3. conflict flag       │
   │  chunks ÷ duration   │                            │    (new batched prompt)│
   │                      │                            │ 4. skip report         │
   │ → density.json       │                            │ → clips JSON           │
   └──────────────────────┘                            └────────────────────────┘
              │                                                        │
              └────────────────────────┬───────────────────────────────┘
                                       ▼
                         ┌─────────────────────────────┐
                         │ renderers: terminal + JSON  │
                         └─────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │ docs/demo/ — static site    │
                         │ committed JSON + YT iframes │
                         │ GitHub Pages, no backend    │
                         └─────────────────────────────┘
```

### 3.1 Density — `rag/knowledge/density.py`

**Purpose:** measure how much of a video's runtime contains checkable claims.
**Depends on:** `claims.json`, `chunks.json`, `videos.json` in the workspace. No network.
**Used by:** `cli.py density`, the static demo.

Algorithm:

1. For each claim, resolve `claim.evidence[].chunk_id` to its chunk. Chunks with at least
   one validated claim are *claim-bearing*.
2. Group claim-bearing chunks by `video_id`.
3. Compute the **interval union** of their `[start_seconds, end_seconds]` ranges.
   Chunks deliberately overlap (`CHUNK_OVERLAP_WORDS = 25`), so naive summation
   double-counts. Union is required for correctness.
4. `density = union_seconds / video.duration_seconds`; also report
   `claims_per_minute = claim_count / (duration_seconds / 60)`.

**Honesty requirements — these are load-bearing, not decoration.** Claim extraction is an
LLM step with imperfect recall, so a chunk may contain a claim the model missed.
Therefore:

- Density is reported as a **floor**: "at least N minutes," never "only N minutes."
- It is named **claim density**, never a quality or "slop" score. A good explainer or a
  story legitimately produces few atomic claims and is not padding. The README must say
  this in plain words.
- Percentages round to whole numbers ("12%", not "12.4%") because chunk boundaries are
  partly estimated (§5.1) and finer precision would be false.

This follows the existing discipline in `core/models.py:53` — derive signals from counted
data, never from LLM self-rating.

Output `density.json`:

```json
[{"video_id": "abc123", "video_title": "...", "channel": "...",
  "upload_date": "20260411", "duration_seconds": 1440,
  "claim_bearing_seconds": 176, "density": 0.12, "claim_count": 9,
  "claims_per_minute": 0.38, "any_estimated_timestamps": true,
  "segments": [{"start_seconds": 112.0, "end_seconds": 178.0}]}]
```

### 3.2 Answer gate — `rag/retrieval/clips.py`

**Purpose:** return only the clips that *answer* a question, not those that mention its
topic. This single step is the product.
**Depends on:** `retrieval/hybrid.py`, `retrieval/reranker.py`, `core/llm.py`.
**Used by:** `cli.py clips`, `api.py POST /clips`, the static demo.

| Step | Mechanism | LLM calls |
|---|---|---|
| 1. Retrieve | Existing hybrid (vector + BM25) + cross-encoder rerank → top `RERANK_KEEP_TOP` (8) | 0 |
| 2. **Answer gate** | **One batched call** over all 8 chunks → per chunk `answers` / `mentions` / `unrelated` + a verbatim answering span | 1 |
| 3. Conflict flag | **One batched call** over all kept clips → list of conflicting index pairs | 1 (skipped if <2 clips) |
| 4. Skip report | Pure arithmetic over `videos.json` | 0 |

**Why step 3 needs a new prompt rather than reusing the synthesizer.**
`synthesizer.build_relationship_prompt` (line 64) returns exactly *one* relationship label
for a whole group of claims. It cannot say *which pair* conflicts, and calling it pairwise
over 5 clips would cost 10 LLM calls instead of 1 — breaking the cost budget that makes
casual use viable. So `clips.py` gets its own prompt: all kept clips in, a list of
conflicting index pairs out, one call.

It inherits the existing prompt's discipline rather than its code — a closed label set,
JSON-only output with no markdown fences, and validation that every returned index refers
to a clip actually passed in (invented indices are discarded, mirroring
`parse_relationship_response`'s `valid_claim_ids` check at `synthesizer.py:93`).
**Only `contradiction` raises a flag in v1.** `partial_agreement` and `different_context`
are real signals but too subtle to render as a warning in a five-row list; they return in
v3 alongside drift.

**~2 LLM calls per question.** Batching follows the existing
`CLAIM_EXTRACTION_BATCH_SIZE` pattern. Low per-use cost is a feature, not an
optimization: the abandonment research shows tools die when cost-per-use exceeds payoff.

**Hallucination guard (mirrors `claim_extractor.py`'s chunk_id validation).** The gate
returns a verbatim answering span. That span MUST be an exact substring of the chunk's
text. If it is not, the chunk is downgraded to `mentions` and excluded. The system never
displays text a source did not say. This is the same guarantee `claim_extractor` makes
about evidence, applied to spans.

Ranking among `answers` chunks: reranker score descending, tie-broken toward
`is_estimated == False` so exactly-anchored clips surface first.

Cap at `CLIP_MAX_RETURNED` (5). Pair comparisons capped at 10.

Output shape (also the demo's data contract):

```json
{"question": "does creatine cause bloating?",
 "workspace_id": "fitness",
 "generated_at": "2026-09-24T00:00:00Z",
 "provider": "gemini",
 "clips": [
   {"rank": 1, "chunk_id": "vid1_c14", "video_id": "vid1",
    "video_title": "...", "channel": "@Nippard", "upload_date": "20260411",
    "start_seconds": 1170.0, "end_seconds": 1218.0, "is_estimated": true,
    "span": "water retention is intramuscular, not subcutaneous",
    "watch_url": "https://youtu.be/vid1?t=1167",
    "conflicts_with": [2]}],
 "skipped": {"video_count": 9, "total_seconds": 13860,
             "video_ids": ["vid3", "vid4"]},
 "llm_calls": 2}
```

`vector_store.py:114-122` already stores `chunk_id`, `video_id`, `video_title`,
`channel`, `start_seconds`, `end_seconds`, and `text` in the Qdrant payload — verified,
so no join back to `chunks.json` is needed at query time. `is_estimated` is **not** in the
payload and must be joined from `chunks.json`, or added to the payload during indexing.
Adding it to the payload is preferred; it requires a re-index, which is already idempotent
(`vector_store.py:112`).

### 3.3 CLI

Two new argparse subparsers, matching the existing style in `cli.py:729-794`:

```
python3 cli.py density <workspace> [--json]
python3 cli.py clips <workspace> "<question>" [--json]
```

`clips` is deliberately separate from the existing `chat`. `chat` returns prose; `clips`
returns what to watch. Neither replaces the other.

### 3.4 Static demo — `docs/demo/`

- Precompute `density` for a fixed nutrition/fitness corpus and `clips` for ~8 fixed
  questions. Commit the JSON to `docs/demo/data/`.
- One `index.html` plus a small amount of vanilla JS: a question picker, the rendered
  clip list, and a YouTube `<iframe>` with `?start=` so the viewer watches the creator
  say it. No framework, no build step, no backend, no key.
- Served by GitHub Pages from `docs/`.

The demo is not a screenshot; it is the verification mechanism. A skeptic clicks a
timestamp and confirms the claim in five seconds, which converts critics into validators.

**Attribution and fair-use posture.** Each clip shows the channel name, the video title,
the publish date, and a link to the source video at the timestamp. Quotes are short and
verbatim, attributed, and drive traffic to the creator. Framing is informational —
never accusatory, never a ranking of creators. A takedown contact appears in the demo
footer. Committed demo JSON carries `generated_at` so readers know it is a dated snapshot.

### 3.5 Local mode, verified

`core/llm.py:12` already supports Ollama — "no key, no limits, no cost" — but it is
undocumented and unverified. **This is two of the four surviving gaps (§1: #2 sovereignty,
#3 no caps) and therefore the single most load-bearing section of this spec.** It ships in
phase 2, before the demo, because the positioning now rests on it. Making the claim
defensible:

1. Run the full pipeline end-to-end on Ollama: ingest → index → extract-claims →
   density → clips.
2. Retrieval is provider-independent (local embeddings + local reranker), so the existing
   `evals/evaluate.py` already covers it. **The answer gate is not covered.**
3. Add `evals/dataset_answergate_v1.json`: ~20 hand-labeled
   `(question, chunk_id, answers|mentions|unrelated)` rows drawn from the real corpus.
   Measure gate agreement against those labels under Gemini and under Ollama.
4. Publish **both** numbers in the README.

This turns "runs fully local" from aspiration into a measured claim, and it extends the
existing eval-harness habit to the new component. It also removes the API-key barrier —
the largest remaining onboarding blocker after Docker.

## 4. Open-source readiness

Shipped in v1, ordered by how hard each one blocks adoption:

1. **`LICENSE` (MIT).** Absent today. Without it the default is all-rights-reserved and
   no company may legally use the code — which makes stars from companies worthless.
   MIT over AGPL because the goal is adoption.
2. **Commit `docker-compose.yml`** (exists untracked). Must bundle the
   `bgutil-ytdlp-pot-provider` sidecar, ffmpeg, and the API into one command, and must be
   verified from a clean clone.
3. **Commit demo output** so the README works for someone who never installs anything.
4. **README rewrite**, in this order: tagline → demo link → the captionless-video example
   (gap #1) → a clips example → fully-local setup with both accuracy numbers → no-caps and
   scriptability → density as a secondary signal → honest limitations. Today's
   "What Makes This Different" sits at line 159; the hook belongs at the top, and the
   ordering must match the §1 gap ranking rather than the order things were built.
5. **CI** (GitHub Actions) running pytest over `rag/tests/` plus the new pure-function
   tests. Converts the differentiating logic from inline `--test` flags into checked code.
6. **GitHub metadata:** About description, topics, social preview image. All absent today,
   which makes the repo invisible to GitHub's own search.
7. **Rename to `clipgrep`**, pending an availability check on GitHub and PyPI. Chosen for
   verb-ability — "just clipgrep it" — over the current name, which describes nothing.

## 5. Risks

### 5.1 Estimated timestamps (highest risk)

`ingestion/chunker.py:55-71` estimates sentence times by word position, snapping to real
chapter anchors only when the creator supplied them. `is_estimated` records this honestly.
A link 20 seconds off is a bad experience for a product promising "jump to this moment."

Mitigations: bias every `watch_url` 3 seconds early (clamped at 0); use `is_estimated` as
a ranking tie-break; render a `~` marker on estimated times; state the limitation in the
README. No attempt to hide it.

### 5.2 Local-model quality on the gate

Small local models may classify answers/mentions worse than Gemini. Mitigated by
measuring it (§3.5) and publishing both numbers rather than asserting parity. If local
accuracy is materially worse, the README says so and recommends Gemini for the gate while
keeping extraction local.

### 5.3 Density misread as a quality score

Someone will screenshot "12% signal" as "88% garbage." Mitigated by the floor framing,
the name, whole-number rounding, and an explicit README paragraph. Accepted residual risk:
we cannot fully control how a number is quoted.

### 5.4 Scope

v1 is larger than a single feature. Mitigated by phasing so each phase ships
independently and is independently useful — see §7.

### 5.5 Demo corpus drift

Videos get deleted or edited; committed JSON becomes a snapshot of a corpus that no longer
matches. Mitigated by `generated_at` in every committed file and a dated note in the demo.

## 6. Testing

All new logic is designed so its hard parts are pure functions, testable without network,
living beside the existing `rag/tests/test_jobs.py` and `test_security.py`:

| Test | Why it matters |
|---|---|
| Interval union over overlapping chunks | Real bug risk — naive summation double-counts by design |
| Density arithmetic + floor framing + rounding | The headline number must be right |
| Answer-gate response parser | Malformed LLM output must fail closed, not crash |
| **Verbatim-substring validation** | The hallucination guard; must reject invented spans |
| Skip-report arithmetic | The "3h 51m saved" claim |
| `watch_url` formatting, 3s bias, clamp at 0 | Off-by-one on a short clip breaks the demo |
| Conflict-pair index validation | Invented indices must be discarded, not rendered |
| Gate accuracy vs. hand labels (Gemini + Ollama) | Makes the local-mode claim defensible |

Infrastructure failures must be distinguishable from real verdicts, following the existing
pattern in `claim_clusterer.py:53-108` where an LLM failure returns `errored=True` rather
than being silently counted as a genuine negative.

## 7. Phases

Each phase is independently shippable and independently useful.

| Phase | Contents | Depends on |
|---|---|---|
| **0** | LICENSE, docker-compose committed + verified, GitHub metadata, CI skeleton | nothing |
| **1** | `retrieval/clips.py` (answer gate), `cli.py clips`, `api.py POST /clips`, tests | nothing |
| **2** | **Local-mode verification**, `dataset_answergate_v1.json`, both accuracy numbers published | phase 1 |
| **3** | `knowledge/density.py`, `cli.py density`, tests | phase 1 conventions |
| **4** | `docs/demo/` static site, committed corpus JSON, GitHub Pages | phases 1, 3 |
| **5** | README rewrite, rename to `clipgrep` | phases 0-4 |

**Reordered after the §1 falsification.** Local-mode verification moved from phase 3 to
phase 2 because it carries two of the four surviving differentiators; density moved from
phase 1 to phase 3 because `SponsorBlock` already serves its strongest use case and it is
no longer the headline. The answer gate leads because both the demo and the v2 skill export
consume its output.

Phase 0 is independent of all engine work and should not wait on it. If scope must be cut,
the honest minimum that still lands a defensible position is **phases 0, 1, 2, 5** —
density and the static demo can follow.

## 8. New configuration

Added to `core/config.py`, which is the single place tunables live:

```python
CLIP_MAX_RETURNED = 5          # clips shown per question; also bounds the conflict call
CLIP_LINK_LEAD_SECONDS = 3     # start links slightly early; estimated timestamps drift
DENSITY_ROUND_TO_PERCENT = True
```

## 9. Decision record

| Decision | Rationale |
|---|---|
| Narrow to clips, not a knowledge platform | `Tencent/WeKnora` holds the generic position with ~29k stars and corporate backing |
| **Position on sovereignty + no caps + any video, NOT on unique capability** | The uniqueness claim was falsified (§1): NotebookLM does cross-source comparison, ingests YouTube, embeds a player, and cites exact transcript spans. `VoiceStudio` (~34.8k) and `open-seo` (~20.5k) both win without novel capability |
| **Captionless / same-day video is the sharpest demo** | The one thing NotebookLM provably cannot do; fails visibly there, works here |
| Local mode headlined, measured, and moved to phase 2 | Carries gaps #2 and #3; unlocks r/LocalLLaMA; measured against hand labels so the claim survives scrutiny |
| **Density demoted from headline to signal** | `SponsorBlock`'s crowdsourced highlight already serves popular videos better; density's real edge is the long tail with no crowd data |
| Static demo retained in v1 | The visibility gap is still the binding constraint; `gods-eye-view` earned ~41k stars in 30 days on a browser demo |
| Verbatim-substring validation on gate spans | Extends the existing hallucination-guard discipline to the new component |
| Verification framed as engineer credibility, not a consumer hook | Users cannot perceive an architectural guarantee; overselling it would invite the comparison we lose |
| Skill export deferred to v2 | The gate is what makes an exported skill trustworthy; exporting first ships the commodity version |
| Drift deferred to v3 | Novel and shareable, but appears in no user-reported pain |
| Density is a floor, never a quality score | Extraction recall is imperfect; overclaiming would burn the repo's main asset |
