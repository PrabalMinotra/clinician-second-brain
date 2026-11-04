# Requirement traceability

| Requirement | Source | Implementation / observed boundary |
|---|---|---|
| No diagnosis, inferred stage or treatment advice | User; Developer Guide pp.1,6 | Templates copy confirmed input; no model or diagnostic image interpretation. Required diagnosis/plan cannot be inferred. |
| Three MVP documents | Developer Guide pp.1,5; submission deck p.4 | Referral, patient sheet, MDT note from one frozen snapshot. Teaching summary is outside this MVP. |
| Clinician-confirmed facts | Developer Guide pp.1,3 | Explicit fact confirmation, revision checks, snapshot per draft; intake never silently updates facts. |
| Multimodal intake | User; OHC email pp.1–2 | Pasted notes/transcripts, text PDFs, TXT/MD, photos via local OCR; scanned and mixed PDFs via macOS Vision/PDFKit. Actual audio transcription not connected. |
| Patient history for oncology | User | Timeline, categories, search, source drawer, pathology, imaging, medicines, allergies, comorbidities, prior treatment, performance status, recorded plan and follow-up. Unknowns explicit; history completeness not guaranteed. |
| PII protection | User; deck p.4; OHC email p.2 | Synthetic-only guard, local extraction, metadata stripping, conservative screening, mandatory manual privacy review, encryption, owner-scoped access and minimised audit metadata. Screening limitations disclosed. |
| Frozen facts, no fabricated citations | Developer Guide pp.3,6 | Exact fact/source copies. References point to immutable snapshot or accepted text. Unknown source IDs block approval. No external clinical support is claimed. |
| Sources and paragraph editing | Deck pp.3–4; guide p.4 | Source drawer, original/current comparison, accept/reject/edit, encrypted intermediate revision history. |
| Approval gate on backend | Guide pp.4,7 | All paragraphs reviewed; attestation; content hash; clinician role; exact current history revision; no unresolved missing placeholder in included text. |
| Edit invalidates approval | Guide pp.4,7 | Clears approver/time/hash and resets to in_review. Changes to confirmed facts or reviewed history invalidate old drafts. |
| Export approved exact version only | Guide pp.4,7 | Authenticated backend checks role, ownership, status, hash, history revision and pending source queue. Text export only; no send. |
| Source recency / external evidence | Deck pp.3–4; guide p.6 | Not connected. History dates are shown. No guideline-recency or PubMed-support claim is made. |
| Readability target ≤6 | Deck pp.5,7; guide p.6 | Approximate English proxy displayed; high grades flagged; grade 6 is not claimed achieved. Complex recorded facts stay unchanged. |
| CARE integration, zero core changes | OHC email; guide pp.1–2 | Installable Django plugin app, migration, URL module; React federated manifest. Actual CARE host/auth/encounter import CP1 not verified. Local fallback implemented. |
| Audit | Guide pp.4–5 | Access/source/draft/approval/export metadata, hashes and revisions. Clinical payloads and edit history encrypted separately. Not an immutable external audit sink. |
| Synthetic-only development | Guide pp.1,7; OHC email p.2 | Backend checks explicit boolean and synthetic case ownership. No real PHI allowance switch. Fixture dates labelled fictional. |

## Deliberate product decisions

- An oncology report is a document to transcribe and organise, not an image to diagnose.
- A planned treatment is not treated as completed treatment.
- “Not recorded” does not become “none”, “normal”, “negative” or “no known allergies”.
- An OCR confidence value is not a clinical certainty value. Exact strings and source review remain necessary.
- Historical stage wording can differ over time. Wording checks request clinician review; they do not medically reconcile or restage a case.
- Patient-history references are not evidence of guideline correctness. External medical claims are not added by the template engine.
- The sensitive workflow stays in the local Django process. A static hosted copy would not enforce its server approval/access controls, so it is not presented as the functioning product.

## Doctor queries from image-derived text

Image/PDF → local extraction → identifier screening → manual correction/privacy review → accepted history → local source-cited retrieval. Queries search confirmed case facts and accepted, privacy-reviewed sources only. Answers preserve source wording and dates, distinguish unknowns from negative findings, and never infer that planned treatment was completed. Requests for new diagnoses, stage inference, prognosis or treatment advice receive a boundary response. No external model or patient-data transmission is involved.
