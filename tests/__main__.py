from . import static_tests, test_pygdbmi


exit(test_pygdbmi.main() + static_tests.main())
