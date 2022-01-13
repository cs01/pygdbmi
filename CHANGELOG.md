# pygdbmi release history

## dev
* Strings containing escapes are now unescaped, both for messages in error records, which were previously mangled (#57), and textual records, which were previously left escaped (#58)

## 0.10.0.1
* Fix bug with `time_to_check_for_additional_output_sec`, as it was not being used when passed to `GdbController`

## 0.10.0.0

 **Breaking Changes**

* Drop support for Python 3.5
* Update `GdbController()` API. New API is `GdbController(command: Optional[List[str]], time_to_check_for_additional_output_sec: Optional[int])`.
* `GdbController.verify_valid_gdb_subprocess()` was removed
* Remove `NoGdbProcessError` error

Other Changes

* Add new `IoManager` class to handle more generic use-cases
* [dev] use pytest for testing
* gdb mi parsing remains unchanged

## 0.9.0.3

* Drop support for 2.7, 3.4
* Add support for 3.7, 3.8
* Add `py.typed` file so mypy can enforce type hints on `pygdbmi`
* Do not log in StringStream (#36)
* Updates to build and CI tests (use nox)
* Use mkdocs and mkdocstrings
* Doc updates

## 0.9.0.2
* More doc updates

## 0.9.0.1
* Update docs

## 0.9.0.0
* Stop buffering output
* Use logger in GdbController; modify `verbose` arguments.
* Remove support for Python 3.3

## 0.8.4.0
* Add method `get_subprocess_cmd` to view the gdb command run in the shell

## 0.8.3.0
* Improve reading gdb responses on unix (performance, bugfix) (@mouuff)

## 0.8.2.0
* Add support for [record and replay (rr) gdb supplement](http://rr-project.org/)

## 0.8.1.1
* Discard unexpected text from gdb

## 0.8.1.0
* Add native Windows support

## 0.8.0.0
* Make parsing more efficient when gdb outputs large strings
* Add new methods to GdbController class: `spawn_new_gdb_subprocess`, `send_signal_to_gdb`, and `interrupt_gdb`

## 0.7.4.5
* Update setup.py

## 0.7.4.4
* Fix windows ctypes import (#23, @rudolfwalter)

## 0.7.4.3
* Workaround gdb bug with repeated dictionary keys

## 0.7.4.2
* Improved buffering of incomplete gdb mi output (@trapito)
* Remove support of Python 3.2

## 0.7.4.1
* Preserve leading and trailing spaces in gdb/mi output (plus unit tests)
* Add unit test for buffering of gdb/mi output
* Documentation updates
* Refactoring

## 0.7.4.0
* Add more exception types (`NoGdbProcessError`, `GdbTimeoutError`)
* Add logic fixes for Windows (@johncf)
* Use codecs.open() to open the readme.rst, to prevent locale related bugs (@mariusmue)

## 0.7.3.3
* Add alternate pipe implementation for Windows

## 0.7.3.2
* Replace `epoll` with `select` for osx compatibility (@felipesere)

## 0.7.3.1
* Fix README

## 0.7.3.0
* Add support for gdb/mi (optional) tokens (@mariusmue)
