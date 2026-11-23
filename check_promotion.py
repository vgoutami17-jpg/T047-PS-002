
import sqlite3
from database.db import DB_PATH

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("""
    SELECT coupon_code, promotion_type
    FROM promotions
    WHERE coupon_code = 'FREESHIP'
""")

print(cursor.fetchall())

connection.close()
