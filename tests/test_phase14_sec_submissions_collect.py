from __future__ import annotations

import hashlib
import json

import pytest

from scripts import phase14_sec_submissions_collect as collector


CIK = "0000000123"
OTHER_CIK = "0000000456"


def _document(*, cik=CIK, archive=True):
    name = f"CIK{cik}-submissions-001.json"
    return {
        "cik": int(cik),
        "filings": {
            "recent": _filings("2025-08-09", f"{cik}-25-000001"),
            "files": [{"name": name}] if archive else [],
        },
    }


def _filings(date, accession):
    return {
        "accessionNumber": [accession],
        "acceptanceDateTime": [date + "T18:00:00Z"],
        "form": ["10-Q"],
        "filingDate": [date],
    }


def _archive():
    return _filings("2013-08-09", f"{CIK}-13-000001")


def test_default_dry_run_writes_nothing_does_not_need_user_agent(tmp_path, monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    out = tmp_path / "sec"
    result = collector.collect([CIK], out)
    assert result["status"] == "DRY_RUN_ONLY"
    assert not out.exists()


def test_one_issuer_root_and_archival_resumes_with_sha_and_quota(tmp_path, monkeypatch):
    calls = []
    originals = {
        f"CIK{CIK}.json": json.dumps(_document()).encode(),
        f"CIK{CIK}-submissions-001.json": json.dumps(_archive()).encode(),
    }

    def fake_download(name, ua):
        calls.append((name, ua))
        return originals[name]
    monkeypatch.setattr(collector, "_fetch_sec_document", fake_download)
    out = tmp_path / "evidence"
    first = collector.collect([CIK], out, execute=True,
                              user_agent="Meridyen Financial Research owner@valid.org")
    assert first["status"] == "COMPLETE_SOURCE_DOWNLOADS_NOT_PIT_CERTIFIED"
    assert first["files_downloaded"] == 2
    assert first["requests_reserved_this_run"] == 2
    assert first["canonical_pit_certified"] is False
    assert first["sqlite_modified"] is False
    saved = json.loads((out / "sec_sources_manifest.json").read_text())
    assert saved["documents"][f"CIK{CIK}.json"]["sha256"] == hashlib.sha256(
        originals[f"CIK{CIK}.json"]
    ).hexdigest()
    assert saved["documents"][f"CIK{CIK}.json"]["source_authenticity_independently_verified"] is False
    assert len(calls) == 2
    second = collector.collect([CIK], out, execute=True,
                               user_agent="Meridyen Financial Research owner@valid.org")
    assert second["files_reused"] == 2
    assert second["requests_reserved_this_run"] == 0
    assert len(calls) == 2
    budget = json.loads((out / "sec_utc_request_budget.json").read_text())
    assert budget["attempts"] == 2


def test_small_run_quota_stops_and_resumes_just_missing_archive(tmp_path, monkeypatch):
    calls = []
    def fake_download(name, _ua):
        calls.append(name)
        return json.dumps(
            _document() if name == f"CIK{CIK}.json" else _archive()
        ).encode()
    monkeypatch.setattr(collector, "_fetch_sec_document", fake_download)
    out = tmp_path / "sec"
    first = collector.collect([CIK], out, execute=True, max_requests=1,
                              user_agent="Meridyen Equity owner@valid.org")
    assert first["status"] == "STOPPED_REVIEW_REQUIRED"
    assert first["error_code"] == "SEC_RUN_REQUEST_BUDGET_EXHAUSTED"
    assert first["files_downloaded"] == 1
    assert len(calls) == 1
    second = collector.collect([CIK], out, execute=True, max_requests=1,
                               user_agent="Meridyen Equity owner@valid.org")
    assert second["status"] == "COMPLETE_SOURCE_DOWNLOADS_NOT_PIT_CERTIFIED"
    assert second["files_downloaded"] == 1
    assert second["files_reused"] == 1
    assert len(calls) == 2


def test_remote_policy_429_stops_no_retries(tmp_path, monkeypatch):
    calls = []
    def denied(name, _ua):
        calls.append(name)
        raise collector.CollectorBlocked("SEC_ACCESS_POLICY_OR_LIMIT_429")
    monkeypatch.setattr(collector, "_fetch_sec_document", denied)
    out = tmp_path / "sec"
    report = collector.collect([CIK], out, execute=True,
                               user_agent="Meridyen Equity owner@valid.org")
    assert report["status"] == "STOPPED_REVIEW_REQUIRED"
    assert report["error_code"] == "SEC_ACCESS_POLICY_OR_LIMIT_429"
    assert report["requests_reserved_this_run"] == 1
    assert len(calls) == 1
    assert not (out / f"CIK{CIK}.json").exists()
    assert not (out / ".phase14_sec_submissions_collect.lock").exists()


def test_persistent_daily_quota_stops_even_if_new_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        collector, "_fetch_sec_document",
        lambda name, ua: json.dumps(_document()).encode(),
    )
    out = tmp_path / "sec"
    first = collector.collect([CIK], out, execute=True, max_requests=1,
                              daily_budget=1,
                              user_agent="Meridyen Equity owner@valid.org")
    assert first["files_downloaded"] == 1
    second = collector.collect([CIK], out, execute=True, max_requests=20,
                               daily_budget=1,
                               user_agent="Meridyen Equity owner@valid.org")
    assert second["error_code"] == "SEC_LOCAL_DAILY_BUDGET_EXHAUSTED"
    assert second["files_reused"] == 1
    assert second["requests_reserved_this_run"] == 0


def test_archive_traversal_and_wrong_cik_rejected_without_network(tmp_path, monkeypatch):
    def invalid_root(name, _ua):
        root = _document()
        root["filings"]["files"] = [{"name": "../secrets.json"}]
        return json.dumps(root).encode()
    monkeypatch.setattr(collector, "_fetch_sec_document", invalid_root)
    out = tmp_path / "sec"
    report = collector.collect([CIK], out, execute=True,
                               user_agent="Meridyen Equity owner@valid.org")
    assert report["error_code"] == "SEC_ARCHIVE_FILENAME_INVALID"
    assert not (tmp_path / "secrets.json").exists()
    assert report["files_downloaded"] == 1
    assert report["files_reused"] == 0

    with pytest.raises(collector.CollectorBlocked, match="CIK_MISMATCH"):
        collector._validate_document(
            json.dumps(_document(cik=OTHER_CIK)).encode(),
            f"CIK{CIK}.json", expected_cik=CIK
        )


def test_saved_source_tampering_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "_fetch_sec_document",
                        lambda name, ua: json.dumps(_document(archive=False)).encode())
    out = tmp_path / "sec"
    collector.collect([CIK], out, execute=True,
                      user_agent="Meridyen Equity owner@valid.org")
    target = out / f"CIK{CIK}.json"
    tampered = json.dumps(_document(archive=True)).encode()
    target.write_bytes(tampered)
    report = collector.collect([CIK], out, execute=True,
                               user_agent="Meridyen Equity owner@valid.org")
    assert report["status"] == "STOPPED_REVIEW_REQUIRED"
    assert report["error_code"] == "SEC_SAVED_SOURCE_HASH_MISMATCH"
    assert target.read_bytes() == tampered


def test_no_unsafe_user_agent_or_second_process(tmp_path, monkeypatch):
    for ua in ("AutomatedM10", "Meridyen admin@example.com",
               "Company foo@valid.org\nCRLF"):
        with pytest.raises(ValueError):
            collector._validate_user_agent(ua)
    folder = tmp_path / "sec"
    folder.mkdir()
    lock = folder / ".phase14_sec_submissions_collect.lock"
    lock.write_text('{"pid":123}')
    result = collector.collect([CIK], folder, execute=False)
    assert result["status"] == "DRY_RUN_ONLY"
    with pytest.raises(collector.CollectorBlocked, match="ALREADY_LOCKED"):
        collector.collect([CIK], folder, execute=True,
                          user_agent="Meridyen Equity owner@valid.org")
    assert lock.exists()


def test_existing_json_without_manifest_is_reused_without_provenance_claim(tmp_path):
    folder = tmp_path / "sec"
    folder.mkdir()
    (folder / f"CIK{CIK}.json").write_text(json.dumps(_document(archive=False)))
    result = collector.collect([CIK], folder, execute=True,
                               user_agent="Meridyen Equity owner@valid.org")
    assert result["files_downloaded"] == 0
    assert result["files_reused"] == 1
    record = json.loads((folder / "sec_sources_manifest.json").read_text())[
        "documents"][f"CIK{CIK}.json"]
    assert record["origin"] == "PREEXISTING_LOCAL_SOURCE_NOT_VERIFIED"


def test_output_inside_git_repository_rejected(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(collector.CollectorBlocked, match="OUTSIDE_GIT_REPO"):
        collector.collect([CIK], tmp_path / "sources")


def test_httpx_redirect_and_policy_are_fail_closed(monkeypatch):
    # httpx.MockTransport ensures there are no real SEC requests.
    statuses = [302, 403, 429, 503, 404]
    for status in statuses:
        def transport_handler(request, *, http_status=status):
            assert request.url.host == "data.sec.gov"
            return __import__("httpx").Response(
                http_status, text="Denied", request=request
            )
        import httpx
        real_client = httpx.Client
        monkeypatch.setattr(
            collector.httpx, "Client",
            lambda *args, **kwargs: real_client(
                transport=httpx.MockTransport(transport_handler),
                follow_redirects=False,
            ),
        )
        with pytest.raises(collector.CollectorBlocked, match="SEC_"):
            collector._fetch_sec_document(
                f"CIK{CIK}.json", "Meridyen Equity owner@valid.org"
            )
