
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ps002.db"


def main():
    connection = sqlite3.connect(DB_PATH)

    try:
        cart_id = int(input("Enter your new Cart ID: "))

        cursor = connection.execute("""
            UPDATE carts
            SET expires_at = '2020-01-01 00:00:00'
            WHERE cart_id = ?
            AND status = 'ACTIVE'
        """, (cart_id,))

        connection.commit()
        print("Rows updated:", cursor.rowcount)

    finally:
        connection.close()


if __name__ == "__main__":
    main()
