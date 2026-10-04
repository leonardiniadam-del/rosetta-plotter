"""Errors whose message is shown to the student exactly as written."""


class ImportProblem(Exception):
    """A file can't be used. str(exc) is a plain-language message for the student."""
