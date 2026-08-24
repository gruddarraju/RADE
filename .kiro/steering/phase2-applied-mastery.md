---
inclusion: manual
---

# Phase 2: Applied Data Engineering Mastery (3 Months)

## Goal

Achieve deep-level expertise in Apache Spark, Data Warehousing, and Lakehouse architectures. Be interview-ready with production-grade projects on real Big Data clusters.

## Track A: Apache Spark Deep Dive

### Learning Modules
1. **Apache Spark & World of EMR** — Spark architecture, EMR cluster setup
2. **Spark DataFrame Mastery** — Advanced DataFrame operations, UDFs, window functions
3. **Spark Internals & Performance Optimization** — DAG, stages, partitioning, memory management
4. **Spark Query Optimization & Execution Strategies** — Catalyst optimizer, AQE, join strategies
5. **Spark Production Engineering & Troubleshooting** — Monitoring, debugging, production configs

### Hackathon Deliverable
- Production-grade project on a real Big Data cluster (EMR)
- Deep Spark knowledge demonstrated through optimization and troubleshooting

### Key Skills
- Spark internals (DAG, stages, tasks, shuffles)
- Performance tuning (partitioning, caching, broadcast joins)
- EMR cluster management and configuration
- Production monitoring and troubleshooting

---

## Track B: Data Warehousing & Lakehouse Deep Dive

### Learning Modules
1. **Data Modeling & Dimensional Warehousing** — Star schema, snowflake, SCD types
2. **Amazon Redshift Deep Dive** — Distribution styles, sort keys, query optimization
3. **Modern Data Engineering Stack for Lakehouse Engineering** — Modern tools and frameworks
4. **Lakehouse & Medallion Architecture** — Bronze/Silver/Gold layers, data quality
5. **Apache Iceberg for Lakehouse Engineering** — Table format, time travel, schema evolution

### Hackathon Deliverables
- Production-grade Data Warehousing project (Dimensional Modeling on Redshift)
- Production-grade Lakehouse project (Iceberg + Medallion Architecture)

### Key Skills
- Dimensional modeling (facts, dimensions, SCDs)
- Amazon Redshift optimization
- Lakehouse architecture patterns
- Apache Iceberg table management
- Medallion architecture (Bronze → Silver → Gold)

---

## When Helping with Phase 2 Work

- Optimize for performance — consider partitioning, data skew, and shuffle
- Use Spark DataFrame API with proper column expressions (avoid string-based col refs when possible)
- Follow Medallion Architecture conventions: raw (Bronze) → cleaned (Silver) → business-ready (Gold)
- Apply dimensional modeling best practices (Kimball methodology)
- Use Apache Iceberg features: schema evolution, partition evolution, time travel
- Write production-ready code with logging, error handling, and config externalization
- Consider data quality checks at each layer transition
