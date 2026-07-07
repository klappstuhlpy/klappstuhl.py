from klappstuhl.enums import UpdateState
from klappstuhl.models import (
    ApiVersions,
    DeleteResult,
    ImageInfo,
    ImageUpdate,
    RateLimit,
    ScanReport,
    ShareResult,
    UploadResult,
)


def test_upload_result_properties():
    r = UploadResult.from_dict(
        {"total": 3, "errors": 1, "skipped": 0, "infected": 0, "links": ["a"], "raw_links": ["b"]}
    )
    assert r.successful == 2
    assert not r.is_success

    ok = UploadResult.from_dict({"total": 2, "errors": 0, "skipped": 0, "infected": 0,
                                 "links": ["a", "b"], "raw_links": ["c", "d"]})
    assert ok.is_success
    assert ok.successful == 2


def test_upload_result_tolerates_missing_keys():
    r = UploadResult.from_dict({"total": 1, "errors": 0})
    assert r.links == []
    assert r.raw_links == []
    assert r.infected == 0


def test_delete_result():
    r = DeleteResult.from_dict({"file": "abc", "failed": False})
    assert r.file == "abc"
    assert r.failed is False


def test_image_info():
    info = ImageInfo.from_dict(
        {"width": 32, "height": 24, "format": "png", "color": "Rgba8", "file_size": 1234}
    )
    assert info.width == 32 and info.height == 24
    assert info.format == "png"
    assert info.file_size == 1234


def test_share_result():
    s = ShareResult.from_dict({"id": "xyz", "url": "https://k.me/m/xyz", "content_type": "image/png"})
    assert s.id == "xyz"
    assert s.url.endswith("/m/xyz")


def test_scan_report_verdicts():
    clean = ScanReport.from_dict({"sha256": "d", "file_size": 10, "verdict": "clean"})
    assert clean.is_clean and not clean.is_infected

    bad = ScanReport.from_dict(
        {"sha256": "d", "file_size": 10, "verdict": "infected", "clamav_clean": False,
         "clamav_virus": "Eicar-Test", "vt_status": "detected", "vt_positives": 40, "vt_total": 70}
    )
    assert bad.is_infected
    assert bad.vt_positives == 40


def test_image_update_unknown_state_degrades():
    upd = ImageUpdate.from_dict(
        {"service": "web", "image": "nginx:latest", "state": "banana", "checked_at": 5}
    )
    assert upd.state is UpdateState.UNKNOWN

    upd2 = ImageUpdate.from_dict(
        {"service": "web", "image": "nginx:latest", "state": "update_available", "checked_at": 5}
    )
    assert upd2.state is UpdateState.UPDATE_AVAILABLE


def test_api_versions():
    v = ApiVersions.from_dict(
        {"current": "v1", "versions": [{"version": "v1", "status": "stable", "base_path": "/api/v1"}]}
    )
    assert v.current == "v1"
    assert v.versions[0].base_path == "/api/v1"


def test_rate_limit_from_headers():
    rl = RateLimit.from_headers(
        {"x-ratelimit-limit": "25", "x-ratelimit-remaining": "14",
         "x-ratelimit-reset": "1713373688", "x-ratelimit-reset-after": "0.98"}
    )
    assert rl is not None
    assert rl.limit == 25
    assert rl.remaining == 14
    assert rl.reset_after == 0.98

    assert RateLimit.from_headers({}) is None
