import os
import requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
VARIANT_ID = 51377786945800  # size 28

def is_in_stock():
	url = f"https://derschutze.com/cart/{VARIANT_ID}:1"
	response = requests.get(url)
	if response.status_code == 200:
		text = response.text.lower()
		# Shopify returns "sold out" or redirects if not available
		if "sold out" in text:
			print(f"Variant {VARIANT_ID} is sold out")
			return False
		else:
			print(f"Variant {VARIANT_ID} can be added to cart")
			return True
	else:
		print(f"Failed to check cart endpoint. Status code: {response.status_code}")
		return False

def send_discord_notification():
	requests.post(WEBHOOK_URL, json={
		"content": f"https://derschutze.com/cart/{VARIANT_ID}:1"
	})

if is_in_stock():
	send_discord_notification()
	print("Notification sent!")
else:
	print("Still sold out.")
