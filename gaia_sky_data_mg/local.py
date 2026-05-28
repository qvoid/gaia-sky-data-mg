import json
from pathlib import Path
from typing import List, Optional

from .dataset import Dataset

SPECIAL_DIRS = {'tmp', 'cache', 'procedural-planet-textures'}


def discover_local_datasets(data_path: Path) -> List[Dataset]:
    if not data_path.exists():
        return []

    datasets = []
    for item in sorted(data_path.iterdir()):
        if not item.is_dir():
            continue
        if item.name in SPECIAL_DIRS or item.name.startswith('.'):
            continue

        dataset_json = item / "dataset.json"
        if not dataset_json.exists():
            continue

        ds = read_local_dataset_json(dataset_json)
        if ds is not None:
            ds.installed = True
            ds.local_version = ds.version
            datasets.append(ds)

    return datasets


def read_local_dataset_json(dataset_json_path: Path) -> Optional[Dataset]:
    try:
        with open(dataset_json_path, 'r') as f:
            data = json.load(f)
        ds = Dataset.from_json(data)
        return ds
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return None


def cross_reference(local_datasets: List[Dataset], remote_datasets: List[Dataset]) -> List[Dataset]:
    remote_by_key = {ds.key: ds for ds in remote_datasets}

    for local_ds in local_datasets:
        remote_ds = remote_by_key.get(local_ds.key)
        if remote_ds is not None:
            local_ds.outdated = remote_ds.version > local_ds.version
            local_ds.version = remote_ds.version
            local_ds.size_bytes = remote_ds.size_bytes
            local_ds.type = remote_ds.type
            local_ds.description = remote_ds.description or local_ds.description
            local_ds.sha256 = remote_ds.sha256
            local_ds.file = remote_ds.file
            local_ds.check = remote_ds.check
            local_ds.replaces = remote_ds.replaces
            local_ds.replaced_by = remote_ds.replaced_by
            local_ds.min_gs_version = remote_ds.min_gs_version

    return local_datasets


def get_dataset_dir(data_path: Path, dataset_key: str) -> Optional[Path]:
    if not data_path.exists():
        return None
    for item in data_path.iterdir():
        if not item.is_dir():
            continue
        dataset_json = item / "dataset.json"
        if not dataset_json.exists():
            continue
        ds = read_local_dataset_json(dataset_json)
        if ds is not None and ds.key == dataset_key:
            return item
    return None


def find_local_dataset(data_path: Path, dataset_key: str) -> Optional[Dataset]:
    ds_dir = get_dataset_dir(data_path, dataset_key)
    if ds_dir is None:
        return None
    ds = read_local_dataset_json(ds_dir / "dataset.json")
    if ds is not None:
        ds.installed = True
        ds.local_version = ds.version
    return ds


def remove_dataset(data_path: Path, dataset_key: str) -> bool:
    import shutil
    ds_dir = get_dataset_dir(data_path, dataset_key)
    if ds_dir is None:
        return False
    shutil.rmtree(ds_dir)
    return True
