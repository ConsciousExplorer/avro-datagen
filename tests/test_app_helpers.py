"""Tests for pure helpers in the Streamlit app module.

Importing `avro_datagen.app` executes the page top-to-bottom, which Streamlit
supports in "bare mode" — it logs a missing-ScriptRunContext warning and carries
on. That is enough to reach the module-level helpers.
"""

import pytest

streamlit = pytest.importorskip("streamlit")

from avro_datagen import app  # noqa: E402


class TestSaveDirWritable:
    """Read-only schema dirs are a supported setup, not a crash (issue #19)."""

    def test_existing_writable_dir(self, tmp_path):
        assert app._save_dir_writable(tmp_path) is True

    def test_read_only_dir(self, tmp_path):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o555)
        try:
            assert app._save_dir_writable(ro) is False
        finally:
            ro.chmod(0o755)

    def test_missing_dir_under_writable_parent(self, tmp_path):
        """The default `schemas` dir often does not exist — mkdir will create it."""
        assert app._save_dir_writable(tmp_path / "schemas") is True

    def test_missing_dir_under_read_only_parent(self, tmp_path):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o555)
        try:
            assert app._save_dir_writable(ro / "schemas") is False
        finally:
            ro.chmod(0o755)

    def test_defaults_to_save_dir(self):
        assert app._save_dir_writable() == app._save_dir_writable(app.SAVE_DIR)


class TestJsonFormatToggle:
    def test_defaults_to_wire(self):
        streamlit.session_state.pop("json_format", None)
        assert app._human_json_selected() is False

    def test_human_selected(self):
        streamlit.session_state["json_format"] = "Human"
        try:
            assert app._human_json_selected() is True
        finally:
            streamlit.session_state.pop("json_format", None)

    def test_format_record_passes_through_in_wire_mode(self):
        streamlit.session_state.pop("json_format", None)
        schema = {
            "type": "record",
            "name": "T",
            "fields": [{"name": "ts", "type": {"type": "long", "logicalType": "timestamp-millis"}}],
        }
        record = {"ts": 0}
        assert app._format_record(record, schema) == {"ts": 0}

    def test_format_record_humanizes_when_selected(self):
        streamlit.session_state["json_format"] = "Human"
        try:
            schema = {
                "type": "record",
                "name": "T",
                "fields": [
                    {"name": "ts", "type": {"type": "long", "logicalType": "timestamp-millis"}}
                ],
            }
            assert app._format_record({"ts": 0}, schema) == {"ts": "1970-01-01T00:00:00.000Z"}
        finally:
            streamlit.session_state.pop("json_format", None)
