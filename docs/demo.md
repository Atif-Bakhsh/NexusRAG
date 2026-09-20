# Three-minute local demonstration

Record this walkthrough after configuring the API key and reviewing the benchmark. Until
then, use retrieval-only CLI output and explicitly identify the Mermaid graph fixture.
No completed video or live answer benchmark is claimed in this repository.

- **0:00–0:30 — Question and corpus.** Explain the comparison and show the commit/hash manifest.
  “This tests whether graph evidence helps on one architecture corpus; no improvement is assumed.”
- **0:30–1:15 — Success.** In Compare, ask “How does Checkout reach Quote through Shipping?”
  Expand the graph path, exact source excerpts and pinned line links. Both systems can succeed.
- **1:15–1:50 — Limitation.** Ask whether a Kafka outage definitely fails every checkout. Explain
  that documentation cannot establish runtime consequences. A safe response must acknowledge this.
- **1:50–2:25 — Failure.** Show the development lookup question about Frontend login. The relevant
  row is in the services overview but can fall outside the eight selected chunks. Graph routing
  falls back to vector retrieval for this nonrelational question. Do not call a retrieval miss a
  generated hallucination: generation quality is measured separately.
- **2:25–3:00 — Measurements.** Open benchmark results. Describe complete-evidence counts,
  sample sizes, latency boundaries and API tokens/cost. Show one raw record and explain that
  manually assessed correctness, faithfulness and citation support are separate metrics.

Before publishing: remove secrets from the screen, review all forty labels and answer judgments,
record the frozen run configuration, publish the raw outputs with attribution, and tag the actual
release commit. A public repository destination and a finished video still need to be supplied.
