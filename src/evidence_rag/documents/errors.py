"""Safe application errors shared by document services."""


class IntakeError(RuntimeError):
    """Bounded client-facing failure without source content or private paths."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
