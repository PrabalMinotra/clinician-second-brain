# Verification record — 24 October 2026

## Observed passing checks

- React TypeScript check: `npm run check`.
- Vite production build: `npm run build`, including standalone UI and federated manifest asset.
- Django system check: no issues.
- Django migration consistency: no changes detected.
- **34 backend tests passed** with isolated test database.
- Authenticated local browser: clinician sign-in, seeded history, completeness flags, three-document generation, paragraph review surface, citation controls and approval modal.
- Unapproved export is disabled in the UI; backend approval/export rejection cases exercised in tests.
- Actual native OCR exercised on `fixtures/synthetic-note.png`.
- Actual scanned-PDF OCR exercised on `fixtures/synthetic-scan.pdf`.
- TXT extraction exercised on `fixtures/synthetic-note.txt`.
- Synthetic fixture name, email and phone removed from the extracted text in all three modalities.
- Multipart file upload reaches the pending-review queue, verified with the Django test client.
- Source-date entry works through native browser `setValue` using an ISO date. Browser automation `fill` did not reliably set the native date control; this was an automation-path limitation, not a server validation bypass.
- Local HTTP readiness returned 200. Local app runs on loopback only.
- Default-viewport overview inspected visually; patient stage/date no longer wrap onto multiple lines. Screenshot retained as `docs/preview.png`.

## Important observed limitation

Native OCR read the fixture's `cT2 N1 M0` as `CT2 N1 MO` while reporting confidence 1.0. The build neither automatically corrects nor accepts that text. A clinician must verify every extraction, including identifiers and clinical tokens. Wording differences from confirmed stage text are flagged without medical restaging.

## Not verified or connected

- Automated browser file chooser did not reliably complete the intended synthetic-image upload smoke check; extraction itself was separately verified directly. No claim of a fully automated browser-upload test is made.
- Actual handwritten doctor-note accuracy or multilingual OCR; English printed fixture only. No medical OCR accuracy rate claimed.
- Mobile breakpoints have responsive styles but were not separately device-tested.
- Live CARE host/facility permissions, host token auth, encounter import or CP1.
- Claude, PubMed, guideline recency or semantic claim-support validation.
- Actual audio recording/transcription.
- Clinical validation, real PII handling, legal compliance certification, load testing or production security review.
- Reading-grade target <=6 or a measured 50% drafting-time reduction.

The local service uses the Django development server. Source text and drafts are encrypted; the local key resides beside the database outside source control. This is a hackathon setup, not institutional key management or a production deployment.

## Image-to-text and doctor-query extension

- 53 backend tests pass, including image-intake → privacy screening → pending exclusion → clinician review → source-cited query integration.
- TypeScript check and production build pass with the new Ask the record view.
- Native image and scanned-PDF OCR were exercised on synthetic fixtures, followed by retrieval from explicitly corrected/accepted text.
- Browser checks confirmed dated imaging excerpts and source controls, unrecorded allergies/medicines, and refusal of treatment advice.
- `POST /api/second_brain/cases/{id}/query/` accepts question and expected case revision. It enforces clinician role, ownership, CSRF and stale-revision rejection.
- Queries use field aliases and local lexical relevance, not a generative or semantic clinical reasoning model. Unrecognised questions may need rephrasing. Returned passages are literal excerpts.
- Query text and answers are not stored in audit records; only case revision, status, count and source IDs are recorded.
- Original-image previews are transient browser object URLs; original images are not retained by the server.
- Handwriting/multilingual accuracy remains unvalidated; clinician transcription/privacy review remains mandatory.
