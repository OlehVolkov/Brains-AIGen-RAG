from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Sequence
from urllib import error, parse, request

from brain.shared import logger
from brain.config import BrainPaths


DEFAULT_NOTE_GLOBS = (
    "EN/Literature and Priorities.md",
    "UA/Література та пріоритети.md",
)

URL_PATTERN = re.compile(r"https?://[^\s<>\]\"']+")
FILENAME_PATTERN = re.compile(r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)\"?", re.IGNORECASE)
SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
PDF_HINT_PATTERN = re.compile(r"(^|[/?=&])pdf([=/&#.]|$)", re.IGNORECASE)


class PdfLinkHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.candidates: list[str] = []
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "meta":
            content = normalized.get("content", "")
            name = normalized.get("name", "").lower()
            prop = normalized.get("property", "").lower()
            if name in {"citation_pdf_url", "dc.identifier", "dc.relation.ispartof"}:
                self._add(content)
            elif prop in {"og:url", "og:see_also"} and ".pdf" in content.lower():
                self._add(content)
            return

        href = normalized.get("href", "")
        if not href:
            return
        rel = normalized.get("rel", "").lower()
        attr_type = normalized.get("type", "").lower()
        title = normalized.get("title", "").lower()
        if (
            ".pdf" in href.lower()
            or "application/pdf" in attr_type
            or "pdf" in rel
            or "pdf" in title
            or PDF_HINT_PATTERN.search(href)
        ):
            self._add(href)

    def _add(self, raw_url: str) -> None:
        if not raw_url:
            return
        candidate = _normalize_url(parse.urljoin(self.base_url, raw_url))
        if candidate and candidate not in self._seen:
            self._seen.add(candidate)
            self.candidates.append(candidate)


def list_source_note_paths(
    repo_root: Path,
    note_globs: Sequence[str] | None = None,
) -> list[Path]:
    patterns = tuple(note_globs or DEFAULT_NOTE_GLOBS)
    results: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches: list[Path] = []
        if any(token in pattern for token in "*?[]"):
            matches = sorted(
                path
                for path in repo_root.glob(pattern)
                if path.is_file() and path.suffix.lower() == ".md"
            )
        else:
            candidate = repo_root / pattern
            if candidate.is_file() and candidate.suffix.lower() == ".md":
                matches = [candidate]
        for match in matches:
            if match not in seen:
                seen.add(match)
                results.append(match)
    return results


def _normalize_url(raw_url: str) -> str:
    url = raw_url.strip().strip("<>")
    while url and url[-1] in ".,;:!?":
        url = url[:-1]
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1]
    return url


def extract_http_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in URL_PATTERN.findall(text):
        url = _normalize_url(match)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def candidate_pdf_urls(url: str) -> list[str]:
    candidates: list[str] = []
    parsed = parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    if host in {"arxiv.org", "www.arxiv.org"} and parsed.path.startswith("/abs/"):
        paper_id = parsed.path.removeprefix("/abs/")
        candidates.append(f"https://arxiv.org/abs/{paper_id}")
        candidates.append(f"https://arxiv.org/pdf/{paper_id}.pdf")
    if host in {"doi.org", "dx.doi.org"}:
        doi = path.lstrip("/")
        doi_lower = doi.lower()
        if doi_lower.startswith("10.48550/arxiv."):
            paper_id = doi.split("arXiv.", 1)[-1].split("arxiv.", 1)[-1]
            candidates.append(f"https://arxiv.org/abs/{paper_id}")
            candidates.append(f"https://arxiv.org/pdf/{paper_id}.pdf")
    if host in {"openreview.net", "www.openreview.net"} and parsed.path == "/forum":
        note_id = parse.parse_qs(parsed.query).get("id", [None])[0]
        if note_id:
            candidates.append(f"https://openreview.net/pdf?id={note_id}")
    candidates.append(url)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _header_value(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    value = headers.get(name, "")
    return value if isinstance(value, str) else str(value)


def is_pdf_response(*, final_url: str, content_type: str, content_disposition: str) -> bool:
    lowered_type = content_type.lower().split(";", 1)[0].strip()
    if lowered_type in {"application/pdf", "application/x-pdf"}:
        return True
    if ".pdf" in content_disposition.lower():
        return True
    return parse.urlparse(final_url).path.lower().endswith(".pdf")


def infer_pdf_filename(*, source_url: str, final_url: str, content_disposition: str) -> str:
    match = FILENAME_PATTERN.search(content_disposition)
    raw_name = ""
    if match:
        raw_name = parse.unquote(match.group(1) or match.group(2) or "")
    if not raw_name:
        final_name = Path(parse.urlparse(final_url).path).name
        source_name = Path(parse.urlparse(source_url).path).name
        raw_name = final_name or source_name or "download"
    raw_name = Path(raw_name).name
    stem = SANITIZE_PATTERN.sub("_", Path(raw_name).stem).strip("._") or "download"
    return stem[:160] + ".pdf"


def extract_pdf_urls_from_html(html: str, *, base_url: str) -> list[str]:
    parser = PdfLinkHTMLParser(base_url)
    parser.feed(html)
    parser.close()
    return parser.candidates


def _read_html_payload(response: Any, *, max_bytes: int = 1_000_000) -> str:
    payload = response.read(max_bytes)
    charset = "utf-8"
    content_type = _header_value(response.headers, "Content-Type")
    match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, re.IGNORECASE)
    if match:
        charset = match.group(1)
    return payload.decode(charset, errors="replace")


def unique_pdf_path(pdf_dir: Path, filename: str) -> Path:
    candidate = pdf_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        alternative = pdf_dir / f"{stem}-{counter}{suffix}"
        if not alternative.exists():
            return alternative
        counter += 1


def fetch_manifest_path(paths: BrainPaths) -> Path:
    return paths.index_root / "fetch_manifest.json"


def write_fetch_manifest(
    paths: BrainPaths,
    *,
    source_notes: Sequence[Path],
    requested_urls: Sequence[str],
    results: Sequence[dict[str, Any]],
) -> Path:
    paths.index_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_notes": [
            path.relative_to(paths.repo_root).as_posix()
            if path.is_relative_to(paths.repo_root)
            else str(path)
            for path in source_notes
        ],
        "requested_url_count": len(requested_urls),
        "result_count": len(results),
        "results": list(results),
    }
    manifest_path = fetch_manifest_path(paths)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def fetch_pdf_url(
    *,
    source_url: str,
    source_notes: Sequence[str],
    paths: BrainPaths,
    timeout: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    attempts: list[dict[str, str]] = []
    queue = list(candidate_pdf_urls(source_url))
    seen_candidates: set[str] = set()
    while queue:
        candidate_url = queue.pop(0)
        if candidate_url in seen_candidates:
            continue
        seen_candidates.add(candidate_url)
        try:
            req = request.Request(
                candidate_url,
                headers={
                    "User-Agent": "brain-pdf-fetch/0.1",
                    "Accept": "application/pdf,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                },
            )
            with request.urlopen(req, timeout=timeout) as response:
                final_url = response.geturl()
                content_type = _header_value(response.headers, "Content-Type")
                content_disposition = _header_value(response.headers, "Content-Disposition")
                if not is_pdf_response(
                    final_url=final_url,
                    content_type=content_type,
                    content_disposition=content_disposition,
                ):
                    html = _read_html_payload(response)
                    discovered_candidates = extract_pdf_urls_from_html(html, base_url=final_url)
                    new_candidates = [
                        discovered
                        for discovered in discovered_candidates
                        if discovered not in seen_candidates and discovered not in queue
                    ]
                    queue.extend(new_candidates)
                    message = f"content-type={content_type or 'unknown'}"
                    if new_candidates:
                        message += f"; discovered={len(new_candidates)}"
                    attempts.append(
                        {
                            "candidate_url": candidate_url,
                            "status": "not_pdf",
                            "message": message,
                        }
                    )
                    continue

                filename = infer_pdf_filename(
                    source_url=source_url,
                    final_url=final_url,
                    content_disposition=content_disposition,
                )
                target_path = paths.pdf_dir / filename
                if target_path.exists():
                    return {
                        "status": "exists",
                        "source_url": source_url,
                        "candidate_url": candidate_url,
                        "resolved_url": final_url,
                        "source_notes": list(source_notes),
                        "saved_path": target_path.relative_to(paths.repo_root).as_posix(),
                        "content_type": content_type,
                        "attempts": attempts,
                    }

                if dry_run:
                    return {
                        "status": "downloadable",
                        "source_url": source_url,
                        "candidate_url": candidate_url,
                        "resolved_url": final_url,
                        "source_notes": list(source_notes),
                        "saved_path": (paths.pdf_dir / filename).relative_to(paths.repo_root).as_posix(),
                        "content_type": content_type,
                        "attempts": attempts,
                    }

                paths.pdf_dir.mkdir(parents=True, exist_ok=True)
                final_path = unique_pdf_path(paths.pdf_dir, filename)
                with final_path.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
                logger.info("Downloaded PDF from {} to {}", final_url, final_path)
                return {
                    "status": "downloaded",
                    "source_url": source_url,
                    "candidate_url": candidate_url,
                    "resolved_url": final_url,
                    "source_notes": list(source_notes),
                    "saved_path": final_path.relative_to(paths.repo_root).as_posix(),
                    "content_type": content_type,
                    "attempts": attempts,
                }
        except error.HTTPError as exc:
            attempts.append(
                {
                    "candidate_url": candidate_url,
                    "status": "http_error",
                    "message": f"{exc.code} {exc.reason}",
                }
            )
        except error.URLError as exc:
            attempts.append(
                {
                    "candidate_url": candidate_url,
                    "status": "url_error",
                    "message": str(exc.reason),
                }
            )
        except Exception as exc:
            attempts.append(
                {
                    "candidate_url": candidate_url,
                    "status": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "status": "failed",
        "source_url": source_url,
        "source_notes": list(source_notes),
        "saved_path": None,
        "attempts": attempts,
    }


def fetch_pdfs_from_notes(
    paths: BrainPaths,
    *,
    note_globs: Sequence[str] | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    timeout: int = 20,
) -> dict[str, Any]:
    note_paths = list_source_note_paths(paths.repo_root, note_globs=note_globs)
    if not note_paths:
        raise ValueError("No matching literature notes were found.")

    urls_to_notes: dict[str, list[str]] = {}
    for note_path in note_paths:
        note_key = (
            note_path.relative_to(paths.repo_root).as_posix()
            if note_path.is_relative_to(paths.repo_root)
            else str(note_path)
        )
        for url in extract_http_urls(note_path.read_text(encoding="utf-8")):
            urls_to_notes.setdefault(url, []).append(note_key)

    requested_urls = list(urls_to_notes)
    if limit is not None and limit >= 0:
        requested_urls = requested_urls[:limit]

    results = [
        fetch_pdf_url(
            source_url=url,
            source_notes=urls_to_notes[url],
            paths=paths,
            timeout=timeout,
            dry_run=dry_run,
        )
        for url in requested_urls
    ]
    manifest_path = write_fetch_manifest(
        paths,
        source_notes=note_paths,
        requested_urls=requested_urls,
        results=results,
    )
    status_counts: dict[str, int] = {}
    for item in results:
        status = str(item["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "source_note_count": len(note_paths),
        "source_notes": [
            path.relative_to(paths.repo_root).as_posix()
            if path.is_relative_to(paths.repo_root)
            else str(path)
            for path in note_paths
        ],
        "requested_url_count": len(requested_urls),
        "dry_run": dry_run,
        "downloaded_count": status_counts.get("downloaded", 0),
        "downloadable_count": status_counts.get("downloadable", 0),
        "existing_count": status_counts.get("exists", 0),
        "failed_count": status_counts.get("failed", 0),
        "status_counts": status_counts,
        "manifest_path": str(manifest_path),
        "results": results,
    }
