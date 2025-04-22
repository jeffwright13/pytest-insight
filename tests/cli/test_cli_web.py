import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
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
    cli_web.api_explorer_app.invoke(["status"])
    out = capsys.readouterr().out
    assert "not running" in out.lower()
    assert "to start" in out.lower()


def test_status_running(monkeypatch, tmp_path, capsys, mocker):
    # Simulate running process
    pid = os.getpid()  # Use current process to avoid killing anything
    host = "127.0.0.1"
    port = "12345"
    with open(cli_web.PID_FILE, "w") as f:
        f.write(str(pid))
    with open(cli_web.INFO_FILE, "w") as f:
        f.write(f"host={host}\nport={port}\npid={pid}\ncmd=uvicorn ...\n")
    monkeypatch.setattr("psutil.Process", lambda p: mock.Mock(is_running=lambda: True))
    cli_web.api_explorer_app.invoke(["status"])
    out = capsys.readouterr().out
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
    cli_web.api_explorer_app.invoke(["stop"])
    out = capsys.readouterr().out
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
    cli_web.api_explorer_app.invoke(["stop"])
    out = capsys.readouterr().out
    assert "no running api explorer" in out.lower()


def test_status_orphaned(monkeypatch, capsys, mocker):
    # Simulate orphaned uvicorn process
    for f in [cli_web.PID_FILE, cli_web.INFO_FILE]:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    monkeypatch.setattr(
        "psutil.process_iter",
        lambda attrs: iter([mock.Mock(info={"cmdline": ["uvicorn", "foo"]})]),
    )
    cli_web.api_explorer_app.invoke(["status"])
    out = capsys.readouterr().out
    assert "not running" in out.lower()
    assert "orphaned" in out.lower()
