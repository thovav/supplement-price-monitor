import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


PRODUCTS = {
    "l_carnitine": {
        "name": "Core Champs L-Carnitine 1000 mg - 90 Tabs",
        "url": (
            "https://www.cycheapersupplements.com/"
            "muscle-mass/12988-core-champs-l-carnitine-1000-mg-90-tabs-90-servings.html"
        ),
        "title_pattern": r"Core Champs L-CARNITINE 1000 Mg 90 Tabs",
    },

    "pure_iso_whey": {
        "name": "Yava Labs Pure Iso Whey 2000 g - 66 Servings",
        "url": (
            "https://www.cycheapersupplements.com/"
            "muscle-mass/13408-yava-labs-pure-iso-whey-2000-g-66-servings.html"
        ),
        "title_pattern": r"Yava Labs Pure Iso Whey 2000 g - 66 Servings",
    },

    "core_isolate_exp": {
        "name": "Exp 08/02/2027 CORE CHAMPS 100% ISOLATE WHEY PROTEIN 2 Kgs - 67 Servings",
        "url": (
            "https://www.cycheapersupplements.com/"
            "muscle-mass/13607-exp-08022027-core-champs-100-isolate-whey-protein-2-kgs-67-servings.html"
        ),
        "title_pattern": (
            r"Exp 08/02/2027 CORE CHAMPS 100% ISOLATE "
            r"WHEY PROTEIN 2 Kgs -67 Servings"
        ),
    },
}


PRICE_FILE = Path("price_history.json")
PRICE_DROP_FILE = Path("price_drop_detected.json")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def get_product_price(product):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36"
        )
    }

    response = requests.get(
        product["url"],
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the specific product title.
    title = soup.find(
        string=re.compile(
            product["title_pattern"],
            re.IGNORECASE
        )
    )

    if not title:
        raise RuntimeError(
            f"Could not find product title: {product['name']}"
        )

    product_section = title.parent

    # Walk up the HTML tree until we reach the product
    # information section containing the prices.
    for _ in range(8):
        if product_section.parent:
            product_section = product_section.parent

        section_text = product_section.get_text(
            " ",
            strip=True
        )

        if "€" in section_text:
            break

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

            if price > 0:
                prices.append(price)

        except ValueError:
            continue

    if not prices:
        raise RuntimeError(
            f"Could not find a valid price for: {product['name']}"
        )

    current_price = prices[0]

    print(
        f"{product['name']}"
    )

    print(
        f"Detected prices: "
        f"{[f'€{p:.2f}' for p in prices]}"
    )

    print(
        f"Current price: "
        f"€{current_price:.2f}"
    )

    return current_price


def load_price_history():
    if not PRICE_FILE.exists():
        return {}

    try:
        with open(PRICE_FILE, "r") as f:
            history = json.load(f)

        # New multi-product format.
        if isinstance(history, dict):
            return history

        # Convert the old single-product list format.
        if isinstance(history, list):
            return {
                "l_carnitine": history
            }

    except (json.JSONDecodeError, TypeError):
        return {}

    return {}


def get_previous_price(history, product_id):
    product_history = history.get(product_id, [])

    if not product_history:
        return None

    return product_history[-1]["price"]


def save_price_history(history):
    with open(PRICE_FILE, "w") as f:
        json.dump(history, f, indent=2)


def add_price_to_history(history, product_id, price, checked_at):
    if product_id not in history:
        history[product_id] = []

    product_history = history[product_id]

    today = checked_at[:10]

    # Don't create duplicate entries if the workflow is
    # manually run more than once on the same day.
    if (
        product_history
        and product_history[-1].get("checked_at", "")[:10] == today
    ):
        product_history[-1] = {
            "price": round(price, 2),
            "checked_at": checked_at
        }
    else:
        product_history.append({
            "price": round(price, 2),
            "checked_at": checked_at
        })


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

def record_price_drop(
    product_id,
    product,
    previous_price,
    current_price
):
    reduction = previous_price - current_price
    percentage = (reduction / previous_price) * 100

    data = {
        "product_id": product_id,
        "product_name": product["name"],
        "url": product["url"],
        "previous_price": round(previous_price, 2),
        "current_price": round(current_price, 2),
        "reduction": round(reduction, 2),
        "percentage": round(percentage, 1)
    }

    with open(PRICE_DROP_FILE, "w") as f:
        json.dump(data, f, indent=2)
def send_price_drop_notification(
    product,
    previous_price,
    current_price
):
    reduction = previous_price - current_price
    percentage = (reduction / previous_price) * 100

    message = (
        f"🔔 PRICE DROP!\n\n"
        f"{product['name']}\n\n"
        f"Previous price: €{previous_price:.2f}\n"
        f"New price: €{current_price:.2f}\n"
        f"Reduction: €{reduction:.2f} "
        f"({percentage:.1f}%)\n\n"
        f"👉 {product['url']}"
    )

    send_telegram(message)


def send_monitor_failure_notification(errors):
    message = (
        "⚠️ PRICE MONITOR WARNING\n\n"
        "One or more products could not be checked.\n\n"
        + "\n".join(
            f"• {error}"
            for error in errors
        )
    )

    send_telegram(message)


def main():
    # Remove any previous price-drop trigger.
    # This prevents yesterday's alert from being sent again.
    if PRICE_DROP_FILE.exists():
        PRICE_DROP_FILE.unlink()

    history = load_price_history()

    checked_at = datetime.now(timezone.utc).isoformat()

    errors = []

    for product_id, product in PRODUCTS.items():

        print("\n" + "=" * 60)

        try:
            current_price = get_product_price(product)

            previous_price = get_previous_price(
                history,
                product_id
            )

            if previous_price is None:

                print(
                    f"No previous price for "
                    f"{product['name']}."
                )

            else:

                print(
                    f"Previous price: "
                    f"€{previous_price:.2f}"
                )

                if current_price < previous_price:

                    print(
                        "PRICE DROP DETECTED!"
                    )

                    record_price_drop(
                        product_id,
                        product,
                        previous_price,
                        current_price
                    )

                    send_price_drop_notification(
                        product,
                        previous_price,
                        current_price
                    )

                    print(
                        "Telegram price-drop "
                        "notification sent."
                    )

                elif current_price > previous_price:

                    print(
                        "Price increased. "
                        "No notification."
                    )

                else:

                    print(
                        "Price unchanged."
                    )

            add_price_to_history(
                history,
                product_id,
                current_price,
                checked_at
            )

        except Exception as error:

            error_message = (
                f"{product['name']}: {error}"
            )

            print(
                f"ERROR: {error_message}"
            )

            errors.append(error_message)

    # Save all successful product checks.
    save_price_history(history)

    print("\n" + "=" * 60)
    print("Price history saved.")

    if errors:

        print(
            f"{len(errors)} product(s) failed."
        )

        send_monitor_failure_notification(
            errors
        )

    else:

        print(
            "All products checked successfully."
        )
    main()
