from time import time

from pygdbmi.gdbmiparser import parse_response


def get_test_input(n_repetitions):
    data = ", ".join(
        ['"/a/path/to/parse/' + str(i) + '"' for i in range(n_repetitions)]
    )
    return "=test-message,test-data=[" + data + "]"


def get_avg_time_to_parse(input_str, num_runs):
    avg_time = 0
    for _ in range(num_runs):
        t0 = time()
        parse_response(input_str)
        t1 = time()
        time_to_run = t1 - t0
        avg_time += time_to_run / num_runs
    return avg_time


# def test_big_o():
#     num_runs = 2

#     large_input_len = 100000

#     single_input = get_test_input(1)
#     large_input = get_test_input(large_input_len)

#     t_small = get_avg_time_to_parse(single_input, num_runs) or 0.0001
#     t_large = get_avg_time_to_parse(large_input, num_runs)
#     bigo_n = (t_large / large_input_len) / t_small
#     assert bigo_n < 1  # with old parser, this was over 3
