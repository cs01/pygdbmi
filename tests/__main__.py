from . import test_pygdbmi, static_tests

exit(test_pygdbmi.main() + static_tests.main())
