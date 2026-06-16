"""Tests for environment-variable coercion helpers in audioflow2mqtt."""

import pytest

from audioflow2mqtt import env_to_bool


class TestEnvToBool:
    @pytest.mark.parametrize("value", ["False", "false", "FALSE", "0", "no", "off", ""])
    def test_falsey_strings(self, value):
        assert env_to_bool(value, default=True) is False

    @pytest.mark.parametrize("value", ["True", "true", "1", "yes", "on", "anything"])
    def test_truthy_strings(self, value):
        assert env_to_bool(value, default=False) is True

    def test_unset_uses_default(self):
        # os.getenv returns None when the variable is unset.
        assert env_to_bool(None, default=True) is True
        assert env_to_bool(None, default=False) is False

    def test_whitespace_is_stripped(self):
        assert env_to_bool("  False  ", default=True) is False

    def test_regression_home_assistant_false_disables(self):
        # Regression for the bug where HOME_ASSISTANT=False (a non-empty string)
        # was always truthy, so HA discovery could never be disabled via env var.
        assert env_to_bool("False", default=True) is False
