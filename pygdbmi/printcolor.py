import os

USING_WINDOWS = os.name == "nt"


def print_red(x):
    if USING_WINDOWS:
        print(x)
    else:
        print("\033[91m {}\033[00m".format(x))


def print_green(x):
    if USING_WINDOWS:
        print(x)
    else:
        print("\033[92m {}\033[00m".format(x))


def print_cyan(x):
    if USING_WINDOWS:
        print(x)
    else:
        print("\033[96m {}\033[00m".format(x))


def fmt_green(x):
    if USING_WINDOWS:
        return x
    else:
        return "\033[92m {}\033[00m".format(x)


def fmt_cyan(x):
    if USING_WINDOWS:
        return x
    else:
        return "\033[96m {}\033[00m".format(x)
