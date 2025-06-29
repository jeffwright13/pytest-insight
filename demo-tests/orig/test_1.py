import logging
import random
import sys
import warnings

import pytest

LOG_LEVELS = [
    logging.DEBUG,
    logging.INFO,
    logging.WARNING,
    logging.ERROR,
    logging.CRITICAL,
]


def log_making_fixture(fake_data, logger):
    for _ in range(random.randint(1, 10)):
        logger.log(random.choice(LOG_LEVELS), fake_data)
        logger.log(random.choice(LOG_LEVELS), fake_data)
        logger.log(random.choice(LOG_LEVELS), fake_data)
        logger.log(random.choice(LOG_LEVELS), fake_data)
    pass


def test_random_logs(fake_data, logger):
    log_making_fixture()


@pytest.fixture
def error_fixtureure(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 0


def test_a_ok(fake_data, logger):
    print("This test doesn't have much to say, but it passes - ok!!")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    pass


def test_b_fail(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 0


def test_c_error(fake_data, logger):
    print("This test should be marked as an Error.")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    pass


def test_d1_skip_inline(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    pytest.skip("Skipping this test with inline call to 'pytest.skip()'.")


pytest.mark.skip(reason="Skipping this test with decorator.")


def test_d2_skip(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)


def test_d3_skip_decorator(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    pytest.skip("Skipping this test with inline call to 'pytest.skip()'.")


def test_e1_xfail_by_inline_and_has_reason(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    pytest.xfail("Marked as Xfail with inline call to 'pytest.xfail()'.")


@pytest.mark.xfail(reason="Marked as Xfail with decorator.")
def test_e2_xfail_by_decorator_and_has_reason(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    pytest.xfail("Marked as Xfail with decorator.")


def test_f1_xfails_by_inline_even_though_assertTrue_happens_before_pytestDotXfail(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert True
    pytest.xfail("Marked as Xfail with inline call to 'pytest.xfail()'.")


@pytest.mark.xfail(reason="Marked as Xfail with decorator.")
def test_f2_xpass_by_xfail_decorator_and_has_reason(fake_data, logger):
    print("This test is marked Xfail by use of decorator '@pytest.mark.xfail'.")
    print("However, because its outcome is a PASS, it is classified as XPass instead.")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    pass


@pytest.mark.parametrize("test_input, expected", [("3+5", 8), ("2+4", 6), ("6*9", 42)])
def test_g_eval_parameterized(fake_data, test_input, expected, logger):
    print(f"Testing {test_input} == {expected}")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert eval(test_input) == expected


@pytest.fixture
def log_testname(fake_data, logger):
    logger.info(f"Running test {__name__}...")
    logger.info("Setting test up...")
    logger.info("Executing test...")
    logger.info("Tearing test down...")


def test_1_passes_and_has_logging_output(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert True


def test_2_fails_and_has_logging_output(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 0 == 1


def test_3_fails(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 0


def test_4_passes(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert True


@pytest.mark.skip
def test_5_marked_SKIP(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 1


@pytest.mark.xfail
def test_6_marked_xfail_by_decorator_but_passes_and_has_no_reason(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 1


@pytest.mark.xfail
def test_7_marked_xfail_by_decorator_and_fails_and_has_no_reason(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 0


# Method and its test that causes warnings
def api_v1(fake_data, logger):
    warnings.warn(UserWarning("api v1, should use functions from v2"))
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    return 1


def test_8_causes_a_warning(fake_data, logger):
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert api_v1() == 1


# # These tests are helpful in showing how pytest deals with various types
# # of output (stdout, stderr, log)
def test_9_lorem_fails(capsys, logger):
    lorem = """"Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.

    Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem. Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur? Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur?

    At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident, similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus id quod maxime placeat facere possimus, omnis voluptas assumenda est, omnis dolor repellendus. Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non recusandae. Itaque earum rerum hic tenetur a sapiente delectus, ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis doloribus asperiores repellat."""
    print(lorem)
    assert False


def test_10_fail_capturing(fake_data, capsys, logger):
    print("FAIL this stdout is captured")
    print("FAIL this stderr is captured", file=sys.stderr)
    logger.warning("FAIL this log is captured")
    with capsys.disabled(logger):
        print("FAIL stdout not captured, going directly to sys.stdout")
        print("FAIL stderr not captured, going directly to sys.stderr", file=sys.stderr)
        logger.warning("FAIL is this log captured?")
    print("FAIL this stdout is also captured")
    print("FAIL this stderr is also captured", file=sys.stderr)
    logger.warning("FAIL this log is also captured")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert False


def test_10b_failed_capturing(fake_data, capsys, logger):
    print("FAILED this stdout is captured")
    print("FAILED this stderr is captured", file=sys.stderr)
    logger.warning("FAILED this log is captured")
    with capsys.disabled(logger):
        print("FAILED stdout not captured, going directly to sys.stdout")
        print("FAILED stderr not captured, going directly to sys.stderr", file=sys.stderr)
        logger.warning("FAIL is this log captured?")
    print("FAILED this stdout is also captured")
    print("FAILED this stderr is also captured", file=sys.stderr)
    logger.warning("FAILED this log is also captured")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert False


def test_11_pass_capturing(fake_data, capsys, logger):
    print("\nPASS this stdout is captured")
    print("PASS this stderr is captured", file=sys.stderr)
    logger.warning("PASS this log is captured")
    with capsys.disabled(log_testname, logger):
        print("PASS stdout not captured (capsys disabled), going directly to sys.stdout")
        print(
            "PASS stderr not captured (capsys disabled), going directly to sys.stderr",
            file=sys.stderr,
        )
        logger.warning("is this log captured?")
    print("PASS this stdout is also captured")
    print("PASS this stderr is also captured", file=sys.stderr)
    logger.warning("PASS this log is also captured")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert True


def test_12_fails_and_has_stdout(fake_data, logger):
    print("this test fails")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 0 == 1


def test_13_passes_and_has_stdout(fake_data, logger):
    print(
        "This test passes. This message is a 'print' and is consumed by Pytest via" " stdout."
    )  # stdout is consumed by pytest
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert True


# These 2 tests can intentionally cause an error - useful for testing;
# if the fixture is commented out, the test throws an error at setup.
#
# @pytest.fixture()
# def fixture_for_fun(log_testname, logger):
#     pass


def test_14_causes_error_pass_stderr_stdout_stdlog(fake_data, fixture_for_fun, logger):
    print("PASS this stdout is captured")
    print("PASS this stderr is captured", file=sys.stderr)
    logger.warning("PASS this log is captured")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 1


def test_15_causes_error_fail_stderr_stdout_stdlog(fake_data, fixture_for_fun, logger):
    print("FAIL this stdout is captured")
    print("FAIL this stderr is captured", file=sys.stderr)
    logger.warning("FAIL this log is captured")
    logger.critical(fake_data)
    logger.error(fake_data)
    logger.warning(fake_data)
    logger.info(fake_data)
    logger.debug(fake_data)
    assert 0


def test_16_fail_compare_dicts_for_pytest_icdiff(logger):
    listofStrings = ["Hello", "hi", "there", "look", "at", "this"]
    listofInts = [7, 10, 45, 23, 18, 77]
    assert len(listofStrings) == len(listofInts)
    assert listofStrings == listofInts


@pytest.mark.flaky(reruns=0)
def test_flaky_0(logger):
    # time.sleep(random.uniform(0.1, 0.75))
    assert random.choice([True, False])


@pytest.mark.flaky(reruns=1)
def test_flaky_1(logger):
    # time.sleep(random.uniform(0.1, 0.75))
    assert random.choice([True, False])


@pytest.mark.flaky(reruns=2)
def test_flaky_2(logger):
    # time.sleep(random.uniform(0.1, 0.75))
    assert random.choice([True, False])


@pytest.mark.flaky(reruns=3)
def test_flaky_3(logger):
    # time.sleep(random.uniform(0.1, 0.75))
    assert random.choice([True, False])


@pytest.mark.flaky(reruns=2)
def test_flaky_always_fail(logger):
    # time.sleep(random.uniform(0.1, 0.75))
    assert False


@pytest.mark.flaky(reruns=2)
def test_flaky_always_pass(logger):
    # time.sleep(random.uniform(0.1, 0.75))
    assert True
