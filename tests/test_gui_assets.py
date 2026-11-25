from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="GUI dependency is not installed")

import gui_app
import token_cost


def test_version_has_single_source():
    assert gui_app.VERSION == token_cost.VERSION


def test_bundled_asset_path_resolves():
    icon = gui_app.resource("assets/app_icon.ico")
    assert icon.is_file()
    assert icon.stat().st_size > 0
