import argparse
import json
import sys
from pathlib import Path

from nexusrag.config import Settings


def main():
    parser = argparse.ArgumentParser(prog="nexusrag")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate frozen corpus and draft evaluation labels")
    commands.add_parser("download-model", help="Download pinned BGE weights and tokenizers")
    preflight = commands.add_parser(
        "preflight", help="Read-only checks; no downloads or paid calls"
    )
    preflight.add_argument("--require-ready", action="store_true")
    preflight.add_argument("--require-generation", action="store_true")
    ingestion = commands.add_parser("ingest", help="Sequential, idempotent ingestion")
    ingestion.add_argument(
        "--assertions", type=Path, help="Reuse exported assertions without LLM calls"
    )
    ingestion.add_argument(
        "--fixture-graph",
        action="store_true",
        help="Diagnostic Mermaid fixture; NOT LLM extraction",
    )
    ask = commands.add_parser("ask", help="Query and print the full structured record")
    ask.add_argument("question")
    ask.add_argument("--mode", choices=["vector", "graph_vector"], default="vector")
    ask.add_argument("--retrieval-only", action="store_true")
    evaluation = commands.add_parser(
        "evaluate", help="Frozen paired comparison; generation is opt-in"
    )
    evaluation.add_argument("--split", choices=["dev", "test"], default="dev")
    evaluation.add_argument("--generate", action="store_true")
    evaluation.add_argument("--repeats", type=int, choices=[1, 2, 3], default=1)
    evaluation.add_argument("--allow-unreviewed", action="store_true")
    score = commands.add_parser("score", help="Aggregate complete human judgments")
    score.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValueError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "Invalid environment settings; see docs/CONFIGURATION.md",
                }
            )
        )
        sys.exit(1)
    if args.command == "preflight":
        from nexusrag.preflight import run as preflight_run

        result = preflight_run(settings, args.require_ready, args.require_generation)
        print(json.dumps(result, indent=2))
        sys.exit(1 if result["status"] == "failed" else 0)
    if args.command == "validate":
        from nexusrag.evaluation.runner import load_questions
        from nexusrag.ingestion.corpus import load_corpus

        manifest, _ = load_corpus(settings.corpus_dir)
        questions = load_questions(Path("evaluation/questions.jsonl"), settings)
        print(
            json.dumps(
                {
                    "documents": len(manifest.documents),
                    "questions": len(questions),
                    "human_reviewed": sum(q.review_status == "human_reviewed" for q in questions),
                }
            )
        )
    elif args.command == "download-model":
        from nexusrag.generation.llm import token_count
        from nexusrag.retrieval.embeddings import Embedder

        print(
            {
                "embedding_tokens": Embedder(settings).count("NexusRAG"),
                "generation_tokens": token_count("NexusRAG"),
            }
        )
    elif args.command == "ingest":
        from nexusrag.ingestion.pipeline import ingest

        if args.fixture_graph:
            settings.graph_source = "mermaid_fixture"
        print(json.dumps(ingest(settings, args.assertions), indent=2))
    elif args.command == "ask":
        from nexusrag.models import AskRequest
        from nexusrag.service import QueryService

        service = QueryService(settings)
        try:
            result = service.ask(
                AskRequest(question=args.question, mode=args.mode), generate=not args.retrieval_only
            )
            print(json.dumps(result, indent=2))
            if result["status"] != "completed":
                sys.exit(1)
        finally:
            service.graph.close()
    elif args.command == "score":
        from nexusrag.evaluation.judgments import score_judgments

        print(json.dumps(score_judgments(args.run_dir), indent=2))
    elif args.command == "evaluate":
        from nexusrag.evaluation.runner import run

        print(run(settings, args.split, args.generate, args.repeats, args.allow_unreviewed))


if __name__ == "__main__":
    main()
