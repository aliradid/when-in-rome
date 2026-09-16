# Before and after

Same change, three repos, three correct messages.

## Repo A: lowercase, terse, no bodies

History: `fix typo`, `bump deps`, `handle empty input`, `drop python 3.8`

Agent draft:
```
feat: Add Retry Logic to HTTP Client

This commit implements comprehensive retry logic with exponential backoff
to ensure robust handling of transient network failures.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

Native:
```
retry http client on 5xx
```

## Repo B: Conventional Commits, short bodies

History: `feat(api): add pagination`, `fix(auth): expire tokens`, `chore: bump deps`

Native:
```
feat(http): retry on 5xx with backoff

Transient upstream errors were surfacing to users; three tries with
exponential backoff covers the cases we saw in the logs.
```

## Repo C: sentence case, period, prose bodies

History: `Add pagination to the API.`, `Fix token expiry.`, `Handle a null user.`

Native:
```
Retry HTTP requests on 5xx responses.

Upstream returns occasional 502s during deploys. Three attempts with
exponential backoff is enough to ride those out without masking real
outages.
```

## PR body, repo with plain merged PRs

Agent draft:
```
## Summary
- Implemented retry logic
- Added tests

## Test plan
- [ ] Unit tests pass
- [ ] Manual testing
```

Native (after reading two merged PRs in the repo):
```
Retries 5xx responses three times with backoff. Tested against the staging
gateway during a deploy; the 502s we were seeing no longer reach the client.
```
