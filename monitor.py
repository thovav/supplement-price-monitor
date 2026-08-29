import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


PRODUCT_URL = (
    "https://www.cycheapersupplements.com/"
    "muscle-mass/12988-core-champs-l-carnitine-1000-mg-90-tabs-90-servings.html"
)

PRODUCT_NAME = "Core Champs L-Carnitine 1000 mg - 90 Tabs"

PRICE_FILE = Path("price_history.json")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def get_product_price():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36"
        )
    }

    response = requests.get(
        PRODUCT_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the product title first.
    title = soup.find(
        string=re.compile(
            r"Core Champs L-CARNITINE 1000 Mg 90 Tabs",
            re.IGNORECASE
        )
    )

    if not title:
        raise RuntimeError(
            "Could not find the product title on the page."
        )

    # Get the parent section containing the product information.
    product_section = title.parent

    # Walk upward until we have a sufficiently large section.
    for _ in range(8):
        if product_section.parent:
            product_section = product_section.parent

        section_text = product_section.get_text(
            " ",
            strip=True
        )

        if "21.99" in section_text or "25.99" in section_text:
            break

    # Search ONLY inside the product section.
    text = product_section.get_text(
        " ",
        strip=True
    )

    # Find euro prices.
    matches = re.findall(
        r"€\s*(-?\d+(?:[.,]\d{2})?)",
        text
    )

    prices = []

    for value in matches:
        try:
            price = float(value.replace(",", "."))

            # Ignore zero and negative values.
            if price > 0:
                prices.append(price)

        except ValueError:
            continue

    if not prices:
        raise RuntimeError(
            "Could not find a valid product price."
        )

    # The product page displays:
    #
    # €21.99
    # -€4.00
    # €25.99
    #
    # The first positive euro price is therefore
    # the current selling price.
    current_price = prices[0]

    print(
        f"Detected product prices: "
        f"{[f'€{p:.2f}' for p in prices]}"
    )

    print(
        f"Current product price: "
        f"€{current_price:.2f}"
    )

    return current_price
def load_previous_price():
    if not PRICE_FILE.exists():
        return None

    try:
        data = json.loads(PRICE_FILE.read_text())
        return data.get("price")
    except (json.JSONDecodeError, OSError):
        return None


def save_price(price):
    data = {
        "price": price,
        "checked_at": datetime.utcnow().isoformat() + "Z"
    }

    PRICE_FILE.write_text(
        json.dumps(data, indent=2)
    )


def send_telegram(message):
    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30
    )

    response.raise_for_status()


def main():
    current_price = get_product_price()
    previous_price = load_previous_price()

    print(f"Current price: €{current_price:.2f}")

    if previous_price is None:
        print("No previous price found. Saving current price.")
        save_price(current_price)
        return

    print(f"Previous price: €{previous_price:.2f}")

    if current_price < previous_price:
        reduction = previous_price - current_price
        percentage = (reduction / previous_price) * 100

        message = (
            f"🔔 PRICE DROP!\n\n"
            f"{PRODUCT_NAME}\n\n"
            f"Previous price: €{previous_price:.2f}\n"
            f"New price: €{current_price:.2f}\n"
            f"Reduction: €{reduction:.2f} "
            f"({percentage:.1f}%)\n\n"
            f"👉 {PRODUCT_URL}"
        )

        send_telegram(message)

        print("Price dropped. Telegram notification sent.")

    elif current_price > previous_price:
        print("Price increased. No notification.")

    else:
        print("Price unchanged.")

    save_price(current_price)


if __name__ == "__main__":
    main()
