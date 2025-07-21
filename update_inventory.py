import os
import requests
import pandas as pd

# ====== ENVIRONMENT VARIABLES ======
CSV_FILE_URL = os.getenv("CSV_FILE_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")
SHOPIFY_LOCATION_ID = os.getenv("SHOPIFY_LOCATION_ID")

# ====== HEADERS ======
GRAPHQL_URL = f"https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
}

# ====== STEP 1: READ SUPPLIER CSV ======
print("🔹 Leveranciersvoorraad wordt ingelezen...")
supplier_df = pd.read_csv(CSV_FILE_URL)
supplier_df['product_sku'] = supplier_df['product_sku'].astype(str).str.upper()
print("Voorbeeld leveranciers-SKU's:", supplier_df['product_sku'].head())

# ====== STEP 2: FETCH SHOPIFY PRODUCT VARIANTS ======
def fetch_shopify_variants():
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
    response = requests.post(GRAPHQL_URL, headers=HEADERS, json={"query": query})
    response.raise_for_status()
    return response.json()

print("🔹 Shopify-productvarianten worden opgehaald...")
shopify_data = fetch_shopify_variants()
variant_list = []

for product in shopify_data["data"]["products"]["edges"]:
    for variant_edge in product["node"]["variants"]["edges"]:
        variant = variant_edge["node"]
        sku = variant["sku"]
        inventory_item_id = variant["inventoryItem"]["id"] if variant["inventoryItem"] else None
        if sku and inventory_item_id:
            variant_list.append({
                "sku": sku.upper(),
                "inventory_item_id": inventory_item_id
            })

shopify_df = pd.DataFrame(variant_list)
print("🔹 Voorbeeld Shopify-varianten:\n", shopify_df.head())

# ====== STEP 3: MERGE OP SKU ======
merged = pd.merge(supplier_df, shopify_df, how="inner", left_on="product_sku", right_on="sku")

# ====== STEP 4: UPDATE INVENTORY ======
def update_inventory(inventory_item_id, quantity):
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
            "available": int(quantity)
        }
    }
    response = requests.post(GRAPHQL_URL, headers=HEADERS, json={"query": mutation, "variables": variables})
    response.raise_for_status()
    return response.json()

print("🔹 Voorraad wordt bijgewerkt...")
for _, row in merged.iterrows():
    sku = row["sku"]
    inventory_item_id = row["inventory_item_id"]
    try:
        quantity = int(float(row["actual_stock_level"]))
    except ValueError:
        quantity = 0

    print(f"→ SKU: {sku}, nieuwe voorraad: {quantity}")
    result = update_inventory(inventory_item_id, quantity)

    if result["data"]["inventorySet"]["userErrors"]:
        print("⚠️  Fout:", result["data"]["inventorySet"]["userErrors"])
    else:
        print("✅ Succes:", result["data"]["inventorySet"]["inventoryLevel"])
