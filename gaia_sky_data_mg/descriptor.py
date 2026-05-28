import gzip
import json
import sys
import time
from pathlib import Path
from typing import Optional, List

import requests

from .config import Config, DESCRIPTOR_URL_TEMPLATE
from .dataset import Dataset
from .exceptions import DescriptorFetchError, DescriptorParseError
from .utils import version_to_zero_padded, version_string_to_int

MIN_GS_VERSION = 3030100
DESCRIPTOR_DISCOVERY_CACHE = "descriptor_url_cache.json"
TAGS_API_URL = "https://codeberg.org/api/v1/repos/gaiasky/gaiasky/tags"


class Descriptor:
    def __init__(self, recommended: List[str], datasets: List[Dataset]):
        self.recommended = recommended
        self.datasets = datasets

    def find_by_key(self, key: str) -> Optional[Dataset]:
        for ds in self.datasets:
            if ds.key == key:
                return ds
        return None

    def search(self, keyword: str) -> List[Dataset]:
        kw = keyword.lower()
        results = []
        for ds in self.datasets:
            if (kw in ds.key.lower() or kw in ds.name.lower() or
                    (ds.description and kw in ds.description.lower()) or
                    kw in ds.type.lower()):
                results.append(ds)
        return results


def _resolve_descriptor_url(config: Config) -> str:
    if config.descriptor_url:
        return config.descriptor_url

    # try dynamic discovery
    discovered = _discover_descriptor_url(config)
    if discovered:
        return discovered

    # fallback to configured version
    version_str = version_to_zero_padded(config.gaia_sky_version)
    return DESCRIPTOR_URL_TEMPLATE.format(version=version_str)


def _discover_descriptor_url(config: Config) -> Optional[str]:
    cache_dir = config.get_cache_dir()
    url_cache_file = cache_dir / DESCRIPTOR_DISCOVERY_CACHE

    # check if we already discovered a valid URL recently (cache for 24h)
    if url_cache_file.exists():
        try:
            with open(url_cache_file, 'r') as f:
                cached = json.load(f)
            if time.time() - cached.get('discover_time', 0) < 86400:
                url = cached.get('url')
                if url:
                    return url
        except (json.JSONDecodeError, OSError):
            pass

    # step 1: fetch version tags from Codeberg API
    tags = _fetch_version_tags()
    if not tags:
        return None

    # step 2: generate candidate version integers from tags
    candidates = []
    for tag in tags:
        name = tag.get('name', '')
        try:
            ver_int = version_string_to_int(name)
            if ver_int >= MIN_GS_VERSION:
                candidates.append(ver_int)
        except (ValueError, IndexError):
            continue

    # add configured version as last resort candidate
    candidates.append(config.gaia_sky_version)
    candidates = sorted(set(candidates), reverse=True)

    # step 3: probe each candidate
    for ver in candidates:
        version_str = version_to_zero_padded(ver)
        url = DESCRIPTOR_URL_TEMPLATE.format(version=version_str)
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                # cache the discovered URL
                cache_dir.mkdir(parents=True, exist_ok=True)
                with open(url_cache_file, 'w') as f:
                    json.dump({
                        'url': url,
                        'version': ver,
                        'discover_time': time.time(),
                    }, f)
                return url
        except requests.RequestException:
            continue

    return None


def _fetch_version_tags() -> list:
    try:
        resp = requests.get(TAGS_API_URL, timeout=15)
        resp.raise_for_status()
        tags = resp.json()
        if isinstance(tags, list):
            return tags
    except (requests.RequestException, json.JSONDecodeError):
        pass
    return []


def fetch_descriptor(config: Config, force_refresh: bool = False) -> Descriptor:
    cache_dir = config.get_cache_dir()
    cache_file = cache_dir / "descriptor_cache.json"
    meta_file = cache_dir / "descriptor_cache_meta.json"

    if not force_refresh and cache_file.exists():
        try:
            with open(meta_file, 'r') as f:
                meta = json.load(f)
            fetch_time = meta.get('fetch_time', 0)
            if time.time() - fetch_time < config.cache_ttl_seconds:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                return _parse_descriptor(data)
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    url = _resolve_descriptor_url(config)
    data = _fetch_remote(url)

    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(data, f)
    with open(meta_file, 'w') as f:
        json.dump({'fetch_time': time.time(), 'url': url}, f)

    return _parse_descriptor(data)


def _fetch_remote(url: str) -> dict:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise DescriptorFetchError(f"Failed to fetch descriptor from {url}: {e}")

    try:
        decompressed = gzip.decompress(resp.content)
        return json.loads(decompressed)
    except (gzip.BadGzipFile, json.JSONDecodeError) as e:
        raise DescriptorFetchError(f"Failed to decompress/parse descriptor: {e}")


def _parse_descriptor(data: dict) -> Descriptor:
    recommended = data.get('recommended', [])
    files_raw = data.get('files', [])

    if not isinstance(files_raw, list):
        raise DescriptorParseError("Descriptor 'files' is not a list")

    datasets_by_key = {}
    for entry in files_raw:
        if not isinstance(entry, dict):
            continue
        try:
            ds = Dataset.from_json(entry)
        except (ValueError, TypeError, KeyError):
            continue

        if ds.min_gs_version < MIN_GS_VERSION:
            continue
        if not ds.key:
            continue

        if ds.key in datasets_by_key:
            existing = datasets_by_key[ds.key]
            if ds.version > existing.version:
                datasets_by_key[ds.key] = ds
        else:
            datasets_by_key[ds.key] = ds

    datasets = list(datasets_by_key.values())
    for ds in datasets:
        if ds.replaces:
            for replaced_key in ds.replaces:
                replaced = datasets_by_key.get(replaced_key)
                if replaced and not replaced.replaced_by:
                    replaced.replaced_by = ds.key

    return Descriptor(recommended=recommended, datasets=datasets)
