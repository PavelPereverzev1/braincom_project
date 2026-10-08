"""
Script to parse product details from brain.com.ua using Requests and BeautifulSoup4.
Saves extracted product data directly into PostgreSQL/Django DB.
"""

import os
import re
import sys
from decimal import Decimal
from pprint import pprint

import requests
from bs4 import BeautifulSoup

from load_django import *
from parser_app.models import Product

URL = "https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_16_Pro_Max_256GB_Black_Titanium-p1145443.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
}


def clean_text(text: str | None) -> str | None:
    """Removes extra spaces, newlines, and non-breaking spaces."""
    if not text:
        return None
    text = text.replace("\xa0", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if cleaned else None


def clean_price(price_raw: str | None) -> Decimal | None:
    """Safely extracts price and converts to Decimal."""
    if not price_raw:
        return None

    # Залишаємо тільки цифри, крапки та коми
    price_str = str(price_raw).replace(",", ".").strip()
    price_str = re.sub(r"[^\d.]", "", price_str)

    try:
        return Decimal(price_str) if price_str else None
    except (ValueError, ArithmeticError):
        return None


def run():
    print("=== Starting BS4 / Requests Parser ===")

    try:
        response = requests.get(URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"Failed to fetch page content: {e}")
        return

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
        "parser_type": "BS4",
    }

    # Extract Code first (critical field)
    try:
        code_elem = soup.select_one(".br-pr-code-val, #product_code .br-pr-code-val")
        if code_elem:
            parsed_data["code"] = clean_text(code_elem.text)
    except Exception as e:
        print(f"Error parsing product code: {e}")

    if not parsed_data["code"]:
        print("[Error] Product code not found! Aborting save to DB to prevent invalid data.")
        return

    # Extract Title
    try:
        title_elem = soup.select_one("h1.desktop-only-title, h1.main-title, h1")
        if title_elem:
            parsed_data["title"] = clean_text(title_elem.text)
    except Exception as e:
        print(f"Error parsing title: {e}")

    # Extract Specifications
    characteristics = {}
    try:
        chr_container = soup.select_one(".br-pr-chr")
        if chr_container:
            for section in chr_container.select(".br-pr-chr-item"):
                rows = section.select("div > div > div")

                for row in rows:
                    spans = row.select("span")
                    if len(spans) >= 2:
                        key = clean_text(spans[0].text)
                        val = clean_text(spans[1].text)
                        if key and val:
                            characteristics[key] = val
    except Exception as e:
        print(f"Error parsing characteristics: {e}")

    parsed_data["characteristics"] = characteristics

    def get_spec_val(keys):
        for spec_key, spec_val in characteristics.items():
            for target_key in keys:
                if target_key.lower() in spec_key.lower():
                    return spec_val
        return None

    parsed_data["color"] = get_spec_val(["Колір", "Цвет"])
    parsed_data["memory"] = get_spec_val(["Вбудована пам'ять", "Объем памяти", "Пам'ять"])
    parsed_data["vendor"] = get_spec_val(["Виробник", "Производитель", "Бренд"])
    parsed_data["screen_diagonal"] = get_spec_val(["Діагональ екрану", "Диагональ экрана", "Діагональ дисплея"])
    parsed_data["screen_resolution"] = get_spec_val(
        ["Роздільна здатність екрану", "Разрешение дисплея", "Роздільна здатність дисплея"]
    )

    # Extract Prices
    try:
        buy_btn = soup.select_one("a.order-block-btn, [data-price]")

        if buy_btn and buy_btn.get("data-price"):
            current_price = clean_price(buy_btn.get("data-price"))
            without_discount = clean_price(buy_btn.get("data-without-discount-price"))

            if current_price and current_price > 0:
                if without_discount and without_discount != current_price:
                    parsed_data["price_regular"] = without_discount
                    parsed_data["price_promo"] = current_price
                else:
                    parsed_data["price_regular"] = current_price

        if not parsed_data["price_regular"]:
            old_price_elem = soup.select_one(".br-pr-op .price-wrapper")
            new_price_elem = soup.select_one(".br-pr-np .price-wrapper")

            old_price = clean_price(old_price_elem.text) if old_price_elem else None
            new_price = clean_price(new_price_elem.text) if new_price_elem else None

            if old_price and new_price:
                parsed_data["price_regular"] = old_price
                parsed_data["price_promo"] = new_price
            elif new_price:
                parsed_data["price_regular"] = new_price

    except Exception as e:
        print(f"Error parsing prices: {e}")

    # Extract Review Count
    try:
        reviews_elem = soup.select_one(".reviews-count span, a.reviews-count")
        if reviews_elem:
            digits = "".join(filter(str.isdigit, reviews_elem.text))
            parsed_data["reviews_count"] = int(digits) if digits else 0
    except Exception as e:
        print(f"Error parsing reviews count: {e}")

    # Extract Photos
    photos = []
    try:
        photo_elements = soup.select(".main-pictures-block img, .br-prs-f img, .product-block-bottom img")

        for img in photo_elements:
            raw_src = img.get("src") or img.get("data-src")
            src = clean_text(raw_src)

            if src:
                if "no-photo" in src or "static/retail/images" in src:
                    continue

                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = "https://brain.com.ua" + src

                src_big = src.replace("small_", "big_")

                if src_big not in photos:
                    photos.append(src_big)

    except Exception as e:
        print(f"Error parsing photos: {e}")

    parsed_data["photos"] = photos

    print("\n--- Extracted Data ---")
    pprint(parsed_data)
    print("----------------------\n")

    # Save to Django ORM
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
    print(f"[Success] {action} record in DB (ID: {product.id}, Code: {product.code})")


if __name__ == "__main__":
    run()