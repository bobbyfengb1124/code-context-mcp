from ccctx.walk import MAX_BYTES, skip_reason


def test_skip_reasons():
    assert skip_reason("vendor/x/a.go", b"package x", 9) == "vendored"
    assert skip_reason("web/node_modules/a.js", b"x", 1) == "vendored"
    assert skip_reason("big.py", b"x", MAX_BYTES + 1) == "too large"
    assert skip_reason("img.png", b"\x89PNG\x00\x01", 6) == "binary"
    assert skip_reason("src/vendor.py", b"x = 1", 5) is None  # only directories count as vendored
