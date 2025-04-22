import os
import sys
from unittest import mock

import pytest
import pytest_insight.cli.cli_web as cli_web


@pytest.fixture(autouse=True)
def cleanup_pid_info_files():
    # Ensure no leftover files before and after each test
    yield
    for f in [cli_web.PID_FILE, cli_web.INFO_FILE]:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass


@pytest.fixture(autouse=True)
def mock_sparklines(monkeypatch):
    monkeypatch.setitem(sys.modules, "sparklines", mock.Mock())
    yield


def test_status_not_running(capsys, mocker):
    # Ensure files do not exist
    for f in [cli_web.PID_FILE, cli_web.INFO_FILE]:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(cli_web.app, ["api-explorer", "status"], standalone_mode=False)
    out = result.output
    assert "not running" in out.lower()
    assert "to start" in out.lower()


@pytest.mark.xfail(
    reason="Typer CLI subprocess does not inherit mocks; see https://github.com/tiangolo/typer/issues/389"
)
def test_status_running(monkeypatch, tmp_path, capsys, mocker):
    # Simulate running process
    pid = os.getpid()  # Use current process to avoid killing anything
    host = "127.0.0.1"
    port = "12345"
    with open(cli_web.PID_FILE, "w") as f:
        f.write(str(pid))
    with open(cli_web.INFO_FILE, "w") as f:
        f.write(f"host={host}\nport={port}\npid={pid}\ncmd=uvicorn ...\n")
    # Patch psutil.Process at import location
    mocker.patch("pytest_insight.cli.cli_web.psutil.Process", lambda p: mock.Mock(is_running=lambda: True))
    from typer.testing import CliRunner

    runner = CliRunner()
    assert os.path.exists(cli_web.PID_FILE), f"PID_FILE missing: {cli_web.PID_FILE}"
    assert os.path.exists(cli_web.INFO_FILE), f"INFO_FILE missing: {cli_web.INFO_FILE}"
    result = runner.invoke(cli_web.app, ["api-explorer", "status"], standalone_mode=False)
    out = result.output
    if "running" not in out.lower():
        print(f"DEBUG OUTPUT (status_running): {out!r}")
    assert "running" in out.lower()
    assert host in out
    assert port in out
    assert str(pid) in out
    assert "to stop" in out.lower()


def test_stop_running(monkeypatch, capsys, mocker):
    # Simulate process tree kill
    pid = os.getpid()
    with open(cli_web.PID_FILE, "w") as f:
        f.write(str(pid))
    with open(cli_web.INFO_FILE, "w") as f:
        f.write(f"host=127.0.0.1\nport=12345\npid={pid}\ncmd=uvicorn ...\n")
    fake_proc = mock.Mock()
    fake_proc.children.return_value = []
    fake_proc.terminate.return_value = None
    fake_proc.is_running.return_value = False
    mocker.patch("psutil.Process", return_value=fake_proc)
    mocker.patch("psutil.wait_procs", return_value=([], []))
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(cli_web.app, ["api-explorer", "stop"], standalone_mode=False)
    out = result.output
    assert "stopped" in out.lower() or "no process found" in out.lower()
    assert not os.path.exists(cli_web.PID_FILE)
    assert not os.path.exists(cli_web.INFO_FILE)


def test_stop_not_running(capsys):
    # No PID file
    for f in [cli_web.PID_FILE, cli_web.INFO_FILE]:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(cli_web.app, ["api-explorer", "stop"], standalone_mode=False)
    out = result.output
    assert "no running api explorer" in out.lower()


@pytest.mark.xfail(
    reason="Typer CLI subprocess does not inherit mocks; see https://github.com/tiangolo/typer/issues/389"
)
def test_status_orphaned(monkeypatch, capsys, mocker):
    # Simulate orphaned uvicorn process
    for f in [cli_web.PID_FILE, cli_web.INFO_FILE]:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    # Patch psutil.process_iter at import location
    mocker.patch(
        "pytest_insight.cli.cli_web.psutil.process_iter",
        lambda attrs: iter([mock.Mock(info={"cmdline": ["uvicorn", "foo"]})]),
    )
    # Create dummy files to trigger orphaned logic
    with open(cli_web.PID_FILE, "w") as f:
        f.write("99999")
    with open(cli_web.INFO_FILE, "w") as f:
        f.write("host=127.0.0.1\nport=12345\npid=99999\ncmd=uvicorn ...\n")
    from typer.testing import CliRunner

    runner = CliRunner()
    assert os.path.exists(cli_web.PID_FILE), f"PID_FILE missing: {cli_web.PID_FILE}"
    assert os.path.exists(cli_web.INFO_FILE), f"INFO_FILE missing: {cli_web.INFO_FILE}"
    result = runner.invoke(cli_web.app, ["api-explorer", "status"], standalone_mode=False)
    out = result.output
    if "orphaned" not in out.lower():
        print(f"DEBUG OUTPUT (status_orphaned): {out!r}")
    assert "not running" in out.lower()
    assert "orphaned" in out.lower()
