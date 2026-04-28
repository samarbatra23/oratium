import oratium


def test_package_importable() -> None:
    assert oratium is not None


def test_version_is_set() -> None:
    assert isinstance(oratium.__version__, str)
    assert oratium.__version__
