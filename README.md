# The Clinician's Second Brain

A working, local React + Django hackathon application for **oncology history and administrative documentation**. Synthetic data only. It does not diagnose, infer stages, interpret diagnostic images, recommend treatment, estimate prognosis, or issue clinical decisions.

## Open the application

Run from this directory:

```bash
bash scripts/setup.sh
bash scripts/start.sh
```

Open **http://localhost:8000**. Your random local demo login is in `.runtime/demo-login.txt` (owner-read/write only). The seeded user is `clinician`. Setup preserves existing data. Requires Python 3.11+, Node 20+, and npm. On macOS, Command Line Tools are needed to compile the on-device Vision OCR helper. On other hosts, install Tesseract for individual images; scanned-PDF OCR currently uses the macOS helper.

The application has already been installed and built in this checkout. To restart it, only `bash scripts/start.sh` is needed. The development server binds to loopback, not the LAN. This is the guide's local fallback, not a deployed CARE installation.

## Working features

- Clinician login, expiring HttpOnly sessions, CSRF enforcement, role checks, per-owner case access and failed-login throttling.
- Synthetic cases and clinician-confirmed case facts, with optimistic revision checks.
- Longitudinal history organised by source date and category, search, source drawer and explicit unknown fields.
- Pasted notes and dictation transcripts; TXT/Markdown; PDF text extraction; PNG/JPEG/WebP OCR; scanned/mixed PDF OCR on macOS. Optional Sarvam audio transcription and English speech translation are connected for short synthetic voice notes.
- Local PDF/image processing. Image re-encoding strips metadata. Original uploads are discarded after extraction. Screened text is encrypted and quarantined until transcription/privacy review.
- Conservative direct-identifier screening for labelled names, addresses, dates of birth, emails, phone numbers and common IDs. **Screening is not validated anonymisation.** Names in prose, handwriting errors and indirect identifiers may be missed. Review is mandatory; only synthetic data is permitted.
- **Ask the record:** doctor questions retrieve exact excerpts from confirmed case facts and accepted, privacy-reviewed sources, including OCR-derived notes. Responses show dates and clickable citations, report missing information, and decline diagnostic or treatment-advice requests. No external LLM is used. Questions and answers are not persisted; access metadata is audited.
- Temporary side-by-side original-image preview during new OCR review; it stays in browser memory and is revoked when review closes.
- Three document types generated from the **same frozen clinician-confirmed case snapshot**: referral letter, patient information sheet and tumour-board note. Accepted history is copied exactly with source references.
- Paragraph acceptance/rejection, editing with original/current comparison, source drawers, encrypted revision history, and an approximate English readability indicator.
- Backend-enforced approval bound to SHA-256 of the complete draft payload, clinician identity and timestamp. Edits reset approval; accepted/rejected history changes invalidate existing drafts. Pending new uploads block approval/export until reviewed.
- Export of the approved exact version as text, with approval metadata, hash and source register. No auto-send.
- Server-side activity history without clinical text in audit metadata. Case facts, source text, snapshots and draft revisions are encrypted at rest using Fernet.

## Demonstrate the product

1. Sign in and open `SYN-ONC-001`. The supplied oral-cancer example is preloaded. The event dates are **fictional**; medications, allergies, treatment history and performance status remain explicitly not recorded.
2. Open Patient history. Search and inspect a source. Expand completeness checks to see which details still need clinician confirmation.
3. Add a record. Upload `fixtures/synthetic-note.png`, `fixtures/synthetic-scan.pdf`, or `fixtures/synthetic-note.txt`. These contain deliberately fictional identifiers to exercise screening. Explicitly confirm synthetic input.
4. Inspect the extraction. **Vision OCR can render `M0` as `MO` with high confidence**. Correct the stage text against the fixture. Do not treat confidence as a clinical accuracy score. Review the date and all remaining identifiers, then accept the source.
5. Review the confirmed facts independently. Accepting a source does not silently rewrite the diagnosis, stage or MDT plan. Wording differences are surfaced for comparison; different stages over time are not reconciled automatically.
6. Open Document studio and create the three drafts. Open each source link and review each paragraph. Reject irrelevant text; edit and accept as needed. The patient sheet may exceed grade 6 because complex clinician facts and history are preserved verbatim; the indicator reports that limitation.
7. Open **Ask the record** and try “What imaging is documented?”, “What treatment has the patient received?”, or “Are allergies recorded?”. Inspect source citations. Unreviewed uploads are excluded. A recorded plan is not presented as completed treatment. “Should we prescribe cisplatin?” receives a scope-boundary response.
8. Try approving while paragraphs remain pending: the backend rejects it. After all paragraphs are accepted/rejected, attest and approve. Export the text.
9. Edit an approved paragraph: approval clears and export becomes blocked. A changed case/history revision requires fresh drafts.
10. Open Activity log to inspect actions, IDs, revision numbers and approval hashes.

## Checks

```bash
(cd frontend && npm run check && npm run build)
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations --check --dry-run
(cd backend && ../.venv/bin/python -m pytest -q)
```

Tests cover access isolation, roles, CSRF, synthetic guards, identifier screening, encryption, paragraph review, unknown source IDs, missing facts, stale edits, changed history, hash tampering and export gating. The unit suite uses an isolated test database. Native OCR needs OS-level execution permissions; it was separately exercised on the included image and scanned-PDF fixtures. Known visual QA and integration limits are recorded in `docs/VERIFICATION.md`.

## Architecture

```text
React / Vite (standalone UI + federated ./manifest)
  │ same-origin session + CSRF
  ▼
/api/second_brain/ (standalone Django plugin app)
  ├─ role + object access + synthetic guard
  ├─ local extraction → identifier screening → pending source
  ├─ clinician review → immutable accepted history
  ├─ manually confirmed facts → frozen snapshot → deterministic drafts
  └─ paragraph review → approval hash → exact-version text export
       │
       ▼
SQLite (local fallback): encrypted payloads + audit metadata
```

SQLite is used for the self-contained fallback; Django models can use a host PostgreSQL database. The Python package is installable (`pip install -e .`) and frontend build exposes a federation manifest. No CARE core files were edited. See `docs/CARE-INTEGRATION.md` for the deliberate integration boundary.

## Current boundaries

This is a **tested hackathon prototype, not a clinically validated system**. CARE encounter import, CARE facility-scoped permission mapping, host token authentication, Claude generation, live PubMed retrieval, semantic guideline support checks, and microphone capture are not connected. Audio-file transcription is available through Sarvam. The UI discloses these boundaries. Core features need no API key. Optional Sarvam voice and text translation send explicitly confirmed synthetic input externally.

Templates deliberately copy supplied facts. Source links identify frozen case facts and reviewed source text; they are **not claims of external guideline support**. The English reading-grade proxy is not validated, and the grade-6 target is not guaranteed. Unknown fields are never interpreted as normal findings, absence of disease, or no known allergies.

Local encryption keys reside in `.runtime/` beside the database, outside source control. This protects against casual database inspection, not a compromised local account or lost key. There is no key rotation/KMS, institutional tenancy, secure backup policy, record retention/deletion workflow, immutable external audit sink or production HTTPS configuration. Do not put real patient data in this application. A clinical deployment requires appropriate validation and security/privacy review. Original-image retention for authorised clinical review must be designed inside the institutional EMR; it is intentionally absent here.

## Source requirements

All 17 pages of the three provided PDFs were read. The implementation prioritises the Developer Guide's three-document MVP over the submission deck's four-document vision. The OHC email recommends synthetic data and a focused CARE workflow.

- `../Health-a-thon Clinicians Second Brain.pdf` (7 pages): product vision and oral-cancer example.
- `../Second Brain Developer Guide.pdf` (8 pages): React/Django plugin shape, frozen facts, evidence boundaries and approval state machine.
- `../email about OHC.pdf` (2 pages): CARE extension opportunity, examples and synthetic-data recommendation.
- User extension: multimodal records, patient privacy, longitudinal oncology context, and no diagnostic output.

Detailed requirement mapping: `docs/REQUIREMENTS.md`. Current official sources: [CARE plugin system](https://docs.ohc.network/contributing/plugins/), [CARE scaffold](https://github.com/ohcnetwork/care_scaffold), [CARE AI Vision](https://github.com/ohcnetwork/care_ai_vision_fe), and [CARE Filly](https://github.com/ohcnetwork/care_filly).

## Sarvam multilingual intake

In **Add a record**, choose **Sarvam voice note** to upload WAV, MP3, M4A, OGG, FLAC or WebM (under 30 seconds, up to 10 MB). Choose an original-language transcript or English translation. For pasted notes, enable **Translate note to English with Sarvam**, select the source language, and keep input under 2,000 characters. Both require synthetic-data confirmation and explicit external-processing consent. Results enter the encrypted pending-source queue and require clinician review; they never update confirmed facts automatically. The original screened text is shown alongside translated notes.

The backend uses `saaras:v4` for speech and `sarvam-translate:v1` for text. Authentication stays server-side. Set `SARVAM_API_KEY` in the server environment or store it in `.runtime/sarvam-key` with permissions `0600`. Restart the server after changing credentials. The supplied key is installed in that private runtime file; it is not embedded in the frontend. Translation input is screened before sending; raw audio cannot be screened before sending. Original audio is not retained by this app. Provider retention is governed by Sarvam's policies.

Speech synthesis, document intelligence, document translation and chat are additional Sarvam capabilities, but are not enabled in this integration. Local OCR, deterministic drafting and citation-based record queries remain the default workflows. Translation and transcription may alter clinical terms or numbers and must be checked against the source.

Official references: [speech transcription](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe), [text translation](https://docs.sarvam.ai/api-reference/text/translate-text), [capabilities](https://docs.sarvam.ai/api/getting-started/welcome).

## Local CARE sandbox integration

A separate integration workspace is available at `../care-sandbox`. It runs actual CARE services, loads Second Brain as a federated app and supports authorised synthetic encounter-note import. The standalone app described above remains separate. See [the CARE integration runbook](docs/CARE-INTEGRATION.md) for URLs, source paths, checks and remaining boundaries.

## Hosted submission

Container and Render Blueprint configuration are available. See [deployment and submission instructions](docs/DEPLOYMENT.md). Public deployment is pending; the Blueprint runs the standalone MVP, not the CARE host.

### Case readiness and AI Evidence Reviewer

- **Case readiness** shows confirmed, missing and review-needed fields for the selected document. It compares explicitly labeled entries across same-day sources and compares the current record with the last approved draft.
- **My review queue** lets a case owner assign a read-only review of a specific revision to another clinician. The reviewer can mark it reviewed or request changes. A newer case revision invalidates the assignment. To provision a second account on a synthetic demo instance, set a distinct `SECOND_BRAIN_REVIEWER_PASSWORD` before startup. The seeded username is `demo-reviewer`. Keep the owner and reviewer passwords separate.
- **Reusable templates** let a clinician choose required fields and draft across their own cases. Required sections still need review and acceptance before approval.
- **AI Evidence Reviewer** uses a pinned [DeBERTa NLI model](https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall) to classify three pairs of bundled fictional excerpts. The hosted app serves the model outputs generated offline. It does not run inference on demand or take user input. Raw records, uploads and CARE data are excluded from this model path. The displayed review questions are authored prompts, and the model cannot edit case facts or approve documents.

To reproduce the evidence results, use Python 3.12 with `onnxruntime==1.23.2` and `tokenizers==0.22.1`. Download `config.json`, `tokenizer.json`, and the platform-appropriate quantized ONNX weights from model revision `a150876415327c80daeff35ca6f68f5ed8cf5c24`. Rename the weights `model.onnx` in that directory and run `python scripts/build_evidence_review.py /path/to/model-directory`. The checked-in results were generated with `onnx/model_qint8_arm64.onnx`. The three examples demonstrate the feature and do not measure model accuracy.
