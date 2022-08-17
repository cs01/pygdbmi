import os
from typing import Any


__all__ = [
    "fmt_cyan",
    "fmt_green",
    "print_cyan",
    "print_green",
    "print_red",
]


USING_WINDOWS = os.name == "nt"


def print_red(x: Any) -> None:
    if USING_WINDOWS:
        print(x)
    else:
        print(f"\033[91m {x}\033[00m")


def print_green(x: Any) -> None:
    if USING_WINDOWS:
        print(x)
    else:
        print(f"\033[92m {x}\033[00m")


def print_cyan(x: Any) -> None:
    if USING_WINDOWS:
        print(x)
    else:
        print(f"\033[96m {x}\033[00m")


def fmt_green(x: Any) -> str:
    if USING_WINDOWS:
        return x
    else:
        return f"\033[92m {x}\033[00m"


def fmt_cyan(x: Any) -> str:
    if USING_WINDOWS:
        return x
    else:
        return f"\033[96m {x}\033[00m"
