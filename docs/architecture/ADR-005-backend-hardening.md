# ADR-005: Transaction authorization and continuous verification

Date: 2026-09-26. Status: accepted.

## Scope

The user authorized the next backend hardening and CI batch. No frontend, deployment, external integrations or real review decisions are included.

## Decisions

- Keep the existing request-entry authentication check, and additionally revalidate the session inside every authenticated write transaction after SQLite obtains its write lock. A revocation committed before lock acquisition must block that write. A write which acquired its lock before a concurrent revocation can finish first; this is the defined serialization order, not retroactive cancellation. Reads remain request-entry authenticated.
- A per-connection transaction guard keeps this enforcement shared by Brain and account operations without nesting transactions or storing raw tokens in the database. Guard failure rolls back and releases the lock. Trusted CLI connections have no guard.
- Validate decoded JSON recursively (using an iterative walk) for overflow to infinity and unpaired Unicode surrogates, including object keys. The existing size limit, duplicate-key check and constant rejection remain in place.
- Add deterministic regression coverage for revocation between authentication and write, simultaneous expected-revision updates, and malformed JSON. Keep synthetic review data in temporary fixture databases.
- Add a read-only GitHub Actions workflow for Windows/Linux and Python 3.11/3.13, installing the lockfile, validating schemas, running the suite and exercising the synthetic demo. No secrets, deployment steps, database uploads or privileged pull-request triggers. Disable persisted checkout credentials and bound job time.

## Limitations

The workflow is checked in, not yet executed on GitHub. Actions are pinned to immutable commit IDs verified with upstream `git ls-remote` (checkout v7 and setup-python v6). Local checks cannot establish Linux or Python 3.11 compatibility. This batch is targeted hardening, not an independent penetration test or production certification.

## References

- [GitHub Python CI guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [Checkout action](https://github.com/actions/checkout)
- [Setup Python action](https://github.com/actions/setup-python)
