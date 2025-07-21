import csv
import os
import requests
import shopify
from io import StringIO

# Ophalen van secrets/omgevingsvariabelen
SHOP_URL = os.getenv("SHOPIFY_STORE_URL")  # bijv. 'd8e0w6-ep.myshopify.com'
API_VERSION = os.getenv("SHOPIFY_API_VERSION")  # bijv. '2025-07'
ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
CSV_FILE_URL = os.getenv("CSV_FILE_URL")
LOCATION_ID = os.getenv("SHOPIFY_LOCATION_ID")

# Shopify sessie starten
shop_url = f"https://{ACCESS_TOKEN}@{SHOP_URL}/admin/api/{API_VERSION}"
shopify.ShopifyResource.set_site(shop_url)

# CSV ophalen
response = requests.get(CSV_FILE_URL)
response.raise_for_status()
csv_content = response.content.decode("utf-8")
reader = csv.DictReader(StringIO(csv_content), delimiter="\t")

# Mapping op SKU
for row in reader:
    sku = row["product_sku"]
    new_stock = int(float(row["actual_stock_level"]))

    # Zoek variant via SKU
    variants = shopify.Variant.find(query=f"sku:{sku}")
    if not variants:
        print(f"SKU {sku} niet gevonden in Shopify.")
        continue

    for variant in variants:
        inventory_item_id = variant.inventory_item_id

        # Update voorraad via InventoryLevel
        payload = {
            "location_id": LOCATION_ID,
            "inventory_item_id": inventory_item_id,
            "available": new_stock
        }

        update_url = f"https://{SHOP_URL}/admin/api/{API_VERSION}/inventory_levels/set.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": ACCESS_TOKEN
        }

        res = requests.post(update_url, headers=headers, json=payload)

        if res.status_code == 200:
            print(f"Voorraad voor SKU {sku} succesvol bijgewerkt naar {new_stock}.")
        else:
            print(f"Fout bij bijwerken SKU {sku}: {res.status_code} - {res.text}")
