---
type: "query"
date: "2026-05-23T04:35:12.538776+00:00"
question: "how does the spark API work"
contributor: "graphify"
source_nodes: ["spark()", "consume_spark()", "generate_spark()", "SparkResponse", "Mission"]
---

# Q: how does the spark API work

## Answer

POST /spark hits spark() (spark.py:22). Flow: 1) check_budget() gates token cost. 2) consume_spark() opens a DB connection via get_db() and increments the spark_usage counter (5 sparks per 60-min window per uid/session_id, fail-open on DB error). 3) generate_spark() calls complete_text(interaction_type='spark') via provider_service, which returns a 2-3 sentence answer + a Mission object (4-5 MissionStep items). 4) record_usage() upserts token_usage for the billing month. Response is SparkResponse schema. GET /session/:id calls session_status() -> get_session_status() to read the current window count without consuming.

## Source Nodes

- spark()
- consume_spark()
- generate_spark()
- SparkResponse
- Mission