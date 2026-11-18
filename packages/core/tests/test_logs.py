import json

import pytest
from compback_core.logs import configure_logging, get_logger, scrub_value


def test_scrubs_ssn_ein_email_in_values() -> None:
    out = scrub_value("ssn 123-45-6789 ein 12-3456789 mail a.b@example.com")
    assert "123-45-6789" not in out
    assert "12-3456789" not in out
    assert "example.com" not in out


def test_scrubs_sensitive_keys_nested() -> None:
    assert scrub_value({"user": {"password": "x", "name": "ok"}}) == {
        "user": {"password": "[REDACTED]", "name": "ok"}
    }


def test_logger_output_has_no_pii(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json=True, service="test")
    get_logger("t").info("evt", fein="12-3456789", note="SSN 123456789", email="x@y.io")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(line)
    assert data["fein"] == "[REDACTED]"
    assert data["email"] == "[REDACTED]"
    assert "123456789" not in line
