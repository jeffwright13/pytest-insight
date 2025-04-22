import pytest

pytest_plugins = ["pytester"]


@pytest.fixture
def testdir_or_pytester(request):
    # Pytest >=7 uses pytester, older uses testdir
    if "pytester" in request.fixturenames:
        return request.getfixturevalue("pytester")
    return request.getfixturevalue("testdir")


def strip_ansi(s):
    import re

    ansi_escape = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
    return ansi_escape.sub("", s)


def test_plugin_registers_and_runs(testdir_or_pytester):
    testdir = testdir_or_pytester
    testdir.makepyfile(
        """
        def test_example():
            assert 1 == 1
    """
    )
    result = testdir.runpytest("--insight")
    print(result.stdout.str())
    assert result.ret == 0
    # Uncomment the following after confirming the summary appears:
    # result.stdout.fnmatch_lines(["*Session*tests*"])


@pytest.mark.parametrize(
    "cli_option,expected",
    [
        ("--insight-sut-name=mySUT", "mySUT"),
        ("--insight-testing-system=mySYS", "mySYS"),
    ],
)
def test_plugin_cli_options(testdir_or_pytester, cli_option, expected):
    testdir = testdir_or_pytester
    testdir.makepyfile(
        """
        def test_example():
            pass
    """
    )
    result = testdir.runpytest("--insight", cli_option)
    out = result.stdout.str()
    out_stripped = strip_ansi(out)
    print(out_stripped)
    assert expected in out_stripped


@pytest.mark.skip(reason="storage not implemented")
def test_plugin_handles_storage_error():
    pass
