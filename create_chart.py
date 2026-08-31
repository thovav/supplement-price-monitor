import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt


PRICE_FILE = Path("price_history.json")
OUTPUT_FILE = Path("price_history.png")


PRODUCT_NAMES = {
    "l_carnitine": "L-Carnitine",
    "pure_iso_whey": "Pure Iso Whey",
    "core_isolate_exp": "Core Isolate Whey",
}


def load_history():
    with open(PRICE_FILE, "r") as f:
        return json.load(f)


def build_chart(history):
    plt.figure(figsize=(12, 6))

    for product_id, product_name in PRODUCT_NAMES.items():

        records = history.get(product_id, [])

        if not records:
            continue

        dates = []
        prices = []

        for record in records:
            date = datetime.fromisoformat(
                record["checked_at"].replace("Z", "+00:00")
            )

            dates.append(date)
            prices.append(record["price"])

        plt.plot(
            dates,
            prices,
            marker="o",
            label=product_name
        )

    plt.title("Supplement Price History")
    plt.xlabel("Date")
    plt.ylabel("Price (€)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    plt.savefig(
        OUTPUT_FILE,
        dpi=150
    )

    plt.close()

    print(f"Chart saved to {OUTPUT_FILE}")


def main():
    if not PRICE_FILE.exists():
        raise RuntimeError(
            "price_history.json does not exist."
        )

    history = load_history()

    build_chart(history)


if __name__ == "__main__":
    main()
