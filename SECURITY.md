# Security policy

## Supported versions

Security fixes go into the latest release.

## Reporting a vulnerability

Please do not open a public issue for security problems. Report them privately through GitHub's
[private vulnerability reporting](../../security/advisories/new) ("Report a vulnerability" on the Security tab).

Include what you found, how to reproduce it, and the version or commit. You get an answer within a week. Once a
fix is released, the advisory is published with credit, unless you prefer otherwise.

## Deployment notes

- Serve Appfit over HTTPS and set `COOKIE_SECURE=true`; the Helm chart does this for a TLS ingress.
- `JWT_SECRET` must be random and at least 32 characters. The API refuses to start with the example values.
- Change the bootstrap admin password after the first login.
- The API expects same-origin requests. Cookie-authenticated writes must send `X-Requested-With`.
