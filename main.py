import os
import time
import requests
from typing import List, Tuple, Optional

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")

# STORE_BASE = "https://derschutze.com"
STORE_BASE = "https://shop.travisscott.com"

# Voorbeeld product — variant_ids kunnen leeg blijven als auto-fetch aan staat.
PRODUCTS = [
    {
        "handle": "cj-x-fragment-x-nike-houston-to-ise-mie-longsleeve",
        "variant_ids": [
            # 52611247636744,
            # 50662297796872,
            # 44560884072575,
        ],
    },
]

# Realistisch browser User-Agent + headers om botfilter te omzeilen
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/122.0.0.0 Safari/537.36")
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    # Referer moet per product ingesteld worden wanneer we een handle kennen
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    # Optional: Connection keep-alive
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(DEFAULT_HEADERS)
REQUEST_TIMEOUT = 15


def product_js_url(handle: str) -> str:
    return f"{STORE_BASE}/products/{handle}.js"


def atc_url(variant_id: int) -> str:
    return f"{STORE_BASE}/cart/{variant_id}:1"


def fetch_product_json(handle: str, retries: int = 3, backoff: float = 1.0) -> Optional[dict]:
    """
    Try to fetch /products/{handle}.js using browser-like headers.
    Returns parsed JSON dict on success, or None on permanent failure.
    If blocked (403/401/429), returns None and prints instruction.
    """
    url = product_js_url(handle)
    # set Referer specifically for this product
    headers = session.headers.copy()
    headers["Referer"] = f"{STORE_BASE}/products/{handle}"

    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            status = resp.status_code
            if status == 200:
                try:
                    return resp.json()
                except ValueError:
                    print(f"[{handle}] JSON parse error (status 200).")
                    return None
            elif status in (403, 401):
                # Likely blocked by bot protection
                print(f"[{handle}] REQUEST BLOCKED (HTTP {status}).")
                print("— Probeer in je browser: open:")
                print(f"  {url}")
                print("  Kopieer de JSON response en plak 'm lokaal als backup.")
                return None
            elif status == 429:
                print(f"[{handle}] Rate limited (429). Backing off.")
                time.sleep(backoff * attempt)
            else:
                print(f"[{handle}] Unexpected status {status}. Attempt {attempt}/{retries}.")
                time.sleep(backoff * attempt)
        except requests.RequestException as e:
            print(f"[{handle}] Request failed: {e}. Attempt {attempt}/{retries}.")
            time.sleep(backoff * attempt)
    print(f"[{handle}] Failed to fetch product JSON after {retries} attempts.")
    return None


def extract_variants_from_product_json(product_json: dict) -> List[dict]:
    """
    Given the product JSON (from /products/{handle}.js), return the variants list.
    Each variant is the dict with at least 'id', 'title', 'available'.
    """
    if not product_json:
        return []
    return product_json.get("variants", [])


def ensure_product_variants_autofilled(products: List[dict]) -> List[dict]:
    """
    For every product entry, if 'variant_ids' is empty, try to auto-fill from handle.
    If fetching is blocked, leaves variant_ids as-is and prints an instruction.
    """
    for p in products:
        handle = p.get("handle")
        vids = p.get("variant_ids", []) or []
        if not handle:
            continue
        if vids:
            # already specified
            continue
        product_json = fetch_product_json(handle)
        if product_json:
            variants = extract_variants_from_product_json(product_json)
            ids = [v.get("id") for v in variants if v.get("id")]
            p["variant_ids"] = ids
            print(f"[{handle}] Auto-filled {len(ids)} variant_ids.")
        else:
            print(f"[{handle}] Could not auto-fill variant IDs (blocked or failed).")
            print("If blocked, open the product .js in your browser and paste the JSON into a file,")
            print("or manually add variant IDs to the PRODUCTS list.")
    return products


def is_variant_available_in_product_json(product_json: dict, variant_id: int) -> bool:
    for v in product_json.get("variants", []):
        if int(v.get("id")) == int(variant_id):
            return bool(v.get("available"))
    return False


def get_variant_info_from_product_json(product_json: dict, variant_id: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return (product_title, variant_title/size, image_url) from product JSON.
    """
    if not product_json:
        return None, None, None
    product_title = product_json.get("title", None)
    variant_title = None
    for v in product_json.get("variants", []):
        if int(v.get("id")) == int(variant_id):
            variant_title = v.get("title")
            break
    image_url = None
    images = product_json.get("images", []) or []
    if images:
        src = images[0]
        if src:
            image_url = "https:" + src if isinstance(src, str) and src.startswith("//") else src
    return product_title, variant_title, image_url


def build_embed(product_title: str, variant_id: int, size_text: Optional[str], image_url: Optional[str]):
    url = atc_url(variant_id)
    embed = {"title": product_title or "Product", "url": url}
    if size_text:
        embed["description"] = f"Size: {size_text}"
    if image_url:
        embed["thumbnail"] = {"url": image_url}
    return embed


def send_embeds(embeds: List[dict]):
    if not WEBHOOK_URL:
        print("WEBHOOK_URL not set — not sending Discord messages. Debug print only:")
        for e in embeds:
            print("EMBED:", e)
        return
    for i in range(0, len(embeds), 10):
        batch = embeds[i:i + 10]
        payload = {"embeds": batch}
        try:
            resp = session.post(WEBHOOK_URL, json=payload, timeout=REQUEST_TIMEOUT)
            if resp.status_code >= 400:
                print(f"Failed to send webhook (status {resp.status_code}): {resp.text}")
        except requests.RequestException as e:
            print("Webhook POST failed:", e)


def main_once():
    """
    One pass: ensure variant IDs, fetch product JSONs, collect in-stock embeds, send.
    """
    filled_products = ensure_product_variants_autofilled(PRODUCTS)
    embeds = []

    for p in filled_products:
        handle = p.get("handle")
        vids = p.get("variant_ids", []) or []
        # Try fetching product JSON once per product to reuse
        product_json = fetch_product_json(handle) if handle else None
        if product_json is None:
            print(f"[{handle}] Skipping checks for this product (couldn't fetch product JSON).")
            continue

        for vid in vids:
            available = is_variant_available_in_product_json(product_json, vid)
            if available:
                product_title, size_text, image_url = get_variant_info_from_product_json(product_json, vid)
                embed = build_embed(product_title, vid, size_text, image_url)
                embeds.append(embed)
                print(f"[{handle}] Variant {vid} -> AVAILABLE ({size_text})")
            else:
                print(f"[{handle}] Variant {vid} -> sold out / unavailable")

    if embeds:
        send_embeds(embeds)
        print(f"✅ Sent {len(embeds)} embed(s).")
    else:
        print("❌ No in-stock variants found.")


if __name__ == "__main__":
    # Run a single pass. If you want continuous monitoring, wrap main_once() in a loop with sleep.
    main_once()
