import os
import csv
import requests

# Haal secrets op uit environment
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")
SHOPIFY_LOCATION_ID = os.getenv("SHOPIFY_LOCATION_ID")
CSV_FILE_URL = os.getenv("CSV_FILE_URL")

HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    "Content-Type": "application/json"
}


def fetch_supplier_data():
    response = requests.get(CSV_FILE_URL)
    response.raise_for_status()
    content = response.content.decode("utf-8").splitlines()
    # Kies delimiter afhankelijk van bestand: ',' of ';'
    reader = csv.DictReader(content, delimiter=',')
    supplier_data = []

    for row in reader:
        print(f"🔍 Kolommen in CSV: {row.keys()}")  # DEBUG

        sku = row.get("product_sku", "").strip().upper()
        try:
            stock = int(float(row.get("actual_stock_level", 0)))
        except ValueError:
            stock = 0

        if sku:
            print(f"📦 CSV SKU: {sku} → voorraad: {stock}")
            supplier_data.append((sku, stock))
        else:
            print("⚠️ Geen geldige SKU gevonden in deze rij:", row)

    return supplier_data


def get_inventory_items():
    print("🛒 Ophalen Shopify SKUs...")

    inventory_map = {}

    query = """
    {
      products(first: 100) {
        edges {
          node {
            variants(first: 100) {
              edges {
                node {
                  sku
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

    url = f"{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    response = requests.post(url, headers=HEADERS, json={"query": query})
    response.raise_for_status()

    data = response.json()

    for product_edge in data["data"]["products"]["edges"]:
        for variant_edge in product_edge["node"]["variants"]["edges"]:
            variant = variant_edge["node"]
            sku = variant["sku"].strip().upper()
            inventory_item_id = variant["inventoryItem"]["id"]
            if sku:
                inventory_map[sku] = inventory_item_id
                print(f"✅ Shopify SKU gevonden: {sku} → {inventory_item_id}")

    return inventory_map


def update_inventory(inventory_item_id, quantity):
    mutation = """
    mutation inventoryAdjustQuantity($input: InventoryAdjustQuantityInput!) {
      inventoryAdjustQuantity(input: $input) {
        inventoryLevel {
          id
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
            "availableDelta": quantity,  # Wordt vervangen hieronder
            "locationId": SHOPIFY_LOCATION_ID
        }
    }

    # Voor deze methode moeten we delta berekenen i.p.v. absolute waarde.
    # Daarom eerst huidige voorraad ophalen.
    # Maar we gebruiken hier de absolute set via andere mutatie:

    mutation_set = """
    mutation inventorySet($input: InventorySetOnHandQuantitiesInput!) {
      inventorySetOnHandQuantities(input: $input) {
        inventoryLevels {
          available
          location {
            id
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables_set = {
        "input": {
            "onHandQuantities": [
                {
                    "inventoryItemId": inventory_item_id,
                    "locationId": SHOPIFY_LOCATION_ID,
                    "availableQuantity": quantity
                }
            ]
        }
    }

    url = f"{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    response = requests.post(url, headers=HEADERS, json={
        "query": mutation_set,
        "variables": variables_set
    })

    result = response.json()
    if "errors" in result:
        print("❌ Shopify GraphQL fout:", result["errors"])
    elif result.get("data", {}).get("inventorySetOnHandQuantities", {}).get("userErrors"):
        print("⚠️ Shopify userErrors:", result["data"]["inventorySetOnHandQuantities"]["userErrors"])
    else:
        print("✅ Voorraad bijgewerkt:", quantity)


def main():
    supplier_data = fetch_supplier_data()
    shopify_inventory = get_inventory_items()

    for sku, stock in supplier_data:
        inventory_item_id = shopify_inventory.get(sku)
        if inventory_item_id:
            print(f"🔄 SKU {sku} → update voorraad naar {stock}")
            update_inventory(inventory_item_id, stock)
        else:
            print(f"❌ SKU {sku} niet gevonden in Shopify")


if __name__ == "__main__":
    main()
