# Technology Decisions, Pros, Cons, and Upgrade Paths

This document explains why the POC uses each model and library, what tradeoffs we accept for the demo, and what we can choose later to improve accuracy, speed, or production readiness.

## Decision Principles

- The demo path must be free to run locally.
- Audio, transcript, and customer data should stay on the reviewer's machine during the POC.
- Every AI judgment must be validated against saved transcript turns.
- Accuracy-sensitive parts should be replaceable behind provider interfaces.
- The manager UI should explain system readiness and evidence, not expose technical complexity.

## Current POC Choices

| Area | Current choice | Why we chose it | Pros | Cons | Better option when needed |
| --- | --- | --- | --- | --- | --- |
| Speech-to-text | `faster-whisper` with `base.en` | Free local transcription with good Python support and simple deployment path. | No paid API, runs locally, faster than original Whisper on many machines, supports timestamps, easy to test. | `base.en` can mis-hear names, accents, noisy calls, overlapping speech, or domain terms. First model download takes time. | Use `small.en`, `medium.en`, `large-v3`, or `distil-large-v3` for better accuracy. For production, evaluate managed STT such as Azure Speech, AWS Transcribe, Google STT, Deepgram, or Whisper API if paid services are allowed. |
| Local LLM analysis | Ollama `qwen2.5:7b` | Free local structured reasoning for intent, mood, resolution, manager brief, and recommendations. | No per-call cost, transcript stays local, easy model switching, strong enough for POC structured summaries. | Slower than cloud models on some laptops, quality depends on local hardware, JSON can still need validation, model download is large. | Try `llama3.1:8b`, `mistral`, `qwen2.5:14b`, or a quantized larger model. For paid production accuracy, compare against GPT-4.1/4o, Claude, Gemini, or domain-tuned models. |
| Evidence validation | Deterministic validation layer | Keeps LLM claims grounded in immutable transcript turns. | Prevents invented quotes and timestamps, makes "Show Me Why" defensible, gives auditors a clear chain of evidence. | It cannot fix a bad transcript; it can only reject unsupported AI output. It may reject useful paraphrases if evidence is not exact enough. | Add confidence scoring, human review workflow, transcript correction, stricter schemas, and evaluation sets with expected labels. |
| Audio tooling | FFmpeg and FFprobe | Reliable local audio conversion and channel handling. | Mature, cross-platform, supports many formats, good for stereo channel extraction. | Requires local installation and PATH setup. Some codecs may still fail. | Containerize FFmpeg for consistent reviewer setup, or use managed media processing in production. |
| API framework | FastAPI | Lightweight Python API with typed request/response models. | Fast to build, OpenAPI docs, strong Pydantic validation, easy testing. | Python process management needs care in production; async/sync boundaries must stay clear. | Keep FastAPI for production if team is comfortable, or split workers into Celery/RQ/Temporal if processing volume grows. |
| Web app | React, TypeScript, Vite | Quick, typed manager UI development. | Fast local dev, strong component testing, good ecosystem, easy dashboard interactions. | Requires Node setup; UI complexity can grow quickly. | Keep React for production; add a design system only after interaction patterns settle. |
| Database | SQLite | Simple persistent store for local POC. | Free, zero server setup, easy backup/reset, enough for demo data. | Not ideal for concurrent production traffic or multi-user hosting. | Move to PostgreSQL when hosted multi-user access, stronger concurrency, or analytics queries are required. |
| Background processing | Local single-worker queue | Non-blocking processing without adding infrastructure. | Easy to understand, deterministic local behavior, supports queued calls for demo. | One process can be a bottleneck; worker restart/recovery is simpler than production queue systems. | Use Redis Queue, Celery, Dramatiq, Temporal, or cloud queues for production reliability and scale. |
| Health visibility | `/api/health` plus bottom status bar | Reviewers need to know if API, DB, worker, STT, and LLM are ready. | Clear demo readiness, immediate setup guidance, avoids hidden failures. | It checks readiness, not transcription or analysis accuracy. | Add deep health checks that run a tiny fixture audio through STT and analysis on demand. |

## Model Accuracy Strategy

The POC should not claim "100% accurate AI." Instead, it should claim a defensible process:

1. Transcribe audio locally.
2. Save immutable transcript turns with timestamps.
3. Ask the local LLM for structured analysis.
4. Reject any AI claim that does not point to saved transcript evidence.
5. Show the manager exactly why a call was flagged.
6. Measure accuracy using sample calls and expected labels.

This is stronger than a simple `audio -> STT -> LLM -> dashboard` flow because unsupported LLM output cannot silently become a manager-facing decision.

## Recommended Evaluation Path

| Evaluation | What it proves | POC approach |
| --- | --- | --- |
| STT word accuracy | Whether transcript text matches the recording. | Compare model transcript against provided or manually corrected sample transcripts using WER. |
| Speaker accuracy | Whether agent/customer attribution is correct. | Validate stereo channel mapping and sample known calls. |
| Intent accuracy | Whether the LLM understood what the customer wanted. | Compare structured intent against expected labels for a sample set. |
| Mood accuracy | Whether the mood label and shift point are reasonable. | Compare against reviewer labels and require evidence-backed mood shifts. |
| Resolution accuracy | Whether the call was actually resolved. | Track false resolution cases separately from simple positive wording. |
| Manager priority accuracy | Whether the ranked list matches human judgment. | Use a small gold set and tune score weights. |

## What To Choose For Better Results

If transcription is wrong:

- Move from `base.en` to `small.en` or `medium.en`.
- Use `large-v3` or `distil-large-v3` for higher accuracy if the laptop can handle it.
- Add domain vocabulary correction for bank terms, account terms, names, and locations.
- Use paid STT only outside the free demo path if accuracy is more important than zero cost.

If analysis is wrong:

- Try a stronger local Ollama model such as `qwen2.5:14b` or a stronger Llama-family model.
- Use stricter prompts and schemas with examples of positive, neutral, negative, unresolved, and false-resolution calls.
- Keep deterministic validation on even with stronger models.
- Compare local LLM output against a paid model offline for evaluation only, if allowed.

If the app is slow:

- Use a smaller STT model for demo speed and mark it as a demo tradeoff.
- Queue batch processing and show progress instead of blocking the user.
- Cache completed transcript and analysis results in SQLite.
- Move heavy processing to a separate worker process.

If reviewers ask about production:

- Keep the same interfaces but replace SQLite with PostgreSQL.
- Replace local single-worker queue with a durable queue.
- Add authentication, audit logs, retention rules, redaction, and deployment monitoring.
- Run regular accuracy evaluation using labeled samples.

## Current Recommendation

For this hackathon POC, keep the default stack:

- `faster-whisper base.en` for free local STT
- Ollama `qwen2.5:7b` for free local analysis
- deterministic evidence validation for trust
- SQLite for persistent local data
- React/FastAPI for fast vertical delivery

For the final demo, prepare one stronger-model option as a documented upgrade path, but do not make the default flow depend on paid services.
