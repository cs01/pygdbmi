from setuptools import find_packages, setup, Command
import sys
from pygdbmi.tests import test_app

# from distutils.core import setup,
EXCLUDE_FROM_PACKAGES = []
version = '0.0.1.8'


class TestCommand (Command):
    description = 'test task'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        sys.exit(test_app.main())


setup(
    name='pygdbmi',
    version=version,
    author='Chad Smith',
    author_email='chadsmith27@gmail.com',
    description=('Parse gdb machine interface output with Python'),
    url='https://github.com/cs01/pygdbmi',
    license='BSD',
    packages=find_packages(exclude=EXCLUDE_FROM_PACKAGES),
    include_package_data=True,
    keywords=['gdb', 'python', 'machine-interface', 'parse', 'frontend'],
    scripts=[],
    entry_points={},
    extras_require={},
    zip_safe=False,
    cmdclass={'test': TestCommand},
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)
