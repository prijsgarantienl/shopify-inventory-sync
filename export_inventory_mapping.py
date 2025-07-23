import os
import csv
import requests

SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")

def query_shopify(cursor=None):
    after = f', after: "{cursor}"' if cursor else ''
    return {
        "query": f"""
        {{
          productVariants(first: 100{after}) {{
            pageInfo {{
              hasNextPage
              endCursor
            }}
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

def fetch_all_variants():
    all_items = []
    cursor = None
    while True:
        query = query_shopify(cursor)
        response = requests.post(
            f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
            json=query,
            headers={
                "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
                "Content-Type": "application/json"
            }
        )
        data = response.json()["data"]["productVariants"]
        for edge in data["edges"]:
            node = edge["node"]
            if node["sku"] and node["inventoryItem"]:
                all_items.append((node["sku"], node["inventoryItem"]["id"]))

        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return all_items

def save_to_csv(data, filename="inventory_mapping.csv"):
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["sku", "inventory_item_id"])
        writer.writerows(data)

if __name__ == "__main__":
    print("📦 Ophalen van alle SKU's en inventory_item_id's...")
    mapping = fetch_all_variants()
    save_to_csv(mapping)
    print(f"✅ Klaar! {len(mapping)} items opgeslagen in inventory_mapping.csv")
