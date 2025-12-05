from ebaysdk.finding import Connection as Finding
from statistics import mean

def get_ebay_average_price(gpu_name, app_id):
    try:
        api = Finding(appid=app_id, config_file=None)
        
        # Search parameters
        response = api.execute('findCompletedItems', {
            'keywords': f"{gpu_name} -box -broken -parts -fan -heatsink",
            'categoryId': '27386',  # 27386 is the category ID for Graphics Cards
            'itemFilter': [
                {'name': 'Condition', 'value': '3000'},       # 3000 = Used
                {'name': 'SoldItemsOnly', 'value': 'true'}    # Only items that actually sold
            ],
            'sortOrder': 'EndTimeSoonest',  # Get the most recent sales
            'paginationInput': {
                'entriesPerPage': '10',
                'pageNumber': '1'
            }
        })

        # Parse results
        if response.reply.searchResult.count == '0':
            return 0.0

        items = response.reply.searchResult.item
        prices = []

        for item in items:
            # item.sellingStatus.currentPrice.value is the sold price
            # item.sellingStatus.currentPrice._currencyId is the currency (usually USD)
            price = float(item.sellingStatus.currentPrice.value)
            prices.append(price)

        if prices:
            avg_price = round(mean(prices), 2)
            print(f"   (API) Found {len(prices)} sold items. Avg: ${avg_price}")
            return avg_price
            
    except Exception as e:
        print(f"   (API) Error: {e}")
        return 0.0

# --- TEST THE FUNCTION ---
# Replace this with your actual App ID from developer.ebay.com
MY_APP_ID = 'YOUR_APP_ID_HERE' 

# Test it
price = get_ebay_average_price("NVIDIA GeForce RTX 3080", MY_APP_ID)
print(f"Final Average: ${price}")