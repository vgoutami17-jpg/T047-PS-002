
import sqlite3
from database.db import DB_PATH

def create_order(order_id, customer_id, total_amount):

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    # Check customer
    cursor.execute(
        "SELECT customer_id FROM customers WHERE customer_id = ?",
        (customer_id,)
    )

    customer = cursor.fetchone()

    if customer is None:
        print("Customer not found!")
        connection.close()
        return

    # Create order
    try:
        cursor.execute("""
            INSERT INTO orders
            (order_id, customer_id, total_amount)
            VALUES (?, ?, ?)
        """, (order_id, customer_id, total_amount))

        connection.commit()
        print("Order created successfully!")
        print("Order ID:", order_id)
        print("Customer ID:", customer_id)
        print("Total Amount: Rs.", total_amount)
        print("Status: CREATED")

    except sqlite3.IntegrityError:
        print("Order ID already exists!")

    connection.close()


if __name__ == "__main__":
    order_id = input("Enter order ID: ")
    customer_id = input("Enter customer ID: ")
    amount = float(input("Enter total amount: "))

    create_order(order_id, customer_id, amount)
