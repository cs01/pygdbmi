import subprocess
import sys

def run(cmd):
    print("Running %r" % ' '.join(cmd))
    subprocess.check_call(cmd)


def main():
    files = ["pygdbmi"]
    if sys.version_info.major == 3 and sys.version_info.minor >= 6:
        run(["black", "--check"] + files)
    run(["flake8"] + files)
    return 0


if __name__ == "__main__":
    exit(main())
