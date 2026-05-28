# Gaia Sky Dataset Download System Analysis

## 1. Overview

Gaia Sky's dataset management system allows users to download, enable, disable, update, and remove astronomical datasets (star catalogs, galaxy catalogs, texture packs, etc.) through a GUI dialog. The system fetches dataset metadata from a remote JSON descriptor, resolves mirror URLs, downloads tar.gz archives with resume support, verifies SHA-256 checksums, and extracts files to the local data directory.

### Key Source Files

| File | Role |
|------|------|
| `core/src/gaiasky/gui/datasets/DatasetManagerWindow.java` | GUI dialog for dataset management |
| `core/src/gaiasky/util/datadesc/DatasetUtils.java` | Builds server/local dataset metadata |
| `core/src/gaiasky/util/datadesc/Dataset.java` | Single dataset data model |
| `core/src/gaiasky/util/datadesc/DatasetGroup.java` | Container for all datasets, organized by type |
| `core/src/gaiasky/util/datadesc/DatasetType.java` | Dataset type classification (catalog-star, etc.) |
| `core/src/gaiasky/util/datadesc/DatasetDownloadUtils.java` | Download helpers (decompress, mirror keyword, etc.) |
| `core/src/gaiasky/util/DownloadHelper.java` | HTTP download with resume and checksum |
| `assets/conf/config.yaml` | Mirror URL and descriptor URL configuration |

---

## 2. Dataset Download Address Source

### 2.1 Data Descriptor

The system fetches a **data descriptor** JSON file (gzipped) from a configured URL. This file contains metadata for all available datasets.

**Configured in** `assets/conf/config.yaml`:

```yaml
program:
  url:
    dataMirror: https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/
    dataDescriptor: https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/gaiasky-data-03060501.json.gz
```

- The descriptor filename encodes the Gaia Sky version it targets: `gaiasky-data-03060501.json.gz` corresponds to version 3.6.5.1.
- The descriptor URL can also point to a local file using the `file://` protocol.

### 2.2 Mirror URL and Keyword Replacement

Dataset download URLs in the descriptor JSON use a **mirror keyword** placeholder `@mirror-url@`. At runtime, this placeholder is replaced with the currently selected mirror URL.

```java
// DatasetDownloadUtils.java
public static final String mirrorKeyword = "@mirror-url@";

// Usage pattern (in DatasetManagerWindow.java and elsewhere):
String url = dataset.file.replace(mirrorKeyword, GaiaSky.settings().program.url.getCurrentDataMirror());
```

### 2.3 Mirror Selection

The system supports multiple mirrors with failover. On startup (`WelcomeGui.java`), it tests each mirror in sequence by fetching `index.html`:

```java
var mirrors = GaiaSky.settings().program.url.dataMirrors;
DownloadHelper.testConnection(mirrors[index] + "index.html",
    (url) -> {
        GaiaSky.settings().program.url.currentMirror = mirrors[index];
        success.run();
    },
    () -> { /* try next mirror */ });
```

Currently only one mirror is configured by default:
- **Primary**: `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/`

### 2.4 Complete URL Chain

```
1. Descriptor: https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/gaiasky-data-03060501.json.gz
2. Dataset file (in descriptor): @mirror-url@/catalogs/gaia-dr3.tar.gz
3. Resolved download URL: https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/catalogs/gaia-dr3.tar.gz
```

---

## 3. Data Descriptor JSON Structure

The gzipped JSON descriptor has this structure:

```json
{
  "recommended": ["dataset-key-1", "dataset-key-2"],
  "files": [
    {
      "key": "gaia-dr3-default",
      "name": "Gaia DR3",
      "type": "catalog-lod",
      "version": 3,
      "mingsversion": 3030100,
      "file": "@mirror-url@/catalogs/gaia-dr3/gaia-dr3-default.tar.gz",
      "check": "catalogs/gaia-dr3/dataset.json",
      "description": "Gaia Data Release 3 default catalog...",
      "releasenotes": ["Updated positions", "Fixed magnitudes"],
      "links": ["https://www.cosmos.esa.int/web/gaia/dr3"],
      "creator": "Gaia Collaboration",
      "credits": ["ESA/Gaia"],
      "size": 1234567890,
      "nobjects": 1811709771,
      "sha256": "abcdef1234567890...",
      "replaces": ["gaia-dr2-default"],
      "replacedby": null,
      "files": ["catalogs/gaia-dr3/gaia-dr3-default/"],
      "images": ["@mirror-url@/images/gaia-dr3-default.jpg"]
    }
  ]
}
```

### JSON Field Mapping

The `Dataset` constructor (`Dataset.java`) parses JSON with support for multiple field name variants:

| JSON Field(s) | Java Field | Type | Description |
|----------------|-----------|------|-------------|
| `key` | `key` | String | Unique identifier (kebab-case) |
| `name` | `name` | String | Display name |
| `type` | `type` | String | Dataset type string |
| `version` | `serverVersion` | int | Server-side version number |
| `mingsversion` | `minGsVersion` | int | Minimum Gaia Sky version required |
| `file` | `file` | String | Download URL (with `@mirror-url@`) |
| `check` | `checkStr` | String | Relative path to `dataset.json` |
| `description` / `desc` | `description` | String | Description text |
| `releasenotes` / `releaseNotes` | `releaseNotes` | String[] | Release notes (string or array) |
| `links` / `link` | `links` | String[] | Information links |
| `creator` / `author` | `creator` | String | Dataset creator |
| `credits` / `credit` | `credits` | String[] | Data credits |
| `size` / `sizeBytes` | `sizeBytes` | long | Size in bytes |
| `nobjects` / `nObjects` / `numObjects` | `nObjects` | long | Number of objects |
| `sha256` | `sha256` | String | SHA-256 checksum |
| `replaces` | `replaces` | String[] | Keys of datasets this one replaces |
| `replacedby` / `replacedBy` | `replacedBy` | String | Key of dataset that replaces this one |
| `files` / `data` | `files` | String[] | Relative file paths included |
| `images` | `images` | String[] | Image URLs (with `@mirror-url@`) |

---

## 4. Version Checking

### 4.1 Gaia Sky Version vs Dataset Version

Two separate version checks exist:

1. **`minGsVersion`** (in descriptor JSON as `mingsversion`): The minimum Gaia Sky version required to use the dataset. If `dataset.minGsVersion > Settings.SOURCE_VERSION`, the dataset is **disabled and highlighted in red** in the UI. Users cannot enable it.

2. **`version` / `serverVersion` vs `myVersion`**: The dataset's own version number. Used to detect updates.

### 4.2 Update Detection

In `DatasetUtils.buildLocalDatasets()`:
- For each local dataset, the system reads its `dataset.json` file to get `myVersion`
- Compares `myVersion` against `serverVersion` from the descriptor
- If `serverVersion > myVersion`, the dataset is marked `outdated = true`

```java
// In Dataset.java
private static int checkJsonVersion(Path path) {
    // Reads version from local dataset.json
}

// In DatasetUtils.java
if (serverDd != null) {
    Dataset serverDs = serverDd.findDatasetByKey(localDs.key);
    if (serverDs != null && serverDs.serverVersion > localDs.myVersion) {
        localDs.outdated = true;
        localDs.serverVersion = serverDs.serverVersion;
    }
}
```

### 4.3 Version Number Format

Versions are encoded as integers: e.g., `3030100` = version 3.3.1. The minimum version for datasets is `3030100` (Gaia Sky 3.3.1+). Datasets with lower version requirements are filtered out during parsing.

### 4.4 Dataset Replacement Chain

Datasets can declare replacement relationships:
- `replaces`: Array of dataset keys this dataset replaces
- `replacedBy`: Key of a newer dataset that replaces this one

The system uses `updateReplacedBy()` in `DatasetGroup` to cross-reference these and display warnings for deprecated datasets.

---

## 5. Available Dataset Types

### 5.1 Type Categories

Defined in `DatasetType.java` with icons and sort weights:

| Type String | Icon | Sort Weight | Description |
|-------------|------|-------------|-------------|
| `data-pack` | icon-data | 0 | Base data packages |
| `texture-pack` | icon-texture | 1 | Texture packs |
| `catalog-lod` | icon-catalog | 2 | LOD (level-of-detail) star catalogs |
| `catalog-gaia` | icon-catalog | 3 | Gaia-specific catalogs |
| `catalog-star` | icon-catalog | 4 | Star catalogs |
| `catalog-gal` | icon-catalog | 5 | Galaxy catalogs |
| `catalog-cluster` | icon-catalog | 6 | Cluster catalogs |
| `catalog-sso` | icon-catalog | 7 | Solar System Object catalogs |
| `catalog-other` | icon-catalog | 8 | Other catalogs |
| `mesh` | icon-mesh | 9 | 3D mesh models |
| `spacecraft` | icon-spacecraft | 10 | Spacecraft models |
| `system` | icon-system | 11 | System data |
| `volume` | icon-volume | 12 | Volume rendered data |
| `virtualtex-pack` | icon-virtualtex | 13 | Virtual texture packs |
| `other` | icon-other | 14 | Unclassified |

### 5.2 Incompatibility Rules

Some dataset types have mutual exclusion rules (`DatasetManagerWindow.checkDatasetIncompatibilities()`):

- **`catalog-lod`**: Only one LOD catalog can be enabled at a time
- **`catalog-cluster`**: Only one cluster catalog can be enabled at a time
- **`catalog-gal` with key containing "sdss"**: Only one SDSS galaxy catalog at a time

When a user tries to enable a conflicting dataset, a confirmation dialog is shown.

---

## 6. Download Flow

### 6.1 Step-by-Step Process

```
1. STARTUP
   └─ WelcomeGui tests mirror connectivity
   └─ Downloads gaiasky-data-XXXXXX.json.gz descriptor
   └─ Parses JSON into DatasetGroup

2. UI DISPLAY
   └─ DatasetManagerWindow shows two tabs: "Available" and "Installed"
   └─ Left pane: list of datasets grouped by type (collapsible)
   └─ Right pane: details of selected dataset

3. DOWNLOAD TRIGGER
   └─ User clicks "Install" or "Update" button
   └─ actionDownloadDataset() or actionUpdateDataset() called
   └─ downloadDataset() invoked

4. PRE-DOWNLOAD CHECKS
   └─ Checks disk space: needs size + size*1.5 (for compressed + extracted)
   └─ Creates temp file: <tempDir>/<filename>.part

5. HTTP DOWNLOAD (DownloadHelper.downloadFile)
   └─ Supports resume via Range header if .part file exists
   └─ 1024-byte buffer streaming download
   └─ Progress tracking with speed calculation
   └─ SHA-256 checksum computed during download

6. POST-DOWNLOAD
   └─ Verify SHA-256 checksum against descriptor
   └─ Decompress tar.gz to data location
   └─ Clean up temp .part file
   └─ Enable dataset (add to dataFiles settings)
   └─ Reload UI

7. UPDATE FLOW
   └─ actionUpdateDataset() first deletes old dataset
   └─ Then downloads new version
   └─ Updates version numbers and outdated flags
```

### 6.2 Download with Resume

`DownloadHelper.java` implements resume support:
1. Checks for existing `.part` file
2. If found and not too old, sends `Range: bytes=<existingSize>-` header
3. Appends to existing file instead of starting over

### 6.3 Cancellation

Downloads can be cancelled via `Gdx.net.cancelHttpRequest(request)`. The cancel handler cleans up state and reloads the UI.

### 6.4 Error Handling

- **Disk space insufficient**: Shows notification, aborts before download
- **Checksum mismatch**: Logs error, shows notification, increments error count
- **Decompression failure**: Logs error, shows notification
- **Network failure**: Shows notification, cleans up temp file
- All error paths reload the UI after a short delay (0.5-1.5 seconds)

---

## 7. Local Dataset Discovery

The system discovers locally installed datasets by:

1. Scanning the data directory for JSON files starting with `catalog-` or `dataset-`
2. Each such JSON file must have a corresponding `dataset.json` in its directory
3. Directories `tmp`, `cache`, `procedural_tex` are excluded from scanning
4. Local datasets are cross-referenced with server datasets for version checking
5. Images for local datasets are discovered using patterns: `image.jpg`, `image00.jpg` through `image99.jpg`

### Base Data and Texture Packs

- Datasets marked as `baseData` or of type `texture-pack` are always enabled and cannot be disabled
- The `baseData` flag is determined by whether the dataset is included in the default installation

---

## 8. Key URLs Summary

| Purpose | URL |
|---------|-----|
| Data mirror | `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/` |
| Data descriptor | `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/gaiasky-data-03060501.json.gz` |
| Version check | `https://codeberg.org/api/v1/repos/gaiasky/gaiasky/tags` |
| Internet check | `https://fedoraproject.org/static/hotspot.txt` |
| Gaia TAP service | `https://gaia.ari.uni-heidelberg.de/tap/sync` |
| SIMBAD lookup | `https://simbad.u-strasbg.fr/simbad/sim-id?Ident=` |

---

## 9. Configuration

All URLs are configurable in `assets/conf/config.yaml` under `program.url`:

```yaml
program:
  url:
    versionCheck: https://codeberg.org/api/v1/repos/gaiasky/gaiasky/tags
    dataMirror: https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/
    dataDescriptor: https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/gaiasky-data-03060501.json.gz
```

The data descriptor URL can also point to a local file using the `file://` protocol prefix, useful for offline or development scenarios.

---

## 10. Local Directory Structure After Download

### 10.1 Data Root Directory

All datasets are stored under the **data location** directory, configurable via `data.location` in settings:

| OS | Default Path |
|----|-------------|
| Linux | `~/.local/share/gaiasky/data/` |
| macOS | `~/.gaiasky/data/` |
| Windows | `~/.gaiasky/data/` |

A temporary directory for downloads exists at `<data-location>/tmp/`.

The `$data/` token in descriptor files always resolves to this data root. For example, if the data location is `/opt/gaiasky/data/`, then `$data/default-data/dataset.json` resolves to `/opt/gaiasky/data/default-data/dataset.json`.

### 10.2 How tar.gz Files Are Extracted

The tar.gz archive preserves its internal directory structure during extraction. The `DatasetDownloadUtils.decompress()` method extracts all tar entries using `entry.getName()` as the relative path under the data location directory. **No path transformation or rewriting occurs.**

This means the tar.gz must contain files whose paths directly correspond to the `check` and `files` fields in the descriptor. For example, if `check` is `$data/catalog-nbg/dataset.json`, the tar.gz must contain `catalog-nbg/dataset.json` at its root.

### 10.3 Complete Local Directory Tree

Below is the full local directory structure when all available datasets are installed. Each dataset lives in its own top-level directory under the data root, identified by its key. Each directory contains a `dataset.json` metadata file plus the actual data files.

```
<data-location>/
├── tmp/                                    # Temporary download directory (.part files)
│
├── default-data/                           # [data-pack] Base data pack (REQUIRED)
│   ├── dataset.json
│   ├── vsop87/                             # VSOP87 orbital elements
│   │   └── vsop87a.bin
│   ├── tex/                                # Textures
│   │   └── lut/                            # Look-up tables (biome, etc.)
│   ├── galaxy/                             # Milky Way sprites
│   │   └── sprites/
│   └── models/                             # 3D models
│       └── controllers/
│
├── hi-res-textures/                        # [texture-pack] High resolution textures
│   └── dataset.json
│
├── gaia-dr3-best/                          # [catalog-gaia] Gaia DR3 best stars (~646K)
│   └── dataset.json
│
├── gaia-dr3-default/                       # [catalog-lod] Gaia DR3 default LOD (~15M)
│   └── dataset.json
│
├── gaia-dr3-small/                         # [catalog-lod] Gaia DR3 small (~8M)
│   └── dataset.json
│
├── gaia-dr3-medium/                        # [catalog-lod] Gaia DR3 medium (~50M)
│   └── dataset.json
│
├── gaia-dr3-large/                         # [catalog-lod] Gaia DR3 large (~122M)
│   └── dataset.json
│
├── gaia-dr3-verylarge/                     # [catalog-lod] Gaia DR3 very large (~466M)
│   └── dataset.json
│
├── gaia-dr3-extralarge/                    # [catalog-lod] Gaia DR3 extra large (~707M)
│   └── dataset.json
│
├── gaia-dr3-bright/                        # [catalog-lod] Gaia DR3 bright (~11M)
│   └── dataset.json
│
├── gaia-dr3-ruwe/                          # [catalog-lod] Gaia DR3 RUWE (~958M)
│   └── dataset.json
│
├── gaia-dr3-geodist/                       # [catalog-lod] Gaia DR3 bayesian distances (~1.5B)
│   └── dataset.json
│
├── gaia-dr3-fidelity/                      # [catalog-lod] Gaia DR3 fidelity (~394M)
│   └── dataset.json
│
├── gaia-dr3-photdist/                      # [catalog-lod] Gaia DR3 photometric distances (~471M)
│   └── dataset.json
│
├── gaia-dr3-tiny/                          # [catalog-gaia] Gaia DR3 tiny (~2.5M)
│   └── dataset.json
│
├── gaia-dr3-weeny/                         # [catalog-gaia] Gaia DR3 weeny (~1.9M)
│   └── dataset.json
│
├── catalog-gcns/                           # [catalog-gaia] Gaia Catalog of Nearby Stars (~331K)
│   └── dataset.json
│
├── catalog-cns5/                           # [catalog-star] Fifth Catalog of Nearby Stars (~5.9K)
│   └── dataset.json
│
├── catalog-whitedwarfs-dr2/                # [catalog-gaia] DR2 White Dwarfs (~256K)
│   └── dataset.json                        #   replaced by catalog-whitedwarfs-edr3
│
├── catalog-whitedwarfs-edr3/               # [catalog-gaia] eDR3 White Dwarfs (~359K)
│   └── dataset.json
│
├── catalog-variablestars-dr2/              # [catalog-gaia] DR2 Cepheid and RR Lyrae (~106K)
│   └── dataset.json                        #   replaced by catalog-variablestars-dr3
│
├── catalog-variablestars-dr3/              # [catalog-gaia] DR3 Cepheid and RR Lyrae (~187K)
│   └── dataset.json
│
├── catalog-gd1/                            # [catalog-gaia] GD-1 stellar stream (~1.4K)
│   └── dataset.json
│
├── catalog-hipparcos/                      # [catalog-star] Hipparcos new reduction (~118K)
│   └── dataset.json
│
├── catalog-nbg/                            # [catalog-gal] NEARGALCAT nearby galaxies (~875)
│   └── dataset.json
│
├── catalog-sdss-12/                        # [catalog-gal] SDSS DR12 (~328K)
│   └── dataset.json
│
├── catalog-sdss-14/                        # [catalog-gal] SDSS DR14 (~3M)
│   └── dataset.json
│
├── catalog-sdss-17/                        # [catalog-gal] SDSS DR17 (~2.8M)
│   └── dataset.json
│
├── catalog-sdss-18/                        # [catalog-gal] SDSS DR18 (~3.6M)
│   └── dataset.json
│
├── catalog-clusters-hunt-reffert-2023/     # [catalog-cluster] DR3 Open Clusters (~7.2K)
│   └── dataset.json
│
├── catalog-ocdr2/                          # [catalog-cluster] Open Clusters DR2 (~2K)
│   └── dataset.json
│
├── catalog-mwsc/                           # [catalog-cluster] MWSC (~3K)
│   └── dataset.json
│
├── catalog-nebulae/                        # [catalog-other] NGC2000 Nebulae (47)
│   └── dataset.json
│
├── catalog-asteroids-fpr/                  # [catalog-sso] Asteroids Gaia FPR (~157K)
│   └── dataset.json                        #   replaces catalog-asteroids-dr3, -nea, -trojan
│
├── catalog-asteroids-dr3/                  # [catalog-sso] Asteroids Gaia DR3 (~155K)
│   └── dataset.json                        #   replaced by catalog-asteroids-fpr
│
├── catalog-asteroids-dr3-nea/             # [catalog-sso] NEA asteroids Gaia DR3 (~155K)
│   └── dataset.json                        #   replaced by catalog-asteroids-fpr
│
├── catalog-asteroids-dr3-trojan/          # [catalog-sso] Trojan asteroids Gaia DR3 (~1.5K)
│   └── dataset.json                        #   replaced by catalog-asteroids-fpr
│
├── catalog-asteroids-dr2/                  # [catalog-sso] Asteroids Gaia DR2 (~14K)
│   └── dataset.json
│
├── catalog-gps/                            # [spacecraft] GPS Satellite Network
│   └── dataset.json
│
├── gargantua-blackhole/                    # [catalog-other] Gargantua black hole (1)
│   └── dataset.json
│
├── oort-cloud/                             # [catalog-other] Oort cloud (10K particles)
│   └── dataset.json
│
├── nasa-exoplanet-archive/                 # [system] NASA Exoplanet Archive (~9.8K)
│   └── dataset.json
│
├── system-exonia/                          # [system] Exonia system (7)
│   └── dataset.json
│
├── system-dr3-gl876/                       # [system] Gl876 system (2)
│   └── dataset.json
│
├── system-dr3-hd40503/                     # [system] HD40503 system (2)
│   └── dataset.json
│
├── system-dr3-hd81040/                     # [system] HD81040 system (2)
│   └── dataset.json
│
├── system-dr3-hd114762/                    # [system] HD114762 system (2)
│   └── dataset.json
│
├── system-dr3-j0805-4812/                  # [system] J0805+4812 system (2)
│   └── dataset.json
│
├── system-dr3-ucac2-1151977/              # [system] UCAC2 1151977 system (2)
│   └── dataset.json
│
├── system-dr3-wd0141-675/                  # [system] WD0141-675 system (2)
│   └── dataset.json
│
├── system-gaia-bhs/                        # [system] Gaia DR3 black holes (6)
│   └── dataset.json                        #   replaces system-gaia-BH1, BH2, BH3
│
├── mission-gaia/                           # [spacecraft] ESA's Gaia mission
│   └── dataset.json
│
├── mission-artemis/                        # [spacecraft] Artemis I and II missions
│   └── dataset.json
│
├── mission-pioneer/                        # [spacecraft] Pioneer 10 and 11 missions
│   └── dataset.json
│
├── spacecraft-euclid/                      # [spacecraft] ESA Euclid
│   └── dataset.json
│
├── spacecraft-jwst/                        # [spacecraft] James Webb Space Telescope
│   └── dataset.json
│
├── spacecraft-hst/                         # [spacecraft] Hubble Space Telescope
│   └── dataset.json
│
├── spacecraft-iss/                         # [spacecraft] International Space Station
│   └── dataset.json
│
├── spacecraft-voyagers/                    # [spacecraft] Voyager 1 and 2
│   └── dataset.json
│
├── mesh-dust-dr2/                          # [mesh] Dust iso-density maps (Gaia DR2)
│   └── dataset.json                        #   replaced by mesh-dust-dr3
│
├── mesh-dust-dr3/                          # [mesh] Dust iso-density maps (Gaia DR3)
│   └── dataset.json
│
├── mesh-hii-dr2/                           # [mesh] HII regions map (Gaia DR2)
│   └── dataset.json                        #   replaced by mesh-hii-dr3
│
├── mesh-hii-dr3/                           # [mesh] HII regions map (Gaia DR3)
│   └── dataset.json
│
├── mesh-stardensity-dr2/                   # [mesh] Star density map (Gaia DR2)
│   └── dataset.json                        #   replaced by mesh-stardensity-dr3
│
├── mesh-stardensity-dr3/                   # [mesh] Star density map (Gaia DR3)
│   └── dataset.json
│
├── vt-earth-diffuse-sentinel/              # [virtualtex-pack] Earth surface VT Sentinel-2 (3.4GB)
│   └── dataset.json                        #   replaces vt-earth-diffuse-nasa
│
├── vt-earth-diffuse-nasa/                  # [virtualtex-pack] 128K Earth surface VT NASA (1.3GB)
│   └── dataset.json
│
├── vt-earth-topography-gmted2010/          # [virtualtex-pack] 128K Earth elevation VT USGS (645MB)
│   └── dataset.json
│
├── vt-earth-clouds-nasa/                   # [virtualtex-pack] 64K Earth cloud VT NASA (378MB)
│   └── dataset.json
│
├── vt-mars-diffuse-vanvliet/               # [virtualtex-pack] 64K Mars diffuse VT (1.2GB)
│   └── dataset.json
│
├── vt-mars-topography-mola/                # [virtualtex-pack] 64K Mars elevation VT MOLA (68MB)
│   └── dataset.json
│
├── vt-moon-diffuse-vanvliet/               # [virtualtex-pack] 64K Moon diffuse VT (2.7GB)
│   └── dataset.json
│
├── vt-moon-topography-lro/                 # [virtualtex-pack] 8K Moon topography VT LRO (8.4MB)
│   └── dataset.json
│
├── vt-moon-topography-nasa/                # [virtualtex-pack] 32K Moon topography NASA (41MB)
│   └── dataset.json
│
├── volumetric-aurora/                      # [volume] Volumetric Aurora
│   └── dataset.json
│
└── saturn-rings/                           # [volume] Saturn rings (1.5M particles)
    └── dataset.json
```

### 10.4 Dataset Catalog by Type

The following table lists every unique dataset (latest version only) from the remote descriptor, organized by type:

#### data-pack

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `default-data` | Base data pack | 63 | 71 MB | - | `$data/default-data/dataset.json` |

#### texture-pack

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `hi-res-textures` | High resolution textures | 15 | 248 MB | 76 | `$data/hi-res-textures/dataset.json` |

#### catalog-lod (LOD star catalogs, mutually exclusive)

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `gaia-dr3-default` | Gaia DR3 default | 3 | 1.0 GB | 15,127,025 | `$data/catalog-gaia-dr3-default/dataset.json` |
| `gaia-dr3-small` | Gaia DR3 small | 2 | 534 MB | 8,199,560 | `$data/catalog-gaia-dr3-small/dataset.json` |
| `gaia-dr3-medium` | Gaia DR3 medium | 2 | 3.1 GB | 49,939,229 | `$data/catalog-gaia-dr3-medium/dataset.json` |
| `gaia-dr3-large` | Gaia DR3 large | 2 | 7.4 GB | 122,183,859 | `$data/catalog-gaia-dr3-large/dataset.json` |
| `gaia-dr3-verylarge` | Gaia DR3 very large | 2 | 27.9 GB | 466,144,211 | `$data/catalog-gaia-dr3-verylarge/dataset.json` |
| `gaia-dr3-extralarge` | Gaia DR3 extra large | 2 | 42.1 GB | 707,157,643 | `$data/catalog-gaia-dr3-extralarge/dataset.json` |
| `gaia-dr3-bright` | Gaia DR3 bright | 2 | 731 MB | 11,269,665 | `$data/catalog-gaia-dr3-bright/dataset.json` |
| `gaia-dr3-ruwe` | Gaia DR3 RUWE | 2 | 57.1 GB | 957,749,159 | `$data/catalog-gaia-dr3-ruwe/dataset.json` |
| `gaia-dr3-geodist` | Gaia DR3 bayesian distances | 2 | 86.9 GB | 1,467,764,764 | `$data/catalog-gaia-dr3-geodist/dataset.json` |
| `gaia-dr3-fidelity` | Gaia DR3 fidelity | 2 | 23.5 GB | 393,678,770 | `$data/catalog-gaia-dr3-fidelity/dataset.json` |
| `gaia-dr3-photdist` | Gaia DR3 photometric distances | 2 | 28.1 GB | 470,812,656 | `$data/catalog-gaia-dr3-photdist/dataset.json` |

#### catalog-gaia

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `gaia-dr3-best` | Gaia DR3 best | 1 | 44 MB | 646,400 | `$data/catalog-gaia-dr3-best/dataset.json` |
| `gaia-dr3-tiny` | Gaia DR3 tiny | 3 | 170 MB | 2,552,302 | `$data/catalog-gaia-dr3-tiny/dataset.json` |
| `gaia-dr3-weeny` | Gaia DR3 weeny | 3 | 130 MB | 1,939,279 | `$data/catalog-gaia-dr3-weeny/dataset.json` |
| `catalog-gcns` | Gaia Catalog of Nearby Stars | 3 | 138 MB | 331,078 | `$data/catalog-gcns/dataset.json` |
| `catalog-whitedwarfs-edr3` | eDR3 White Dwarfs | 1 | 31 MB | 359,073 | `$data/catalog-whitedwarfs-edr3/dataset.json` |
| `catalog-variablestars-dr3` | DR3 Cepheid and RR Lyrae | 1 | 149 MB | 186,928 | `$data/catalog-variablestars-dr3/dataset.json` |
| `catalog-gd1` | GD-1 stellar stream | 2 | 110 KB | 1,365 | `$data/catalog-gd1/dataset.json` |

#### catalog-star

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `catalog-cns5` | Fifth Catalog of Nearby Stars (CNS5) | 3 | 1.2 MB | 5,931 | `$data/catalog-cns5/dataset.json` |
| `catalog-hipparcos` | Hipparcos (new reduction) | 6 | 7.7 MB | 117,955 | `$data/catalog-hipparcos/dataset.json` |

#### catalog-gal (galaxy catalogs)

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `catalog-nbg` | NEARGALCAT | 17 | 4.7 MB | 875 | `$data/catalog-nbg/dataset.json` |
| `catalog-sdss-12` | SDSS DR12 | 8 | 11 MB | 327,835 | `$data/catalog-sdss-12/dataset.json` |
| `catalog-sdss-14` | SDSS DR14 | 8 | 79 MB | 3,040,257 | `$data/catalog-sdss-14/dataset.json` |
| `catalog-sdss-17` | SDSS DR17 | 5 | 70 MB | 2,812,409 | `$data/catalog-sdss-17/dataset.json` |
| `catalog-sdss-18` | SDSS DR18 | 2 | 98 MB | 3,637,836 | `$data/catalog-sdss-18/dataset.json` |

#### catalog-cluster (mutually exclusive)

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `catalog-clusters-hunt-reffert-2023` | DR3 Open Clusters (Hunt, Reffert) | 2 | 991 KB | 7,167 | `$data/catalog-clusters-hunt-reffert-2023/dataset.json` |
| `catalog-ocdr2` | Open Clusters DR2 Catalog | 7 | 141 KB | 2,017 | `$data/catalog-ocdr2/dataset.json` |
| `catalog-mwsc` | MWSC | 7 | 151 KB | 3,006 | `$data/catalog-mwsc/dataset.json` |

#### catalog-sso (Solar System Objects)

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `catalog-asteroids-fpr` | Asteroids and SSO (Gaia FPR) | 4 | 13 MB | 156,588 | `$data/catalog-asteroids-fpr/dataset.json` |
| `catalog-asteroids-dr3` | Asteroids and SSO (Gaia DR3) | 2 | 15 MB | 154,787 | `$data/catalog-asteroids-dr3/dataset.json` |
| `catalog-asteroids-dr3-nea` | NEA asteroids (Gaia DR3) | 1 | 15 MB | 154,787 | `$data/catalog-asteroids-dr3-nea/dataset.json` |
| `catalog-asteroids-dr3-trojan` | Trojan asteroids (Gaia DR3) | 1 | 161 KB | 1,545 | `$data/catalog-asteroids-dr3-trojan/dataset.json` |
| `catalog-asteroids-dr2` | Asteroids and SSO (Gaia DR2) | 2 | 908 KB | 14,104 | `$data/catalog-asteroids-dr2/dataset.json` |

#### catalog-other

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `catalog-nebulae` | NGC2000 Nebulae | 12 | 4.6 MB | 47 | `$data/catalog-nebulae/dataset.json` |
| `gargantua-blackhole` | Gargantua black hole | 5 | 3.1 KB | 1 | `$data/gargantua-blackhole/dataset.json` |
| `oort-cloud` | Oort cloud | 4 | 431 KB | 10,000 | `$data/oort-cloud/dataset.json` |

#### system (planetary systems)

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `nasa-exoplanet-archive` | NASA Exoplanet Archive | 2 | 2.9 MB | 9,793 | `$data/nasa-exoplanet-archive/dataset.json` |
| `system-exonia` | Exonia system | 4 | 2.4 MB | 7 | `$data/system-exonia/dataset.json` |
| `system-dr3-gl876` | Gl876 system | 1 | 1.5 KB | 2 | `$data/system-dr3-gl876/dataset.json` |
| `system-dr3-hd40503` | HD40503 system | 1 | 1.5 KB | 2 | `$data/system-dr3-hd40503/dataset.json` |
| `system-dr3-hd81040` | HD81040 system | 1 | 1.5 KB | 2 | `$data/system-dr3-hd81040/dataset.json` |
| `system-dr3-hd114762` | HD114762 system | 1 | 1.3 KB | 2 | `$data/system-dr3-hd114762/dataset.json` |
| `system-dr3-j0805-4812` | J0805+4812 system | 1 | 1.2 KB | 2 | `$data/system-dr3-j0805-4812/dataset.json` |
| `system-dr3-ucac2-1151977` | UCAC2 1151977 system | 1 | 1.2 KB | 2 | `$data/system-dr3-ucac2-1151977/dataset.json` |
| `system-dr3-wd0141-675` | WD0141-675 system | 2 | 1.5 KB | 2 | `$data/system-dr3-wd0141-675/dataset.json` |
| `system-gaia-bhs` | Gaia DR3 black holes | 2 | 145 KB | 6 | `$data/system-gaia-bhs/dataset.json` |

#### spacecraft

| Key | Name | Version | Size | check |
|-----|------|---------|------|-------|
| `mission-gaia` | ESA's Gaia mission | 1 | 2.2 MB | `$data/mission-gaia/dataset.json` |
| `mission-artemis` | Artemis I and II missions | 1 | 11 MB | `$data/mission-artemis/dataset.json` |
| `mission-pioneer` | Pioneer 10 and 11 missions | 1 | 12 MB | `$data/mission-pioneer/dataset.json` |
| `spacecraft-euclid` | ESA Euclid | 4 | 21.7 MB | `$data/spacecraft-euclid/dataset.json` |
| `spacecraft-jwst` | James Webb Space Telescope | 5 | 3.6 MB | `$data/spacecraft-jwst/dataset.json` |
| `spacecraft-hst` | Hubble Space Telescope | 3 | 8.9 MB | `$data/spacecraft-hst/dataset.json` |
| `spacecraft-iss` | International Space Station | 3 | 24 MB | `$data/spacecraft-iss/dataset.json` |
| `spacecraft-voyagers` | Voyager 1 and 2 | 3 | 3.0 MB | `$data/spacecraft-voyagers/dataset.json` |
| `catalog-gps` | GPS Satellite Network | 2 | 1000 KB | `$data/catalog-gps/dataset.json` |

#### mesh (3D mesh models)

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `mesh-dust-dr3` | Dust iso-density maps (Gaia DR3) | 1 | 1.4 MB | 1 | `$data/mesh-dust-dr3/dataset.json` |
| `mesh-hii-dr3` | HII regions map (Gaia DR3) | 1 | 8.9 MB | 1 | `$data/mesh-hii-dr3/dataset.json` |
| `mesh-stardensity-dr3` | Star density map (Gaia DR3) | 1 | 24 MB | 1 | `$data/mesh-stardensity-dr3/dataset.json` |

#### virtualtex-pack (virtual textures)

| Key | Name | Version | Size | check |
|-----|------|---------|------|-------|
| `vt-earth-diffuse-sentinel` | Earth surface VT Sentinel-2 | 0 | 3.4 GB | `$data/vt-earth-diffuse-sentinel/dataset.json` |
| `vt-earth-diffuse-nasa` | 128K Earth surface VT NASA | 0 | 1.3 GB | `$data/vt-earth-diffuse-nasa/dataset.json` |
| `vt-earth-topography-gmted2010` | 128K Earth elevation VT USGS | 0 | 645 MB | `$data/vt-earth-topography-gmted2010/dataset.json` |
| `vt-earth-clouds-nasa` | 64K Earth cloud VT NASA | 0 | 378 MB | `$data/vt-earth-clouds-nasa/dataset.json` |
| `vt-mars-diffuse-vanvliet` | 64K Mars diffuse VT Celestia | 0 | 1.2 GB | `$data/vt-mars-diffuse-vanvliet/dataset.json` |
| `vt-mars-topography-mola` | 64K Mars elevation VT MOLA | 0 | 68 MB | `$data/vt-mars-topography-mola/dataset.json` |
| `vt-moon-diffuse-vanvliet` | 64K Moon diffuse VT Celestia | 0 | 2.7 GB | `$data/vt-moon-diffuse-vanvliet/dataset.json` |
| `vt-moon-topography-lro` | 8K Moon topography VT LRO | 0 | 8.4 MB | `$data/vt-moon-topography-lro/dataset.json` |
| `vt-moon-topography-nasa` | 32K Moon topography NASA | 1 | 41 MB | `$data/vt-moon-topography-nasa/dataset.json` |

#### volume (volumetric effects)

| Key | Name | Version | Size | Objects | check |
|-----|------|---------|------|---------|-------|
| `volumetric-aurora` | Volumetric Aurora | 2 | 47 KB | 1 | `$data/volumetric-aurora/dataset.json` |
| `saturn-rings` | Saturn rings | 1 | 77 MB | 1,500,000 | `$data/saturn-rings/dataset.json` |

### 10.5 Dataset Replacement Relationships

Some datasets declare replacement chains. When a newer dataset replaces an older one, the UI shows a warning and offers to switch:

| New Dataset | Replaces |
|-------------|----------|
| `catalog-whitedwarfs-edr3` | `catalog-whitedwarfs-dr2` |
| `catalog-variablestars-dr3` | `catalog-variablestars-dr2` |
| `catalog-asteroids-fpr` | `catalog-asteroids-dr3`, `catalog-asteroids-dr3-nea`, `catalog-asteroids-dr3-trojan` |
| `catalog-asteroids-dr3` | `catalog-asteroids-dr2` |
| `mesh-dust-dr3` | `mesh-dust-dr2` |
| `mesh-hii-dr3` | `mesh-hii-dr2` |
| `mesh-stardensity-dr3` | `mesh-stardensity-dr2` |
| `system-gaia-bhs` | `system-gaia-BH1`, `system-gaia-BH2`, `system-gaia-BH3` |
| `vt-earth-diffuse-sentinel` | `vt-earth-diffuse-nasa` |

### 10.6 Recommended Datasets

The descriptor declares these datasets as recommended:

1. `default-data` - Base data pack (required)
2. `gaia-dr3-best` - Gaia DR3 best stars
3. `mission-gaia` - ESA's Gaia mission spacecraft
4. `catalog-nbg` - NEARGALCAT nearby galaxies
5. `catalog-nebulae` - NGC2000 Nebulae
6. `catalog-sdss-12` - SDSS DR12 galaxies

### 10.7 Download URL Pattern

Each dataset's remote tar.gz follows this URL pattern:

```
@mirror-url@<category>/<version-dir>/<dataset-key>.tar.gz
```

Where:
- `@mirror-url@` is replaced with `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/`
- `<category>` is a server-side directory: `basedata`, `tex`, `catalog`, `galaxies`, `clusters`, `nebulae`, `meshes`, `systems`, `extra/spacecraft`, `vt`, `volumes`, `extra`
- `<version-dir>` is like `v063_20260508` (version + date)
- `<dataset-key>` is the dataset identifier

Examples:
| Dataset | Full Download URL |
|---------|------------------|
| default-data | `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/basedata/v063_20260508/default-data.tar.gz` |
| catalog-nbg | `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/galaxies/nbg/v017_20260331/catalog-nbg.tar.gz` |
| spacecraft-jwst | `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/extra/spacecraft/jwst/v005_20260428/spacecraft-jwst.tar.gz` |
| gaia-dr3-default | `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/catalog/dr3/000-default/v03_20240423/catalog-gaia-dr3-default.tar.gz` |
| vt-moon-diffuse-vanvliet | `https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/vt/vt-moon-diffuse-vanvliet/000_20230125/vt-moon-diffuse-vanvliet.tar.gz` |
