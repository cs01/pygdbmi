import os


__all__ = [
    "USING_WINDOWS",
]

USING_WINDOWS = os.name == "nt"
