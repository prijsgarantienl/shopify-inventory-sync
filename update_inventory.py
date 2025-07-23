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

print("✅ Script gestart")
print("SHOPIFY_STORE_URL:", SHOPIFY_STORE_URL or "❌ NIET GEZET")
print("CSV_FILE_URL:", CSV_FILE_URL or "❌ NIET GEZET")
print("🔄 Start voorraad-synchronisatie...")

# Configuratie
BATCH_SIZE = 75
SLEEP_TIME = 20  # om rate limiting te voorkomen

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

def get_inventory_item_id(sku):
    query = {
        "query": f"""
        {{
          productVariants(first: 1, query: "sku:{sku}") {{
            edges {{
              node {{
                sku
                inventoryItem {{
                  id
                }}
              }}
            }}
          }}
        }}
        """
    }
    response = requests.post(
        f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
        json=query,
        headers={
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json"
        }
    )
    try:
        return response.json()["data"]["productVariants"]["edges"][0]["node"]["inventoryItem"]["id"]
    except (KeyError, IndexError):
        return None

def update_inventory(inventory_item_id, new_qty):
    mutation = {
        "query": f"""
        mutation {{
          inventorySetQuantity(input: {{
            inventoryItemId: "{inventory_item_id}",
            availableQuantity: {new_qty},
            locationId: "{SHOPIFY_LOCATION_ID}"
          }}) {{
            inventoryLevel {{
              available
            }}
            userErrors {{
              field
              message
            }}
          }}
        }}
        """
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

if not supplier_data or not shopify_data:
    print("❌ Geen geldige data ingelezen. Stoppen.")
    exit(1)

# Filter de SKU’s die in beide bestanden voorkomen
skus_to_update = []
for sku, row in shopify_data.items():
    if sku in supplier_data:
        try:
            voorraad = int(supplier_data[sku]["actual_stock_level"])
            skus_to_update.append((sku, voorraad))
        except ValueError:
            print(f"⚠️ Ongeldige voorraadwaarde voor SKU {sku}")

print(f"📦 Aantal SKU's voor update: {len(skus_to_update)}")

# In batches doorvoeren
for i in range(0, len(skus_to_update), BATCH_SIZE):
    batch = skus_to_update[i:i + BATCH_SIZE]
    print(f"➡️ Batch {i // BATCH_SIZE + 1} van {(len(skus_to_update) - 1) // BATCH_SIZE + 1}")

    for sku, voorraad in batch:
        inventory_item_id = get_inventory_item_id(sku)
        if not inventory_item_id:
            print(f"⚠️ Geen inventory_item_id voor {sku}")
            continue

        result = update_inventory(inventory_item_id, voorraad)
        if "errors" in result:
            print(f"❌ API fout bij {sku}: {result['errors']}")
        else:
            print(f"✅ {sku}: voorraad ingesteld op {voorraad}")

    print(f"⏳ {SLEEP_TIME} seconden pauze om limieten te respecteren...")
    time.sleep(SLEEP_TIME)

print("🎉 Synchronisatie voltooid.")
