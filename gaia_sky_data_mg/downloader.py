import hashlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from .exceptions import DownloadError, ChecksumMismatchError
from .utils import format_progress_bar, human_readable_bytes

PART_FILE_MAX_AGE_SECONDS = 6 * 3600  # 6 hours


@dataclass
class DownloadResult:
    success: bool
    file_path: Path
    sha256: str = ""
    error: Optional[str] = None


def download_file(
    url: str,
    dest_dir: Path,
    filename: str,
    expected_sha256: Optional[str] = None,
    verbose: bool = False,
) -> DownloadResult:
    dest_dir.mkdir(parents=True, exist_ok=True)
    part_path = dest_dir / f"{filename}.part"

    start_size = 0
    if part_path.exists():
        file_age = time.time() - part_path.stat().st_mtime
        if file_age > PART_FILE_MAX_AGE_SECONDS:
            if verbose:
                print(f"  Stale partial file found (age: {file_age:.0f}s), removing...")
            part_path.unlink()
        else:
            start_size = part_path.stat().st_size
            if verbose:
                print(f"  Resuming from {human_readable_bytes(start_size)}...")

    headers = {}
    if start_size > 0:
        headers['Range'] = f'bytes={start_size}-'

    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
    except requests.RequestException as e:
        return DownloadResult(success=False, file_path=part_path, error=str(e))

    if resp.status_code == 416:
        if verbose:
            print("  Server cannot resume, restarting download...")
        part_path.unlink(missing_ok=True)
        start_size = 0
        headers.pop('Range', None)
        try:
            resp = requests.get(url, stream=True, timeout=30)
        except requests.RequestException as e:
            return DownloadResult(success=False, file_path=part_path, error=str(e))

    if resp.status_code not in (200, 206):
        return DownloadResult(
            success=False, file_path=part_path,
            error=f"HTTP {resp.status_code}"
        )

    total_size = int(resp.headers.get('Content-Length', 0))
    if resp.status_code == 206 and total_size > 0:
        content_range = resp.headers.get('Content-Range', '')
        if '/' in content_range:
            total_size = int(content_range.split('/')[1])
        else:
            total_size = start_size + total_size
    elif resp.status_code == 200:
        start_size = 0

    mode = 'ab' if start_size > 0 else 'wb'
    downloaded = start_size
    sha256_hash = hashlib.sha256()
    last_print = 0.0
    speed_samples = []

    try:
        with open(part_path, mode) as f:
            chunk_start = time.time()
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                f.write(chunk)
                sha256_hash.update(chunk)
                downloaded += len(chunk)

                now = time.time()
                elapsed = now - chunk_start
                if elapsed > 0:
                    speed = len(chunk) / elapsed
                    speed_samples.append(speed)
                    if len(speed_samples) > 20:
                        speed_samples.pop(0)

                if now - last_print >= 0.5:
                    avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0
                    bar = format_progress_bar(downloaded, total_size, avg_speed)
                    sys.stdout.write(f"\r{bar}")
                    sys.stdout.flush()
                    last_print = now

                chunk_start = time.time()
    except (requests.RequestException, IOError) as e:
        sys.stdout.write("\n")
        return DownloadResult(success=False, file_path=part_path, error=str(e))

    sys.stdout.write("\n")

    # If resumed, rehash the full file
    if start_size > 0:
        print("  Verifying checksum (full file)...")
        full_hash = _compute_file_sha256(part_path)
    else:
        full_hash = sha256_hash.hexdigest()

    if expected_sha256 and full_hash != expected_sha256.lower():
        raise ChecksumMismatchError(expected_sha256, full_hash)

    return DownloadResult(success=True, file_path=part_path, sha256=full_hash)


def _compute_file_sha256(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()
