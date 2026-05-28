import os
import shutil
import sys
from pathlib import Path

from .config import Config
from .descriptor import Descriptor, fetch_descriptor
from .dataset import Dataset
from .local import (
    discover_local_datasets, cross_reference,
    find_local_dataset, get_dataset_dir, remove_dataset,
)
from .downloader import download_file, DownloadResult
from .extractor import extract_tar_gz
from .exceptions import (
    DatasetNotFoundError, DownloadError, ChecksumMismatchError,
    ExtractionError, DescriptorFetchError,
)
from .utils import (
    human_readable_bytes, human_readable_nobjects,
    version_int_to_string, confirm_prompt, format_table,
)


def cmd_update(config: Config, args) -> int:
    try:
        desc = fetch_descriptor(config, force_refresh=args.no_cache)
    except DescriptorFetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    data_path = config.get_data_path()
    local_datasets = discover_local_datasets(data_path)
    cross_referenced = cross_reference(local_datasets, desc.datasets)

    updates = [ds for ds in cross_referenced if ds.outdated]

    if not updates:
        print("All datasets are up to date.")
        return 0

    headers = ["KEY", "NAME", "LOCAL VER", "REMOTE VER", "SIZE"]
    rows = []
    for ds in updates:
        rows.append([
            ds.key,
            ds.name,
            str(ds.local_version),
            str(ds.version),
            ds.display_size(),
        ])

    print(f"Updates available for {len(updates)} dataset(s):\n")
    print(format_table(headers, rows))
    return 0


def cmd_list(config: Config, args) -> int:
    data_path = config.get_data_path()

    if getattr(args, 'available', False):
        return _list_available(config, args)
    else:
        return _list_local(config, args)


def _list_local(config: Config, args) -> int:
    data_path = config.get_data_path()
    local_datasets = discover_local_datasets(data_path)

    if not local_datasets:
        print(f"No datasets found in {data_path}")
        print("Use 'list --available' to see downloadable datasets.")
        return 0

    # try cross-reference with remote
    try:
        desc = fetch_descriptor(config, force_refresh=args.no_cache)
        cross_referenced = cross_reference(local_datasets, desc.datasets)
    except DescriptorFetchError:
        cross_referenced = local_datasets

    headers = ["KEY", "NAME", "VERSION", "SIZE", "TYPE", "STATUS"]
    rows = []
    for ds in cross_referenced:
        if ds.outdated:
            status = f"update available (v{ds.version})"
        else:
            status = "installed"
        rows.append([
            ds.key, ds.name,
            str(ds.local_version) if ds.local_version >= 0 else str(ds.version),
            ds.display_size(),
            ds.type,
            status,
        ])

    print(format_table(headers, rows))
    return 0


def _list_available(config: Config, args) -> int:
    try:
        desc = fetch_descriptor(config, force_refresh=args.no_cache)
    except DescriptorFetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    data_path = config.get_data_path()
    local_datasets = discover_local_datasets(data_path)
    local_keys = {ds.key for ds in local_datasets}
    local_versions = {ds.key: ds.version for ds in local_datasets}

    headers = ["KEY", "NAME", "VERSION", "SIZE", "TYPE", "STATUS"]
    rows = []
    for ds in desc.datasets:
        if ds.key in local_keys:
            if ds.version > local_versions.get(ds.key, 0):
                status = "upgradable"
            else:
                status = "installed"
        else:
            status = "available"
        rows.append([ds.key, ds.name, str(ds.version), ds.display_size(), ds.type, status])

    print(format_table(headers, rows))
    return 0


def cmd_info(config: Config, args) -> int:
    package = args.package

    # try remote first
    ds = None
    source = None
    try:
        desc = fetch_descriptor(config, force_refresh=args.no_cache)
        ds = desc.find_by_key(package)
        if ds:
            source = "remote"
    except DescriptorFetchError:
        pass

    # try local
    data_path = config.get_data_path()
    local_ds = find_local_dataset(data_path, package)
    if local_ds:
        if ds is None:
            ds = local_ds
            source = "local"
        else:
            # merge local info
            ds.installed = True
            ds.local_version = local_ds.version

    if ds is None:
        print(f"Dataset '{package}' not found.", file=sys.stderr)
        print("Use 'search' to find available datasets.", file=sys.stderr)
        return 1

    # display
    print(f"Dataset: {ds.name}")
    print(f"  Key:            {ds.key}")
    print(f"  Type:           {ds.type}")
    ver_str = str(ds.version)
    if ds.installed and ds.local_version >= 0:
        ver_str += f" (installed: {ds.local_version})"
        if ds.local_version < ds.version:
            ver_str += " [UPDATE AVAILABLE]"
    print(f"  Version:        {ver_str}")
    print(f"  Min GS version: {version_int_to_string(ds.min_gs_version)}")
    print(f"  Size:           {ds.display_size()}")
    if ds.n_objects >= 0:
        print(f"  Objects:        {ds.n_objects:,}")
    if ds.sha256:
        print(f"  SHA-256:        {ds.sha256}")
    if ds.creator:
        print(f"  Creator:        {ds.creator}")
    if ds.credits:
        print(f"  Credits:        {', '.join(ds.credits)}")
    if ds.description:
        print(f"  Description:    {ds.description}")
    if ds.links:
        print(f"  Links:")
        for link in ds.links:
            resolved = link.replace('@mirror-url@', config.mirror_url)
            print(f"    - {resolved}")
    if ds.replaces:
        print(f"  Replaces:       {', '.join(ds.replaces)}")
    if ds.replaced_by:
        print(f"  Replaced by:    {ds.replaced_by}")
    if ds.release_notes:
        print(f"  Release notes:")
        for note in ds.release_notes:
            print(f"    - {note}")
    if ds.file:
        print(f"  Download URL:   {ds.resolve_url(config.mirror_url)}")

    return 0


def cmd_search(config: Config, args) -> int:
    try:
        desc = fetch_descriptor(config, force_refresh=args.no_cache)
    except DescriptorFetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    results = desc.search(args.keyword)
    if not results:
        print(f"No datasets matching '{args.keyword}'.")
        return 0

    headers = ["KEY", "NAME", "VERSION", "SIZE", "TYPE"]
    rows = [[ds.key, ds.name, str(ds.version), ds.display_size(), ds.type] for ds in results]
    print(f"Found {len(results)} dataset(s):\n")
    print(format_table(headers, rows))
    return 0


def cmd_download(config: Config, args) -> int:
    package = args.package

    try:
        desc = fetch_descriptor(config, force_refresh=args.no_cache)
    except DescriptorFetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    ds = desc.find_by_key(package)
    if ds is None:
        print(f"Dataset '{package}' not found in remote catalog.", file=sys.stderr)
        print("Use 'search' to find available datasets.", file=sys.stderr)
        return 1

    data_path = config.get_data_path()
    local_ds = find_local_dataset(data_path, package)
    if local_ds is not None:
        if local_ds.version == ds.version:
            print(f"Dataset '{package}' v{ds.version} is already installed.")
            return 0
        else:
            print(f"Dataset '{package}' is installed (v{local_ds.version}), remote version is v{ds.version}.")
            if not confirm_prompt("Overwrite local version?"):
                print("Cancelled.")
                return 0
            ds_dir = get_dataset_dir(data_path, package)
            if ds_dir:
                shutil.rmtree(ds_dir)
                print(f"  Removed old version.")

    return _do_download(config, ds, args.verbose)


def cmd_upgrade(config: Config, args) -> int:
    if getattr(args, 'all', False):
        return _cmd_upgrade_all(config, args)
    elif args.package:
        return _cmd_upgrade_one(config, args)
    else:
        print("Error: specify a package name or use --all", file=sys.stderr)
        return 2


def _cmd_upgrade_one(config: Config, args) -> int:
    package = args.package

    try:
        desc = fetch_descriptor(config, force_refresh=args.no_cache)
    except DescriptorFetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    data_path = config.get_data_path()
    local_ds = find_local_dataset(data_path, package)
    if local_ds is None:
        print(f"Dataset '{package}' is not installed. Use 'download' to install it.", file=sys.stderr)
        return 1

    remote_ds = desc.find_by_key(package)
    if remote_ds is None:
        print(f"Dataset '{package}' not found in remote catalog.", file=sys.stderr)
        return 1

    if remote_ds.version <= local_ds.version:
        print(f"Dataset '{package}' is already up to date (v{local_ds.version}).")
        return 0

    print(f"Upgrading {package}: v{local_ds.version} -> v{remote_ds.version}")

    ds_dir = get_dataset_dir(data_path, package)
    if ds_dir:
        shutil.rmtree(ds_dir)
        print(f"  Removed old version.")

    return _do_download(config, remote_ds, args.verbose)


def _cmd_upgrade_all(config: Config, args) -> int:
    try:
        desc = fetch_descriptor(config, force_refresh=args.no_cache)
    except DescriptorFetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    data_path = config.get_data_path()
    local_datasets = discover_local_datasets(data_path)
    cross_referenced = cross_reference(local_datasets, desc.datasets)

    updates = [ds for ds in cross_referenced if ds.outdated]
    if not updates:
        print("All datasets are up to date.")
        return 0

    print(f"Upgrading {len(updates)} dataset(s)...\n")

    errors = 0
    for i, ds in enumerate(updates, 1):
        print(f"[{i}/{len(updates)}] Upgrading {ds.key}...")
        ds_dir = get_dataset_dir(data_path, ds.key)
        if ds_dir:
            shutil.rmtree(ds_dir)

        remote_ds = desc.find_by_key(ds.key)
        if remote_ds is None:
            print(f"  Error: not found in remote catalog.", file=sys.stderr)
            errors += 1
            continue

        try:
            ret = _do_download(config, remote_ds, args.verbose)
            if ret != 0:
                errors += 1
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            errors += 1
        print()

    if errors:
        print(f"Completed with {errors} error(s).")
        return 1
    print("All datasets upgraded successfully.")
    return 0


def cmd_remove(config: Config, args) -> int:
    package = args.package
    data_path = config.get_data_path()

    local_ds = find_local_dataset(data_path, package)
    if local_ds is None:
        print(f"Dataset '{package}' is not installed.", file=sys.stderr)
        return 1

    print(f"Dataset: {local_ds.name} (v{local_ds.version})")
    if not confirm_prompt(f"Remove dataset '{package}'?"):
        print("Cancelled.")
        return 0

    if remove_dataset(data_path, package):
        print(f"Dataset '{package}' removed.")
        return 0
    else:
        print(f"Failed to remove dataset '{package}'.", file=sys.stderr)
        return 1


def _do_download(config: Config, ds: Dataset, verbose: bool = False) -> int:
    url = ds.resolve_url(config.mirror_url)
    tmp_dir = config.get_tmp_dir()
    filename = f"{ds.key}.tar.gz"

    print(f"  Downloading {ds.name} ({ds.display_size()})...")
    if verbose:
        print(f"  URL: {url}")

    try:
        result = download_file(
            url=url,
            dest_dir=tmp_dir,
            filename=filename,
            expected_sha256=ds.sha256,
            verbose=verbose,
        )
    except ChecksumMismatchError as e:
        print(f"\n  Error: {e}", file=sys.stderr)
        print(f"  The partial download was kept for resume.", file=sys.stderr)
        return 1
    except DownloadError as e:
        print(f"\n  Error: {e}", file=sys.stderr)
        return 1

    if not result.success:
        print(f"\n  Error: {result.error}", file=sys.stderr)
        return 1

    print(f"  Download complete. SHA-256 verified.")

    # extract
    data_path = config.get_data_path()
    try:
        extract_tar_gz(result.file_path, data_path, verbose=verbose)
    except ExtractionError as e:
        print(f"  Error: {e}", file=sys.stderr)
        return 1

    print(f"  Extracted to {data_path}")

    # cleanup .part file
    result.file_path.unlink(missing_ok=True)

    print(f"  Dataset '{ds.key}' installed successfully.")
    return 0
