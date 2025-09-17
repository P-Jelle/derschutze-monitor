import os
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
PRODUCT_URL = "https://derschutze.com/collections/pants/products/blossom-v2-selvedge-denim?variant=51377786945800"

def is_in_stock():
	r = requests.get(PRODUCT_URL)
	return "Sold Out" not in r.text

def send_discord_notification():
	requests.post(WEBHOOK_URL, json={"content": f"🔥 Blossom V2 Selvedge Denim might be in stock! Check here: {PRODUCT_URL}"})

if is_in_stock():
	send_discord_notification()
	print("Product is in stock! Notification sent.")
else:
	print("Still sold out.")
