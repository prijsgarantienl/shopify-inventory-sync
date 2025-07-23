import os
import csv
import time
import requests
from io import StringIO

# Omgevingsvariabelen vanuit GitHub Actions
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")
SHOPIFY_LOCATION_ID = os.getenv("SHOPIFY_LOCATION_ID")
CSV_FILE_URL = os.getenv("CSV_FILE_URL")

print("🚀 RUNNING update_inventory.py with inventorySetQuantities mutation")
print("✅ Script gestart")
print("SHOPIFY_STORE_URL:", SHOPIFY_STORE_URL or "❌ NIET GEZET")
print("CSV_FILE_URL:", CSV_FILE_URL or "❌ NIET GEZET")
print("🔄 Start voorraad-synchronisatie...")

# Configuratie
BATCH_SIZE = 75

# --- Functies ---
def fetch_csv(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def read_csv_data(text, key_column):
    reader = csv.DictReader(StringIO(text))
    data = {}
    for row in reader:
        key = row.get(key_column)
        if key:
            data[key.strip()] = row
        else:
            print(f"⚠️ Lege of ongeldige key in rij: {row}")
    return data

def read_inventory_mapping(path="inventory_mapping.csv"):
    mapping = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row.get("Variant SKU")
            item_id = row.get("Inventory Item ID")
            if sku and item_id:
                mapping[sku.strip()] = item_id.strip()
    return mapping

def update_inventory(inventory_item_id, new_qty):
    mutation = {
        "query": '''
        mutation InventorySetQuantities($input: InventorySetQuantitiesInput!) {
          inventorySetQuantities(input: $input) {
            inventoryAdjustmentGroup {
              createdAt
              reason
              changes {
                name
                delta
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        ''',
        "variables": {
            "input": {
                "name": "available",
                "reason": "GitHub sync",
                "ignoreCompareQuantity": True,
                "quantities": [
                    {
                        "inventoryItemId": inventory_item_id,
                        "locationId": SHOPIFY_LOCATION_ID,
                        "quantity": new_qty
                    }
                ]
            }
        }
    }

    response = requests.post(
        f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
        json=mutation,
        headers={
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json"
        }
    )
    return response.json()

# --- Uitvoeren ---
supplier_csv = fetch_csv(CSV_FILE_URL)
supplier_data = read_csv_data(supplier_csv, key_column="product_sku")

with open("products_export_1.csv", encoding="utf-8") as f:
    shopify_data = read_csv_data(f.read(), key_column="Variant SKU")

inventory_mapping = read_inventory_mapping()

if not supplier_data or not shopify_data or not inventory_mapping:
    print("❌ Geen geldige data ingelezen. Stoppen.")
    exit(1)

# Filter de SKU’s die in beide bestanden voorkomen
skus_to_update = []
for sku, row in shopify_data.items():
    if sku in supplier_data and sku in inventory_mapping:
        try:
            voorraad = int(supplier_data[sku]["actual_stock_level"])
            inventory_item_id = inventory_mapping[sku]
            skus_to_update.append((sku, voorraad, inventory_item_id))
        except ValueError:
            print(f"⚠️ Ongeldige voorraadwaarde voor SKU {sku}")

print(f"📦 Aantal SKU's voor update: {len(skus_to_update)}")

# In batches doorvoeren
for i in range(0, len(skus_to_update), BATCH_SIZE):
    batch = skus_to_update[i:i + BATCH_SIZE]
    print(f"➡️ Batch {i // BATCH_SIZE + 1} van {(len(skus_to_update) - 1) // BATCH_SIZE + 1}")

    for sku, voorraad, inventory_item_id in batch:
        result = update_inventory(inventory_item_id, voorraad)
        if "errors" in result:
            print(f"❌ API fout bij {sku}: {result['errors']}")
        elif result.get("data", {}).get("inventorySetQuantities", {}).get("userErrors"):
            user_errors = result["data"]["inventorySetQuantities"]["userErrors"]
            print(f"⚠️ Fout bij {sku}: {user_errors}")
        else:
            print(f"✅ {sku}: voorraad ingesteld op {voorraad}")

print("🎉 Synchronisatie voltooid.")
