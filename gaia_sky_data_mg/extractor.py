import tarfile
from pathlib import Path
from typing import Optional

from .exceptions import ExtractionError


def extract_tar_gz(
    archive_path: Path,
    dest_dir: Path,
    verbose: bool = False,
) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tarfile.open(archive_path, 'r:gz') as tar:
            # security: prevent path traversal
            for member in tar.getmembers():
                member_path = dest_dir / member.name
                try:
                    member_path.resolve().relative_to(dest_dir.resolve())
                except ValueError:
                    raise ExtractionError(f"Unsafe path in archive: {member.name}")

            if verbose:
                print(f"  Extracting to {dest_dir}...")

            tar.extractall(path=str(dest_dir))
        return True
    except tarfile.TarError as e:
        raise ExtractionError(f"Failed to extract archive: {e}")
    except OSError as e:
        raise ExtractionError(f"IO error during extraction: {e}")
