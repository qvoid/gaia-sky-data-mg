# Gaia Sky Data Manager

A command-line tool for managing [Gaia Sky](https://zah.uni-heidelberg.de/institutes/ari/gaia/outreach/gaiasky) datasets. Download, update, and remove astronomical catalogs, texture packs, spacecraft models, and more — all from the terminal with resume support and SHA-256 verification.

## Features

- **Browse & search** all available Gaia Sky datasets
- **Download with resume** — interrupted downloads pick up where they left off
- **SHA-256 verification** on every download
- **Automatic extraction** of tar.gz archives
- **Update detection** — compare local datasets against the remote catalog
- **Batch upgrade** all outdated datasets at once
- **Zero config** — works out of the box with sensible defaults
- **Single dependency** — only `requests` beyond the Python standard library

## Requirements

- Python 3.8+
- pip

## Installation

```bash
# Clone or copy the project
cd gaia-sky-data-mg

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (uses Tsinghua mirror)
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ requests
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ -e .
```

After installation the `gaia-sky-data-mg` command is available inside the virtual environment. You can also run it directly with:

```bash
python -m gaia_sky_data_mg.cli <command> [options]
```

## Usage

### Global Options

```
gaia-sky-data-mg [-c CONFIG] [--data-path PATH] [--no-cache] [-v] <command> [command-args]

Options:
  -c, --config FILE       Path to config file (default: ~/.config/gaia-sky-data-mg/config.json)
  --data-path PATH        Override data storage directory
  --no-cache              Force fresh descriptor fetch (ignore cache)
  -v, --verbose           Show detailed output including URLs and debug info
```

### Commands

#### `list` — List datasets

Without flags, lists locally installed datasets:

```bash
gaia-sky-data-mg list
```

```
KEY                  NAME                  VERSION  SIZE    TYPE           STATUS
-------------------- --------------------- -------- ------- -------------- -----------
gargantua-blackhole  Gargantua black hole  5        3.1 KB  catalog-other  installed
volumetric-aurora    Volumetric Aurora     2        46.9 KB volume         installed
```

With `--available`, lists all remote datasets and shows their status:

```bash
gaia-sky-data-mg list --available
```

```
KEY                        NAME                                        VERSION  SIZE       TYPE             STATUS
-------------------------- ------------------------------------------- -------- ---------- ---------------- ----------
default-data               Base data pack                              63       71.1 MB    data-pack        available
gaia-dr3-default           Gaia DR3 default                            3        1010.2 MB  catalog-lod      available
gargantua-blackhole        Gargantua black hole                        5        3.1 KB     catalog-other    installed
volumetric-aurora          Volumetric Aurora                           2        46.9 KB    volume           upgradable
```

Status values:
- **available** — not installed locally
- **installed** — up to date
- **upgradable** — a newer version exists on the server

#### `info <package>` — Show dataset details

Displays all metadata for a dataset: description, version, size, checksum, download URL, credits, links, and replacement chain.

```bash
gaia-sky-data-mg info catalog-nbg
```

```
Dataset: NEARGALCAT
  Key:            catalog-nbg
  Type:           catalog-gal
  Version:        17
  Min GS version: 3.6.5.1
  Size:           4.6 MB
  Objects:        875
  SHA-256:        e467e67e9b84476c37dbb5f217198fc7527e7e507b7c11982c2121d78a17f23c
  Creator:        Toni Sagristà
  Description:    Updated Nearby Galaxy Catalog...
  Links:
    - https://heasarc.gsfc.nasa.gov/W3Browse/all/neargalcat.html
  Download URL:   https://gaia.ari.uni-heidelberg.de/.../catalog-nbg.tar.gz
```

Works for both installed and remote-only datasets.

#### `search <keyword>` — Search datasets

Case-insensitive search across key, name, description, and type fields:

```bash
gaia-sky-data-mg search dr3
```

```
Found 8 dataset(s):

KEY                   NAME                              VERSION  SIZE       TYPE
--------------------- --------------------------------- -------- ---------- ----------
gaia-dr3-best         Gaia DR3 best                     1        43.9 MB    catalog-gaia
gaia-dr3-default      Gaia DR3 default                  3        1010.2 MB  catalog-lod
mesh-dust-dr3         Dust iso-density maps (Gaia DR3)  1        1.4 MB     mesh
...
```

#### `download <package>` — Download a dataset

Downloads the tar.gz archive, verifies the SHA-256 checksum, and extracts it to the data directory.

```bash
gaia-sky-data-mg download catalog-nbg
```

If the dataset is already installed with the same version, the download is skipped. If a different version is installed, you are prompted for confirmation before overwriting:

```
Dataset 'catalog-nbg' is installed (v16), remote version is v17.
Overwrite local version? [y/N]:
```

**Resume support:** If a download is interrupted, a `.part` file is left in the `tmp/` directory. Running the same download command again resumes from where it stopped:

```
  Downloading NEARGALCAT (4.6 MB)...
  Resuming from 2.1 MB...
  [============================] 100.0% 4.6 MB / 4.6 MB  1.2 MB/s
  Verifying checksum (full file)...
  Download complete. SHA-256 verified.
```

Partial files older than 6 hours are automatically discarded and the download starts fresh.

#### `update` — Check for updates

Fetches the latest remote descriptor and compares it against locally installed datasets:

```bash
gaia-sky-data-mg update
```

```
Updates available for 2 dataset(s):

KEY            NAME       LOCAL VER  REMOTE VER  SIZE
-------------- ---------- ---------- ----------- --------
catalog-nbg    NEARGALCAT 16         17          4.6 MB
mesh-dust-dr3  Dust       0          1           1.4 MB
```

#### `upgrade <package>` — Upgrade a single dataset

Removes the old version and downloads the latest:

```bash
gaia-sky-data-mg upgrade catalog-nbg
```

```
Upgrading catalog-nbg: v16 -> v17
  Removed old version.
  Downloading NEARGALCAT (4.6 MB)...
  ...
```

#### `upgrade --all` — Upgrade all outdated datasets

Scans for every installed dataset that has an update available and upgrades them in sequence:

```bash
gaia-sky-data-mg upgrade --all
```

```
Upgrading 2 dataset(s)...

[1/2] Upgrading catalog-nbg...
  ...
[2/2] Upgrading mesh-dust-dr3...
  ...

All datasets upgraded successfully.
```

#### `remove <package>` — Remove a dataset

Deletes the dataset directory after confirmation:

```bash
gaia-sky-data-mg remove catalog-nbg
```

```
Dataset: NEARGALCAT (v17)
Remove dataset 'catalog-nbg'? [y/N]: y
Dataset 'catalog-nbg' removed.
```

## Configuration

By default, no configuration file is needed. The tool uses sensible defaults:

| Setting | Default | Description |
|---------|---------|-------------|
| `data_path` | `./data` | Where datasets are stored (relative to CWD) |
| `mirror_url` | `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/` | Download mirror |
| `descriptor_url` | auto-discovered | Remote descriptor URL (auto-detected, see below) |
| `gaia_sky_version` | `3060501` (3.6.5.1) | Fallback version if auto-discovery fails |
| `cache_dir` | `~/.cache/gaia-sky-data-mg` | Descriptor cache location |
| `cache_ttl_seconds` | `3600` (1 hour) | How long the cached descriptor is considered fresh |

To override defaults, create a config file at `~/.config/gaia-sky-data-mg/config.json`:

```json
{
    "data_path": "/opt/gaiasky/data",
    "mirror_url": "https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/",
    "cache_ttl_seconds": 7200
}
```

Or use command-line flags to override per invocation:

```bash
gaia-sky-data-mg --data-path /opt/gaiasky/data list
gaia-sky-data-mg --config /path/to/custom-config.json list
```

## Descriptor Auto-Discovery

The tool automatically discovers the correct data descriptor URL without any manual configuration. The process works as follows:

1. **Check local cache** — If a descriptor URL was discovered in the last 24 hours, reuse it directly.
2. **Fetch Gaia Sky version tags** — Query the [Codeberg API](https://codeberg.org/api/v1/repos/gaiasky/gaiasky/tags) for the list of Gaia Sky release tags (e.g. `3.7.2`, `3.7.1`, `3.6.11`, ...).
3. **Probe the server** — For each version (from newest to oldest), send an HTTP HEAD request to `gaiasky-data-{version}.json.gz` on the mirror. The first URL that returns HTTP 200 is used.
4. **Cache the result** — The discovered URL is cached in `~/.cache/gaia-sky-data-mg/descriptor_url_cache.json` for 24 hours.
5. **Fallback** — If the API is unreachable or no descriptor is found, the tool falls back to the version configured in `gaia_sky_version` (default: `3060501`).

This means you normally **do not need to configure any version number**. The tool will find the latest available descriptor automatically.

If you want to pin a specific descriptor URL (e.g. for testing or offline use), set it in the config file:

```json
{
    "descriptor_url": "https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/gaiasky-data-03060501.json.gz"
}
```

Or use a local file:

```json
{
    "descriptor_url": "file:///path/to/gaiasky-data-03060501.json.gz"
}
```

When `descriptor_url` is set explicitly, auto-discovery is skipped entirely.

## Data Storage

Downloaded datasets are extracted under the data path (`./data` by default):

```
data/
├── tmp/                        # Temporary directory for .part download files
├── catalog-nbg/                # One directory per dataset
│   ├── dataset.json            # Metadata
│   └── ...                     # Data files
├── volumetric-aurora/
│   ├── dataset.json
│   └── ...
└── default-data/
    ├── dataset.json
    └── ...
```

Each dataset directory contains a `dataset.json` file with metadata (key, version, type, etc.) used for local discovery and version tracking. The directory layout is compatible with Gaia Sky's own data directory structure, so you can point Gaia Sky at the same data path.

## Dataset Types

The remote catalog includes datasets of the following types:

| Type | Description | Example |
|------|-------------|---------|
| `data-pack` | Base data packages | `default-data` |
| `texture-pack` | Texture packs | `hi-res-textures` |
| `catalog-lod` | Level-of-detail star catalogs | `gaia-dr3-default` |
| `catalog-gaia` | Gaia-specific catalogs | `gaia-dr3-best`, `catalog-gcns` |
| `catalog-star` | Star catalogs | `catalog-hipparcos` |
| `catalog-gal` | Galaxy catalogs | `catalog-nbg`, `catalog-sdss-17` |
| `catalog-cluster` | Cluster catalogs | `catalog-ocdr2` |
| `catalog-sso` | Solar System Object catalogs | `catalog-asteroids-fpr` |
| `catalog-other` | Other catalogs | `catalog-nebulae`, `oort-cloud` |
| `system` | Planetary systems | `nasa-exoplanet-archive` |
| `spacecraft` | Spacecraft models and missions | `mission-gaia`, `spacecraft-jwst` |
| `mesh` | 3D mesh models | `mesh-dust-dr3` |
| `virtualtex-pack` | Virtual texture packs | `vt-moon-diffuse-vanvliet` |
| `volume` | Volumetric effects | `volumetric-aurora`, `saturn-rings` |

## How It Works

1. **Descriptor discovery** — On first run, the tool automatically discovers the data descriptor URL by querying the Gaia Sky version tags from Codeberg and probing the mirror server. The discovered URL is cached for 24 hours.

2. **Descriptor fetch** — The gzipped JSON descriptor is downloaded and parsed. This file lists all available datasets with their metadata, download URLs, sizes, and checksums. The parsed descriptor is cached locally for 1 hour (configurable via `cache_ttl_seconds`).

3. **Download** — When you run `download`, the tool resolves the `@mirror-url@` placeholder in the dataset's download URL, streams the tar.gz to a `.part` file in `tmp/`, and computes a running SHA-256 hash.

4. **Resume** — If a `.part` file already exists and is less than 6 hours old, the tool sends an HTTP `Range` header to resume the download from where it left off. After a resumed download completes, the full file is re-hashed to verify integrity.

5. **Extract** — The verified tar.gz is extracted directly into the data directory. The archive's internal paths become subdirectories under the data root.

6. **Version tracking** — The tool reads `dataset.json` from each local directory to determine installed versions and cross-references with the remote descriptor to detect updates.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (network, checksum, file I/O, etc.) |
| 2 | Invalid arguments |
| 130 | Interrupted by user (Ctrl+C) |

## License

This tool is provided as-is for managing Gaia Sky datasets. Gaia Sky itself is developed by the Astronomisches Rechen-Institut (ARI) at Heidelberg University and is released under the LGPL.
