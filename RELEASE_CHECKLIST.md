# v0.1.0 release checklist

## Completed before GitHub repository creation
- [x] Standalone clean Git history created; private operational repository history not copied.
- [x] MIT licence added.
- [x] Deployment-specific environment names/paths and write author removed from public defaults.
- [x] Protocol tests pass under local Python 3.
- [x] Legacy broker fixture suite passes against disposable Trac fixture.
- [x] Known private host/domain/path/key marker scan passes.
- [x] README, security policy, contribution/AI policy, changelog, provenance inventory and example configuration added.
- [x] GitHub Actions protocol-test matrix prepared.

## Requires repository owner / GitHub repository
- [ ] Create empty public GitHub repository (do not initialise it with README/LICENSE/gitignore).
- [ ] Provide the repository `owner/name` or SSH URL so this prepared clean history can be pushed.
- [ ] Enable Issues and private vulnerability reporting if available.
- [ ] Confirm GitHub detects the MIT licence.
- [ ] Review/default-branch protection settings after first push.
- [ ] Run GitHub Actions and resolve any platform/version failures.
- [ ] Validate a fresh clone and disposable Trac workflow from the public repository.
- [ ] Tag/publish v0.1.0 only after those checks pass.
