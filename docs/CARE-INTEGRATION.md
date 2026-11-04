# CARE integration

The original `second-brain` app remains the standalone local fallback at port 8000. A separate CARE sandbox now lives at `/Users/prabalminotra/Downloads/csb/care-sandbox`, with independent backend/frontend plugin repositories. It uses actual CARE services rather than an API mock.

## Implemented

- CARE staff JWT authentication using the host's validator; no separate plugin login.
- Federated `/second-brain` page, user navigation entry, and `EncounterActions` button.
- Explicit, read-only import of allowlisted synthetic encounter notes into the encrypted pending-source queue.
- Server checks of patient, encounter, and encounter-clinical-data access; permissions are rechecked whenever a linked case is accessed.
- Source note, patient, facility and encounter references, source modification time and import time retained as encrypted provenance.
- Independent clinician fact confirmation, source review, citation-based record questions, deterministic documents and exact-version approval/export.
- Repeated import returns the existing clinician-owned case without duplicating notes.
- All registration and service configuration are external to CARE core. No tracked core files are changed.

Import is limited by both a server UUID allowlist and the encounter's explicit synthetic marker. It does not send CARE content to Sarvam. Optional voice/text translation separately requires synthetic confirmation and external-processing consent. The supplied Sarvam key is server-only; provider credits are currently exhausted.

## Open

CARE: http://127.0.0.1:48057

Synthetic encounter import: http://127.0.0.1:48057/second-brain?encounter=94d3822c-8b71-472d-8414-19329177d001

Sandbox fixture login: `care-admin` / `Ohcn@123`. This user is assigned to the dedicated synthetic facility through CARE's normal facility-administrator assignment. No superuser bypass is added.

## Source and operations

Backend plugin: `care-sandbox/care/care_second_brain`

Frontend plugin: `care-sandbox/care_second_brain_fe`

The full runbook, saved ports, private runtime settings, logs and verification evidence are under `care-sandbox/.agent/`. See `.agent/README.md` and `.agent/VERIFICATION.md`. Plugin repositories have independent local Git roots and have not been published.

The sandbox runs in the dedicated `care-second-brain` Colima VM. Use only its `.agent/compose.sh` wrapper. The host frontend starts through `.agent/frontend.sh`; the remote starts with `npm run dev` in `care_second_brain_fe`. Preserve the private encryption key and database volumes.

## Remaining boundaries

This is a synthetic local development integration, not a hospital deployment. Patient portal access, CARE document write-back, refreshed imports of changed notes, institutional tenancy/key management and clinical validation remain outside the implementation. Per-clinician case ownership is retained in addition to CARE permissions; team-shared cases are not implemented. Image/scanned-PDF OCR in the container needs a separately installed OCR helper; typed notes and text PDFs work without one. The original macOS standalone app retains its local OCR helper.

A hospital connection requires administrator-approved deployment against its CARE version and an appropriate validation/privacy process. The plugin does not accept real patient imports merely because a client checks a synthetic checkbox.
