# RADE Project Standards & Conventions

## Code Standards

### Python
- Use Python 3.9+ (AWS Lambda and EMR compatible)
- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Docstrings for all public functions (Google style)
- Use virtual environments or requirements.txt for dependency management

### PySpark
- Prefer DataFrame API over RDD API
- Use `F.col()` imports from `pyspark.sql.functions as F`
- Chain transformations readably (one per line for complex pipelines)
- Always specify schemas explicitly when reading data
- Partition output data appropriately for downstream consumers

### SQL
- Use uppercase for SQL keywords (SELECT, FROM, WHERE)
- Use CTEs over nested subqueries for readability
- Include comments for complex business logic
- Follow naming conventions: snake_case for columns and tables

## Project Structure

Organize projects consistently:

```
project-name/
├── src/                    # Source code
│   ├── jobs/              # Spark/ETL jobs
│   ├── lambdas/           # Lambda function handlers
│   ├── dags/              # Airflow DAGs
│   └── utils/            # Shared utilities
├── tests/                 # Unit and integration tests
├── infra/                 # IaC (CloudFormation/CDK)
├── configs/               # Environment configs
├── data/                  # Sample/test data (not production)
├── docs/                  # Documentation
├── scripts/               # Helper scripts
├── .github/workflows/     # CI/CD pipelines
├── requirements.txt       # Python dependencies
└── README.md              # Project overview
```

## Learning Module Structure

Each module folder under `learning/` follows this pattern:

```
module-folder/
├── transcripts/           # Auto-extracted video transcripts (.txt)
├── presentation/          # Editable transcript-grounded PowerPoint decks
├── notes/                 # Personal notes and summaries
├── code/                  # Practice code and exercises
└── hackathon/             # Project work (where applicable)
```

Transcripts are extracted using the crawler tool at `learning/scripts/crawl_transcripts.py`.

### Transcript-Grounded Presentation Standards

- **Source boundary and coverage**: Treat `<module>/transcripts/*.txt` as the module's canonical presentation corpus. VTT siblings are alternate caption files, not additional sources. Label PDFs, artifacts, other transcript directories, and downstream modules as supporting context rather than silently expanding the core corpus. Before finalizing a deck, mechanically verify that every intended TXT basename appears verbatim in a source index or traceable source map and supports the presentation; list deliberate exclusions or supporting sources with their reason.
- **Evidence labels**: Use `TRANSCRIPT-DERIVED` for faithful source material, `TRANSCRIPT + GUIDANCE` when adding explanation or updated operational advice, `CURRENT SAFETY GUIDANCE` for guardrails not asserted by the transcript, and `SUPPORTING CONTEXT` (or a more specific label) for cross-module material. Distinguish reported demonstrations, illustrative code, learner-measured results, and unverified testimonials or outcome claims.
- **Safe modernization**: Do not silently present corrected or modernized advice as the original lesson. Preserve the transcript claim where useful, visibly separate corrections and current guardrails, and verify volatile AWS/API/CLI/security guidance against authoritative current documentation when feasible. Never present root use, broad administrator access, long-lived keys, secrets in prompts, destructive commands, inferred paths, broad overwrites, or generated infrastructure as production defaults.
- **Editable PPTX validation**: Keep instructional text and diagrams as native PowerPoint text/vector objects rather than flattened screenshots. Reopen the saved `.pptx` and verify expected slide count and dimensions, nonempty slides/headings, exact source coverage, approved visible fonts, shape bounds, and absence of unintended pictures, charts, tables, media, or embeddings. Render and visually inspect slides when tooling permits because coordinate checks cannot detect all clipping, overflow, overlap, substitution, or readability problems. Reopen and ZIP-test the OOXML package for corruption.
- **Cleanup and protected sources**: Remove temporary renders, unpacked OOXML, scratch files, one-off edit/validation scripts, and temporary environments after final validation unless they are intentionally maintained project tooling. Never treat `learning/phase1-starter/07-agentic-data-engineering-with-amazon-q/transcripts-project-labs-misrouted/` as temporary: do not delete, move, rename, merge, or deduplicate that corpus without the user's explicit approval for that specific operation. If used, cite it only as clearly labeled supporting context unless an approved reclassification changes the boundary.

## AWS Best Practices

- Never hardcode credentials — use IAM roles and environment variables
- Tag all resources with project name and environment
- Use separate AWS accounts or at minimum separate prefixes for dev/staging/prod
- Enable CloudWatch logging for all services
- Use S3 lifecycle policies for cost management
- Follow least-privilege principle for IAM policies

## Data Engineering Patterns

- **Idempotency**: All pipelines should be safe to re-run
- **Schema validation**: Validate data at ingestion boundaries
- **Partitioning**: Partition by date (year/month/day) unless business logic dictates otherwise
- **File formats**: Use Parquet for analytics, JSON for event streams
- **Naming**: Use snake_case for all data assets (tables, columns, S3 paths)

## Interview Readiness

For every project completed, prepare:
- **STAR Story**: Situation, Task, Action, Result
- **Architecture Diagram**: Clear visual of data flow
- **Key Metrics**: Volume processed, latency, cost savings
- **Challenges & Solutions**: What went wrong and how you fixed it
- **LinkedIn Post**: Summary of the project for your profile

## Tooling

### Transcript Crawler (`learning/scripts/`)
- Uses Playwright to extract Vimeo auto-generated captions from DEH platform
- Requires session cookies (exported via `export_cookies.py`)
- Saves transcripts as `.txt` files inside each module's `transcripts/` folder
- Run: `python crawl_transcripts.py --config config.yaml --course "Course Name"`

### Summarizer (`learning/scripts/`)
- Uses Ollama (local LLM) to summarize transcript files into Word documents
- Generates structured `.docx` with table of contents and per-lesson summaries
- Run: `python summarize_to_docx.py --config config.yaml`
- Requires Ollama running locally with a pulled model (e.g., `ollama pull llama3`)
