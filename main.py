import os
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
# VARIANT_ID = 51377786945800  # size 28
VARIANT_ID = 51377787011336  # size 32

STORE_BASE = "https://derschutze.com"

def is_in_stock():
    url = f"{STORE_BASE}/cart/{VARIANT_ID}:1"
    r = requests.get(url, allow_redirects=True)
    if r.status_code == 200:
        text = r.text.lower()
        # Shopify returns "sold out" in the response if not available
        if "sold out" in text:
            print(f"Variant {VARIANT_ID} is sold out")
            return False
        print(f"Variant {VARIANT_ID} can be added to cart")
        return True
    print(f"Failed to check cart endpoint. Status code: {r.status_code}")
    return False

def get_friendly_title():
    """
    After the ATC GET, the item is in the cart.
    cart.js returns items with product_title and variant_title (size).
    """
    try:
        r = requests.get(f"{STORE_BASE}/cart.js")
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            if str(item.get("variant_id")) == str(VARIANT_ID):
                product = item.get("product_title", "").strip()
                size = item.get("variant_title", "").strip()
                friendly = f"{product} {size}".strip()
                # example -> '"blossom v2" raw Denim 34'
                return friendly
    except Exception as e:
        print("Could not read cart.js:", e)
    return None

def send_discord_notification(title_text):
    payload = {
        "embeds": [
            {
                "title": title_text or "ATC",
                "url": f"{STORE_BASE}/cart/{VARIANT_ID}:1",
                # optional nice touch: green accent
                "color": 0x00FF00
            }
        ]
    }
    requests.post(WEBHOOK_URL, json=payload)

if is_in_stock():
    title = get_friendly_title()  # e.g. '"blossom v2" raw Denim 34'
    print("Sending:", title or "ATC")
    send_discord_notification(title)
    print("Notification sent!")
else:
    print("Still sold out.")
