"""
SeleniumBase (UC Mode) automation & scraper for brain.com.ua.
Bypasses 403 AJAX blocks on live search, extracts product data,
and saves it into PostgreSQL via Django ORM.
"""

import time
from decimal import Decimal
from pprint import pprint

from bs4 import BeautifulSoup
from seleniumbase import SB

from load_django import *
from parser_app.models import Product

SEARCH_QUERY = "Apple iPhone 15 128GB Black"
BASE_URL = "https://brain.com.ua/"


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    import re
    text = text.replace("\xa0", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if cleaned else None


def clean_price(price_raw: str | None) -> Decimal | None:
    if not price_raw:
        return None
    import re
    price_str = str(price_raw).replace(",", ".").strip()
    price_str = re.sub(r"[^\d.]", "", price_str)
    try:
        return Decimal(price_str) if price_str else None
    except (ValueError, ArithmeticError):
        return None


def run():
    print("=== Starting SeleniumBase (UC Mode) Parser ===")

    with SB(uc=True, headless=False) as sb:
        sb.uc_open_with_reconnect(BASE_URL, reconnect_time=3)
        sb.sleep(2)

        desktop_input_selector = ".header-bottom input.quick-search-input"

        sb.wait_for_element_visible(desktop_input_selector, timeout=15)

        driver = sb.driver
        search_input = driver.find_element("css selector", desktop_input_selector)

        search_input.click()
        sb.sleep(0.3)
        search_input.clear()

        search_input.send_keys(SEARCH_QUERY)

        dropdown_item_selector = ".qsr-products-list a.qsr-item"

        sb.wait_for_element_visible(dropdown_item_selector, timeout=15)

        first_product = driver.find_element("css selector", dropdown_item_selector)
        first_product_url = first_product.get_attribute("href")

        try:
            first_product.click()
        except Exception:
            driver.get(first_product_url)

        soup = BeautifulSoup(sb.get_page_source(), "html.parser")

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
            "status": "Done",
            "parser_type": "Selenium",
        }

        code_elem = soup.select_one(".br-pr-code-val, #product_code .br-pr-code-val")
        if code_elem:
            parsed_data["code"] = clean_text(code_elem.text)

        if not parsed_data["code"]:
            print("[Error] Could not extract product code.")
            return

        title_elem = soup.select_one("h1.desktop-only-title, h1.main-title, h1")
        if title_elem:
            parsed_data["title"] = clean_text(title_elem.text)

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

        parsed_data["color"] = get_spec(["Колір", "Цвет"])
        parsed_data["memory"] = get_spec(["Вбудована пам'ять", "Объем памяти", "Пам'ять"])
        parsed_data["vendor"] = get_spec(["Виробник", "Производитель", "Бренд"])
        parsed_data["screen_diagonal"] = get_spec(["Діагональ екрану", "Диагональ экрана"])
        parsed_data["screen_resolution"] = get_spec(["Роздільна здатність екрану", "Разрешение дисплея"])

        buy_btn = soup.select_one("a.order-block-btn, [data-price]")
        if buy_btn and buy_btn.get("data-price"):
            cur_p = clean_price(buy_btn.get("data-price"))
            old_p = clean_price(buy_btn.get("data-without-discount-price"))

            if cur_p and cur_p > 0:
                if old_p and old_p != cur_p:
                    parsed_data["price_regular"] = old_p
                    parsed_data["price_promo"] = cur_p
                else:
                    parsed_data["price_regular"] = cur_p

        reviews_elem = soup.select_one(".reviews-count span, a.reviews-count")
        if reviews_elem:
            digits = "".join(filter(str.isdigit, reviews_elem.text))
            parsed_data["reviews_count"] = int(digits) if digits else 0

        photos = []
        for img in soup.select(".main-pictures-block img, .br-prs-f img, .product-block-bottom img"):
            src = clean_text(img.get("src") or img.get("data-src"))
            if src and "no-photo" not in src and "static/retail/images" not in src:
                if src.startswith("//"):
                    src = f"https:{src}"
                elif src.startswith("/"):
                    src = f"https://brain.com.ua{src}"

                src_big = src.replace("small_", "big_")
                if src_big not in photos:
                    photos.append(src_big)

        parsed_data["photos"] = photos

        print("\n--- Extracted Data ---")
        pprint(parsed_data)
        print("--------------------------------\n")

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
        print(f"Success {action} DB record (ID: {product.pk}, Code: {product.code})")


if __name__ == "__main__":
    run()