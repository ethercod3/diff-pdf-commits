from __future__ import annotations

from diff_pdf_commits.config import safe_label
from diff_pdf_commits.process import decode_output


def test_safe_label_keeps_filename_friendly_characters() -> None:
    assert safe_label("feature/pdf-diff@HEAD~1") == "feature_pdf-diff_HEAD_1"


def test_decode_output_replaces_invalid_bytes() -> None:
    assert decode_output(b"ok\xff") == "ok\ufffd"
