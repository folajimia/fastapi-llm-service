# Lesson 06D — Test `ChatService` Without a Network Call

## Objective

Test the service directly with a fake LLM client. This is a unit test: it does not start FastAPI, contact PostgreSQL, or call a real model provider.

## Test code

The fake client lives in the test file itself — it is test scaffolding, not application code:

```python
# tests/unit/test_chat_service.py
import asyncio

from app.services.chat import ChatService


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)   # record what the service asked
        return self.response


def test_chat_service_returns_llm_response() -> None:
    fake_client = FakeLLMClient(response="hello from the fake")
    service = ChatService(llm_client=fake_client)

    result = asyncio.run(service.reply("hello"))

    assert result == "hello from the fake"
    assert fake_client.prompts == [
        "You are a helpful assistant.\nUser: hello"
    ]
```

Why the fake records prompts into `self.prompts`: without it you could only assert on the *response*. Recording the input lets you also prove the service built the prompt correctly — that is the `assert fake_client.prompts == [...]` line.

**Note the `\n` in the expected prompt (single backslash).** The version currently in the repo asserts `\\n` — a literal backslash and the letter `n` — because the service has the same double-escape bug. Both must be fixed together; see [[Lessons/06B Wiring the Route to the Service|06B]] Step 3.

## Why this test proves something useful

It proves that:

- `ChatService` accepts an LLM client dependency.
- The service builds the expected prompt.
- The service awaits the client.
- The service returns the client’s response.
- No real network call is required.

## Run it

```bash
mkdir -p tests/unit
poetry run pytest tests/unit/test_chat_service.py -q
```

Expected result:

```text
1 passed
```

## Add a failure test

```python
def test_chat_service_propagates_provider_failure() -> None:
    class FailingClient:
        async def generate(self, prompt: str) -> str:
            raise RuntimeError("simulated provider failure")

    service = ChatService(llm_client=FailingClient())

    try:
        asyncio.run(service.reply("hello"))
    except RuntimeError as error:
        assert str(error) == "simulated provider failure"
    else:
        raise AssertionError("Expected the provider failure")
```

Later, replace this manual `try`/`except` style with a pytest exception helper when the project’s test tooling is expanded.

## Do not test the wrong layer here

This test should not assert HTTP status codes. HTTP status codes belong in an API test using `TestClient`. This test focuses on service behavior.

## Full checkpoint

- [ ] `ChatService` has no FastAPI imports.
- [ ] A fake client returns a deterministic answer.
- [ ] The service test makes no real network call.
- [ ] The test checks both the response and the generated prompt.
- [ ] A provider failure case has been considered.
- [ ] The test passes through `poetry run pytest`.

## Mentor discussion

1. Which service behaviors should be tested next?
2. Should provider errors be translated inside `ChatService` or by a higher-level error-mapping layer?
3. When should we add async pytest support rather than using `asyncio.run`?

## Progress

- Status: **In progress — test exists and passes, but currently asserts the `\\n` bug. Fix the assertion along with the service prompt (see [[Lessons/06B Wiring the Route to the Service|06B]] Step 3), then add the failure test below.**
- Completed: [x] Fake client returns a deterministic answer. [x] No real network call. [x] Test checks the response. [ ] Test checks the prompt with a real newline. [ ] Failure case added.
- Test output: 3 passed (current suite)
- Date:
- Commit:

