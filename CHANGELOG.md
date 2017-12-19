# pygdbmi release history

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
