import os
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
# VARIANT_ID = 51377786945800  # size 28
VARIANT_ID = 51377787011336  # size 32

STORE_BASE = "https://derschutze.com"
ATC_URL = f"{STORE_BASE}/cart/{VARIANT_ID}:1"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; stock-checker/1.0)"
})

def is_in_stock():
    r = session.get(ATC_URL, allow_redirects=True, timeout=20)
    if r.status_code == 200:
        if "sold out" in r.text.lower():
            print(f"Variant {VARIANT_ID} is sold out")
            return False
        print(f"Variant {VARIANT_ID} can be added to cart")
        return True
    print(f"ATC check failed: {r.status_code}")
    return False

def get_title_from_cart():
    try:
        r = session.get(f"{STORE_BASE}/cart.js", timeout=20)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            # In cart.js, the variant id is "id"
            if str(item.get("id")) == str(VARIANT_ID):
                product = (item.get("product_title") or "").strip()
                size = (item.get("variant_title") or "").strip()
                if product and size:
                    return f"{product} {size}"
                # Fallback to item["title"] which is often "Product — Size"
                if item.get("title"):
                    return item["title"].strip()
    except Exception as e:
        print("cart.js read failed:", e)
    return None

def get_title_from_shopify_json():
    """Fallback path if cart.js didn't have the item."""
    try:
        r_var = session.get(f"{STORE_BASE}/variants/{VARIANT_ID}.json", timeout=20)
        if r_var.status_code != 200:
            return None
        variant = r_var.json().get("variant", {})
        product_id = variant.get("product_id")
        var_title = (variant.get("title") or "").strip()
        if not product_id:
            return var_title or None

        r_prod = session.get(f"{STORE_BASE}/products/{product_id}.json", timeout=20)
        if r_prod.status_code != 200:
            return var_title or None
        product_title = (r_prod.json().get("product", {}).get("title") or "").strip()
        if product_title and var_title:
            return f'{product_title} {var_title}'
        return product_title or var_title or None
    except Exception as e:
        print("Shopify JSON fallback failed:", e)
        return None

def build_title():
    # Try cart (most accurate to what’s actually in the cart)
    title = get_title_from_cart()
    if title:
        return title
    # Fallback to Shopify JSON endpoints (if enabled)
    title = get_title_from_shopify_json()
    if title:
        return title
    # Last resort
    return "ATC"

def send_discord_notification(title_text):
    payload = {
        "embeds": [
            {
                "title": title_text,  # e.g. `"blossom v2" raw Denim 34`
                "url": ATC_URL,
                "color": 0x00FF00
            }
        ]
    }
    session.post(WEBHOOK_URL, json=payload, timeout=20)

if is_in_stock():
    title = build_title()
    print("Sending:", title)
    send_discord_notification(title)
    print("Notification sent!")
else:
    print("Still sold out.")
