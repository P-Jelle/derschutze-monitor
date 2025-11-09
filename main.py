import os
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# STORE_BASE = "https://derschutze.com"
STORE_BASE = "https://shop.travisscott.com"

# You only need to know the product handle and variant ID
PRODUCTS = [
    {
        "handle": "air-jordan-1-low-og-sp-november-fragment-pl",  # Example handle
        "variant_ids": [
            # 52611247636744,
            # 50662297796872,
            44560884072575,
        ],
    },
]

USER_AGENT = "Mozilla/5.0 (compatible; stock-checker/4.0)"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def atc_url(variant_id: int) -> str:
    return f"{STORE_BASE}/cart/{variant_id}:1"


def is_in_stock(handle: str, variant_id: int) -> bool:
    """
    Checks live product availability via /products/{handle}.js
    This is the same data Shopify uses to enable or disable size buttons.
    """
    try:
        r = session.get(f"{STORE_BASE}/products/{handle}.js", timeout=15)
        if r.status_code != 200:
            print(f"⚠️ Failed to load {handle}.js (status {r.status_code})")
            return False

        product = r.json()
        for variant in product.get("variants", []):
            if variant["id"] == variant_id:
                available = bool(variant.get("available"))
                return available
        return False
    except Exception as e:
        print(f"Error checking stock for {handle} ({variant_id}): {e}")
        return False


def get_variant_info(handle: str, variant_id: int):
    """Returns (title, size, image_url) for the given variant."""
    try:
        r = session.get(f"{STORE_BASE}/products/{handle}.js", timeout=15)
        r.raise_for_status()
        product = r.json()
        product_title = product.get("title", "Product").strip()
        image_url = None
        if product.get("images"):
            src = product["images"][0]
            image_url = "https:" + src if src.startswith("//") else src

        size_text = None
        for v in product.get("variants", []):
            if v["id"] == variant_id:
                size_text = v.get("title", "").strip()
                break

        return product_title, size_text, image_url
    except Exception as e:
        print(f"Error getting info for {handle}: {e}")
        return None, None, None


def build_embed(handle: str, variant_id: int):
    """Builds Discord embed for an in-stock variant."""
    if not is_in_stock(handle, variant_id):
        print(f"{variant_id}: still sold out.")
        return None

    product_title, size_text, image_url = get_variant_info(handle, variant_id)
    desc = f"Size: {size_text}" if size_text else None

    embed = {
        "title": product_title or "Product",
        "url": atc_url(variant_id),
    }
    if desc:
        embed["description"] = desc
    if image_url:
        embed["thumbnail"] = {"url": image_url}

    print(f"{variant_id}: ✅ IN STOCK -> {product_title} | {size_text or 'Unknown'}")
    return embed


def send_embeds(embeds):
    """Send embeds in batches (Discord max = 10 per message)."""
    for i in range(0, len(embeds), 10):
        batch = embeds[i:i + 10]
        payload = {"embeds": batch}
        session.post(WEBHOOK_URL, json=payload, timeout=15)


def main():
    embeds = []
    for product in PRODUCTS:
        handle = product["handle"]
        for vid in product["variant_ids"]:
            embed = build_embed(handle, vid)
            if embed:
                embeds.append(embed)

    if embeds:
        send_embeds(embeds)
        print(f"✅ Notification sent ({len(embeds)} embed(s))")
    else:
        print("❌ No in-stock variants right now.")


if __name__ == "__main__":
    main()
