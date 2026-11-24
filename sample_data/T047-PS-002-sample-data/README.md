# PS-002 – Order, Promotion and Returns Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T047.

## Files

| File | What it holds | Row count |
|---|---|---|
| `catalogue.csv` | SKU master (40 SKUs, 6 categories) | 40 |
| `promotions.csv` | Promotion definitions (8, overlapping eligibility) | 8 |
| `customers.csv` | Customers with tier and shipping state | 10 |
| `commands.txt` | Command file processed top to bottom (count excludes `#` comment lines) | 284 |

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with at most 2 places (no commas, no symbol); percentages as plain numbers (12.5 = 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix.

### `catalogue.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `sku_id` | string | SKU-nnn | — | Primary key |
| `name` | string | — | — | — |
| `category` | string | — | ELECTRONICS / FASHION / GROCERY / BOOKS / HOME / BEAUTY | — |
| `mrp` | decimal | Rs | — | Never used as a discount base |
| `selling_price` | decimal | Rs | — | Base for all discounts and the 70% line cap |
| `stock` | integer | units | >= 0 | Opening stock on 2026-10-01 00:00:00; changed only by checkouts, cancellations, returns and STOCK_ADJUST |
| `weight_g` | integer | grams | — | Per unit; shipping surcharge is on total cart weight |
| `on_sale` | boolean | — | true / false | Coupons never apply to sale-flagged lines |
| `gst_slab` | integer | percent | 0 / 5 / 12 / 18 / 28 | — |
| `returnable` | boolean | — | true / false | GROCERY and BEAUTY are non-returnable categories |

### `promotions.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `promo_id` | string | PROMO-nn | — | — |
| `type` | string | — | CATEGORY_OFFER / PERCENT_COUPON / FLAT_COUPON / BUY_X_GET_Y / BANK_OFFER / FREE_SHIP_THRESHOLD | — |
| `code` | string | — | — | Coupon code for coupons; blank otherwise. May be blank (deliberately). |
| `category` | string | — | — | Category the offer / BXGY / free-ship threshold applies to; blank = whole cart. May be blank (deliberately). |
| `bank` | string | — | HDFC / ICICI | Bank offers apply only when CHECKOUT mode is CARD with this bank. May be blank (deliberately). |
| `discount_pct` | decimal | percent | — | 0 when not a percentage promotion |
| `discount_flat` | decimal | Rs | — | 0.00 unless FLAT_COUPON |
| `cap_amount` | decimal | Rs | — | Absolute cap on the discount from this promotion; 0.00 = no cap |
| `min_cart_value` | decimal | Rs | — | Coupons: checked after category offers; bank offers: checked on the running discounted amount before the bank offer; FREE_SHIP_THRESHOLD: category subtotal needed |
| `buy_qty` | integer | — | — | BXGY only. May be blank (deliberately). |
| `get_qty` | integer | — | — | BXGY only. May be blank (deliberately). |
| `valid_from` | date | YYYY-MM-DD | — | Inclusive |
| `valid_to` | date | YYYY-MM-DD | — | Inclusive; validity is checked at CHECKOUT time |
| `tier` | string | — | ALL / PRIME | All promotions here are ALL; PRIME benefits are rules, not promotions |

### `customers.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `customer_id` | string | CUST-nnn | — | — |
| `name` | string | — | — | — |
| `tier` | string | — | REGULAR / PRIME | — |
| `state` | string | — | — | Shipping/place-of-supply state; store is in Karnataka; Assam is a north-east state |
| `city` | string | — | — | — |
| `mobile` | string | 10 digits | — | — |
| `wallet_balance` | decimal | Rs | — | Opening wallet balance (wallet refunds add to it) |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order (the file is the event log). Lines starting with `#` are comments and blank lines are ignored.

Conventions chosen here: reservation inactivity is measured from the cart's last CART_* / APPLY_COUPON command to the CHECKOUT timestamp; CHECKOUT `payment_mode` ∈ UPI / CARD / COD / WALLET and `bank` is blank unless CARD. `ORDER_STATUS` with a 5th argument (sku) ships only that line (partial shipment). Return window days are counted from the DELIVERED timestamp (calendar days, inclusive of the boundary day).

| Command | Arguments (in order) | Notes |
|---|---|---|
| `CART_CREATE` | cart_id, customer_id, timestamp | — |
| `CART_ADD` | cart_id, sku_id, qty, timestamp | Reserves stock; adding an existing sku increases its qty |
| `CART_REMOVE` | cart_id, sku_id, timestamp | Releases reservation |
| `CART_UPDATE` | cart_id, sku_id, qty, timestamp | Sets qty; reservation adjusted |
| `APPLY_COUPON` | cart_id, code, timestamp | Max one coupon per order; eligibility is finally judged at CHECKOUT |
| `STOCK_ADJUST` | sku_id, delta, timestamp, reason | Warehouse stock change outside orders (negative = write-off) |
| `CHECKOUT` | cart_id, payment_mode, bank, timestamp | Creates ORD-nnnn (same number as cart) in CREATED, prints invoice; fails whole cart if any reservation lapsed or stock short |
| `ORDER_STATUS` | order_id, new_state, timestamp[, sku_id] | CONFIRMED / PACKED / SHIPPED / DELIVERED; illegal transitions rejected with a named error |
| `CANCEL` | order_id, timestamp | Free before PACKED, 2% after PACKED, not allowed after SHIPPED |
| `RETURN_REQUEST` | order_id, sku_id, qty, refund_mode, timestamp | refund_mode ORIGINAL / WALLET; moves order to RETURN_REQUESTED |
| `RETURN_RECEIVED` | order_id, sku_id, timestamp | RETURNED → REFUNDED; refund computed here |

## Planted scenarios

Every edge case from the brief, and where it sits in this pack:

- **Coupon applied by user before category offer** — `commands.txt` line 49 applies SAVE15 before the FASHION line (10% category offer) is added at line 50; the coupon minimum must be judged at CHECKOUT (line 51) after the category offer
- **Cart value dropping below coupon minimum after category offer** — `commands.txt` line 56: SAVE15 (min 2000) on jeans 1499 + t-shirt 599 = 2098 pre-offer, 1888.20 after the FASHION 10% offer → coupon must be refused at checkout
- **Buy-X-get-Y on items with different prices** — `commands.txt` line 70: fifth FASHION item added to a cart of 5 differently priced non-sale FASHION items (1499, 1299, 649, 349, 449) — buy 2 get 1 → exactly one free item, the cheapest (349)
- **Return of the free item in a buy-X-get-Y** — `commands.txt` line 186: RETURN_REQUEST for SKU-014 (the free item of a 3-item BXGY order) — refund for a Rs 0 line, and the remaining pair no longer earns a free item
- **Cancelling after partial shipment** — `commands.txt` line 107: partial shipment of only SKU-001, then CANCEL at line 109 for the whole order while SKU-023 is still PACKED
- **Reservation expiry during checkout** — `commands.txt` line 95: CHECKOUT 31 minutes after the last cart activity — reservations have expired; the checkout must re-check stock (or fail) rather than use the lapsed reservation
- **GST rounding where line totals do not sum to invoice total** — `commands.txt` line 115: three HOME lines (SKU-028, SKU-029, SKU-032) at 18% GST with SAVE15 — the sum of per-line rounded GST differs from GST on the invoice total by 1 paisa; per-line is the rule

Extra traps (not in the brief, but realistic):

- line 35: SAVE15 on a cart containing sale-flagged SKU-003 — coupon applies to the other lines only
- line 103 then line 104: two coupons on one cart — only one may apply (reject the second or replace; state your choice)
- line 123: HDFC CARD checkout where the cart is above Rs 3,000 on selling price but below it after category offer + coupon → bank offer must not apply
- line 135 cancel before PACKED (free); line 157 after PACKED (2%); line 165 after SHIPPED (reject with named error)
- line 303: REGULAR return on day 10 (last allowed day); line 305: day 11 (reject); line 314: PRIME return on day 30 (allowed); line 266: return of BEAUTY item (non-returnable)
- line 285: return drops the remaining order below the FLAT200 minimum of 1500 → coupon forfeited, refund reduced accordingly
- line 287: WALLET refund mode (instant, +2% bonus credit)
- line 202: STOCK_ADJUST write-off leaves only 2 units of SKU-019 while a cart holds 3 → CHECKOUT at line 203 must fail entirely (no partial checkout)
- line 269: DELIVERED → PACKED (illegal); line 217: CONFIRMED → SHIPPED skipping PACKED (illegal); later lines then follow the legal path
- line 293: FLAT200 applied on 22 Oct although valid_to is 2026-10-20 → reject
- line 229: cart of exactly Rs 499 post-discount (free shipping at/above 499); line 225: total weight exactly 2000 g (no surcharge); line 249: cart weighing 2640 g (surcharge for the part above 2 kg)
- line 307: partial return of 1 of 3 units of one line
- line 263: BXGY + category offer + coupon + HDFC bank offer on one cart — full precedence chain; the free item's line discount is 100%, so decide and document how the 70% line cap interacts with BXGY
- line 275: CHECKOUT exactly 30:00 after the last activity (boundary of the inactivity window — state whether 30:00 is still reserved)
- line 292: exact duplicate of the previous CART_ADD line (adds a second unit — not a parse error)

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

`status` ∈ OK / REJECTED; `error_code` is your named error (e.g. ILLEGAL_TRANSITION, COUPON_MIN_NOT_MET, STOCK_SHORT) or blank. Money to 2 decimals.

Produce these CSV files (header row, same formatting conventions as the inputs, one row per entity in the order stated). Column names must match exactly.

### `invoices.csv`

One row per successful CHECKOUT, in file order.

Columns, in order: `order_id`, `customer_id`, `checkout_ts`, `gross_selling_value`, `category_discount`, `coupon_code`, `coupon_discount`, `bank_discount`, `prime_discount`, `bxgy_free_value`, `taxable_value`, `cgst`, `sgst`, `igst`, `shipping`, `invoice_total`, `promotions_applied`

### `invoice_lines.csv`

One row per order line (free BXGY items as their own row with unit_price 0.00 discount shown).

Columns, in order: `order_id`, `sku_id`, `qty`, `unit_selling_price`, `line_discount`, `line_taxable`, `gst_slab`, `line_gst`, `line_total`

### `command_log.csv`

One row per command in file order.

Columns, in order: `line_no`, `command`, `entity_id`, `status`, `error_code`, `message`

### `order_states.csv`

Final state of every order after the whole file.

Columns, in order: `order_id`, `final_state`, `cancellation_fee`, `refund_amount`, `refund_mode`, `wallet_bonus`
