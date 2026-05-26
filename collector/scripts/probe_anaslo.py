import asyncio
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

LIST_URL = (
    "https://ana-slo.com/%E3%83%9B%E3%83%BC%E3%83%AB%E3%83%87%E3%83%BC%E3%82%BF/"
    "%E5%85%B5%E5%BA%AB%E7%9C%8C/%E3%82%AD%E3%82%B3%E3%83%BC%E3%83%8A%E5%B0%BC%E5%B4%8E%E6%9C%AC%E5%BA%97-%E3%83%87%E3%83%BC%E3%82%BF%E4%B8%80%E8%A6%A7/"
)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="ja-JP")
        page = await ctx.new_page()
        await page.goto(LIST_URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(8000)

        link = page.locator('a[href*="2026-05-14"][href*="data"]').first
        await link.click()
        await page.wait_for_timeout(15000)
        html = await page.content()
        print("url:", page.url)
        print("len:", len(html))
        with open("samples/anaslo_day.html", "w", encoding="utf-8") as f:
            f.write(html)

        soup = BeautifulSoup(html, "lxml")
        print("台番:", len(soup.find_all(string=re.compile("台番"))))
        tables = soup.find_all("table")
        print("tables:", len(tables))
        for t in tables[:3]:
            print("table class", t.get("class"), "rows", len(t.find_all("tr")))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
