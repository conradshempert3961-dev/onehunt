from huntdriver import data
from huntdriver.app import app


def test_data_has_core_entities() -> None:
    assert len(data.DISTRICTS) >= 1
    assert len(data.HUNTER_BIDS) >= 1
    assert len(data.ESTATE_APPLICATIONS) >= 1
    assert len(data.DOCUMENT_SECTIONS) >= 1


def test_app_routes_registered() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/health" in paths
    assert "/hunter/" in paths
    assert "/trophy/" in paths
    assert "/api/hunter/bids" in paths
    assert "/api/trophy/documents" in paths


def test_static_files_exist() -> None:
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "huntdriver" / "static"
    assert (base / "index.html").is_file()
    assert (base / "hunter" / "index.html").is_file()
    assert (base / "trophy" / "index.html").is_file()
    assert (base / "assets" / "css" / "app.css").is_file()
