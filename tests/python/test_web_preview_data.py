from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML_PATH = ROOT / "audioqas" / "web" / "static" / "web-preview.html"
DATA_PATH = ROOT / "audioqas" / "web" / "static" / "web-preview-data.js"


def test_web_preview_uses_shared_data_file():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'location.protocol === "file:" ? "." : "/static-preview"' in html
    assert 'web-preview-data.js?v=' in html
    assert 'web-preview-app.js?v=' in html


def test_web_preview_data_file_exists():
    assert DATA_PATH.exists()
    text = DATA_PATH.read_text(encoding="utf-8")
    assert "compareData" in text
    assert "detailColumns" in text
    assert "modelContent" in text


def test_web_preview_no_duplicate_local_compare_group_defs():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert html.count("const compareGroupDefs =") == 0
    assert "const state = {" not in html


def test_web_preview_html_uses_fresh_asset_version_strategy():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'const assetVersion = location.protocol === "file:"' in html
    assert ': "2026-05-21-compare-upload-cards";' in html
    assert "String(Date.now())" in html
