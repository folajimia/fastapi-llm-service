# Lesson 09 — Observability and Lifespan

## Objective

Make slow and failed requests diagnosable without exposing secrets.

## Structured log fields

```text
event, request_id, conversation_id, provider, model,
latency_ms, status, token_usage, error_type
```

Do not log API keys, authorization headers, user secrets, or sensitive prompt content.

## Request flow

```text
request → request ID → route → service → database/LLM → correlated logs
```

## Health versus readiness

- `/health`: process is alive.
- `/readiness`: required dependencies, such as the database, are ready.

## Lifespan

Use FastAPI’s `lifespan` mechanism for resources shared across requests, such as an HTTP client, database pool, LLM client, or telemetry provider. Create them before `yield`; close them after `yield`.

## Exercise

- [ ] Add request ID middleware or an equivalent request correlation approach.
- [ ] Add structured logs for success and failure.
- [ ] Add `/health` and `/readiness` with distinct meanings.
- [ ] Manage one shared resource with lifespan.
- [ ] Add latency to the LLM request log.

## Mentor questions

1. Which fields are safe to log for this service?
2. What should readiness do if PostgreSQL is unavailable?
3. How will tests exercise startup and shutdown?

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:

## Reference

[FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)

