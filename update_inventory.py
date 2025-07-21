import os
import csv
import requests
from io import StringIO

# Secrets uit GitHub Actions
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")
SHOPIFY_LOCATION_ID = os.getenv("SHOPIFY_LOCATION_ID")
CSV_FILE_URL = os.getenv("CSV_FILE_URL")

def fetch_csv(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def read_csv_data(csv_text, key_column):
    reader = csv.DictReader(StringIO(csv_text), delimiter=",")
    data = {}
    for row in reader:
        key = row.get(key_column)
        if key:
            data[key.strip()] = row
    return data

def build_sku_inventory_map(supplier_data):
    sku_inventory = {}
    for sku, row in supplier_data.items():
        voorraad_str = row.get("Voorraad", "").strip()
        try:
            voorraad = int(float(voorraad_str))
        except ValueError:
            voorraad = 0
        sku_inventory[sku.strip()] = voorraad
    return sku_inventory

def update_inventory_level(inventory_item_id, available):
    url = f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/inventory_levels/set.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "location_id": SHOPIFY_LOCATION_ID,
        "inventory_item_id": inventory_item_id,
        "available": available
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 200:
        print(f"⚠️ Fout bij bijwerken voorraad voor inventory_item_id {inventory_item_id}: {response.text}")
    return response.status_code == 200

def main():
    print("🔄 Start voorraad-synchronisatie...")

    # Haal CSV-bestanden op
    supplier_csv = fetch_csv(CSV_FILE_URL)
    shopify_csv = open("products_export_1.csv", "r", encoding="utf-8").read()

    # Lees data
    supplier_data = read_csv_data(supplier_csv, key_column="Product SKU")
    shopify_data = read_csv_data(shopify_csv, key_column="Variant SKU")

    # Bouw mapping van Variant SKU → inventory_item_id
    variant_inventory_map = {
        sku.strip(): row["Variant Inventory Item ID"].strip()
        for sku, row in shopify_data.items()
        if sku and row.get("Variant Inventory Item ID")
    }

    # Verwerk voorraadupdates
    sku_inventory_map = build_sku_inventory_map(supplier_data)
    for variant_sku, inventory_item_id in variant_inventory_map.items():
        voorraad = sku_inventory_map.get(variant_sku, 0)
        print(f"SKU {variant_sku} → voorraad: {voorraad}")
        success = update_inventory_level(inventory_item_id, voorraad)
        if not success:
            print(f"❌ Mislukt voor SKU {variant_sku}")

    print("✅ Synchronisatie voltooid.")

if __name__ == "__main__":
    main()
