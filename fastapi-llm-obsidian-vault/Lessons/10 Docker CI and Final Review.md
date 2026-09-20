# Lesson 10 — Docker, CI, and Final Review

## Objective

Make the service reproducible for another developer and prevent broken changes from reaching the main branch.

## Docker target

```text
Docker Compose
├── api
└── PostgreSQL
```

The image should install dependencies through Poetry and run the application with an explicit production-oriented command. Uvicorn is acceptable; discuss worker strategy with the mentor rather than adding unnecessary infrastructure.

## CI pipeline

```text
pull request → install → lint → type check → tests → Docker build
```

## Exercise

- [ ] Add a Dockerfile.
- [ ] Add Docker Compose for local API plus PostgreSQL.
- [ ] Confirm a clean checkout can run with the documented commands.
- [ ] Add GitHub Actions for Ruff, type checks, tests, and Docker build.
- [ ] Update README with setup, environment, test, and deployment commands.

## Final architecture review

- [ ] Routes do not contain database queries.
- [ ] Services do not depend on FastAPI request objects unnecessarily.
- [ ] Provider-specific code is isolated.
- [ ] Configuration is typed and secret-safe.
- [ ] Migrations are committed and reviewed.
- [ ] Tests include a fake LLM.
- [ ] Logs can explain a slow request.
- [ ] Docker and CI work from a clean checkout.

## Mentor questions

1. What would you simplify before calling this production-oriented?
2. Which boundary is least convincing and why?
3. What failure case still needs a test?

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:

## Reference

[FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/)

