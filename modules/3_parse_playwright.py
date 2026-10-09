"""
Playwright automation & scraper for brain.com.ua.
Bypasses anti-bot blocks, selects 2nd autocomplete result,
extracts product details with fault-tolerant parsing,
and saves them into PostgreSQL via Django ORM.
"""

import re
import time
from decimal import Decimal
from pprint import pprint

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from load_django import *
from parser_app.models import Product

SEARCH_QUERY = "Apple iPhone 15 128GB Black"
BASE_URL = "https://brain.com.ua/"


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = text.replace("\xa0", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if cleaned else None


def clean_price(price_raw: str | None) -> Decimal | None:
    if not price_raw:
        return None
    price_str = str(price_raw).replace(",", ".").strip()
    price_str = re.sub(r"[^\d.]", "", price_str)
    try:
        return Decimal(price_str) if price_str else None
    except (ValueError, ArithmeticError):
        return None


def safe_extract(func, default=None):
    try:
        res = func()
        return res if res is not None else default
    except Exception:
        return default


def run():
    print("=== Starting Playwright Parser ===")

    parsed_data = {
        "title": None,
        "color": None,
        "memory": None,
        "vendor": None,
        "price_regular": None,
        "price_promo": None,
        "code": None,
        "reviews_count": 0,
        "screen_diagonal": None,
        "screen_resolution": None,
        "photos": [],
        "characteristics": {},
        "status": "Failed",
        "parser_type": "Playwright",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        print(f"[Step 1] Navigating to {BASE_URL}")
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        print(f"[Step 2] Typing search query: '{SEARCH_QUERY}'")
        desktop_input_selector = ".header-bottom input.quick-search-input"

        page.wait_for_selector(desktop_input_selector, state="visible", timeout=15000)

        search_input = page.locator(desktop_input_selector)
        search_input.click()
        search_input.fill("")
        search_input.type(SEARCH_QUERY, delay=40)

        print("[Step 3 & 4] Waiting for live search dropdown results...")
        dropdown_items_selector = ".qsr-products-list a.qsr-item"

        page.wait_for_selector(dropdown_items_selector, state="visible", timeout=15000)

        dropdown_items = page.locator(dropdown_items_selector)
        count = dropdown_items.count()

        if count >= 2:
            target_product = dropdown_items.nth(1)
        else:
            target_product = dropdown_items.nth(0)

        target_url = target_product.get_attribute("href")

        try:
            target_product.click()
        except Exception as e:
            page.goto(target_url, wait_until="domcontentloaded")

        page.wait_for_selector("h1.desktop-only-title", state="visible", timeout=15000)
        page.wait_for_timeout(1500)

        print("[Step 5] Extracting product details...")
        soup = BeautifulSoup(page.content(), "html.parser")

        code_elem = soup.select_one(".br-pr-code-val, #product_code .br-pr-code-val")
        parsed_data["code"] = safe_extract(lambda: clean_text(code_elem.text))

        if not parsed_data["code"]:
            browser.close()
            return

        title_elem = soup.select_one("h1.desktop-only-title, h1.main-title, h1")
        parsed_data["title"] = safe_extract(lambda: clean_text(title_elem.text))

        characteristics = {}
        chr_container = soup.select_one(".br-pr-chr")
        if chr_container:
            for section in chr_container.select(".br-pr-chr-item"):
                rows = section.select("div > div > div")
                for row in rows:
                    spans = row.select("span")
                    if len(spans) >= 2:
                        k = clean_text(spans[0].text)
                        v = clean_text(spans[1].text)
                        if k and v:
                            characteristics[k] = v

        parsed_data["characteristics"] = characteristics

        def get_spec(keys):
            for sk, sv in characteristics.items():
                for tk in keys:
                    if tk.lower() in sk.lower():
                        return sv
            return None

        parsed_data["color"] = safe_extract(lambda: get_spec(["Колір", "Цвет"]))
        parsed_data["memory"] = safe_extract(lambda: get_spec(["Вбудована пам'ять", "Объем памяти", "Пам'ять"]))
        parsed_data["vendor"] = safe_extract(lambda: get_spec(["Виробник", "Производитель", "Бренд"]))
        parsed_data["screen_diagonal"] = safe_extract(lambda: get_spec(["Діагональ екрану", "Диагональ экрана"]))
        parsed_data["screen_resolution"] = safe_extract(lambda: get_spec(["Роздільна здатність екрану", "Разрешение дисплея"]))

        def parse_prices():
            buy_btn = soup.select_one("a.order-block-btn, [data-price]")
            if buy_btn and buy_btn.get("data-price"):
                cur_p = clean_price(buy_btn.get("data-price"))
                old_p = clean_price(buy_btn.get("data-without-discount-price"))

                if cur_p and cur_p > 0:
                    if old_p and old_p != cur_p:
                        return old_p, cur_p
                    return cur_p, None
            return None, None

        reg_p, promo_p = safe_extract(parse_prices, default=(None, None))
        parsed_data["price_regular"] = reg_p
        parsed_data["price_promo"] = promo_p

        def parse_reviews():
            reviews_elem = soup.select_one(".reviews-count span, a.reviews-count")
            if reviews_elem:
                digits = "".join(filter(str.isdigit, reviews_elem.text))
                return int(digits) if digits else 0
            return 0

        parsed_data["reviews_count"] = safe_extract(parse_reviews, default=0)

        def parse_photos():
            photos_list = []
            for img in soup.select(".main-pictures-block img, .br-prs-f img, .product-block-bottom img"):
                src = clean_text(img.get("src") or img.get("data-src"))
                if src and "no-photo" not in src and "static/retail/images" not in src:
                    if src.startswith("//"):
                        src = f"https:{src}"
                    elif src.startswith("/"):
                        src = f"https://brain.com.ua{src}"

                    src_big = src.replace("small_", "big_")
                    if src_big not in photos_list:
                        photos_list.append(src_big)
            return photos_list

        parsed_data["photos"] = safe_extract(parse_photos, default=[])
        parsed_data["status"] = "Done"

        browser.close()

    print("\n--- Extracted Data (Playwright) ---")
    pprint(parsed_data)
    print("-----------------------------------\n")

    if parsed_data["code"]:
        try:
            product, created = Product.objects.update_or_create(
                code=parsed_data["code"],
                defaults={
                    "title": parsed_data["title"],
                    "color": parsed_data["color"],
                    "memory": parsed_data["memory"],
                    "vendor": parsed_data["vendor"],
                    "price_regular": parsed_data["price_regular"],
                    "price_promo": parsed_data["price_promo"],
                    "reviews_count": parsed_data["reviews_count"],
                    "screen_diagonal": parsed_data["screen_diagonal"],
                    "screen_resolution": parsed_data["screen_resolution"],
                    "photos": parsed_data["photos"],
                    "characteristics": parsed_data["characteristics"],
                    "status": parsed_data["status"],
                    "parser_type": parsed_data["parser_type"],
                },
            )
            action = "Created new" if created else "Updated existing"
            print(f"[DB Success] {action} record (ID: {product.pk}, Code: {product.code})")
        except Exception as e:
            print(f"[DB Error] Failed to save product to Postgres: {e}")
    else:
        print("[DB Skip] Product code missing, skipped database saving.")


if __name__ == "__main__":
    run()
