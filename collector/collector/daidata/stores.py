"""台データオンライン店舗IDマッピング"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DaidataStore:
    helix_store_id: str
    daidata_shop_id: str
    name: str
    note: str = ""


STORES: dict[str, DaidataStore] = {
    "maruhan_umeda": DaidataStore(
        helix_store_id="maruhan_umeda",
        daidata_shop_id="207042",
        name="マルハン梅田店",
    ),
}


def shop_id_from_url(url: str) -> str | None:
    import re

    m = re.search(r"daidata\.goraggio\.com/(\d+)", url)
    return m.group(1) if m else None


def resolve_store(helix_store_id: str, url: str | None = None) -> DaidataStore | None:
    if url:
        sid = shop_id_from_url(url)
        if sid:
            for s in STORES.values():
                if s.daidata_shop_id == sid:
                    return s
            return DaidataStore(helix_store_id, sid, helix_store_id)
    return STORES.get(helix_store_id)
