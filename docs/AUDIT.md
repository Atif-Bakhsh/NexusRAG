# Readiness audit

Scope: preserve the existing local RAG architecture; make no paid API calls.

| Requirement / finding | Decision | Verification |
| --- | --- | --- |
| Understand existing implementation | Inspect application, corpus, labels, results, migrations, tests, packaging and GitHub CI before edits | Architecture and completion report |
| Missing operational documentation | Document existing flows and exact free-first commands | Runbook commands and smoke test |
| No comprehensive preflight | Add read-only checks with actionable, sanitized failures | Unit and local infrastructure checks |
| Settings can exceed documented limits | Validate numeric caps and positive cost rates | Configuration tests |
| Graph readiness trusts a marker | Compare stored assertion count to actual relationships | Integration test with a removed relationship |
| Benchmark may switch corpus mid-run | Refuse a changed active corpus and save labels with run | Regression test |
| Index identity omits manifest content | Include manifest digest in new index identities | Changed-manifest regression test |
| Imported assertion IDs are trusted | Recompute and verify canonical identity | Artifact validation tests |
| CI builds images without exercising them | Add free fixture ingestion and HTTP/CLI smoke checks | Local Docker smoke and GitHub Actions |
| Public presentation contains stale claims | Free-first README, diagnostic caveats, resume evidence and release checklist | Documentation review and public repository audit |

Human label review, semantic extraction review, live answer quality, a demo recording,
and a measured release remain outside this unpaid implementation pass.
