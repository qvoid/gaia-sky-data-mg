from dataclasses import dataclass, field
from typing import Optional, List

from .utils import human_readable_bytes, human_readable_nobjects


@dataclass
class Dataset:
    key: str
    name: str
    type: str
    version: int
    min_gs_version: int
    file: str
    check: str
    description: Optional[str] = None
    release_notes: Optional[List[str]] = None
    links: Optional[List[str]] = None
    creator: Optional[str] = None
    credits: Optional[List[str]] = None
    size_bytes: int = -1
    n_objects: int = -1
    sha256: Optional[str] = None
    replaces: Optional[List[str]] = None
    replaced_by: Optional[str] = None
    files: Optional[List[str]] = None
    images: Optional[List[str]] = None
    # local-only
    installed: bool = False
    local_version: int = -1
    outdated: bool = False

    @staticmethod
    def from_json(data: dict) -> 'Dataset':
        def _get(*keys, default=None):
            for k in keys:
                if k in data:
                    return data[k]
            return default

        def _to_list(val):
            if val is None:
                return None
            if isinstance(val, str):
                return [val]
            return list(val)

        release_notes_raw = _get('releasenotes', 'releaseNotes')
        if isinstance(release_notes_raw, str):
            release_notes = release_notes_raw.split('\n')
        else:
            release_notes = _to_list(release_notes_raw)

        return Dataset(
            key=_get('key', default=''),
            name=_get('name', default=''),
            type=_get('type', default='other'),
            version=int(_get('version', default=0)),
            min_gs_version=int(_get('mingsversion', default=0)),
            file=_get('file', default=''),
            check=_get('check', default=''),
            description=_get('description', 'desc'),
            release_notes=release_notes,
            links=_to_list(_get('links', 'link')),
            creator=_get('creator', 'author'),
            credits=_to_list(_get('credits', 'credit')),
            size_bytes=int(_get('size', 'sizeBytes', default=-1)),
            n_objects=int(_get('nobjects', 'nObjects', 'numObjects', default=-1)),
            sha256=_get('sha256'),
            replaces=_to_list(_get('replaces')),
            replaced_by=_get('replacedby', 'replacedBy'),
            files=_to_list(_get('files', 'data')),
            images=_to_list(_get('images')),
        )

    def resolve_url(self, mirror_url: str) -> str:
        return self.file.replace('@mirror-url@', mirror_url)

    def is_update_available(self) -> bool:
        return self.outdated or (self.installed and self.local_version >= 0 and self.local_version < self.version)

    def display_size(self) -> str:
        return human_readable_bytes(self.size_bytes)

    def display_nobjects(self) -> str:
        return human_readable_nobjects(self.n_objects)
