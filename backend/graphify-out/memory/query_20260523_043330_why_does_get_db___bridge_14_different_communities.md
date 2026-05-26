---
type: "query"
date: "2026-05-23T04:33:30.243392+00:00"
question: "Why does get_db() bridge 14 different communities?"
contributor: "graphify"
source_nodes: ["get_db()", "Direct psycopg2 Over Supabase SDK Pattern"]
---

# Q: Why does get_db() bridge 14 different communities?

## Answer

get_db() (app/core/database.py L49) is the only database access primitive in the entire backend — there is no connection pool, no ORM, no repository layer. Every service that needs DB access (all 14 community groups) imports and calls it directly. This creates a single chokepoint with 122 edges: a bottleneck that also means replacing psycopg2 or adding asyncpg would require touching the entire codebase at once.

## Source Nodes

- get_db()
- Direct psycopg2 Over Supabase SDK Pattern