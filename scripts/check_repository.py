"""Check public documentation, archived results and the reviewed CPU examples."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

from sync_scoreboard import ROOT, summarize, rendered_documents


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def main():
    summary = read_json("data/results.json")
    raw = (ROOT / summary["source_file"]).read_bytes()
    require(summarize(raw, summary["source_file"]) == summary, "Generated results are stale")
    for doc, content in rendered_documents(summary).items():
        require((ROOT / doc).read_text(encoding="utf-8") == content, f"Stale scoreboard: {doc}")
    print("PASS: all five top tens, aggregate scores, tied ranks and rendered results")

    sources = read_json("data/sources.json")
    source_ids = {s["id"] for s in sources}
    require(len(source_ids) == len(sources), "Duplicate source IDs")
    for source in sources:
        require(bool(re.fullmatch(r"[0-9a-f]{64}", source["sha256"])), "Invalid source SHA256")
    packages = read_json("data/packages.json")
    package_ids = {p["id"] for p in packages}
    require(len(package_ids) == len(packages), "Duplicate package IDs")
    for package in packages:
        require(bool(re.fullmatch(r"[0-9a-f]{64}", package["zip_sha256"])), "Invalid ZIP SHA256")
        require(package["evidence_source"] in source_ids, "Missing package provenance")
        require(package["final_leaderboard_mapping"] == "unconfirmed", "Review final package mapping")
    measurements = read_json("data/measurements.json")
    for row in measurements:
        require(row["source_id"] in source_ids, "Missing measurement provenance")
        require(row["kind"] in {"local_device_history", "historical_official_report"}, "Unknown measurement kind")
        if row.get("package_id") is not None:
            require(row["package_id"] in package_ids, "Unknown package ID")
        if row.get("cases_us") is not None:
            require(len(row["cases_us"]) == 5, "Expected one complete five-case run")
            total = sum(Decimal(v) for v in row["cases_us"])
            require(total == Decimal(row["total_us"]), f"Five-case sum mismatch: {row['id']}")
    print(f"PASS: provenance references and {len(measurements)} historical measurement records")

    audit = read_json("data/concat-p07-audit.json")
    p07 = next(p for p in packages if p["id"] == audit["package_id"])
    require(audit["zip_sha256"] == p07["zip_sha256"], "P07 audit ZIP mismatch")
    for item in audit["source_and_build_files"]:
        require(item["matches_frozen_file"] and
                p07["source_members_sha256"][item["member"]] == item["sha256"],
                "P07 frozen source identity mismatch")
    installer = audit["installer"]
    require(installer["matches_frozen_file"] and
            p07["installer_members_sha256"][installer["member"]] == installer["sha256"],
            "P07 frozen installer identity mismatch")
    p07_run = next(m for m in measurements if m["id"] == "concat-p07-original")
    require(p07_run["total_us"] == audit["recorded_total_us"], "P07 audit timing mismatch")

    article_manifest = read_json("data/articles.json")
    require(len({a['path'] for a in article_manifest}) == len(article_manifest), "Duplicate articles")
    blocks = 0
    for article in article_manifest:
        path = ROOT / article["path"]
        require(hashlib.sha256(path.read_bytes()).hexdigest() == article["content_sha256"],
                f"Article content hash changed: {article['path']}")
        content = path.read_text(encoding="utf-8")
        for i, code in enumerate(re.findall(r"```python\s*\n(.*?)```", content, re.S), 1):
            # These are the reviewed, self-contained standard-library models in the articles.
            result = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", code],
                                    capture_output=True, text=True, encoding="utf-8", timeout=20)
            require(result.returncode == 0,
                    f"CPU model failed: {article['path']} block {i}\n{result.stderr}")
            blocks += 1
    print(f"PASS: {len(article_manifest)} article hashes and {blocks} CPU models (no NPU execution)")

    links = 0
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts or ".local" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        require(not re.search(r"[A-Z]:\\|/home/ma-user/|-----BEGIN .*PRIVATE KEY-----", content),
                f"Machine-local or credential material in {path.relative_to(ROOT)}")
        prose = re.sub(r"```.*?```", "", content, flags=re.S)
        for target in re.findall(r"\]\(([^)]+)\)", prose):
            target = target.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            dest = (path.parent / unquote(parsed.path)).resolve()
            require(dest.is_relative_to(ROOT), f"Link leaves repository: {path} -> {target}")
            require(dest.exists(), f"Broken local link: {path.relative_to(ROOT)} -> {target}")
            links += 1
    print(f"PASS: {links} local Markdown file links; external URLs are not fetched")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
