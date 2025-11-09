import os
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# STORE_BASE = "https://derschutze.com"
STORE_BASE = "https://shop.travisscott.com"

VARIANT_IDS = [
    # 52611247636744,
    # 50662297796872,
    44560884072575,
]

USER_AGENT = "Mozilla/5.0 (compatible; stock-checker/2.0)"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def atc_url(variant_id: int) -> str:
    return f"{STORE_BASE}/cart/{variant_id}:1"


# ---------- STOCK CHECK METHODS ----------

def is_in_stock_via_json(variant_id: int) -> bool:
    """Check stock using /variants/{id}.json (most reliable when available)."""
    try:
        r = session.get(f"{STORE_BASE}/variants/{variant_id}.json", timeout=15)
        if r.status_code != 200:
            return False
        data = r.json().get("variant", {})
        return bool(data.get("available"))
    except Exception:
        return False


def get_product_handle_from_variant(variant_id: int):
    """Fetch product handle via the /variants endpoint (used for .js fallback)."""
    try:
        r = session.get(f"{STORE_BASE}/variants/{variant_id}.json", timeout=15)
        if r.status_code != 200:
            return None
        product_id = r.json().get("variant", {}).get("product_id")
        if not product_id:
            return None
        rp = session.get(f"{STORE_BASE}/products/{product_id}.json", timeout=15)
        if rp.status_code != 200:
            return None
        product = rp.json().get("product", {})
        return product.get("handle")
    except Exception:
        return None


def is_in_stock_via_product_handle(variant_id: int, handle: str) -> bool:
    """Check stock via /products/{handle}.js — same data Shopify uses on site."""
    try:
        r = session.get(f"{STORE_BASE}/products/{handle}.js", timeout=15)
        if r.status_code != 200:
            return False
        product = r.json()
        for v in product.get("variants", []):
            if v["id"] == variant_id:
                return v.get("available", False)
        return False
    except Exception:
        return False


def is_in_stock_via_atc(variant_id: int) -> bool:
    """Fallback: ATC check — only if JSON endpoints fail."""
    try:
        r = session.get(atc_url(variant_id), allow_redirects=True, timeout=15)
        text = r.text.lower()
        if any(x in text for x in ["sold out", "unavailable", "out of stock", "cart is empty"]):
            return False
        return r.status_code == 200
    except Exception:
        return False


def is_in_stock(variant_id: int) -> bool:
    """Unified reliable check with fallbacks."""
    # 1. Try variant JSON
    if is_in_stock_via_json(variant_id):
        return True

    # 2. Try product handle
    handle = get_product_handle_from_variant(variant_id)
    if handle and is_in_stock_via_product_handle(variant_id, handle):
        return True

    # 3. Fallback ATC
    return is_in_stock_via_atc(variant_id)


# ---------- INFO FETCHING ----------

def get_variant_info(variant_id: int):
    """Return (title, size, image_url) from JSON endpoints."""
    try:
        rv = session.get(f"{STORE_BASE}/variants/{variant_id}.json", timeout=15)
        if rv.status_code != 200:
            return None, None, None
        variant = rv.json().get("variant", {})
        size_text = variant.get("title", "").strip()
        product_id = variant.get("product_id")
        image_url = None
        product_title = None
        if product_id:
            rp = session.get(f"{STORE_BASE}/products/{product_id}.json", timeout=15)
            if rp.status_code == 200:
                product = rp.json().get("product", {})
                product_title = product.get("title", "").strip()
                imgs = product.get("images", [])
                if imgs:
                    src = imgs[0].get("src")
                    if src:
                        image_url = "https:" + src if src.startswith("//") else src
        return product_title, size_text, image_url
    except Exception:
        return None, None, None


# ---------- DISCORD ----------

def build_embed_for_variant(variant_id: int):
    """Build Discord embed if variant is in stock."""
    if not is_in_stock(variant_id):
        print(f"{variant_id}: still sold out.")
        return None

    product_title, size_text, image_url = get_variant_info(variant_id)
    if not product_title:
        product_title = "Product"
    desc = f"Size: {size_text}" if size_text else None

    embed = {
        "title": product_title,
        "url": atc_url(variant_id),
    }
    if desc:
        embed["description"] = desc
    if image_url:
        embed["thumbnail"] = {"url": image_url}

    print(f"{variant_id}: IN STOCK -> {product_title} | {size_text or 'Unknown'}")
    return embed


def send_embeds(embeds):
    """Send embeds in batches (Discord max = 10 per message)."""
    for i in range(0, len(embeds), 10):
        batch = embeds[i:i+10]
        payload = {"embeds": batch}
        session.post(WEBHOOK_URL, json=payload, timeout=15)


# ---------- MAIN ----------

def main():
    embeds = []
    for vid in VARIANT_IDS:
        embed = build_embed_for_variant(vid)
        if embed:
            embeds.append(embed)

    if embeds:
        send_embeds(embeds)
        print(f"✅ Notification sent ({len(embeds)} embed(s))")
    else:
        print("❌ No in-stock variants right now.")


if __name__ == "__main__":
    main()
