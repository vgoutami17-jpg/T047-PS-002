
import sqlite3
from database.db import DB_PATH

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("""
    SELECT promotion_name, category,
           buy_quantity, get_quantity, is_active
    FROM promotions
    WHERE coupon_code = 'BOGO1'
""")

result = cursor.fetchall()

print("BOGO OFFER DETAILS:")
print(result)

connection.close()
