# Lesson 08 — Reliable LLM Workflows

## Objective

Build deterministic workflows that validate inputs, call the model safely, validate outputs, and apply business rules.

## Workflow shape

```text
input → validation → prompt → model → response validation → business rules → output
```

Start with explicit workflows such as `summarize`, `extract`, or `classify`. Do not build an autonomous agent until the product genuinely requires one.

## Structured output

```python
from pydantic import BaseModel


class ExtractedPerson(BaseModel):
    name: str
    occupation: str | None = None
    country: str | None = None
```

Treat model output as untrusted input. Validate it before passing it through the rest of the application.

## Reliability rules

- Set explicit timeouts.
- Retry only failures that are safe to retry.
- Avoid retrying validation errors indefinitely.
- Map provider failures to application errors.
- Never log API keys or sensitive prompt content.

## Exercise

- [ ] Add one workflow endpoint.
- [ ] Use a Pydantic output model.
- [ ] Add a fake LLM response.
- [ ] Test invalid model output.
- [ ] Test provider timeout/error behavior.

## Mentor questions

1. Which failures are retryable?
2. Where should prompt templates live?
3. What is the correct API response when output validation fails?

## Progress

- Status: **Not started**
- Completed: [ ]
- Date:

