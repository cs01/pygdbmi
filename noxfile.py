import itertools
import nox  # type: ignore
from pathlib import Path
import shutil

nox.options.sessions = ["tests", "lint", "docs"]
nox.options.reuse_existing_virtualenvs = True


# Run tests with (at least) the oldest and newest versions we support.
# If these are modified, also modify .github/workflows/tests.yml and the list of supported versions
# in setup.py.
@nox.session(python=["3.7", "3.10"])
def tests(session):
    session.install(".", "pytest")
    session.run("pytest", *session.posargs)


LINTED_PATHS = set(
    str(p.resolve())
    for p in itertools.chain(
        # All top-level Python files.
        Path(".").glob("*.py"),
        # Plus Python files in these specified directories.
        *(Path(d).glob("**/*.py") for d in ("pygdbmi", "tests"))
    )
)

ISORT_OPTIONS = ["--profile", "black", "--lines-after-imports", "2"]


# `format` is a builtin so the function is named differently.
@nox.session(name="format")
def format_(session):
    """Re-format all Python source files or, if positionals are passed, only the
    specified files."""
    files = LINTED_PATHS
    if session.posargs:
        # Only use positional arguments which are linted files.
        files = files & {str(Path(f).resolve()) for f in session.posargs}

    session.install("isort", "black", "flake8", "mypy", "check-manifest")
    session.run("isort", *ISORT_OPTIONS, *files)
    session.run("black", *files)


@nox.session()
def lint(session):
    session.install("isort", "black", "flake8", "mypy", "check-manifest")
    session.run("isort", "--check-only", *ISORT_OPTIONS, *LINTED_PATHS)
    session.run("black", "--check", *LINTED_PATHS)
    session.run("flake8", *LINTED_PATHS)
    session.run("mypy", *LINTED_PATHS)
    session.run("check-manifest")
    session.run("python", "setup.py", "check", "--metadata", "--strict")


def install_mkdoc_dependencies(session):
    session.install("-r", "mkdoc_requirements.txt")


@nox.session
def docs(session):
    install_mkdoc_dependencies(session)
    session.run("mkdocs", "build")


@nox.session
def serve_docs(session):
    install_mkdoc_dependencies(session)
    session.run("mkdocs", "serve")


@nox.session
def publish_docs(session):
    install_mkdoc_dependencies(session)
    session.run("mkdocs", "gh-deploy")


@nox.session(python="3.7")
def build(session):
    session.install("setuptools", "wheel", "twine")
    shutil.rmtree("dist", ignore_errors=True)
    shutil.rmtree("build", ignore_errors=True)
    session.run("python", "setup.py", "--quiet", "sdist", "bdist_wheel")
    session.run("twine", "check", "dist/*")


@nox.session(python="3.7")
def publish(session):
    build(session)
    print("REMINDER: Has the changelog been updated?")
    session.run("python", "-m", "twine", "upload", "dist/*")
    publish_docs(session)
