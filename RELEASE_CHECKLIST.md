# v0.1.0 release checklist

## Completed

- [x] Standalone clean Git history created; private operational repository history not copied.
- [x] MIT licence added with Kelly McLellan as copyright holder.
- [x] Git commit identity sanitized to the maintainer's GitHub noreply identity.
- [x] Deployment-specific environment names/paths and write author removed from public defaults.
- [x] Protocol tests pass under local Python 3.
- [x] Compatibility broker fixture suite passes against disposable Trac 1.4.4/Python 2.7.18 and Trac 1.6/Python 3.9.2 fixtures.
- [x] Trac 1.6 adapter-to-broker Unix-socket integration test passes against a disposable copy of the upgraded staged environment.
- [x] Known private host/domain/path/key/personal-email marker scan passes.
- [x] Comprehensive human-readable and AI-compatible README added.
- [x] Repository `AGENTS.md` added with development, documentation, privacy and security rules.
- [x] Security policy, contribution/AI policy, changelog, provenance inventory and generic example configuration added.
- [x] GitHub Actions package/protocol-test matrix prepared.
- [x] Private GitHub repository created and clean history pushed.
- [x] Fresh SSH clone validated after history sanitization.
- [x] ChatGPT GitHub connector granted repository access.

## Before making the repository public

- [x] Confirm GitHub Actions succeeds on the current release candidate (Python 3.10-3.13 matrix).
- [x] Validate clean package installation/startup through GitHub Actions on supported Python versions; local host Python 3.9 is deliberately below the supported minimum.
- [x] Re-run full reachable-history privacy/provenance scan after final documentation changes.
- [ ] Confirm repository settings are appropriate: Issues as desired, private vulnerability reporting if available, and default-branch protection/rules reviewed.
- [x] Confirm GitHub recognizes the MIT licence.
- [x] Change package version from `0.1.0.dev0` to `0.1.0` after release-candidate CI acceptance.

## After making the repository public

- [ ] Verify public anonymous clone/read access and repeat privacy/content spot checks from the public view.
- [ ] Confirm public README rendering, licence detection, and Actions status.
- [ ] Tag `v0.1.0` only after the public checks pass.
- [ ] Publish GitHub Release `v0.1.0` with release notes/changelog summary.
