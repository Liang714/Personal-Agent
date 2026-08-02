class AgentError(Exception):
    """Base class for expected, user-facing failures with a clear cause."""


class OllamaUnavailableError(AgentError):
    pass


class NotAuthenticatedError(AgentError):
    pass


class ReauthRequiredError(AgentError):
    pass


class MemoExtractionError(AgentError):
    pass


class TranscriptionError(AgentError):
    pass
