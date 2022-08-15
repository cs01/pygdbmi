<h1 align="center">
pygdbmi - Get Structured Output from GDB's Machine Interface
</h1>

<p align="center">

<a href="https://github.com/cs01/pygdbmi/actions">
<img src="https://github.com/cs01/pygdbmi/workflows/Tests/badge.svg?branch=master" alt="Test status" /></a>

<a href="https://badge.fury.io/py/pygdbmi">
<img src="https://badge.fury.io/py/pygdbmi.svg" alt="PyPI version"/></a>

</p>

**Documentation** [https://cs01.github.io/pygdbmi](https://cs01.github.io/pygdbmi)

**Source Code** [https://github.com/cs01/pygdbmi](https://github.com/cs01/pygdbmi)

---

Python (**py**) [**gdb**](https://www.gnu.org/software/gdb/) machine interface [(**mi**)](https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html)

> GDB/MI is a line based machine oriented text interface to GDB and is activated by specifying using the --interpreter command line option (see Mode Options). It is specifically intended to support the development of systems which use the debugger as just one small component of a larger system.

## What's in the box?

1.  A function to parse gdb machine interface string output and return structured data types (Python dicts) that are JSON serializable. Useful for writing the backend to a gdb frontend. For example, [gdbgui](https://github.com/cs01/gdbgui) uses pygdbmi on the backend.
2.  A Python class to control and interact with gdb as a subprocess

To get [machine interface](https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html) output from gdb, run gdb with the `--interpreter=mi2` flag like so:

```
gdb --interpreter=mi2
```

## Installation

    pip install pygdbmi

## Compatibility

### Operating Systems

Cross platform support for Linux, macOS and Windows

- Linux/Unix

  Ubuntu 14.04 and 16.04 have been tested to work. Other versions likely work as well.

- macOS

  Note: the error `please check gdb is codesigned - see taskgated(8)` can be fixed by codesigning gdb with [these instructions](http://andresabino.com/2015/04/14/codesign-gdb-on-mac-os-x-yosemite-10-10-2/). If the error is not fixed, please [create an issue in github](https://github.com/cs01/pygdbmi/issues).

- Windows

  Windows 10 has been tested to work with MinGW and cygwin.

### gdb versions

- gdb 7.6+ has been tested. Older versions may work as well.

## Examples

gdb mi defines a syntax for its output that is suitable for machine readability and scripting: [example output](https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Simple-Examples.html#GDB_002fMI-Simple-Examples):

```
-> -break-insert main
<- ^done,bkpt={number="1",type="breakpoint",disp="keep",
enabled="y",addr="0x08048564",func="main",file="myprog.c",
fullname="/home/myprog.c",line="68",thread-groups=["i1"],
times="0"}
<- (gdb)
```

Use `pygdbmi.gdbmiparser.parse_response` to turn that string output into a JSON serializable dictionary

```python
from pygdbmi import gdbmiparser
from pprint import pprint
response = gdbmiparser.parse_response('^done,bkpt={number="1",type="breakpoint",disp="keep", enabled="y",addr="0x08048564",func="main",file="myprog.c",fullname="/home/myprog.c",line="68",thread-groups=["i1"],times="0"')
pprint(response)
pprint(response)
# Prints:
# {'message': 'done',
#  'payload': {'bkpt': {'addr': '0x08048564',
#                       'disp': 'keep',
#                       'enabled': 'y',
#                       'file': 'myprog.c',
#                       'fullname': '/home/myprog.c',
#                       'func': 'main',
#                       'line': '68',
#                       'number': '1',
#                       'thread-groups': ['i1'],
#                       'times': '0',
#                       'type': 'breakpoint'}},
#  'token': None,
#  'type': 'result'}
```

## Programmatic Control Over gdb

But how do you get the gdb output into Python in the first place? If you want, `pygdbmi` also has a class to control gdb as subprocess. You can write commands, and get structured output back:

```python
from pygdbmi.gdbcontroller import GdbController
from pprint import pprint

# Start gdb process
gdbmi = GdbController()
print(gdbmi.command)  # print actual command run as subprocess
# Load binary a.out and get structured response
response = gdbmi.write('-file-exec-file a.out')
pprint(response)
# Prints:
# [{'message': 'thread-group-added',
#   'payload': {'id': 'i1'},
#   'stream': 'stdout',
#   'token': None,
#   'type': 'notify'},
#  {'message': 'done',
#   'payload': None,
#   'stream': 'stdout',
#   'token': None,
#   'type': 'result'}]
```

Now do whatever you want with gdb. All gdb commands, as well as gdb [machine interface commands](<(https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Input-Syntax.html#GDB_002fMI-Input-Syntax)>) are acceptable. gdb mi commands give better structured output that is machine readable, rather than gdb console output. mi commands begin with a `-`.

```python
response = gdbmi.write('-break-insert main')  # machine interface (MI) commands start with a '-'
response = gdbmi.write('break main')  # normal gdb commands work too, but the return value is slightly different
response = gdbmi.write('-exec-run')
response = gdbmi.write('run')
response = gdbmi.write('-exec-next', timeout_sec=0.1)  # the wait time can be modified from the default of 1 second
response = gdbmi.write('next')
response = gdbmi.write('next', raise_error_on_timeout=False)
response = gdbmi.write('next', raise_error_on_timeout=True, timeout_sec=0.01)
response = gdbmi.write('-exec-continue')
response = gdbmi.send_signal_to_gdb('SIGKILL')  # name of signal is okay
response = gdbmi.send_signal_to_gdb(2)  # value of signal is okay too
response = gdbmi.interrupt_gdb()  # sends SIGINT to gdb
response = gdbmi.write('continue')
response = gdbmi.exit()
```

## Parsed Output Format

Each parsed gdb response consists of a list of dictionaries. Each dictionary has keys `message`, `payload`, `token`, and `type`.

- `message` contains a textual message from gdb, which is not always present. When missing, this is `None`.
- `payload` contains the content of gdb's output, which can contain any of the following: `dictionary`, `list`, `string`. This too is not always present, and can be `None` depending on the response.
- `token` If an input command was prefixed with a (optional) token then the corresponding output for that command will also be prefixed by that same token. This field is only present for pygdbmi output types `nofity` and `result`. When missing, this is `None`.

The `type` is defined based on gdb's various [mi output record types](<(https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI-Output-Records.html#GDB_002fMI-Output-Records)>), and can be

- `result` - the result of a gdb command, such as `done`, `running`, `error`, etc.
- `notify` - additional async changes that have occurred, such as breakpoint modified
- `console` - textual responses to cli commands
- `log` - debugging messages from gdb's internals
- `output` - output from target
- `target` - output from remote target
- `done` - when gdb has finished its output

## Contributing

Documentation fixes, bug fixes, performance improvements, and functional improvements are welcome. You may want to create an issue before beginning work to make sure I am interested in merging it to the master branch.

pygdbmi uses [nox](https://github.com/theacodes/nox) for automation.

See available tasks with

```
nox -l
```

Run tests and lint with

```
nox -s tests
nox -s lint
```

Positional arguments passed to `nox -s tests` are passed directly to `pytest`. For instance, to run only the parse tests use

```
nox -s tests -- tests/test_gdbmiparser.py
```

See [`pytest`'s documentation](https://docs.pytest.org/) for more details on how to run tests.

To format code using the correct settings use

```
nox -s format
```

Or, to format only specified files, use

```
nox -s format -- example.py pygdbmi/IoManager.py
```

## Similar projects

- [tsgdbmi](https://github.com/Guyutongxue/tsgdbmi) A port of pygdbmi to TypeScript
- [danielzfranklin/gdbmi](https://github.com/danielzfranklin/gdbmi) A port of pygdbmi to Rust

## Projects Using pygdbmi

- [gdbgui](https://github.com/cs01/gdbgui) implements a browser-based frontend to gdb, using pygdbmi on the backend
- [PINCE](https://github.com/korcankaraokcu/PINCE) is a gdb frontend that aims to provide a reverse engineering tool and a reusable library focused on games. It uses pygdbmi to parse gdb/mi based output for some functions
- [avatar²](https://github.com/avatartwo/avatar2) is an orchestration framework for reversing and analysing firmware of embedded devices. It utilizes pygdbmi for internal communication to different analysis targets.
- Know of another project? Create a PR and add it here.

## Authors

- [Chad Smith](https://github.com/cs01) (main author and creator).
- [Marco Barisione](http://www.barisione.org/) (co-maintainer).
- [The community](https://github.com/cs01/pygdbmi/graphs/contributors). Thanks especially to @mariusmue, @bobthekingofegypt, @mouuff, and @felipesere.
