import subprocess


def run(cmd):
    print("Running %r" % ' '.join(cmd))
    subprocess.check_call(cmd)


def main():
    files = ["pygdbmi"]
    # TODO turn back on for Python 3.6+
    # run(["black", "--check"] + files)
    run(["flake8"] + files)
    return 0


if __name__ == "__main__":
    exit(main())
