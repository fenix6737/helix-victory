"""店舗ごとのデータソース定義"""

from dataclasses import dataclass
from enum import Enum


class DataSource(str, Enum):
    DAIDATA = "daidata"
    KICONA_MULTI = "kicona_multi"  # アナスロ + みんレポ + みんパチ
    MARUHAN_MULTI = "maruhan_multi"  # daidata + アナスロ + みんレポ


@dataclass(frozen=True)
class StoreSourceConfig:
    store_id: str
    source: DataSource
    url: str
    name: str


STORE_SOURCES: dict[str, StoreSourceConfig] = {
    "maruhan_umeda": StoreSourceConfig(
        store_id="maruhan_umeda",
        source=DataSource.MARUHAN_MULTI,
        url="https://daidata.goraggio.com/207042",
        name="マルハン梅田店",
    ),
    "kicona_amagasaki": StoreSourceConfig(
        store_id="kicona_amagasaki",
        source=DataSource.KICONA_MULTI,
        url="https://ana-slo.com/%E3%83%9B%E3%83%BC%E3%83%AB%E3%83%87%E3%83%BC%E3%82%BF/%E5%85%B5%E5%BA%AB%E7%9C%8C/%E3%82%AD%E3%82%B3%E3%83%BC%E3%83%8A%E5%B0%BC%E5%B4%8E%E6%9C%AC%E5%BA%97-%E3%83%87%E3%83%BC%E3%82%BF%E4%B8%80%E8%A6%A7/",
        name="キコーナ尼崎本店",
    ),
}


def get_store_config(store_id: str, url_override: str | None = None) -> StoreSourceConfig | None:
    cfg = STORE_SOURCES.get(store_id)
    if not cfg:
        return None
    if url_override:
        return StoreSourceConfig(cfg.store_id, cfg.source, url_override, cfg.name)
    return cfg
