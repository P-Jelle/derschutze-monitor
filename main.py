import os
import math
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
# STORE_BASE = "https://derschutze.com"
STORE_BASE = "https://shop.travisscott.com"
VARIANT_IDS = [
    # 52611247636744,
    # 50662297796872,
    44560884072575,
    44560883155071
]
USER_AGENT = "Mozilla/5.0 (compatible; stock-checker/1.0)"
USE_JSON_CHECK_ONLY = False

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def atc_url(variant_id: int) -> str:
    return f"{STORE_BASE}/cart/{variant_id}:1"

def is_in_stock_via_atc(variant_id: int) -> bool:
    """ATC check (adds the item to cart)."""
    r = session.get(atc_url(variant_id), allow_redirects=True, timeout=20)
    return r.status_code == 200 and "sold out" not in r.text.lower()

def is_in_stock_via_json(variant_id: int) -> bool:
    """
    JSON-only check that doesn't add to cart.
    Many Shopify stores expose /variants/{id}.json with 'available' boolean.
    """
    try:
        rv = session.get(f"{STORE_BASE}/variants/{variant_id}.json", timeout=20)
        if rv.status_code != 200:
            return False
        variant = rv.json().get("variant", {}) or {}
        return bool(variant.get("available"))
    except Exception:
        return False

def get_from_cart_for(variant_id: int):
    """
    After ATC, read cart.js and pull (product_title, size_text, image_url) for this variant.
    """
    try:
        r = session.get(f"{STORE_BASE}/cart.js", timeout=20)
        r.raise_for_status()
        for item in r.json().get("items", []):
            if str(item.get("id")) == str(variant_id):
                product = (item.get("product_title") or "").strip()
                size = (item.get("variant_title") or "").strip()
                # Image
                image_url = item.get("image") or None
                if not image_url:
                    fi = item.get("featured_image") or {}
                    image_url = fi.get("url")
                return product or None, size or None, image_url
    except Exception as e:
        print("cart.js read failed:", e)
    return None, None, None

def get_from_shopify_json_for(variant_id: int):
    """
    Fallback using Shopify JSON endpoints.
    Returns (product_title, size_text, image_url).
    """
    product_title, size_text, image_url = None, None, None
    try:
        rv = session.get(f"{STORE_BASE}/variants/{variant_id}.json", timeout=20)
        if rv.status_code != 200:
            return None, None, None
        variant = rv.json().get("variant", {}) or {}
        size_text = (variant.get("title") or "").strip()
        product_id = variant.get("product_id")
        variant_image_id = variant.get("image_id")

        if product_id:
            rp = session.get(f"{STORE_BASE}/products/{product_id}.json", timeout=20)
            if rp.status_code == 200:
                product = rp.json().get("product", {}) or {}
                product_title = (product.get("title") or "").strip()

                # choose image
                images = product.get("images", []) or []
                if variant_image_id:
                    for img in images:
                        if str(img.get("id")) == str(variant_image_id) and img.get("src"):
                            src = img["src"]
                            image_url = "https:" + src if src.startswith("//") else src
                            break
                if not image_url and images:
                    src = images[0].get("src")
                    if src:
                        image_url = "https:" + src if src.startswith("//") else src

        return product_title or None, size_text or None, image_url
    except Exception as e:
        print("Shopify JSON fallback failed:", e)
        return None, None, None

def build_embed_for_variant(variant_id: int):
    """
    Returns an embed dict for this variant if in stock, else None.
    """
    in_stock = is_in_stock_via_json(variant_id) if USE_JSON_CHECK_ONLY else is_in_stock_via_atc(variant_id)
    if not in_stock:
        print(f"{variant_id}: still sold out")
        return None

    product_title, size_text, image_url = get_from_cart_for(variant_id)
    if not product_title:
        product_title, size_text, image_url = get_from_shopify_json_for(variant_id)

    title_for_embed = product_title or "ATC"
    desc = f"Size: {size_text}" if size_text else None

    embed = {
        "title": title_for_embed,
        "url": atc_url(variant_id),
    }
    if desc:
        embed["description"] = desc
    if image_url:
        embed["thumbnail"] = {"url": image_url}

    print(f"{variant_id}: sending embed -> {title_for_embed} | {desc or ''} | image: {image_url or 'none'}")
    return embed

def send_embeds(embeds):
    """Send embeds in batches of 10 to respect Discord webhook limits."""
    for i in range(0, len(embeds), 10):
        batch = embeds[i:i+10]
        payload = {"embeds": batch}
        session.post(WEBHOOK_URL, json=payload, timeout=20)

def main():
    embeds = []
    for vid in VARIANT_IDS:
        embed = build_embed_for_variant(vid)
        if embed:
            embeds.append(embed)

    if embeds:
        send_embeds(embeds)
        print(f"Notification sent! ({len(embeds)} embed(s))")
    else:
        print("No in-stock variants right now.")


if __name__ == "__main__":
    main()
