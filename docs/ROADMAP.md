# Development roadmap

## MVP status (2026-10-24)

- [x] Desktop GUI (PySide6) and cancellation
- [x] Validate public uploader URLs (`uu`, `ux`, `uN` hosts)
- [x] Traverse public listing pagination and deduplicate file IDs
- [x] Sequential download via normal Edge button interaction
- [x] Local JSON manifest, SHA-256 verification, safe filenames
- [x] No overwrite of existing files
- [x] Unit tests covering URL handling, pagination and manifests
- [x] GitHub Actions unit tests + manually triggered unsigned Windows build
- [ ] Test with explicit permission on real public uploader.jp pages
- [ ] Verify all download button variations (headless Edge)
- [ ] Verify paginated uploader with 30+ files and empty uploader
- [ ] Verify interruption/retry and 403/429/503 handling on Windows
- [ ] Verify downloaded file bytes/hash against manually acquired reference
- [ ] Confirm site rules for automated downloading; contact operator if uncertain
- [ ] Select a license and publish an initial release (no auto-release before E2E)

## Known limitations

- Password-protected uploads and CAPTCHAs are not supported.
- A failed download is retried once unless access restrictions are detected.
- All pages are scanned again at the start of a resumed run.
- Saved metadata includes file URL and name, SHA-256 and local byte count, but not uploader comments/date.
- No EXE signature; executable must be tested and signed if distributed widely.
- Unit tests do not prove functionality against the live service.

## Suggested issue backlog

1. Site fixture-based browser tests for public listing + detail pages.
2. More reliable interruption with bounded retry on transient network errors.
3. Listing metadata archival, CSV export and preview selection.
4. Windows test for build artifact and browser availability.
5. Japanese release notes and reproducible checksum for signed binary.
