class LLMError(Exception):
    """Base class for all LLM-related failures."""


class LLMTimeoutError(LLMError):
    """The provider did not answer within the timeout."""


class LLMProviderError(LLMError):
    """The provider answered with an error (rate limit, 5xx, auth...)."""


class LLMResponseValidationError(LLMError):
    """The provider answered, but the answer was not valid for our workflow."""
