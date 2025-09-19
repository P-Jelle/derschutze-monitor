import os
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
# VARIANT_ID = 51377786945800  # size 28
VARIANT_ID = 51377787011336  # size 32

STORE_BASE = "https://derschutze.com"
ATC_URL = f"{STORE_BASE}/cart/{VARIANT_ID}:1"

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; stock-checker/1.0)"})


def is_in_stock():
    r = session.get(ATC_URL, allow_redirects=True, timeout=20)
    if r.status_code == 200 and "sold out" not in r.text.lower():
        return True
    return False


def get_from_cart():
    """Return (title, image_url) if present in cart.js for our variant."""
    try:
        r = session.get(f"{STORE_BASE}/cart.js", timeout=20)
        r.raise_for_status()
        for item in r.json().get("items", []):
            if str(item.get("id")) == str(VARIANT_ID):
                # Title
                product = (item.get("product_title") or "").strip()
                size = (item.get("variant_title") or "").strip()
                title = (f"{product} {size}".strip()) or (item.get("title") or "ATC")

                # Image (Shopify usually provides absolute URL in item["image"])
                image_url = item.get("image") or None
                # Some themes expose featured_image as dict with "url"
                if not image_url:
                    fi = item.get("featured_image") or {}
                    image_url = fi.get("url")

                return title, image_url
    except Exception as e:
        print("cart.js read failed:", e)
    return None, None


def get_from_shopify_json():
    """
    Fallback using Shopify JSON endpoints.
    Returns (title, image_url).
    """
    title, image_url = None, None
    try:
        rv = session.get(f"{STORE_BASE}/variants/{VARIANT_ID}.json", timeout=20)
        if rv.status_code != 200:
            return None, None
        variant = rv.json().get("variant", {})
        var_title = (variant.get("title") or "").strip()
        product_id = variant.get("product_id")
        variant_image_id = variant.get("image_id")

        if product_id:
            rp = session.get(f"{STORE_BASE}/products/{product_id}.json", timeout=20)
            if rp.status_code == 200:
                product = rp.json().get("product", {}) or {}
                product_title = (product.get("title") or "").strip()
                if product_title and var_title:
                    title = f"{product_title} {var_title}"
                else:
                    title = product_title or var_title or "ATC"

                # Find best image:
                # 1) Variant image match
                images = product.get("images", []) or []
                if variant_image_id:
                    for img in images:
                        if str(img.get("id")) == str(variant_image_id) and img.get("src"):
                            image_url = "https:" + img["src"] if img["src"].startswith("//") else img["src"]
                            break
                # 2) First product image
                if not image_url and images:
                    src = images[0].get("src")
                    if src:
                        image_url = "https:" + src if src.startswith("//") else src
        else:
            # No product id—use variant title only
            title = var_title or "ATC"
    except Exception as e:
        print("Shopify JSON fallback failed:", e)

    return title, image_url


def build_title_and_image():
    title, img = get_from_cart()
    if title:
        # Split out the size if title looks like "Product Size"
        parts = title.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0], parts[1], img
        return title, None, img

    title2, img2 = get_from_shopify_json()
    if title2:
        parts = title2.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0], parts[1], img2
        return title2, None, img2

    return "ATC", None, img


def send_discord_notification(product_title, size_text=None, image_url=None):
    embed = {
        "title": product_title,   # just the product name
        "url": ATC_URL,
    }
    # put size on its own line
    if size_text:
        embed["description"] = f"Size: {size_text}"

    if image_url:
        embed["thumbnail"] = {"url": image_url}

    payload = {"embeds": [embed]}
    session.post(WEBHOOK_URL, json=payload, timeout=20)



if is_in_stock():
    product, size, img = build_title_and_image()
    print("Sending:", product, size or "", "| image:", img or "none")
    send_discord_notification(product, size, img)
    print("Notification sent!")
else:
    print("Still sold out.")
