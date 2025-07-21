import os
import pandas as pd
import requests

# Laad omgevingsvariabelen
SHOPIFY_ACCESS_TOKEN = os.environ["SHOPIFY_ACCESS_TOKEN"]
SHOPIFY_STORE_URL = os.environ["SHOPIFY_STORE_URL"]
SHOPIFY_API_VERSION = os.environ["SHOPIFY_API_VERSION"]
SHOPIFY_LOCATION_ID = os.environ["SHOPIFY_LOCATION_ID"]
CSV_FILE_URL = os.environ["CSV_FILE_URL"]

# 1. Laad leverancier CSV
supplier_df = pd.read_csv(CSV_FILE_URL)
supplier_df['product_sku'] = supplier_df['product_sku'].astype(str).str.upper()

# 2. Haal Shopify-productvarianten op
def fetch_shopify_inventory_items():
    query = """
    {
      products(first: 250) {
        edges {
          node {
            variants(first: 100) {
              edges {
                node {
                  id
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
    url = f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }

    response = requests.post(url, json={"query": query}, headers=headers)
    data = response.json()

    variants = []
    for product in data["data"]["products"]["edges"]:
        for variant in product["node"]["variants"]["edges"]:
            sku = variant["node"]["sku"]
            inv_id = variant["node"]["inventoryItem"]["id"]
            if sku:
                variants.append({"sku": sku.upper(), "inventory_item_id": inv_id})
    return pd.DataFrame(variants)

shopify_df = fetch_shopify_inventory_items()

# 3. Merge op SKU
merged_df = pd.merge(supplier_df, shopify_df, how="inner", left_on="product_sku", right_on="sku")

# 4. Update voorraadniveaus
def update_inventory_level(inventory_item_id, available):
    mutation = """
    mutation inventorySet($input: InventorySetInput!) {
      inventorySet(input: $input) {
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
            "locationId": f"gid://shopify/Location/{SHOPIFY_LOCATION_ID}",
            "available": int(available)
        }
    }

    url = f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
    }

    response = requests.post(url, json={"query": mutation, "variables": variables}, headers=headers)
    result = response.json()

    if "errors" in result:
        print("Fout:", result["errors"])
    elif result["data"]["inventorySet"]["userErrors"]:
        print("UserErrors:", result["data"]["inventorySet"]["userErrors"])
    else:
        print(f"Voorraad aangepast: {inventory_item_id} => {available}")

# 5. Loop over gematchte producten
for _, row in merged_df.iterrows():
    stock = int(row["actual_stock_level"])
    inv_id = row["inventory_item_id"]
    update_inventory_level(inv_id, stock)
