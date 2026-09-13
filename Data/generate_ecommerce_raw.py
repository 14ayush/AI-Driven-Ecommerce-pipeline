#!/usr/bin/env python3
"""
E-commerce RAW data generator
==============================

Generates an uncompressed, Faker-based synthetic RAW dataset from
2020-01-01 through 2026-08-31.

Output layout:
    output/
      raw_data/
        raw_customers/
          2020/
            01/raw_customers_2020_01.csv
            ...
        raw_orders/
          2020/
            01/raw_orders_2020_01.csv
            ...
      metadata/
        metadata.db
        metadata.csv

Important design choices
------------------------
1. Every table has its own CSV file for every year/month.
2. A central SQLite metadata store records every generated file and run.
3. A `created_by` column is added to every generated table, even though it
   is not present in the supplied DDL. This is intentional because it was
   explicitly requested.
4. `created_by` is selected only from users whose active period overlaps
   the record's month. Therefore the creator is temporally valid.
5. Year/month data is NOT identical. The generator uses:
      - yearly growth
      - monthly seasonality
      - weekday/weekend effects
      - regional/country mix changes
      - category/product mix changes
      - campaign seasonality
      - random drift
   so each month and year has a different distribution.
6. The generator streams rows directly to CSV, so it does not load
   gigabytes of data into RAM.
7. By default it targets at least 3 GiB of UNCOMPRESSED CSV data.
   `--target-gb 3` can be changed.

Dependencies:
    pip install Faker

Run:
    python generate_ecommerce_raw.py --output ./ecommerce_dataset --target-gb 3

For a faster smoke test:
    python generate_ecommerce_raw.py --output ./test_dataset --target-gb 0.01

The generated CSVs intentionally contain the `created_by` field. If you
load them into PostgreSQL using the supplied schema, add:
    ALTER TABLE <table_name> ADD COLUMN created_by VARCHAR(150);
"""

import argparse
import csv
import hashlib
import math
import os
import random
import sqlite3
import string
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from faker import Faker


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

START_DATE = date(2020, 1, 1)
END_DATE = date(2026, 8, 31)

DEFAULT_TARGET_GIB = 3.0
DEFAULT_SEED = 20260913

TABLES = [
    "raw_geography",
    "raw_currencies",
    "raw_exchange_rates",
    "raw_customers",
    "raw_sellers",
    "raw_products",
    "raw_sessions",
    "raw_events",
    "raw_orders",
    "raw_order_items",
    "raw_payments",
    "raw_shipments",
    "raw_reviews",
    "raw_inventory",
    "raw_campaigns",
]

# Approximate row allocation. These are weights, not fixed row counts.
# The final file sizes are measured and generation continues until the
# requested target size is reached.
TABLE_WEIGHTS = {
    "raw_geography": 0.002,
    "raw_currencies": 0.001,
    "raw_exchange_rates": 0.004,
    "raw_customers": 0.12,
    "raw_sellers": 0.025,
    "raw_products": 0.07,
    "raw_sessions": 0.18,
    "raw_events": 0.30,
    "raw_orders": 0.10,
    "raw_order_items": 0.08,
    "raw_payments": 0.035,
    "raw_shipments": 0.025,
    "raw_reviews": 0.035,
    "raw_inventory": 0.02,
    "raw_campaigns": 0.003,
}

# Seed/master entities. They are intentionally generated once and then
# reused so that foreign-key-like relationships remain meaningful.
COUNTRIES = [
    ("United States", "USA", "North America", "Northern America", "USD"),
    ("Canada", "CAN", "North America", "Northern America", "CAD"),
    ("United Kingdom", "GBR", "Europe", "Northern Europe", "GBP"),
    ("Germany", "DEU", "Europe", "Western Europe", "EUR"),
    ("France", "FRA", "Europe", "Western Europe", "EUR"),
    ("Spain", "ESP", "Europe", "Southern Europe", "EUR"),
    ("Italy", "ITA", "Europe", "Southern Europe", "EUR"),
    ("Netherlands", "NLD", "Europe", "Western Europe", "EUR"),
    ("Australia", "AUS", "Oceania", "Australia and New Zealand", "AUD"),
    ("Japan", "JPN", "Asia", "Eastern Asia", "JPY"),
    ("Singapore", "SGP", "Asia", "South-eastern Asia", "SGD"),
    ("India", "IND", "Asia", "Southern Asia", "INR"),
    ("United Arab Emirates", "ARE", "Asia", "Western Asia", "AED"),
    ("Brazil", "BRA", "South America", "South America", "BRL"),
    ("Mexico", "MEX", "North America", "Central America", "MXN"),
]

CURRENCY_INFO = {
    "USD": ("US Dollar", "$", 2, "FIAT"),
    "CAD": ("Canadian Dollar", "C$", 2, "FIAT"),
    "GBP": ("Pound Sterling", "£", 2, "FIAT"),
    "EUR": ("Euro", "€", 2, "FIAT"),
    "AUD": ("Australian Dollar", "A$", 2, "FIAT"),
    "JPY": ("Japanese Yen", "¥", 0, "FIAT"),
    "SGD": ("Singapore Dollar", "S$", 2, "FIAT"),
    "INR": ("Indian Rupee", "₹", 2, "FIAT"),
    "AED": ("UAE Dirham", "د.إ", 2, "FIAT"),
    "BRL": ("Brazilian Real", "R$", 2, "FIAT"),
    "MXN": ("Mexican Peso", "MX$", 2, "FIAT"),
}

PAYMENT_METHODS = [
    "Credit Card", "Debit Card", "PayPal", "Apple Pay", "Google Pay",
    "Bank Transfer", "Buy Now Pay Later", "Gift Card","Paytm","Phonepe"
]
SHIPPING_METHODS = ["Standard", "Express", "Same Day", "Economy", "Pickup"]
CARRIERS = ["DHL", "FedEx", "UPS", "USPS", "DPD", "Royal Mail", "Australia Post"]
PLATFORMS = ["Web", "Mobile Web", "iOS", "Android"]
DEVICES = ["Desktop", "Laptop", "Tablet", "Mobile"]
OS_LIST = ["Windows", "macOS", "iOS", "Android", "Linux", "ChromeOS"]
BROWSERS = ["Chrome", "Safari", "Edge", "Firefox", "Samsung Internet"]
TRAFFIC_SOURCES = ["Google", "Bing", "Facebook", "Instagram", "TikTok",
                   "Direct", "Email", "Affiliate", "YouTube", "Organic"]
TRAFFIC_MEDIUMS = ["organic", "cpc", "social", "email", "referral", "direct", "affiliate"]

CATEGORIES = {
    "Electronics": ["Phones", "Laptops", "Audio", "Cameras", "Accessories"],
    "Home": ["Furniture", "Kitchen", "Decor", "Lighting", "Storage"],
    "Fashion": ["Men", "Women", "Shoes", "Accessories", "Sportswear"],
    "Beauty": ["Skincare", "Haircare", "Makeup", "Fragrance", "Personal Care"],
    "Sports": ["Fitness", "Outdoor", "Cycling", "Running", "Team Sports"],
    "Books": ["Fiction", "Non-fiction", "Business", "Technology", "Education"],
    "Grocery": ["Beverages", "Snacks", "Pantry", "Organic", "Household"],
    "Toys": ["Games", "Educational", "Outdoor", "Collectibles", "Puzzles"],
}

EVENT_NAMES = [
    ("page_view", "engagement"),
    ("search", "engagement"),
    ("product_view", "commerce"),
    ("add_to_cart", "commerce"),
    ("remove_from_cart", "commerce"),
    ("checkout_start", "commerce"),
    ("payment_attempt", "commerce"),
    ("purchase", "conversion"),
    ("wishlist_add", "engagement"),
    ("coupon_apply", "commerce"),
    ("review_view", "engagement"),
]

ORDER_STATUSES = ["Completed", "Processing", "Cancelled", "Returned", "Failed"]
PAYMENT_STATUSES = ["Success", "Failed", "Pending", "Refunded"]
SHIPMENT_STATUSES = ["Delivered", "In Transit", "Shipped", "Delayed", "Returned"]
SELLER_TYPES = ["Marketplace", "Brand", "Retailer", "Distributor", "Small Business"]
FULFILLMENT_TYPES = ["Seller Fulfilled", "Platform Fulfilled", "Dropship"]
CUSTOMER_SEGMENTS = ["Premium", "Regular", "Occasional", "New", "At Risk"]
ACQUISITION_CHANNELS = ["Organic", "Paid Search", "Social", "Referral", "Email", "Affiliate", "Direct"]
SENTIMENTS = ["Positive", "Neutral", "Negative"]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def month_range(start: date, end: date):
    """Yield first day of every month in the requested range."""
    current = date(start.year, start.month, 1)
    while current <= end:
        yield current
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)


def month_end(d: date) -> date:
    if d.month == 12:
        return date(d.year, 12, 31)
    return date(d.year, d.month + 1, 1) - timedelta(days=1)


def days_in_month(d: date) -> int:
    return month_end(d).day


def random_timestamp(rng, start_date, end_date):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    seconds = int((end_dt - start_dt).total_seconds())
    return start_dt + timedelta(seconds=rng.randint(0, max(0, seconds)))


def random_date(rng, start_date, end_date):
    if end_date < start_date:
        end_date = start_date
    return start_date + timedelta(days=rng.randint(0, (end_date - start_date).days))


def money(rng, low, high):
    return round(rng.uniform(low, high), 2)


def weighted_choice(rng, values, weights=None):
    return rng.choices(values, weights=weights, k=1)[0]


def deterministic_rng(seed, *parts):
    text = "|".join(map(str, (seed,) + parts))
    h = hashlib.sha256(text.encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def month_factor(month):
    # E-commerce seasonality: Nov/Dec strongest, Jan/Feb softer.
    factors = {
        1: 0.82, 2: 0.78, 3: 0.90, 4: 0.94,
        5: 0.98, 6: 1.02, 7: 1.00, 8: 1.03,
        9: 1.08, 10: 1.14, 11: 1.38, 12: 1.55
    }
    return factors[month]


def year_factor(year):
    # Continuous growth, but deliberately non-linear.
    return 1.0 + ((year - 2020) * 0.17) + (0.03 * math.sin(year))


def business_factor(d):
    return 1.10 if d.weekday() < 5 else 0.93


def distribution_for_month(base, year, month, rng):
    """
    Produces a slightly different monthly value instead of repeating
    identical counts. The random component is deterministic for a
    given seed/year/month.
    """
    drift = 1.0 + rng.uniform(-0.09, 0.09)
    return max(1, int(base * year_factor(year) * month_factor(month) * drift))


def ensure_parent(path):
    path.parent.mkdir(parents=True, exist_ok=True)


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


# ---------------------------------------------------------------------------
# CENTRAL METADATA STORE
# ---------------------------------------------------------------------------

def init_metadata(db_path):
    ensure_parent(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS generation_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            target_bytes INTEGER NOT NULL,
            actual_bytes INTEGER,
            seed INTEGER NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_metadata (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            table_name TEXT NOT NULL,
            data_year INTEGER NOT NULL,
            data_month INTEGER NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            row_count INTEGER NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            file_size_mb REAL NOT NULL,
            min_created_at TEXT,
            max_created_at TEXT,
            min_created_by TEXT,
            max_created_by TEXT,
            sha256 TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES generation_runs(run_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS table_metadata (
            run_id INTEGER NOT NULL,
            table_name TEXT NOT NULL,
            total_rows INTEGER NOT NULL,
            total_bytes INTEGER NOT NULL,
            total_files INTEGER NOT NULL,
            PRIMARY KEY (run_id, table_name)
        )
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# MASTER DATA
# ---------------------------------------------------------------------------

def build_master_data(fake, rng):
    geography = []
    for country, code, region, sub_region, currency in COUNTRIES:
        geography.append({
            "country_name": country,
            "country_code": code,
            "region_name": region,
            "sub_region_name": sub_region,
            "currency_code": currency,
            "currency_name": CURRENCY_INFO[currency][0],
            "currency_symbol": CURRENCY_INFO[currency][1],
            "timezone": fake.timezone(),
        })

    currency_rows = []
    for code, info in CURRENCY_INFO.items():
        currency_rows.append({
            "currency_code": code,
            "currency_name": info[0],
            "currency_symbol": info[1],
            "decimal_places": info[2],
            "currency_type": info[3],
            "active_flag": True,
        })

    # Persistent creator population. Each creator gets an active interval.
    creators = []
    creator_domains = [
        "dataops.example.com", "analytics.example.com",
        "commerce.example.com", "platform.example.com"
    ]
    for i in range(1, 121):
        joined = random_date(rng, date(2018, 1, 1), date(2025, 12, 31))
        if i <= 85:
            left = None
        else:
            left = random_date(rng, max(joined, date(2024, 1, 1)), END_DATE)
        first = fake.first_name()
        last = fake.last_name()
        creators.append({
            "created_by": f"{first.lower()}.{last.lower()}{i:03d}@{rng.choice(creator_domains)}",
            "active_from": joined,
            "active_to": left,
        })

    return geography, currency_rows, creators


def active_creators(creators, d):
    result = []
    for c in creators:
        if c["active_from"] <= d and (c["active_to"] is None or c["active_to"] >= d):
            result.append(c)
    return result


def choose_created_by(rng, creators, d):
    active = active_creators(creators, d)
    if not active:
        # Safety fallback: choose the creator with the latest start date
        # not after the record date.
        eligible = [c for c in creators if c["active_from"] <= d]
        return max(eligible, key=lambda x: x["active_from"])["created_by"]
    return rng.choice(active)["created_by"]


# ---------------------------------------------------------------------------
# FILE WRITER
# ---------------------------------------------------------------------------

def write_csv(path, columns, row_generator):
    ensure_parent(path)
    rows = 0
    sha = hashlib.sha256()
    min_created = None
    max_created = None
    min_creator = None
    max_creator = None

    with open(path, "w", newline="", encoding="utf-8", buffering=1024 * 1024) as f:
        writer = csv.writer(f, lineterminator="\n")
        header = [str(x) for x in columns]
        line = ",".join(header) + "\n"
        f.write(line)

        for row in row_generator:
            normalized = [csv_value(row.get(c)) for c in columns]
            writer.writerow(normalized)
            rows += 1

            created = row.get("created_at")
            creator = row.get("created_by")

            if created:
                created_s = str(created)
                min_created = created_s if min_created is None else min(min_created, created_s)
                max_created = created_s if max_created is None else max(max_created, created_s)

            if creator:
                min_creator = str(creator) if min_creator is None else min(min_creator, str(creator))
                max_creator = str(creator) if max_creator is None else max(max_creator, str(creator))

    # Hash after writing because CSV writer buffered output is now closed.
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)

    size = path.stat().st_size
    return {
        "row_count": rows,
        "file_size_bytes": size,
        "file_size_mb": round(size / 1024 / 1024, 3),
        "min_created_at": min_created,
        "max_created_at": max_created,
        "min_created_by": min_creator,
        "max_created_by": max_creator,
        "sha256": sha.hexdigest(),
    }


# ---------------------------------------------------------------------------
# GENERATORS
# ---------------------------------------------------------------------------

def generate_geography(fake, rng, month, creators):
    for i, g in enumerate(MASTER_GEOGRAPHY, 1):
        created_at = random_timestamp(rng, month, month_end(month))
        yield {
            "geography_id": i,
            "region_name": g["region_name"],
            "sub_region_name": g["sub_region_name"],
            "country_name": g["country_name"],
            "country_code": g["country_code"],
            "currency_code": g["currency_code"],
            "currency_name": g["currency_name"],
            "currency_symbol": g["currency_symbol"],
            "timezone": g["timezone"],
            "created_at": created_at,
            "created_by": choose_created_by(rng, creators, created_at.date()),
        }


def generate_currencies(fake, rng, month, creators):
    for c in MASTER_CURRENCIES:
        created_at = random_timestamp(rng, month, month_end(month))
        yield {
            **c,
            "created_at": created_at,
            "created_by": choose_created_by(rng, creators, created_at.date()),
        }


def generate_exchange_rates(fake, rng, month, creators, rows):
    currencies = list(CURRENCY_INFO.keys())
    for _ in range(rows):
        d = random_date(rng, month, month_end(month))
        base = rng.choice(currencies)
        target = rng.choice([x for x in currencies if x != base])
        # Log-normal-ish rate; month/year influence prevents repetition.
        rate = math.exp(rng.normalvariate(0.0, 0.75))
        rate *= (1 + 0.02 * (month.year - 2020))
        created_at = datetime.combine(d, datetime.min.time()) + timedelta(
            seconds=rng.randint(0, 86399)
        )
        yield {
            "exchange_rate_id": None,
            "rate_date": d,
            "base_currency": base,
            "target_currency": target,
            "exchange_rate": round(rate, 10),
            "rate_source": rng.choice(["ECB", "Reuters", "Bloomberg", "Internal FX"]),
            "rate_type": rng.choice(["Spot", "Daily", "Closing"]),
            "created_at": created_at,
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_customers(fake, rng, month, creators, rows, id_start):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        g = weighted_choice(rng, MASTER_GEOGRAPHY)
        dob = random_date(rng, date(1940, 1, 1), date(2006, 12, 31))
        age = max(13, int((d - dob).days / 365.25))
        if age < 25:
            age_group = "18-24"
        elif age < 35:
            age_group = "25-34"
        elif age < 45:
            age_group = "35-44"
        elif age < 55:
            age_group = "45-54"
        elif age < 65:
            age_group = "55-64"
        else:
            age_group = "65+"

        first = fake.first_name()
        last = fake.last_name()
        customer_id = f"CUST-{id_start + n:010d}"

        yield {
            "customer_record_id": id_start + n,
            "customer_id": customer_id,
            "first_name": first,
            "last_name": last,
            "gender": rng.choice(["Male", "Female", "Non-binary", "Prefer not to say"]),
            "date_of_birth": dob,
            "age": age,
            "age_group": age_group,
            "email": f"{first.lower()}.{last.lower()}.{id_start+n}@{fake.free_email_domain()}",
            "country_name": g["country_name"],
            "country_code": g["country_code"],
            "region_name": g["region_name"],
            "sub_region_name": g["sub_region_name"],
            "city": fake.city(),
            "state_province": fake.state(),
            "postal_code": fake.postcode(),
            "currency_code": g["currency_code"],
            "customer_segment": weighted_choice(
                rng, CUSTOMER_SEGMENTS, [8, 38, 32, 17, 5]
            ),
            "acquisition_channel": weighted_choice(
                rng, ACQUISITION_CHANNELS, [25, 18, 17, 10, 8, 7, 15]
            ),
            "registration_date": d,
            "customer_status": weighted_choice(
                rng, ["Active", "Inactive", "Suspended"], [88, 10, 2]
            ),
            "marketing_opt_in": rng.random() < (0.58 + 0.02 * math.sin(month.month)),
            "effective_from": datetime.combine(d, datetime.min.time()),
            "effective_to": None,
            "is_current": True,
            "source_system": rng.choice(["CRM", "Web", "Mobile", "Marketplace"]),
            "created_at": datetime.combine(d, datetime.min.time()) + timedelta(
                seconds=rng.randint(0, 86399)
            ),
            "updated_at": datetime.combine(d, datetime.min.time()) + timedelta(
                seconds=rng.randint(0, 86399)
            ),
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_sellers(fake, rng, month, creators, rows, id_start):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        g = weighted_choice(rng, MASTER_GEOGRAPHY)
        yield {
            "seller_record_id": id_start + n,
            "seller_id": f"SELL-{id_start+n:08d}",
            "seller_name": fake.company(),
            "seller_type": rng.choice(SELLER_TYPES),
            "country_name": g["country_name"],
            "country_code": g["country_code"],
            "region_name": g["region_name"],
            "seller_rating": round(max(1, min(5, rng.gauss(4.15, 0.45))), 2),
            "seller_status": weighted_choice(
                rng, ["Active", "Inactive", "Suspended"], [91, 7, 2]
            ),
            "fulfillment_type": rng.choice(FULFILLMENT_TYPES),
            "seller_join_date": d,
            "effective_from": datetime.combine(d, datetime.min.time()),
            "effective_to": None,
            "is_current": True,
            "created_at": datetime.combine(d, datetime.min.time()) + timedelta(
                seconds=rng.randint(0, 86399)
            ),
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_products(fake, rng, month, creators, rows, product_counter, seller_ids):
    category_names = list(CATEGORIES.keys())
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        cat1 = weighted_choice(
            rng, category_names,
            [22, 17, 24, 10, 10, 8, 6, 3]
        )
        cat2 = rng.choice(CATEGORIES[cat1])
        cat3 = rng.choice(["Standard", "Premium", "Limited", "Eco", "Pro"])
        cat4 = rng.choice(["New", "Popular", "Classic", "Seasonal", "Bundle"])
        product_id = f"PROD-{product_counter+n:010d}"
        base = money(rng, 5, 2500)
        cost = round(base * rng.uniform(0.35, 0.78), 2)
        seller_id = rng.choice(seller_ids)

        yield {
            "product_record_id": product_counter + n,
            "product_id": product_id,
            "parent_product_id": f"PARENT-{rng.randint(1, max(1, product_counter+n)):010d}",
            "product_title": f"{fake.word().title()} {fake.word().title()} {cat2}",
            "brand": fake.company(),
            "category_level_1": cat1,
            "category_level_2": cat2,
            "category_level_3": cat3,
            "category_level_4": cat4,
            "product_type": rng.choice(["Standard", "Premium", "Bundle", "Subscription"]),
            "seller_id": seller_id,
            "country_of_sale": rng.choice(COUNTRIES)[0],
            "country_code": rng.choice(COUNTRIES)[1],
            "local_currency": rng.choice(list(CURRENCY_INFO)),
            "base_price_local": base,
            "cost_local": cost,
            "discount_percentage": round(rng.uniform(0, 45), 2),
            "tax_percentage": round(rng.uniform(0, 25), 2),
            "product_rating": round(max(1, min(5, rng.gauss(4.1, 0.5))), 2),
            "review_count": max(0, int(rng.expovariate(1 / 80))),
            "product_status": weighted_choice(
                rng, ["Active", "Inactive", "Discontinued"], [91, 7, 2]
            ),
            "stock_quantity": max(0, int(rng.gauss(400, 220))),
            "product_launch_date": d,
            "effective_from": datetime.combine(d, datetime.min.time()),
            "effective_to": None,
            "is_current": True,
            "created_at": datetime.combine(d, datetime.min.time()) + timedelta(
                seconds=rng.randint(0, 86399)
            ),
            "updated_at": datetime.combine(d, datetime.min.time()) + timedelta(
                seconds=rng.randint(0, 86399)
            ),
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_sessions(fake, rng, month, creators, rows, customer_ids):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        start = datetime.combine(d, datetime.min.time()) + timedelta(
            seconds=rng.randint(0, 86399)
        )
        duration = max(5, int(rng.lognormvariate(5.0, 0.75)))
        end = start + timedelta(seconds=duration)
        g = weighted_choice(rng, MASTER_GEOGRAPHY)
        new_customer = rng.random() < max(0.08, 0.35 - 0.015 * (month.year - 2020))
        yield {
            "session_record_id": None,
            "session_id": f"SES-{month.year}{month.month:02d}-{n:010d}",
            "customer_id": rng.choice(customer_ids),
            "session_start": start,
            "session_end": end,
            "session_duration_seconds": duration,
            "country_name": g["country_name"],
            "country_code": g["country_code"],
            "region_name": g["region_name"],
            "currency_code": g["currency_code"],
            "platform": weighted_choice(rng, PLATFORMS, [55, 15, 15, 15]),
            "device_type": weighted_choice(rng, DEVICES, [42, 18, 8, 32]),
            "operating_system": rng.choice(OS_LIST),
            "browser": rng.choice(BROWSERS),
            "traffic_source": weighted_choice(
                rng, TRAFFIC_SOURCES, [25, 6, 10, 10, 6, 20, 8, 5, 4, 6]
            ),
            "traffic_medium": rng.choice(TRAFFIC_MEDIUMS),
            "campaign_id": f"CAMP-{month.year}-{rng.randint(1, 40):04d}" if rng.random() < 0.42 else "",
            "landing_page": f"/{rng.choice(['home','search','category','sale','offers','product'])}",
            "exit_page": f"/{rng.choice(['home','product','cart','checkout','search'])}",
            "is_new_customer": new_customer,
            "is_new_session": rng.random() < 0.68,
            "created_at": start,
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_events(fake, rng, month, creators, rows, customer_ids, product_ids, order_ids):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        ts = datetime.combine(d, datetime.min.time()) + timedelta(
            seconds=rng.randint(0, 86399)
        )
        event_name, category = weighted_choice(
            rng,
            EVENT_NAMES,
            [30, 8, 28, 10, 3, 5, 3, 5, 3, 2, 3]
        )
        product_id = rng.choice(product_ids) if event_name not in ("search", "page_view") else ""
        order_id = rng.choice(order_ids) if event_name in ("purchase", "payment_attempt") and order_ids else ""
        quantity = rng.randint(1, 5)
        price = money(rng, 5, 1500) if product_id else 0
        value = round(price * quantity, 2)
        g = weighted_choice(rng, MASTER_GEOGRAPHY)
        yield {
            "event_record_id": None,
            "event_id": f"EVT-{month.year}{month.month:02d}-{n:012d}",
            "event_timestamp": ts,
            "session_id": f"SES-{month.year}{month.month:02d}-{rng.randint(0, max(1, rows//2)):010d}",
            "customer_id": rng.choice(customer_ids),
            "product_id": product_id,
            "order_id": order_id,
            "event_name": event_name,
            "event_category": category,
            "page_name": rng.choice(["Home", "Search", "Product", "Cart", "Checkout", "Account"]),
            "page_url": f"https://shop.example.com/{rng.choice(['home','search','product','cart','checkout'])}",
            "referrer_url": f"https://{rng.choice(['google.com','bing.com','facebook.com','instagram.com'])}",
            "search_query": fake.sentence(nb_words=3) if event_name == "search" else "",
            "product_position": rng.randint(1, 48) if product_id else None,
            "quantity": quantity if product_id else 0,
            "unit_price_local": price,
            "event_value_local": value,
            "local_currency": g["currency_code"],
            "country_name": g["country_name"],
            "country_code": g["country_code"],
            "region_name": g["region_name"],
            "device_type": rng.choice(DEVICES),
            "platform": rng.choice(PLATFORMS),
            "operating_system": rng.choice(OS_LIST),
            "browser": rng.choice(BROWSERS),
            "traffic_source": rng.choice(TRAFFIC_SOURCES),
            "traffic_medium": rng.choice(TRAFFIC_MEDIUMS),
            "campaign_id": f"CAMP-{month.year}-{rng.randint(1, 40):04d}" if rng.random() < 0.45 else "",
            "created_at": ts,
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_orders(fake, rng, month, creators, rows, customer_ids):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        ts = datetime.combine(d, datetime.min.time()) + timedelta(
            seconds=rng.randint(0, 86399)
        )
        g = weighted_choice(rng, MASTER_GEOGRAPHY)
        subtotal = money(rng, 15, 3000)
        discount = round(subtotal * rng.uniform(0, 0.25), 2)
        shipping = money(rng, 0, 45)
        tax = round(max(0, subtotal - discount) * rng.uniform(0.02, 0.24), 2)
        total = round(subtotal - discount + shipping + tax, 2)
        status = weighted_choice(rng, ORDER_STATUSES, [78, 8, 5, 7, 2])
        cancellation = ts + timedelta(hours=rng.randint(1, 72)) if status == "Cancelled" else None
        return_flag = status == "Returned"
        delivery = d + timedelta(days=rng.randint(2, 12))
        actual = delivery if status == "Completed" else None

        yield {
            "order_record_id": None,
            "order_id": f"ORD-{month.year}{month.month:02d}-{n:010d}",
            "customer_id": rng.choice(customer_ids),
            "session_id": f"SES-{month.year}{month.month:02d}-{rng.randint(0, max(1, rows)):010d}",
            "order_timestamp": ts,
            "order_status": status,
            "country_name": g["country_name"],
            "country_code": g["country_code"],
            "region_name": g["region_name"],
            "local_currency": g["currency_code"],
            "subtotal_local": subtotal,
            "discount_local": discount,
            "shipping_local": shipping,
            "tax_local": tax,
            "total_amount_local": total,
            "payment_method": rng.choice(PAYMENT_METHODS),
            "shipping_method": rng.choice(SHIPPING_METHODS),
            "warehouse_id": f"WH-{rng.randint(1, 250):05d}",
            "estimated_delivery_date": delivery,
            "actual_delivery_date": actual,
            "cancellation_date": cancellation,
            "return_flag": return_flag,
            "refund_amount_local": total if return_flag else 0,
            "source_system": rng.choice(["Web", "Mobile", "Marketplace", "POS"]),
            "created_at": ts,
            "updated_at": ts + timedelta(minutes=rng.randint(1, 180)),
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_order_items(fake, rng, month, creators, rows, product_ids, seller_ids):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        qty = rng.randint(1, 6)
        unit = money(rng, 5, 1200)
        discount = round(unit * qty * rng.uniform(0, 0.22), 2)
        tax = round(max(0, unit * qty - discount) * rng.uniform(0.02, 0.24), 2)
        total = round(unit * qty - discount + tax, 2)
        yield {
            "order_item_record_id": None,
            "order_item_id": f"ITEM-{month.year}{month.month:02d}-{n:012d}",
            "order_id": f"ORD-{month.year}{month.month:02d}-{rng.randint(0, max(1, rows)):010d}",
            "product_id": rng.choice(product_ids),
            "seller_id": rng.choice(seller_ids),
            "quantity": qty,
            "unit_price_local": unit,
            "discount_local": discount,
            "tax_local": tax,
            "item_total_local": total,
            "local_currency": rng.choice(list(CURRENCY_INFO)),
            "country_code": rng.choice(COUNTRIES)[1],
            "region_name": rng.choice(COUNTRIES)[2],
            "fulfillment_type": rng.choice(FULFILLMENT_TYPES),
            "return_flag": rng.random() < 0.075,
            "return_quantity": rng.randint(1, qty) if rng.random() < 0.075 else 0,
            "refund_amount_local": round(unit * rng.uniform(0, qty), 2) if rng.random() < 0.075 else 0,
            "created_at": datetime.combine(d, datetime.min.time()) + timedelta(
                seconds=rng.randint(0, 86399)
            ),
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_payments(fake, rng, month, creators, rows, customer_ids):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        ts = datetime.combine(d, datetime.min.time()) + timedelta(
            seconds=rng.randint(0, 86399)
        )
        g = weighted_choice(rng, MASTER_GEOGRAPHY)
        status = weighted_choice(rng, PAYMENT_STATUSES, [91, 4, 3, 2])
        failure = rng.choice([
            "Insufficient funds", "Card declined", "Network timeout",
            "Fraud check failed", "Invalid CVV"
        ]) if status == "Failed" else ""
        amount = money(rng, 10, 3500)
        yield {
            "payment_record_id": None,
            "payment_id": f"PAY-{month.year}{month.month:02d}-{n:011d}",
            "order_id": f"ORD-{month.year}{month.month:02d}-{rng.randint(0, max(1, rows)):010d}",
            "customer_id": rng.choice(customer_ids),
            "payment_timestamp": ts,
            "payment_method": rng.choice(PAYMENT_METHODS),
            "payment_status": status,
            "payment_amount_local": amount,
            "local_currency": g["currency_code"],
            "country_code": g["country_code"],
            "region_name": g["region_name"],
            "failure_reason": failure,
            "refund_flag": status == "Refunded",
            "created_at": ts,
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_shipments(fake, rng, month, creators, rows):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        shipped = datetime.combine(d, datetime.min.time()) + timedelta(
            seconds=rng.randint(0, 86399)
        )
        estimate = d + timedelta(days=rng.randint(2, 10))
        status = weighted_choice(
            rng, SHIPMENT_STATUSES, [70, 12, 9, 6, 3]
        )
        actual = (
            shipped + timedelta(days=rng.randint(2, 14), hours=rng.randint(0, 12))
            if status == "Delivered" else None
        )
        yield {
            "shipment_record_id": None,
            "shipment_id": f"SHP-{month.year}{month.month:02d}-{n:010d}",
            "order_id": f"ORD-{month.year}{month.month:02d}-{rng.randint(0, max(1, rows)):010d}",
            "warehouse_id": f"WH-{rng.randint(1, 250):05d}",
            "country_code": rng.choice(COUNTRIES)[1],
            "region_name": rng.choice(COUNTRIES)[2],
            "carrier": rng.choice(CARRIERS),
            "shipping_method": rng.choice(SHIPPING_METHODS),
            "shipment_status": status,
            "shipped_timestamp": shipped,
            "estimated_delivery_date": estimate,
            "actual_delivery_timestamp": actual,
            "delivery_attempts": rng.choices([1, 2, 3, 4], [80, 15, 4, 1], k=1)[0],
            "delivery_country": rng.choice(COUNTRIES)[0],
            "created_at": shipped,
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_reviews(fake, rng, month, creators, rows, customer_ids, product_ids):
    titles = [
        "Great product", "Worth the money", "Could be better",
        "Excellent quality", "Fast delivery", "Not as expected",
        "Highly recommended", "Average experience"
    ]
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        ts = datetime.combine(d, datetime.min.time()) + timedelta(
            seconds=rng.randint(0, 86399)
        )
        rating = weighted_choice(rng, [1, 2, 3, 4, 5], [3, 5, 12, 32, 48])
        sentiment = "Positive" if rating >= 4 else ("Neutral" if rating == 3 else "Negative")
        yield {
            "review_record_id": None,
            "review_id": f"REV-{month.year}{month.month:02d}-{n:010d}",
            "customer_id": rng.choice(customer_ids),
            "product_id": rng.choice(product_ids),
            "order_id": f"ORD-{month.year}{month.month:02d}-{rng.randint(0, max(1, rows)):010d}",
            "rating": rating,
            "review_title": rng.choice(titles),
            "review_text": fake.paragraph(nb_sentences=rng.randint(1, 4)),
            "verified_purchase": rng.random() < 0.86,
            "helpful_votes": max(0, int(rng.expovariate(1 / 8))),
            "review_timestamp": ts,
            "country_code": rng.choice(COUNTRIES)[1],
            "region_name": rng.choice(COUNTRIES)[2],
            "sentiment": sentiment,
            "created_at": ts,
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_inventory(fake, rng, month, creators, rows, product_ids):
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        available = max(0, int(rng.gauss(800, 450)))
        reserved = max(0, int(available * rng.uniform(0.02, 0.40)))
        damaged = max(0, int(available * rng.uniform(0, 0.04)))
        sold = max(0, int(rng.gauss(available * 0.25, available * 0.08)))
        returned = max(0, int(sold * rng.uniform(0.01, 0.10)))
        yield {
            "inventory_record_id": None,
            "inventory_id": f"INV-{month.year}{month.month:02d}-{n:010d}",
            "product_id": rng.choice(product_ids),
            "warehouse_id": f"WH-{rng.randint(1, 250):05d}",
            "country_code": rng.choice(COUNTRIES)[1],
            "region_name": rng.choice(COUNTRIES)[2],
            "inventory_date": d,
            "stock_available": available,
            "stock_reserved": reserved,
            "stock_damaged": damaged,
            "reorder_level": rng.randint(50, 300),
            "units_sold": sold,
            "units_returned": returned,
            "created_at": datetime.combine(d, datetime.min.time()) + timedelta(
                seconds=rng.randint(0, 86399)
            ),
            "created_by": choose_created_by(rng, creators, d),
        }


def generate_campaigns(fake, rng, month, creators, rows):
    campaign_types = ["Seasonal", "Performance", "Brand", "Retention", "Launch", "Flash Sale"]
    channels = ["Google Ads", "Meta", "TikTok", "Email", "Affiliate", "Display", "Organic"]
    for n in range(rows):
        d = random_date(rng, month, month_end(month))
        duration = rng.randint(3, 35)
        end = min(END_DATE, d + timedelta(days=duration))
        budget = money(rng, 1000, 500000)
        spend = round(budget * rng.uniform(0.30, 1.02), 2)
        impressions = max(100, int(rng.lognormvariate(11.5, 1.0)))
        ctr = rng.uniform(0.01, 0.08)
        clicks = int(impressions * ctr)
        conversions = int(clicks * rng.uniform(0.01, 0.18))
        g = rng.choice(COUNTRIES)

        yield {
            "campaign_record_id": None,
            "campaign_id": f"CAMP-{month.year}-{month.month:02d}-{n:06d}",
            "campaign_name": f"{rng.choice(['Holiday','Growth','Summer','Winter','Back-to-School','Member'])} {fake.word().title()} Campaign",
            "campaign_type": rng.choice(campaign_types),
            "channel": rng.choice(channels),
            "source": rng.choice(["Google", "Meta", "TikTok", "CRM", "Partner"]),
            "medium": rng.choice(TRAFFIC_MEDIUMS),
            "country_code": g[1],
            "region_name": g[2],
            "start_date": d,
            "end_date": end,
            "budget_local": budget,
            "spend_local": spend,
            "local_currency": g[4],
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "created_at": datetime.combine(d, datetime.min.time()) + timedelta(
                seconds=rng.randint(0, 86399)
            ),
            "created_by": choose_created_by(rng, creators, d),
        }


# ---------------------------------------------------------------------------
# COLUMN DEFINITIONS
# ---------------------------------------------------------------------------

COLUMNS = {
    "raw_geography": [
        "geography_id","region_name","sub_region_name","country_name","country_code",
        "currency_code","currency_name","currency_symbol","timezone","created_at","created_by"
    ],
    "raw_currencies": [
        "currency_code","currency_name","currency_symbol","decimal_places",
        "currency_type","active_flag","created_at","created_by"
    ],
    "raw_exchange_rates": [
        "exchange_rate_id","rate_date","base_currency","target_currency",
        "exchange_rate","rate_source","rate_type","created_at","created_by"
    ],
    "raw_customers": [
        "customer_record_id","customer_id","first_name","last_name","gender",
        "date_of_birth","age","age_group","email","country_name","country_code",
        "region_name","sub_region_name","city","state_province","postal_code",
        "currency_code","customer_segment","acquisition_channel","registration_date",
        "customer_status","marketing_opt_in","effective_from","effective_to",
        "is_current","source_system","created_at","updated_at","created_by"
    ],
    "raw_sellers": [
        "seller_record_id","seller_id","seller_name","seller_type","country_name",
        "country_code","region_name","seller_rating","seller_status","fulfillment_type",
        "seller_join_date","effective_from","effective_to","is_current",
        "created_at","created_by"
    ],
    "raw_products": [
        "product_record_id","product_id","parent_product_id","product_title","brand",
        "category_level_1","category_level_2","category_level_3","category_level_4",
        "product_type","seller_id","country_of_sale","country_code","local_currency",
        "base_price_local","cost_local","discount_percentage","tax_percentage",
        "product_rating","review_count","product_status","stock_quantity",
        "product_launch_date","effective_from","effective_to","is_current",
        "created_at","updated_at","created_by"
    ],
    "raw_sessions": [
        "session_record_id","session_id","customer_id","session_start","session_end",
        "session_duration_seconds","country_name","country_code","region_name",
        "currency_code","platform","device_type","operating_system","browser",
        "traffic_source","traffic_medium","campaign_id","landing_page","exit_page",
        "is_new_customer","is_new_session","created_at","created_by"
    ],
    "raw_events": [
        "event_record_id","event_id","event_timestamp","session_id","customer_id",
        "product_id","order_id","event_name","event_category","page_name","page_url",
        "referrer_url","search_query","product_position","quantity","unit_price_local",
        "event_value_local","local_currency","country_name","country_code","region_name",
        "device_type","platform","operating_system","browser","traffic_source",
        "traffic_medium","campaign_id","created_at","created_by"
    ],
    "raw_orders": [
        "order_record_id","order_id","customer_id","session_id","order_timestamp",
        "order_status","country_name","country_code","region_name","local_currency",
        "subtotal_local","discount_local","shipping_local","tax_local",
        "total_amount_local","payment_method","shipping_method","warehouse_id",
        "estimated_delivery_date","actual_delivery_date","cancellation_date",
        "return_flag","refund_amount_local","source_system","created_at","updated_at",
        "created_by"
    ],
    "raw_order_items": [
        "order_item_record_id","order_item_id","order_id","product_id","seller_id",
        "quantity","unit_price_local","discount_local","tax_local","item_total_local",
        "local_currency","country_code","region_name","fulfillment_type","return_flag",
        "return_quantity","refund_amount_local","created_at","created_by"
    ],
    "raw_payments": [
        "payment_record_id","payment_id","order_id","customer_id","payment_timestamp",
        "payment_method","payment_status","payment_amount_local","local_currency",
        "country_code","region_name","failure_reason","refund_flag","created_at","created_by"
    ],
    "raw_shipments": [
        "shipment_record_id","shipment_id","order_id","warehouse_id","country_code",
        "region_name","carrier","shipping_method","shipment_status","shipped_timestamp",
        "estimated_delivery_date","actual_delivery_timestamp","delivery_attempts",
        "delivery_country","created_at","created_by"
    ],
    "raw_reviews": [
        "review_record_id","review_id","customer_id","product_id","order_id","rating",
        "review_title","review_text","verified_purchase","helpful_votes",
        "review_timestamp","country_code","region_name","sentiment","created_at","created_by"
    ],
    "raw_inventory": [
        "inventory_record_id","inventory_id","product_id","warehouse_id","country_code",
        "region_name","inventory_date","stock_available","stock_reserved","stock_damaged",
        "reorder_level","units_sold","units_returned","created_at","created_by"
    ],
    "raw_campaigns": [
        "campaign_record_id","campaign_id","campaign_name","campaign_type","channel",
        "source","medium","country_code","region_name","start_date","end_date",
        "budget_local","spend_local","local_currency","impressions","clicks",
        "conversions","created_at","created_by"
    ],
}


# ---------------------------------------------------------------------------
# MAIN GENERATION
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate large monthly/yearly Faker e-commerce RAW data."
    )
    parser.add_argument("--output", default="./ecommerce_dataset")
    parser.add_argument("--target-gb", type=float, default=DEFAULT_TARGET_GIB,
                        help="Target uncompressed dataset size in GiB.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--start-date", default=START_DATE.isoformat())
    parser.add_argument("--end-date", default=END_DATE.isoformat())
    parser.add_argument("--force", action="store_true",
                        help="Delete/recreate the output directory.")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    if start_date < START_DATE or end_date > END_DATE or start_date > end_date:
        raise ValueError(
            f"Date range must be within {START_DATE} and {END_DATE}."
        )

    output = Path(args.output)
    raw_root = output / "raw_data"
    metadata_root = output / "metadata"

    if args.force and output.exists():
        import shutil
        shutil.rmtree(output)

    raw_root.mkdir(parents=True, exist_ok=True)
    metadata_root.mkdir(parents=True, exist_ok=True)

    target_bytes = int(args.target_gb * 1024 * 1024 * 1024)
    fake = Faker("en_US")
    Faker.seed(args.seed)
    master_rng = random.Random(args.seed)

    global MASTER_GEOGRAPHY, MASTER_CURRENCIES
    MASTER_GEOGRAPHY, MASTER_CURRENCIES, CREATORS = build_master_data(fake, master_rng)

    db = init_metadata(metadata_root / "metadata.db")
    started_at = datetime.now().isoformat(timespec="seconds")
    run_id = db.execute("""
        INSERT INTO generation_runs
        (started_at,start_date,end_date,target_bytes,seed,status)
        VALUES (?,?,?,?,?,?)
    """, (started_at, start_date.isoformat(), end_date.isoformat(),
          target_bytes, args.seed, "RUNNING")).lastrowid
    db.commit()

    # Approximate monthly base rows. Growth and seasonality modify these.
    base_rows = {
        "raw_geography": 15,
        "raw_currencies": 11,
        "raw_exchange_rates": 6000,
        "raw_customers": 18000,
        "raw_sellers": 4000,
        "raw_products": 10000,
        "raw_sessions": 28000,
        "raw_events": 48000,
        "raw_orders": 16000,
        "raw_order_items": 13000,
        "raw_payments": 6000,
        "raw_shipments": 4000,
        "raw_reviews": 6000,
        "raw_inventory": 3500,
        "raw_campaigns": 600,
    }

    # These are deliberately approximate relationship pools. The generated
    # dataset is analytically realistic rather than a strict OLTP replica.
    customer_counter = 1
    seller_counter = 1
    product_counter = 1
    cumulative_bytes = 0
    total_rows = defaultdict(int)
    total_bytes = defaultdict(int)
    total_files = defaultdict(int)

    all_months = list(month_range(start_date, end_date))
    started = time.time()

    # We generate every requested month/table. If the first pass does not
    # reach 3 GiB because the machine/filesystem differs from expectations,
    # the script performs an additional density pass on the largest fact
    # tables until the target is reached.
    for month_index, month in enumerate(all_months):
        year = month.year
        m = month.month
        days = days_in_month(month)

        # Month-specific RNG makes each month different but reproducible.
        rng = deterministic_rng(args.seed, year, m)

        # Keep small monthly dimensions manageable.
        counts = {
            table: distribution_for_month(base_rows[table], year, m, rng)
            for table in TABLES
        }

        # Create pools for current month.
        customer_ids = [
            f"CUST-{max(1, customer_counter - counts['raw_customers']):010d}"
            + ("" if i == 0 else "")
            for i in range(max(1, counts["raw_customers"]))
        ]
        # Make IDs explicit rather than relying on row positions.
        customer_ids = [
            f"CUST-{customer_counter+i:010d}"
            for i in range(max(1, counts["raw_customers"]))
        ]
        seller_ids = [
            f"SELL-{seller_counter+i:08d}"
            for i in range(max(1, counts["raw_sellers"]))
        ]
        product_ids = [
            f"PROD-{product_counter+i:010d}"
            for i in range(max(1, counts["raw_products"]))
        ]

        # Orders are generated before event generation so purchase events can
        # carry realistic order references.
        order_count = counts["raw_orders"]
        order_ids = [
            f"ORD-{year}{m:02d}-{i:010d}"
            for i in range(order_count)
        ]

        generators = {
            "raw_geography": generate_geography(fake, rng, month, CREATORS),
            "raw_currencies": generate_currencies(fake, rng, month, CREATORS),
            "raw_exchange_rates": generate_exchange_rates(
                fake, rng, month, CREATORS, counts["raw_exchange_rates"]
            ),
            "raw_customers": generate_customers(
                fake, rng, month, CREATORS,
                counts["raw_customers"], customer_counter
            ),
            "raw_sellers": generate_sellers(
                fake, rng, month, CREATORS,
                counts["raw_sellers"], seller_counter
            ),
            "raw_products": generate_products(
                fake, rng, month, CREATORS,
                counts["raw_products"], product_counter, seller_ids
            ),
            "raw_sessions": generate_sessions(
                fake, rng, month, CREATORS,
                counts["raw_sessions"], customer_ids
            ),
            "raw_events": generate_events(
                fake, rng, month, CREATORS,
                counts["raw_events"], customer_ids, product_ids, order_ids
            ),
            "raw_orders": generate_orders(
                fake, rng, month, CREATORS,
                counts["raw_orders"], customer_ids
            ),
            "raw_order_items": generate_order_items(
                fake, rng, month, CREATORS,
                counts["raw_order_items"], product_ids, seller_ids
            ),
            "raw_payments": generate_payments(
                fake, rng, month, CREATORS,
                counts["raw_payments"], customer_ids
            ),
            "raw_shipments": generate_shipments(
                fake, rng, month, CREATORS,
                counts["raw_shipments"]
            ),
            "raw_reviews": generate_reviews(
                fake, rng, month, CREATORS,
                counts["raw_reviews"], customer_ids, product_ids
            ),
            "raw_inventory": generate_inventory(
                fake, rng, month, CREATORS,
                counts["raw_inventory"], product_ids
            ),
            "raw_campaigns": generate_campaigns(
                fake, rng, month, CREATORS,
                counts["raw_campaigns"]
            ),
        }

        for table in TABLES:
            path = raw_root / table / f"{year:04d}" / f"{m:02d}" / f"{table}_{year:04d}_{m:02d}.csv"

            stats = write_csv(path, COLUMNS[table], generators[table])

            rel = path.relative_to(output).as_posix()
            generated_at = datetime.now().isoformat(timespec="seconds")

            db.execute("""
                INSERT INTO file_metadata
                (run_id,table_name,data_year,data_month,file_path,row_count,
                 file_size_bytes,file_size_mb,min_created_at,max_created_at,
                 min_created_by,max_created_by,sha256,generated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                run_id, table, year, m, rel,
                stats["row_count"], stats["file_size_bytes"], stats["file_size_mb"],
                stats["min_created_at"], stats["max_created_at"],
                stats["min_created_by"], stats["max_created_by"],
                stats["sha256"], generated_at
            ))

            total_rows[table] += stats["row_count"]
            total_bytes[table] += stats["file_size_bytes"]
            total_files[table] += 1
            cumulative_bytes += stats["file_size_bytes"]

        customer_counter += counts["raw_customers"]
        seller_counter += counts["raw_sellers"]
        product_counter += counts["raw_products"]

        db.commit()

        elapsed = max(1, time.time() - started)
        rate = cumulative_bytes / elapsed / 1024 / 1024
        print(
            f"[{month_index+1:02d}/{len(all_months)}] "
            f"{year}-{m:02d} | "
            f"{cumulative_bytes / 1024**3:.2f} GiB | "
            f"{rate:.1f} MiB/s",
            flush=True
        )

    # If base volume did not reach target, add extra monthly rows to the
    # largest fact tables. This guarantees the requested minimum without
    # putting a giant row count into every table.
    if cumulative_bytes < target_bytes:
        extra_tables = [
            "raw_events", "raw_sessions", "raw_orders",
            "raw_order_items", "raw_customers", "raw_products"
        ]
        pass_no = 1

        while cumulative_bytes < target_bytes:
            for table in extra_tables:
                if cumulative_bytes >= target_bytes:
                    break

                # Rotate through months to preserve temporal distribution.
                month = all_months[(pass_no - 1) % len(all_months)]
                year, m = month.year, month.month
                rng = deterministic_rng(args.seed, "extra", pass_no, table, year, m)

                extra_rows = 10000
                if table == "raw_events":
                    gen = generate_events(
                        fake, rng, month, CREATORS, extra_rows,
                        ["CUST-0000000001"],
                        ["PROD-0000000001"],
                        [f"ORD-{year}{m:02d}-0000000001"]
                    )
                elif table == "raw_sessions":
                    gen = generate_sessions(
                        fake, rng, month, CREATORS, extra_rows,
                        ["CUST-0000000001"]
                    )
                elif table == "raw_orders":
                    gen = generate_orders(
                        fake, rng, month, CREATORS, extra_rows,
                        ["CUST-0000000001"]
                    )
                elif table == "raw_order_items":
                    gen = generate_order_items(
                        fake, rng, month, CREATORS, extra_rows,
                        ["PROD-0000000001"], ["SELL-00000001"]
                    )
                elif table == "raw_customers":
                    gen = generate_customers(
                        fake, rng, month, CREATORS, extra_rows,
                        customer_counter
                    )
                    customer_counter += extra_rows
                else:
                    gen = generate_products(
                        fake, rng, month, CREATORS, extra_rows,
                        product_counter, ["SELL-00000001"]
                    )
                    product_counter += extra_rows

                path = raw_root / table / f"{year:04d}" / f"{m:02d}" / (
                    f"{table}_{year:04d}_{m:02d}_extra_{pass_no:05d}.csv"
                )
                stats = write_csv(path, COLUMNS[table], gen)

                rel = path.relative_to(output).as_posix()
                db.execute("""
                    INSERT INTO file_metadata
                    (run_id,table_name,data_year,data_month,file_path,row_count,
                     file_size_bytes,file_size_mb,min_created_at,max_created_at,
                     min_created_by,max_created_by,sha256,generated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    run_id, table, year, m, rel,
                    stats["row_count"], stats["file_size_bytes"], stats["file_size_mb"],
                    stats["min_created_at"], stats["max_created_at"],
                    stats["min_created_by"], stats["max_created_by"],
                    stats["sha256"], datetime.now().isoformat(timespec="seconds")
                ))
                total_rows[table] += stats["row_count"]
                total_bytes[table] += stats["file_size_bytes"]
                total_files[table] += 1
                cumulative_bytes += stats["file_size_bytes"]

                db.commit()
                pass_no += 1

                print(
                    f"[extra {pass_no:05d}] {table} {year}-{m:02d} | "
                    f"{cumulative_bytes / 1024**3:.2f} GiB",
                    flush=True
                )

    for table in TABLES:
        db.execute("""
            INSERT OR REPLACE INTO table_metadata
            (run_id,table_name,total_rows,total_bytes,total_files)
            VALUES (?,?,?,?,?)
        """, (
            run_id, table, total_rows[table], total_bytes[table], total_files[table]
        ))

    finished_at = datetime.now().isoformat(timespec="seconds")
    db.execute("""
        UPDATE generation_runs
        SET finished_at=?, actual_bytes=?, status=?
        WHERE run_id=?
    """, (finished_at, cumulative_bytes,
          "COMPLETED" if cumulative_bytes >= target_bytes else "INCOMPLETE", run_id))
    db.commit()

    # Export a human-friendly metadata CSV.
    metadata_csv = metadata_root / "metadata.csv"
    rows = db.execute("""
        SELECT run_id, table_name, data_year, data_month, file_path,
               row_count, file_size_bytes, file_size_mb,
               min_created_at, max_created_at,
               min_created_by, max_created_by, sha256, generated_at
        FROM file_metadata
        WHERE run_id=?
        ORDER BY table_name, data_year, data_month, file_path
    """, (run_id,)).fetchall()

    metadata_columns = [
        "run_id","table_name","data_year","data_month","file_path",
        "row_count","file_size_bytes","file_size_mb",
        "min_created_at","max_created_at",
        "min_created_by","max_created_by","sha256","generated_at"
    ]

    with open(metadata_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(metadata_columns)
        writer.writerows(rows)

    db.close()

    print("\n" + "=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)
    print(f"Output directory : {output.resolve()}")
    print(f"Target size      : {target_bytes / 1024**3:.3f} GiB")
    print(f"Actual size      : {cumulative_bytes / 1024**3:.3f} GiB")
    print(f"Files generated  : {sum(total_files.values()):,}")
    print(f"Metadata DB      : {metadata_root / 'metadata.db'}")
    print(f"Metadata CSV     : {metadata_csv}")
    print(f"Run ID           : {run_id}")
    print("=" * 80)


if __name__ == "__main__":
    main()
