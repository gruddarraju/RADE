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
