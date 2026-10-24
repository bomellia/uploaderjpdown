"""Public uploader.jp backup: URL validation, discovery, and sequential browser downloads.

This module never attempts to circumvent passwords, CAPTCHAs, or rate limits.
Only hosts belonging to uploader.jp's known getuploader.com subdomains are allowed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

HOST_PATTERN = re.compile(r"^(?:ux|uu|u\d+)\.getuploader\.com$", re.I)
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
FILE_LINK = re.compile(r"^/([^/]+)/download/(\d+)/?$", re.I)
INDEX_LINK = re.compile(r"^/([^/]+)/index/date/desc/(\d+)/?$", re.I)
RESTRICTED_HTTP = {403, 429, 503}
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def allowed_host(hostname: str | None) -> bool:
    return bool(hostname and HOST_PATTERN.fullmatch(hostname))


def normalize_url(raw: str) -> tuple[str, str]:
    """Return (base URL, uploader slug), keeping the uploader's actual host."""
    try:
        p = urlparse(raw.strip())
        invalid = (
            p.scheme.lower() != "https"
            or not allowed_host(p.hostname)
            or p.username is not None
            or p.password is not None
            or p.port is not None
            or bool(p.query)
        )
    except ValueError as exc:
        raise ValueError("URLが不正です。") from exc
    if invalid:
        raise ValueError("https://u1.getuploader.com/<アップローダー名>/ などの公開URLを入力してください。")
    slug = p.path.strip("/").split("/")[0]
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("アップローダー名が不正です。")
    return f"https://{p.hostname.lower()}/{slug}/", slug


def is_file_href(href: str, slug: str, base: str) -> str | None:
    absolute = urljoin(base, href)
    p = urlparse(absolute)
    if p.scheme != "https" or not allowed_host(p.hostname) or p.username or p.password or p.port is not None:
        return None
    m = FILE_LINK.fullmatch(p.path)
    if not m or m.group(1) != slug or p.query:
        return None
    return f"https://{p.hostname.lower()}/{slug}/download/{m.group(2)}"


def parse_download_links(anchors: list[dict], slug: str, base: str) -> list[dict]:
    found: dict[str, dict] = {}
    for a in anchors:
        url = is_file_href(a.get("href") or "", slug, base)
        if url:
            ident = url.rsplit("/", 1)[-1]
            found.setdefault(ident, {"id": ident, "url": url, "label": (a.get("text") or "").strip()})
    return list(found.values())


def has_next_page(anchors: list[dict], slug: str, base: str, next_page: int) -> bool:
    for a in anchors:
        absolute = urljoin(base, a.get("href") or "")
        p = urlparse(absolute)
        m = INDEX_LINK.fullmatch(p.path)
        if p.scheme == "https" and allowed_host(p.hostname) and not p.query and m and m.group(1) == slug and int(m.group(2)) == next_page:
            return True
    return False


def safe_name(name: str, item_id: str) -> str:
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name or name.split(".")[0].upper() in RESERVED_NAMES:
        name = f"file_{item_id}_{name}"
    return name[:170].rstrip(" .") or f"file_{item_id}"


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def completed_file_valid(target: Path, record: dict) -> bool:
    if record.get("status") != "done" or not record.get("filename"):
        return False
    candidate = (target / record["filename"]).resolve()
    if not candidate.is_relative_to(target.resolve()) or not candidate.is_file():
        return False
    if candidate.stat().st_size <= 0 or candidate.stat().st_size != record.get("bytes"):
        return False
    recorded_hash = record.get("sha256")
    return recorded_hash is None or hash_file(candidate) == recorded_hash


def available_path(target: Path, preferred: str) -> Path:
    """Always reserve a new filename when one already exists; never overwrite user files."""
    candidate = target / preferred
    counter = 2
    while candidate.exists():
        name = Path(preferred)
        candidate = target / f"{name.stem} ({counter}){name.suffix}"
        counter += 1
    return candidate


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".manifest-", suffix=".tmp", delete=False) as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        temp_name = out.name
    os.replace(temp_name, path)


@dataclass
class BackupOptions:
    url: str
    folder: Path
    interval: float = 3.0
    max_pages: int = 300


class Cancelled(Exception):
    pass


def run_backup(opts: BackupOptions, emit, is_cancelled) -> None:
    """Run in a worker thread; navigate public site pages and click normal download controls."""
    from playwright.sync_api import sync_playwright

    base, slug = normalize_url(opts.url)
    if opts.interval < 2.0 or opts.max_pages < 1:
        raise ValueError("アクセス間隔は2秒以上、走査ページ数は1以上にしてください。")
    target = (opts.folder.expanduser().resolve() / slug)
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("uploader") != slug or manifest.get("source") not in (None, base):
                raise ValueError("別のアップローダーの管理ファイルが存在します。保存先を変更してください。")
            if not isinstance(manifest.get("files"), dict):
                raise ValueError("manifest.json の形式が不正です。")
        except json.JSONDecodeError as exc:
            raise ValueError("manifest.json が破損しています。バックアップしてから再実行してください。") from exc
    else:
        manifest = {"version": 2, "uploader": slug, "source": base, "files": {}}
    records = manifest["files"]

    def check() -> None:
        if is_cancelled():
            raise Cancelled()

    def verify_response(page, response) -> None:
        if response and response.status in RESTRICTED_HTTP:
            raise RuntimeError(f"アクセス制限（HTTP {response.status}）。処理を停止します。")
        if response and response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
        current = urlparse(page.url)
        if current.scheme != "https" or not allowed_host(current.hostname):
            raise RuntimeError("外部サイトへの遷移を検出したため停止しました。")
        if page.locator('input[name*=captcha i], iframe[src*=captcha i]').count():
            raise RuntimeError("CAPTCHAを検出したため停止しました。")

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="msedge", headless=True)
        except Exception as exc:
            raise RuntimeError("Microsoft Edgeを起動できません。インストールを確認してください。") from exc
        try:
            context = browser.new_context(accept_downloads=True, locale="ja-JP")
            context.set_default_timeout(20000)
            page = context.new_page()
            emit("status", "一覧ページを走査しています。")
            found: dict[str, dict] = {}
            for n in range(1, opts.max_pages + 1):
                check()
                response = page.goto(f"{base}index/date/desc/{n}", wait_until="domcontentloaded", timeout=30000)
                verify_response(page, response)
                anchors = page.locator("a[href]").evaluate_all("els => els.map(a => ({href:a.getAttribute('href'), text:a.textContent}))")
                items = parse_download_links(anchors, slug, page.url)
                for item in items:
                    found[item["id"]] = item
                emit("status", f"{n}ページを確認：{len(found)}件を検出")
                next_exists = has_next_page(anchors, slug, page.url, n + 1)
                if not next_exists:
                    break
                if n == opts.max_pages:
                    raise RuntimeError("最大走査ページ数に達しました。上限を増やして再実行してください。")
                time.sleep(opts.interval)

            emit("total", len(found))
            if not found:
                emit("status", "公開ファイルが見つかりませんでした。")
                return

            completed = failed = skipped = 0
            for i, item in enumerate(found.values(), start=1):
                check()
                ident = item["id"]
                old = records.get(ident, {})
                if completed_file_valid(target, old):
                    skipped += 1
                    emit("progress", (i, "skip", old["filename"]))
                    continue

                error = ""
                for attempt in range(2):
                    check()
                    try:
                        response = page.goto(item["url"], wait_until="domcontentloaded", timeout=30000)
                        verify_response(page, response)
                        control = page.get_by_role("button", name=re.compile("ダウンロード|Download", re.I))
                        if control.count() == 0:
                            control = page.locator('input[type="submit"][value*="ダウンロード"], input[type="submit"][value*="Download"]')
                        if control.count() == 0:
                            raise RuntimeError("ダウンロードボタンが見つかりません（保護ファイルまたはサイト変更）。")
                        with page.expect_download(timeout=45000) as pending:
                            control.first.click(timeout=15000)
                        download = pending.value
                        original_name = download.suggested_filename or item["label"]
                        filename = f"{ident}_{safe_name(original_name, ident)}"
                        destination = available_path(target, filename)
                        temp_path: Path | None = None
                        try:
                            with tempfile.NamedTemporaryFile(dir=target, prefix=f".{ident}-", suffix=".part", delete=False) as temp:
                                temp_path = Path(temp.name)
                            download.save_as(temp_path)
                            browser_failure = download.failure()
                            if browser_failure:
                                raise RuntimeError(f"ブラウザのダウンロード失敗：{browser_failure}")
                            size = temp_path.stat().st_size
                            if size == 0:
                                raise RuntimeError("空ファイルを受信しました。")
                            digest = hash_file(temp_path)
                            os.replace(temp_path, destination)
                        finally:
                            if temp_path is not None:
                                temp_path.unlink(missing_ok=True)
                        records[ident] = {
                            "url": item["url"], "status": "done", "filename": destination.name,
                            "original_name": original_name, "bytes": size, "sha256": digest,
                        }
                        atomic_json(manifest_path, manifest)
                        completed += 1
                        emit("progress", (i, "done", destination.name))
                        error = ""
                        break
                    except Exception as exc:
                        error = str(exc).splitlines()[0][:250]
                        if "アクセス制限" in error or "CAPTCHA" in error:
                            break
                        if attempt == 0:
                            time.sleep(opts.interval)

                if error:
                    records[ident] = {"url": item["url"], "status": "failed", "error": error}
                    atomic_json(manifest_path, manifest)
                    failed += 1
                    emit("progress", (i, "failed", f"{ident}: {error}"))
                    if "アクセス制限" in error or "CAPTCHA" in error:
                        raise RuntimeError(error)
                check()
                time.sleep(opts.interval)
            emit("status", f"完了：保存{completed}件、既存{skipped}件、失敗{failed}件。詳細はmanifest.jsonを確認してください。")
        finally:
            browser.close()
