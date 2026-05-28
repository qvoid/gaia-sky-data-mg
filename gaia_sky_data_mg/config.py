import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from .utils import version_to_zero_padded


DEFAULT_MIRROR_URL = "https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/"
DEFAULT_DESCRIPTOR_VERSION = 3060501  # 3.6.5.1 -> 03060501 in URL
DESCRIPTOR_URL_TEMPLATE = (
    "https://gaia.ari.uni-heidelberg.de/gaiasky/files/repository/"
    "gaiasky-data-{version}.json.gz"
)


@dataclass
class Config:
    data_path: str = "./data"
    mirror_url: str = DEFAULT_MIRROR_URL
    descriptor_url: Optional[str] = None
    gaia_sky_version: int = DEFAULT_DESCRIPTOR_VERSION
    cache_dir: str = "~/.cache/gaia-sky-data-mg"
    cache_ttl_seconds: int = 3600

    def get_descriptor_url(self) -> str:
        if self.descriptor_url:
            return self.descriptor_url
        version_str = version_to_zero_padded(self.gaia_sky_version)
        return DESCRIPTOR_URL_TEMPLATE.format(version=version_str)

    def get_data_path(self) -> Path:
        return Path(os.path.expanduser(self.data_path)).resolve()

    def get_cache_dir(self) -> Path:
        p = Path(os.path.expanduser(self.cache_dir))
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_tmp_dir(self) -> Path:
        tmp = self.get_data_path() / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        return tmp


def default_config_path() -> Path:
    xdg = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    return Path(xdg) / "gaia-sky-data-mg" / "config.json"


def load_config(config_path: Optional[str] = None) -> Config:
    if config_path is None:
        config_path = str(default_config_path())

    path = Path(os.path.expanduser(config_path))
    if path.exists():
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            return Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            pass

    return Config()


def save_config(config: Config, config_path: Optional[str] = None):
    if config_path is None:
        config_path = str(default_config_path())

    path = Path(os.path.expanduser(config_path))
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w') as f:
        json.dump(asdict(config), f, indent=4)
