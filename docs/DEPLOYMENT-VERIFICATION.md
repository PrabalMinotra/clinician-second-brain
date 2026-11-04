# Deployment verification — 3 November 2026

- Standalone backend: 68 tests passed.
- Standalone TypeScript check and production build passed.
- CARE plugin TypeScript/production build passed.
- CARE integration: 12 tests passed in the dedicated VM, separate test database. Existing test_care database was recreated by Django's test runner; application database was not reset.
- Both CARE core repositories retain clean tracked and staged diffs.
- Linux container build passed (tested on local ARM64 VM; hosting will build for its target architecture).
- Isolated container smoke check passed: seeded clinician authentication, frontend response, one synthetic case, image OCR and scanned-PDF OCR using Tesseract/Poppler.
- A second container started with the same named volume: migrations already applied, existing demo preserved, Gunicorn running, HTTP 200 at http://localhost:18000.
- Local preview credentials: `.runtime/submission-demo-login.txt`, permission 0600. No credentials were printed in logs or added to deployment source.

No public deployment, hosting account, payment, source publication, fresh-browser walkthrough or public HTTPS verification has been completed. Render Blueprint is prepared but not executed. Hosted secrets and actual hostname still need to be supplied. The deployment package runs the standalone app; full CARE hosting remains separate.
