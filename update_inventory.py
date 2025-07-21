import os
import requests
import csv
import io

SHOP_URL = os.environ["SHOPIFY_STORE_URL"]
API_VERSION = os.environ["SHOPIFY_API_VERSION"]
ACCESS_TOKEN = os.environ["SHOPIFY_ACCESS_TOKEN"]
LOCATION_ID = os.environ["SHOPIFY_LOCATION_ID"]
CSV_URL = os.environ["CSV_FILE_URL"]

def download_csv():
    r = requests.get(CSV_URL)
    r.raise_for_status()
    return io.StringIO(r.text)

def get_inventory_item_id(sku):
    query = {
        "query": f"""
        {{
          productVariants(first: 1, query: "sku:{sku}") {{
            edges {{
              node {{
                inventoryItem {{
                  id
                }}
              }}
            }}
          }}
        }}
        """
    }
    headers = {
        "X-Shopify-Access-Token": ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    url = f"https://{SHOP_URL}/admin/api/{API_VERSION}/graphql.json"
    r = requests.post(url, json=query, headers=headers)
    r.raise_for_status()
    data = r.json()
    try:
        return data['data']['productVariants']['edges'][0]['node']['inventoryItem']['id']
    except (IndexError, KeyError):
        return None

def set_inventory_quantity(inventory_item_id, quantity):
    mutation = {
        "query": f"""
        mutation {{
          inventorySetOnHandQuantity(input: {{
            inventoryItemId: "{inventory_item_id}",
            locationId: "{LOCATION_ID}",
            onHandQuantity: {quantity}
          }}) {{
            inventoryLevel {{ id available }}
            userErrors {{ field message }}
          }}
        }}
        """
    }
    headers = {
        "X-Shopify-Access-Token": ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    url = f"https://{SHOP_URL}/admin/api/{API_VERSION}/graphql.json"
    r = requests.post(url, json=mutation, headers=headers)
    r.raise_for_status()
    return r.json()

def main():
    csvfile = download_csv()
    reader = csv.DictReader(csvfile, delimiter=';')

    for row in reader:
        sku = row.get("Artikelnummer")
        try:
            quantity = int(row.get("VoorraadAantal", 0))
        except ValueError:
            quantity = 0

        print(f"SKU {sku} → voorraad: {quantity}")
        inventory_item_id = get_inventory_item_id(sku)
        if inventory_item_id:
            result = set_inventory_quantity(inventory_item_id, quantity)
            print(result)
        else:
            print(f"SKU {sku} niet gevonden in Shopify")

if __name__ == "__main__":
    main()
