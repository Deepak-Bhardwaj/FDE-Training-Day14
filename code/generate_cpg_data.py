"""
generate_cpg_data.py
--------------------
Generates a SYNTHETIC CPG (consumer packaged goods) demand-planning dataset for
Lab 9. All data is invented for teaching multi-agent orchestration.

Produces (in ../data):
  products.json         : the SKUs, their category, weekly capacity, base demand
  sales_history.csv     : ~104 weeks of unit sales per SKU (2 years)
  promotions.json       : promo calendar (which SKU/week had a promo + discount)
  actuals.json          : the TRUE sales for the target week (to score forecasts)

The demand-planner agents use this:
  * Sales agent   -> baseline forecast from sales_history
  * Promo agent   -> uplift from promotions
  * Orchestrator  -> reconciles the two
  * Verifier      -> sanity-checks against capacity + history (actuals let us
                     measure forecast quality with MAPE)
"""
import csv, json, math, os, random

random.seed(9)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))
os.makedirs(DATA, exist_ok=True)

TARGET_WEEK = 105          # the week we are planning for (history is weeks 1..104)
N_WEEKS = 104

PRODUCTS = [
    {"sku": "SKU-BEV-01", "name": "Cola 330ml",        "category": "Beverages", "base": 12000, "capacity": 30000, "promo_sensitivity": 1.8},
    {"sku": "SKU-BEV-02", "name": "Sparkling Water 1L", "category": "Beverages", "base": 7000,  "capacity": 18000, "promo_sensitivity": 1.4},
    {"sku": "SKU-SNK-01", "name": "Potato Chips 150g",  "category": "Snacks",    "base": 9000,  "capacity": 22000, "promo_sensitivity": 2.1},
    {"sku": "SKU-SNK-02", "name": "Choc Biscuits 200g", "category": "Snacks",    "base": 6000,  "capacity": 15000, "promo_sensitivity": 1.9},
    {"sku": "SKU-HOM-01", "name": "Dish Soap 500ml",    "category": "Home Care", "base": 5000,  "capacity": 12000, "promo_sensitivity": 1.3},
    {"sku": "SKU-HOM-02", "name": "Laundry Pods 20ct",  "category": "Home Care", "base": 4000,  "capacity": 11000, "promo_sensitivity": 1.5},
]

with open(os.path.join(DATA, "products.json"), "w") as f:
    json.dump({p["sku"]: p for p in PRODUCTS}, f, indent=2)

# ---- weekly sales history with trend + seasonality + noise + promo spikes ----
promo_calendar = {}   # (sku, week) -> discount_pct
rows = [["sku", "week", "units", "on_promo", "discount_pct"]]

def seasonal(week):
    # simple yearly seasonality (52-week cycle), peak around week 50 (festive)
    return 1.0 + 0.15 * math.sin(2 * math.pi * (week % 52) / 52.0)

for p in PRODUCTS:
    trend = random.uniform(0.0005, 0.0025)     # slow growth per week
    for w in range(1, N_WEEKS + 1):
        base = p["base"] * (1 + trend * w) * seasonal(w)
        on_promo = random.random() < 0.15
        discount = random.choice([10, 15, 20, 25]) if on_promo else 0
        uplift = 1 + (discount / 100.0) * p["promo_sensitivity"] if on_promo else 1.0
        noise = random.uniform(0.92, 1.08)
        units = int(base * uplift * noise)
        if on_promo:
            promo_calendar[f"{p['sku']}|{w}"] = discount
        rows.append([p["sku"], w, units, int(on_promo), discount])

with open(os.path.join(DATA, "sales_history.csv"), "w", newline="") as f:
    csv.writer(f).writerows(rows)

# ---- promotions for the TARGET week (what the planner must account for) ----
target_promos = {}
for p in PRODUCTS:
    if random.random() < 0.5:
        target_promos[p["sku"]] = random.choice([15, 20, 25])
with open(os.path.join(DATA, "promotions.json"), "w") as f:
    json.dump({"target_week": TARGET_WEEK, "promotions": target_promos}, f, indent=2)

# ---- the TRUE sales for the target week (held out, to score forecasts) ----
actuals = {}
for p in PRODUCTS:
    base = p["base"] * (1 + 0.0015 * TARGET_WEEK) * seasonal(TARGET_WEEK)
    disc = target_promos.get(p["sku"], 0)
    uplift = 1 + (disc / 100.0) * p["promo_sensitivity"] if disc else 1.0
    actuals[p["sku"]] = int(base * uplift * random.uniform(0.97, 1.03))
with open(os.path.join(DATA, "actuals.json"), "w") as f:
    json.dump({"target_week": TARGET_WEEK, "actuals": actuals}, f, indent=2)

print(f"Wrote {len(PRODUCTS)} products, {N_WEEKS} weeks of history, "
      f"{len(target_promos)} target-week promos.")
print(f"Target week = {TARGET_WEEK}. Actuals held out for scoring.")
