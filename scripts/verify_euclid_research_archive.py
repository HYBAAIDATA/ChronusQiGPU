"""Verify the retained Notion research closure and posterity archive; never execute it.

Local integrity verification is not independent assurance or runtime integration.
The binary ZIP is base64-transported because the connector writes UTF-8 files.
"""
from pathlib import Path, PurePosixPath
import argparse
import base64
import hashlib
import io
import json
import re
import zipfile


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def bounded_path(root, relative):
    require(type(relative) is str, "path must be a string")
    p = PurePosixPath(relative)
    require(not p.is_absolute() and ".." not in p.parts and "\\" not in relative,
            "unsafe inventory path")
    result = root.joinpath(*p.parts)
    require(result.resolve().is_relative_to(root.resolve()), "inventory path escapes root")
    return result


def verify(root):
    folder = root / "docs/research_archive"
    inventory = json.loads((folder / "inventory.json").read_text())
    pages = inventory["pages"]
    ids = [p["id"] for p in pages]
    require(len(ids) == len(set(ids)), "duplicate page identity")
    for page in pages:
        require(page["status"] == "loaded" and page["truncated"] is False
                and page["unknown_block_ids"] == [], "incomplete page read")
        require(set(page["children"]) <= set(ids), "unresolved child-page reference")
        raw = bounded_path(root, page["repository_path"]).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == page["export_sha256"], "page export hash mismatch")
        require(len(raw) == page["export_bytes"], "page export length mismatch")
        require(not re.search(rb"(?i)X-Amz-(?:Security-Token|Signature|Credential)=", raw),
                "expiring attachment credential retained in note")
    artifact = json.loads((folder / "artifacts/posterity_inventory.json").read_text())
    encoded = bounded_path(root, artifact["transport_path"]).read_bytes()
    archive_bytes = base64.b64decode(b"".join(encoded.split()), validate=True)
    require(hashlib.sha256(archive_bytes).hexdigest() == artifact["archive_sha256"], "archive digest mismatch")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        infos = archive.infolist()
        require(len(infos) == len({p.filename for p in infos}), "duplicate archive member")
        require(len(infos) == artifact["zip_members"], "archive member count mismatch")
        for info in infos:
            path = PurePosixPath(info.filename)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in info.filename,
                    "unsafe archive member path")
            require(info.file_size <= 5_000_000, "oversized historical archive member")
        manifest_bytes = archive.read("EUCLID_POSTERITY_20260718/POSTERITY_MANIFEST.json")
        require(hashlib.sha256(manifest_bytes).hexdigest() == artifact["manifest_sha256"], "manifest digest mismatch")
        manifest = json.loads(manifest_bytes)
        require(set(manifest["files"]) == {r["member"] for r in artifact["members"]}, "manifest membership mismatch")
        for row in artifact["members"]:
            raw = archive.read("EUCLID_POSTERITY_20260718/" + row["member"])
            digest = hashlib.sha256(raw).hexdigest()
            require(digest == row["sha256"] and "sha256:" + digest == manifest["files"][row["member"]],
                    "historical manifest member mismatch")
            if "review_copy" in row:
                require(bounded_path(root, row["review_copy"]).read_bytes() == raw, "review copy differs")
    return {"scope": "LOCAL_ARCHIVAL_INTEGRITY_NOT_RUNTIME_OR_INDEPENDENT_QUALIFICATION",
            "page_count": len(pages), "unresolved_child_pages": 0,
            "attachment_references": len(inventory["attachment_references"]),
            "manifest_entries_verified": len(artifact["members"]),
            "archive_sha256": artifact["archive_sha256"],
            "all_workspace_sources_reconciled": inventory["all_workspace_sources_reconciled"],
            "all_attachments_recovered": inventory["all_attachments_recovered"],
            "historical_memory_loaded": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2))


if __name__ == "__main__":
    main()
