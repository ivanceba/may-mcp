"""Safe errors at the May boundary; upstream text is never a message."""


class MayError(Exception):
    def __init__(self, code: str, message: str, *, outcome_unknown: bool = False) -> None:
        if outcome_unknown:
            message += " The write may have been saved; verify before repeating it."
        super().__init__(message)
        self.code = code
        self.outcome_unknown = outcome_unknown
