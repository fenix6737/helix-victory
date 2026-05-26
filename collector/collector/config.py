import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from collector.sources import STORE_SOURCES, StoreSourceConfig, get_store_config

load_dotenv()


@dataclass
class CollectorConfig:
    api_url: str = os.getenv("API_URL", "http://localhost:8000")
    interval_normal_sec: int = int(os.getenv("COLLECTOR_INTERVAL_NORMAL_SEC", "180"))
    interval_peak_sec: int = int(os.getenv("COLLECTOR_INTERVAL_PEAK_SEC", "45"))
    peak_hours: tuple[int, ...] = tuple(
        int(h) for h in os.getenv("COLLECTOR_PEAK_HOURS", "10,11,17,18,19,20,21").split(",")
    )
    daidata_storage_state: str | None = os.getenv("DAIDATA_STORAGE_STATE")
    daidata_hist_days: int = int(os.getenv("DAIDATA_HIST_DAYS", "7"))
    minrepo_hist_days: int = int(os.getenv("MINREPO_HIST_DAYS", "7"))

    stores: dict[str, StoreSourceConfig] = field(default_factory=dict)

    def __post_init__(self):
        if not self.stores:
            self.stores = {}
            for sid, base in STORE_SOURCES.items():
                env_key = {
                    "maruhan_umeda": "MARUHAN_UMEDA_URL",
                    "kicona_amagasaki": "ANASLO_KICONA_LIST_URL",
                }.get(sid)
                if sid == "kicona_amagasaki" and env_key:
                    url = os.getenv(env_key) or os.getenv("KICONA_AMAGASAKI_URL", base.url)
                elif env_key:
                    url = os.getenv(env_key, base.url)
                else:
                    url = base.url
                self.stores[sid] = get_store_config(sid, url) or base

    @property
    def store_urls(self) -> dict[str, str]:
        return {k: v.url for k, v in self.stores.items()}

    def interval_for_hour(self, hour: int) -> int:
        if hour in self.peak_hours:
            return self.interval_peak_sec
        return self.interval_normal_sec


config = CollectorConfig()
