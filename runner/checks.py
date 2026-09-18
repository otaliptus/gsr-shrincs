"""Validation that remains active under Python optimization."""


def require(condition, message="validation failed"):
    if not condition:
        raise ValueError(message)
