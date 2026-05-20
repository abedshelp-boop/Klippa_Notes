import sys

import pytest

from debug import create_debug


def test_log_is_noop_when_not_dev(capsys):
    d = create_debug(is_dev=False)
    d.log("Sub", "message", {"extra": 1})
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_log_prints_prefixed_when_dev(capsys):
    d = create_debug(is_dev=True)
    d.log("Sub", "message")
    captured = capsys.readouterr()
    assert "[Sub] message" in captured.out


def test_warn_is_noop_when_not_dev(capsys):
    d = create_debug(is_dev=False)
    d.warn("Sub", "careful")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_warn_prints_to_stderr_when_dev(capsys):
    d = create_debug(is_dev=True)
    d.warn("Sub", "careful")
    captured = capsys.readouterr()
    assert "[WARN][Sub] careful" in captured.err


def test_error_always_prints_to_stderr(capsys):
    d = create_debug(is_dev=False)
    d.error("Sub", "boom")
    captured = capsys.readouterr()
    assert "[ERROR][Sub] boom" in captured.err


def test_error_prints_extra_data(capsys):
    d = create_debug(is_dev=True)
    d.error("Sub", "boom", {"code": 500})
    captured = capsys.readouterr()
    assert "[ERROR][Sub] boom" in captured.err
    assert "500" in captured.err
