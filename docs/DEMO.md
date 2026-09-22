# Three-minute portfolio demo

The free demo is available now. A generated-answer recording must wait for the final live
experiment. Clearly identify the active graph source and label-review status.

Before recording, start Docker Desktop and run:

```sh
make up
make ingest-fixture
make preflight
```

If the model cache is empty, run make download-model before ingestion. Open Streamlit at
http://127.0.0.1:58501 and keep .env and secrets out of the recording.

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:25 | README, manifest and architecture | “I built a controlled retrieval experiment over 12 pinned architecture documents, comparing two evidence-retrieval modes.” |
| 0:25–0:55 | Vector CLI query below | “The vector baseline finds semantically related source passages using normalized 384-dimensional BGE embeddings.” |
| 0:55–1:35 | Graph-vector query below; load its query ID in Evidence and execution | Expand the path and original passages. “Every hop has exact source provenance; at most three hops and two selected paths.” |
| 1:35–2:00 | Run the same relationship question in both CLI modes | Compare independently retrieved evidence. During the later live demo, use UI Compare to show two independently generated answers and clickable citations. |
| 2:00–2:30 | Benchmark results and docs/report.md | “Both modes found complete labeled evidence for 11 of 12 answerable development questions. Four other questions test ambiguity or unsupported conclusions. This used a fixture graph and draft labels.” |
| 2:30–3:00 | Frontend-login miss and known limitations | “One lookup misses its supporting overview row. Graph evidence is not always better; a citation pointer also does not prove a claim. Live extraction and human-scored held-out answers are the next experiment.” |

Free CLI queries:

```sh
make ask MODE=vector QUESTION='What is Checkout responsible for?'
make ask MODE=graph_vector QUESTION='How does Checkout reach Quote through Shipping?'
make ask MODE=vector QUESTION='How does Checkout reach Quote through Shipping?'
make ask MODE=vector QUESTION='Does the documented Frontend require login?'
```

Use the returned query IDs in the UI to expand source passages, graph paths, timings, costs
and structured traces. Retrieval-only records have no generated answer and zero provider calls.

After completing FINAL-EXPERIMENT.md, show UI Ask/Compare with:
“What is Checkout responsible for?” and “How does Checkout reach Quote through Shipping?”
Expand clickable answer citations and each graph edge's excerpt. Then ask whether a Kafka
outage definitely fails every checkout, explaining that documentation cannot prove runtime
outage propagation. Report the actual response, including failures; do not script a fabricated
success. Replace historical diagnostic claims only with the final measured results.

The repository is already public at https://github.com/Atif-Bakhsh/NexusRAG.
A recorded video and a measured release tag remain pending.
