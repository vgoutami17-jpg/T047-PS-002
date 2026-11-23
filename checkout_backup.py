
from pathlib import Path
import math


# GST Calculation
def calculate_gst(amount, gst_rate):

    gst_amount = amount * gst_rate / 100

    return round(gst_amount, 2)


# Shipping Calculation
def calculate_shipping(
    order_amount,
    weight_grams,
    customer_tier,
    state,
    free_shipping=False
):

    # PRIME customers always get free shipping
    if customer_tier.upper().strip() == "PRIME":
        return 0

    # Free shipping for qualifying orders or coupon
    if order_amount >= 499 or free_shipping:
        return 0

    # Regular customer shipping
    shipping = 49

    # Extra weight charge above 2 kg
    if weight_grams > 2000:

        extra_weight = weight_grams - 2000
        extra_blocks = math.ceil(extra_weight / 500)

        shipping += extra_blocks * 30

    # North-East states
    north_east_states = [
        "ASSAM",
        "ARUNACHAL PRADESH",
        "MANIPUR",
        "MEGHALAYA",
        "MIZORAM",
        "NAGALAND",
        "SIKKIM",
        "TRIPURA"
    ]

    if state.upper().strip() in north_east_states:
        shipping += 100

    return shipping


# Main Program
if __name__ == "__main__":

    # GST Input
    amount = float(input("Enter product amount: "))
    gst_rate = float(input("Enter GST rate: "))

    gst = calculate_gst(amount, gst_rate)

    print("\n----- GST DETAILS -----")
    print("GST Amount: Rs.", gst)
    print("Total Amount: Rs.", amount + gst)

    # Shipping Input
    order_amount = float(
        input("\nEnter order amount after discount: ")
    )

    weight = int(input("Enter total weight in grams: "))
    tier = input("Enter customer tier: ")
    state = input("Enter delivery state: ")

    free_coupon = input(
        "Is FREESHIP coupon applied? (yes/no): "
    )

    shipping = calculate_shipping(
        order_amount,
        weight,
        tier,
        state,
        free_coupon.lower() == "yes"
    )

    print("\n----- SHIPPING DETAILS -----")
    print("Shipping Charge: Rs.", shipping)

    # Final Bill
    final_amount = order_amount + gst + shipping

    print("\n----- FINAL BILL -----")
    print("Order Amount: Rs.", order_amount)
    print("GST Amount: Rs.", gst)
    print("Shipping Charge: Rs.", shipping)
    print("----------------------")
    print("Final Payable Amount: Rs.", final_amount)

    # Invoice Generation
    invoice = f"""
================================
          PS-002 INVOICE
================================

Product Amount : Rs. {order_amount}
GST Amount     : Rs. {gst}
Shipping       : Rs. {shipping}

--------------------------------
Final Amount   : Rs. {final_amount}
================================
       Thank You For Shopping!
================================
"""

    print(invoice)

    # Save invoice
    output_folder = Path("output")
    output_folder.mkdir(exist_ok=True)

    with open(output_folder / "invoice.txt", "w") as file:
        file.write(invoice)

    print("Invoice saved successfully!")
