"""Engine exception types."""


class EngineError(Exception):
    """Base class for engine errors. `code` is a machine-readable identifier."""

    code = "engine_error"

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class CancelledError(EngineError):
    """Raised when a cooperative cancellation event is set."""

    code = "cancelled"

    def __init__(self, message: str = "Computation cancelled"):
        super().__init__(message)


class ImportError_(EngineError):
    code = "import_error"


class ProcessingError(EngineError):
    code = "processing_error"
