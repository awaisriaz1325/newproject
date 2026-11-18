import pytest
from compback_core.config import Environment, Settings
from pydantic import ValidationError


def test_prod_rejects_unsafe_backends() -> None:
    with pytest.raises(ValidationError, match="not allowed"):
        Settings(env=Environment.PROD)


def test_secrets_hidden_in_repr() -> None:
    s = Settings(env=Environment.TEST)
    assert "compback_app:compback_app" not in repr(s)
