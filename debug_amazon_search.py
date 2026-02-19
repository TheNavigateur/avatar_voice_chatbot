from tools.market_tools import check_amazon_stock

print("Checking stock for 'NIVEA SUN Protect & Moisture Sun Lotion SPF 50+'...")
res = check_amazon_stock("NIVEA SUN Protect & Moisture Sun Lotion SPF 50+", "", region="UK")
print("-" * 40)
print(res)
print("-" * 40)
