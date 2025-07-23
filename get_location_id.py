import os
import requests

SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")  # voorbeeld: 'd8e0w6-ep.myshopify.com'
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-07")

def get_locations():
    url = f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    query = {
        "query": """
        {
          locations(first: 10) {
            edges {
              node {
                id
                name
                legacyResourceId
              }
            }
          }
        }
        """
    }

    response = requests.post(url, json=query, headers=headers)
    
    if response.status_code != 200:
        print("❌ Fout bij API-aanroep:", response.status_code, response.text)
        return

    data = response.json()

    if "errors" in data:
        print("❌ GraphQL fout:", data["errors"])
        return

    edges = data["data"]["locations"]["edges"]
    print(f"📍 Gevonden locaties: {len(edges)}\n")
    for edge in edges:
        loc = edge["node"]
        print(f"- Naam: {loc['name']}")
        print(f"  GID:  {loc['id']}")
        print(f"  Legacy ID: {loc['legacyResourceId']}")
        print()

if __name__ == "__main__":
    print("🔍 Ophalen van Shopify locaties...")
    get_locations()
