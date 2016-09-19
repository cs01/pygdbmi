# pygdbmi - Get Structured Output from GDB's Machine Interface
## pip install pygdbmi
[![Build Status](https://travis-ci.org/cs01/pygdbmi.svg?branch=master)](https://travis-ci.org/cs01/pygdbmi)

## Purpose
Parses gdb machine interface string output and returns structured data types. Run gdb with the `--interpreter=mi2` flag.

Also implements a class to control gdb, `GdbController`, which allows programmatic control of gdb using Python, which can be used to create a front end.

## Examples
Using `pygdbmi.parse_response`, turn gdb machine interface string output

    =thread-group-added,id="i1"

into this dictionary:

    {'message': 'thread-group-added',
    'payload': {
        'id': 'i1'
        },
    'type': 'notify'}

Run gdb as subprocess and write/read from it:

    from pygdbmi.gdbcontroller import GdbController
    from pprint import pprint
    # Start gdb process
    gdbmi = GdbController()
    # Load binary a.out and get structured response
    response = gdbmi.write('file a.out')
    pprint(response)
    [
     {'message': None,
      'payload': 'Reading symbols from ../pygdbmi/tests/sample_c_app/a.out...',
      'type': 'console'},
     {'message': 'done', 'payload': None, 'type': 'result'}
    ]

Now do whatever you want with gdb

    response = gdbmi.write('-exec-run')

## Commands

All regular gdb commands are valid, plus additional "machine interface" gdb commands. See https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Input-Syntax.html#GDB_002fMI-Input-Syntax.

Example mi commands: https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Simple-Examples.html#GDB_002fMI-Simple-Examples

## Parsed Output
Each parsed gdb response consists of a list of dictionaries. Each dictionary has keys `type`, `message`, and `payload`.

The `type` can be

* result - the result of a gdb command, such as `done`, `running`, `error`, etc.
* notify - additional async changes that have occurred, such as breakpoint modified
* console - textual responses to cli commands
* log - debugging messages from gdb's internals
* output - output from target
* target - output from remote target
* done - when gdb has finished its output

see https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Output-Records.html#GDB_002fMI-Output-Records for more information

The `message` contains a textual message from gdb,  which is not always present. When missing, this is `None`.

The `payload` contains the content of gdb's output, which can contain any of the following: `dictionary`, `list`, `string`. This too is not always present, and can be `None` depending on the response.

## Installation

    pip install pygdbmi

or clone, then run

    python setup.py install

## Further Reading

https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html
