#!/usr/bin/env python

import io
import os
import re
from codecs import open

from setuptools import find_packages, setup  # type: ignore

EXCLUDE_FROM_PACKAGES = ["tests"]
CURDIR = os.path.abspath(os.path.dirname(__file__))
README = io.open("README.md", "r", encoding="utf-8").read()

with open("pygdbmi/__init__.py", "r") as fd:
    matches = re.search(
        r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE
    )
    version = "0.0.0.0"
    if matches:
        version = matches.group(1)


setup(
    name="pygdbmi",
    version=version,
    author="Chad Smith",
    author_email="grassfedcode@gmail.com",
    description="Parse gdb machine interface output with Python",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/cs01/pygdbmi",
    license="MIT",
    packages=find_packages(exclude=EXCLUDE_FROM_PACKAGES),
    # https://mypy.readthedocs.io/en/latest/installed_packages.html#making-pep-561-compatible-packages
    package_data={"pygdbmi": ["py.typed"]},
    include_package_data=True,
    keywords=["gdb", "python", "machine-interface", "parse", "frontend"],
    scripts=[],
    entry_points={},
    zip_safe=False,
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
