# Changelog

All notable changes to the AI Email Triage & WhatsApp Notification Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-07-20

### Added
- Multi-stage production `Dockerfile` with slim Python runtimes and Tesseract OCR capabilities.
- Local `docker-compose.yml` service orchestration configurations with persistent volume mapping.
- Automated GitHub Actions CI/CD pipeline configuration at `.github/workflows/ci.yml`.
- Local health check diagnostic helper at `scripts/health_check.py`.
- Non-locking database online backup utility at `scripts/backup_db.py` utilizing the SQLite `backup()` engine.
- Production restoration recovery script at `scripts/restore_db.py` supporting safety archives.
- Custom domain architecture exceptions (`RepositoryError`, `DatabaseError`, and `SchedulerError`).
- Comprehensive testing suites covering validation scopes and pushing pytest statement coverage metrics to 95%.

### Changed
- Configured modular prefixes to empty strings in settings to natively bind case-insensitive `.env` configurations.
- Re-wired application initialization sequencing in `main.py` to use IoC DI container and call StartupValidator.
- Adjusted Google Gemini execution handlers to use standard installed `google-generativeai` package.
