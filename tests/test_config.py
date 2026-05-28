from __future__ import annotations

import pytest

from diff_pdf_commits.config import parse_env_option, safe_label
from diff_pdf_commits.process import decode_output


def test_safe_label_keeps_filename_friendly_characters() -> None:
    assert safe_label("feature/pdf-diff@HEAD~1") == "feature_pdf-diff_HEAD_1"


def test_decode_output_replaces_invalid_bytes() -> None:
    assert decode_output(b"ok\xff") == "ok\ufffd"


def test_parse_env_option_splits_key_and_value() -> None:
    assert parse_env_option("UV_PYTHON=C:\\Python\\python.exe") == ("UV_PYTHON", "C:\\Python\\python.exe")
    assert parse_env_option("EMPTY=") == ("EMPTY", "")


def test_parse_env_option_rejects_missing_key_or_separator() -> None:
    with pytest.raises(ValueError):
        parse_env_option("UV_PYTHON")
    with pytest.raises(ValueError):
        parse_env_option("=value")
