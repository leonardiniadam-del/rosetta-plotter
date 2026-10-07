"""Errors whose message is shown to the student exactly as written."""


class ImportProblem(Exception):
    """A file can't be used. str(exc) is a plain-language message for the student."""


class UserProblem(Exception):
    """Something the student asked for can't be done. str(exc) is a plain-language message for the
    student; `details` is technical text for the app's Details link (often empty)."""

    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.details = details
