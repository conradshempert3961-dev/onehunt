from miniapp.app import app


def test_miniapp_mounts_huntdriver() -> None:
    mount_paths = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            mount_paths.append(path)
        name = getattr(route, "name", None)
        if name == "huntdriver":
            assert path == "/huntdriver"

    assert "/huntdriver" in mount_paths

