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
    """
    Haal alle producten op uit Shopify met bijbehorende inventory item ID's en SKU's.
    """
    url = f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }

    inventory_map = {}
    has_next_page = True
    cursor = None

    while has_next_page:
        query = """
        query ($cursor: String) {
          products(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
            }
            edges {
              cursor
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

        variables = {"cursor": cursor}
        response = requests.post(url, headers=headers, json={"query": query, "variables": variables})
        data = response.json()

        try:
            for product_edge in data["data"]["products"]["edges"]:
                cursor = product_edge["cursor"]
                for variant_edge in product_edge["node"]["variants"]["edges"]:
                    variant = variant_edge["node"]
                    sku = (variant["sku"] or "").strip().upper()
                    inventory_item_id = variant["inventoryItem"]["id"]
                    if sku:
                        inventory_map[sku] = inventory_item_id
        except Exception as e:
            print("Fout bij het uitlezen van de producten:", e)
            break

        has_next_page = data["data"]["products"]["pageInfo"]["hasNextPage"]

    return inventory_map

def update_inventory():
    inventory_map = get_inventory_items()

    print("→ Aantal producten opgehaald uit Shopify:", len(inventory_map))

    response = requests.get(CSV_FILE_URL)
    response.encoding = "utf-8"
    csv_content = response.text.splitlines()
    reader = csv.DictReader(csv_content)

    updates = 0

    for row in reader:
        supplier_sku = str(row.get("product_sku", "")).strip().upper()
        stock_level = int(float(row.get("actual_stock_level", "0")))

        print(f"CSV uitlezing → SKU: {supplier_sku}, voorraad: {stock_level}")

        inventory_item_id = inventory_map.get(supplier_sku)

        if inventory_item_id:
            mutation_url = f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
            mutation = """
            mutation inventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
              inventoryAdjustQuantities(input: $input) {
                inventoryAdjustmentGroup {
                  createdAt
                  reason
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
                    "reason": "correction",
                    "name": "Voorraadsynchronisatie",
                    "changes": [
                        {
                            "inventoryItemId": inventory_item_id,
                            "locationId": f"gid://shopify/Location/{SHOPIFY_LOCATION_ID}",
                            "availableDelta": stock_level  # LET OP: dit corrigeert relatief!
                        }
                    ]
                }
            }

            mutation_response = requests.post(
                mutation_url,
                headers={
                    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
                    "Content-Type": "application/json"
                },
                json={"query": mutation, "variables": variables}
            )

            json_response = mutation_response.json()

            if json_response.get("errors") or json_response.get("data", {}).get("inventoryAdjustQuantities", {}).get("userErrors"):
                print(f"⚠️ Fout bij updaten van voorraad voor {supplier_sku}: {json_response}")
            else:
                print(f"✅ Voorraad aangepast voor {supplier_sku}: {stock_level}")
                updates += 1
        else:
            print(f"SKU {supplier_sku} niet gevonden in Shopify")

    print(f"🔄 Sync compleet. Totaal aantal geüpdatete producten: {updates}")

if __name__ == "__main__":
    update_inventory()
