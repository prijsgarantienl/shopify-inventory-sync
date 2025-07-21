import os
import csv
import requests

# Haal secrets op uit environment
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")
SHOPIFY_LOCATION_ID = os.getenv("SHOPIFY_LOCATION_ID")
CSV_FILE_URL = os.getenv("CSV_FILE_URL")

def get_inventory_items():
    query = """
    {
      products(first: 250) {
        edges {
          node {
            variants(first: 100) {
              edges {
                node {
                  sku
                  id
                  inventoryItem {
                    id
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    response = requests.post(
        f"{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
        },
        json={"query": query}
    )

    data = response.json()
    inventory_items = {}
    try:
        for product in data["data"]["products"]["edges"]:
            for variant in product["node"]["variants"]["edges"]:
                sku = variant["node"]["sku"]
                inventory_item_id = variant["node"]["inventoryItem"]["id"]
                if sku:
                    inventory_items[sku.strip().upper()] = inventory_item_id
    except Exception as e:
        print("Fout bij ophalen van Shopify-inventaris:", e)
    
    return inventory_items

def update_inventory_level(inventory_item_id, available):
    mutation = """
    mutation inventoryAdjustQuantity($input: InventoryAdjustQuantityInput!) {
      inventoryAdjustQuantity(input: $input) {
        inventoryLevel {
          available
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        "input": {
            "inventoryItemId": inventory_item_id,
            "availableDelta": available  # Volledige vervanging werkt niet zonder InventoryLevel ID
        }
    }

    response = requests.post(
        f"{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
        },
        json={"query": mutation, "variables": variables}
    )

    return response.json()

def main():
    print("Start voorraad synchronisatie...")

    # Haal inventory items op uit Shopify
    inventory_items = get_inventory_items()
    print(f"📦 Aantal varianten in Shopify: {len(inventory_items)}")

    # Haal de CSV van de leverancier op
    response = requests.get(CSV_FILE_URL)
    response.encoding = 'utf-8'
    decoded_content = response.text.splitlines()
    reader = csv.DictReader(decoded_content)

    for row in reader:
        leverancier_sku = row.get("product_sku", "").strip().upper()
        try:
            voorraad = int(float(row.get("actual_stock_level", 0)))
        except:
            voorraad = 0

        if not leverancier_sku:
            print(f"⚠️ SKU ontbreekt in rij: {row}")
            continue

        inventory_item_id = inventory_items.get(leverancier_sku)

        print(f"SKU {leverancier_sku} → voorraad: {voorraad}")

        if inventory_item_id:
            result = update_inventory_level(inventory_item_id, voorraad)
            print(f"✅ Bijgewerkt: {leverancier_sku} → voorraad {voorraad}")
        else:
            print(f"❌ SKU {leverancier_sku} niet gevonden in Shopify")

if __name__ == "__main__":
    main()
