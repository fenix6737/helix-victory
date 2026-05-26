from collector.daidata.parser import parse_all_list_html

__all__ = ["parse_all_list_html", "scrape_daidata_store"]


def scrape_daidata_store(*args, **kwargs):
    from collector.daidata.client import scrape_daidata_store as _fn

    return _fn(*args, **kwargs)
