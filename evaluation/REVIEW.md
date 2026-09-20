# Human review and frozen evaluation

All 40 labels are currently `source_checked_by_agent`, **not human-reviewed**. The source
spans were checked against the frozen Markdown. The CLI refuses a release benchmark until
reviewed, unless `--allow-unreviewed` explicitly marks the run diagnostic.

1. Read each question, gold answer, required relationships and every alternative evidence set.
2. Follow the source lines in `corpus/docs/`; verify meaning as well as exact quote matching.
3. Fix labels that are incomplete, ambiguous or too generous. For question 02, the overview
   says .NET; decide whether the C# code examples should be added as a separate language label.
4. Keep paraphrases/equivalent routes within the same split. Do not tune on the test questions.
5. Set `review_status` to `human_reviewed` and `reviewer` to the actual reviewer's name.
6. Run `nexusrag validate`, freeze the settings and record the repository commit before testing.
7. Review extracted assertions as well: a matching quote does not establish the stated edge.
8. Run the held-out comparison. Read both answer and retrieved context when filling judgments.

The 16 development questions and 24 held-out questions are in `questions.jsonl`. Only the
development split is used for the supplied provisional retrieval diagnostic. The test split
has not been run during implementation. Source-checking gold labels is not test-set tuning.

Each benchmark exports `judgments.csv`. Enter `correct` as 0 or 1 against the gold rubric;
count factual claims, claims supported by supplied evidence, cited claims, cited claims
supported by their citations, and factual claims with supporting citations. A single claim
may cite several chunks and still counts once. A pointer can be valid while its support is
wrong. Nonfactual abstention language contributes zero factual claims; any factual claim in
limitations still counts. Mark a failure's earliest causal stage and leave explanatory notes.

`nexusrag score RUN_DIRECTORY` requires complete judgments and named reviewers. It computes
ratios with numerator/denominator, reports zero-denominator metrics as null and separates
correct abstentions from unnecessary abstentions. Run `score` only after manually checking
all outputs. No automated LLM judge is used.
