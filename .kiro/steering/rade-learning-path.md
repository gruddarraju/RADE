# RADE Learning Path Overview

This workspace follows the **RADE (Real Applied Data Engineering)** learning path — a structured, project-driven journey to becoming a highly-paid Data Engineer on AWS.

## Journey Phases

The path progresses through three major phases:

1. **Starter → Hackathon Finisher** (6 weeks) — Foundations and first production project
2. **Applied Data Engineering Mastery** (3 months) — Deep specializations in Spark, Warehousing/Lakehouse, and Streaming/CI-CD
3. **DEH Hall of Fame** (3 months) — Final milestone, full job readiness

## Supporting Habits (Throughout)

- **Mindset**: 30-day daily "Strangest Secret" practice
- **Charity**: Donate to charity every month
- **Goals**: Clear, time-bound goals posted on the wall
- **Live Sessions**: Weekly calls and bootcamps

## Technology Stack

The overall tech stack covered across the journey:

- **Cloud**: AWS (Lambda, EMR, Redshift, MWAA, MSK Kafka, EMR Serverless)
- **Languages**: Python, SQL, PySpark
- **Big Data**: Apache Spark, Spark Structured Streaming
- **Storage/Lakehouse**: Apache Iceberg, Medallion Architecture
- **Orchestration**: Apache Airflow (MWAA)
- **Streaming**: Apache Kafka (MSK)
- **Data Warehousing**: Amazon Redshift, Dimensional Modeling
- **DevOps**: Git, GitHub Actions, CI/CD
- **AI-Assisted**: Agentic AI, Amazon Q

## Guiding Principles

- Every phase ends with a **hands-on project** (Hackathon) to ensure practical skills
- Focus on **interview readiness** — project stories, resume content, LinkedIn presence
- Learn foundational skills **quickly**, then go deep in specializations
- Build **production-grade** projects with real data, not toy examples

## Learning Platform

- Platform: https://learn.dataengineeringhub.in (NewZenler-based LMS)
- Videos hosted on Vimeo with auto-generated English captions
- Transcripts can be crawled using `learning/scripts/crawl_transcripts.py`
- Summaries generated via local LLM using `learning/scripts/summarize_to_docx.py`

## Workspace Structure

```
RADE/
├── .kiro/steering/        # Kiro AI steering files
├── Documents/             # Reference materials (learning path PDF)
└── learning/
    ├── scripts/           # Crawler & summarizer tools
    │   ├── crawl_transcripts.py   # Extract Vimeo captions from DEH platform
    │   ├── export_cookies.py      # Save browser session for auth
    │   ├── summarize_to_docx.py   # Summarize transcripts to Word docs
    │   └── config.yaml            # Credentials (gitignored)
    ├── phase1-starter/            # 6-week foundations
    │   ├── 01-rade-success-blueprint/
    │   │   └── transcripts/       # Extracted transcript files
    │   ├── 02-unix-and-cloud-foundations/
    │   └── ...
    ├── phase2-applied-mastery/    # 3-month deep dives
    │   ├── track-a-spark/
    │   └── track-b-warehousing-lakehouse/
    ├── phase3-interviews-accelerator/  # 3-month job readiness
    └── output/                    # Generated Word doc summaries
```

#[[file:Documents/path.pdf]]
