#!/usr/bin/env python

import os
import re
from codecs import open

from setuptools import find_packages, setup  # type: ignore


EXCLUDE_FROM_PACKAGES = ["tests"]
CURDIR = os.path.abspath(os.path.dirname(__file__))
README = open("README.md", encoding="utf-8").read()

with open("pygdbmi/__init__.py") as fd:
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
        # If modifying the list of supported versions, also update the versions pygdbmi is tested
        # with, see noxfile.py and .github/workflows/tests.yml.
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
