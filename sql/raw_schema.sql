CREATE SCHEMA IF NOT EXISTS ecommerce_raw;

CREATE TABLE ecommerce_raw.raw_geography (
    geography_id       BIGSERIAL PRIMARY KEY,

    region_name        VARCHAR(100),
    sub_region_name    VARCHAR(100),

    country_name       VARCHAR(150),
    country_code       VARCHAR(3),

    currency_code      VARCHAR(10),
    currency_name      VARCHAR(100),
    currency_symbol    VARCHAR(10),

    timezone           VARCHAR(100),

    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_currencies (
    currency_code       VARCHAR(10) PRIMARY KEY,

    currency_name       VARCHAR(100),

    currency_symbol     VARCHAR(20),

    decimal_places      INTEGER,

    currency_type       VARCHAR(50),

    active_flag         BOOLEAN DEFAULT TRUE,

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_exchange_rates (
    exchange_rate_id       BIGSERIAL PRIMARY KEY,

    rate_date              DATE NOT NULL,

    base_currency          VARCHAR(10) NOT NULL,

    target_currency        VARCHAR(10) NOT NULL,

    exchange_rate          NUMERIC(20,10) NOT NULL,

    rate_source            VARCHAR(100),

    rate_type              VARCHAR(50),

    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_customers (
    customer_record_id       BIGSERIAL PRIMARY KEY,

    customer_id              VARCHAR(100),

    first_name               VARCHAR(100),
    last_name                VARCHAR(100),

    gender                   VARCHAR(30),

    date_of_birth            DATE,
    age                      INTEGER,
    age_group                VARCHAR(30),

    email                    VARCHAR(255),

    country_name             VARCHAR(150),
    country_code             VARCHAR(3),

    region_name              VARCHAR(100),
    sub_region_name          VARCHAR(100),

    city                     VARCHAR(150),
    state_province           VARCHAR(150),
    postal_code              VARCHAR(30),

    currency_code            VARCHAR(10),

    customer_segment         VARCHAR(100),

    acquisition_channel      VARCHAR(100),

    registration_date        DATE,

    customer_status          VARCHAR(50),

    marketing_opt_in        BOOLEAN,

    effective_from           TIMESTAMP,
    effective_to             TIMESTAMP,

    is_current               BOOLEAN DEFAULT TRUE,

    source_system            VARCHAR(100),

    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_sellers (
    seller_record_id       BIGSERIAL PRIMARY KEY,

    seller_id              VARCHAR(100),

    seller_name            VARCHAR(255),

    seller_type            VARCHAR(100),

    country_name           VARCHAR(150),
    country_code           VARCHAR(3),

    region_name            VARCHAR(100),

    seller_rating          NUMERIC(5,2),

    seller_status          VARCHAR(50),

    fulfillment_type       VARCHAR(100),

    seller_join_date       DATE,

    effective_from         TIMESTAMP,
    effective_to           TIMESTAMP,

    is_current             BOOLEAN DEFAULT TRUE,

    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_products (
    product_record_id       BIGSERIAL PRIMARY KEY,

    product_id              VARCHAR(100),

    parent_product_id       VARCHAR(100),

    product_title           TEXT,

    brand                   VARCHAR(255),

    category_level_1        VARCHAR(255),
    category_level_2        VARCHAR(255),
    category_level_3        VARCHAR(255),
    category_level_4        VARCHAR(255),

    product_type            VARCHAR(150),

    seller_id               VARCHAR(100),

    country_of_sale         VARCHAR(150),
    country_code            VARCHAR(3),

    local_currency          VARCHAR(10),

    base_price_local        NUMERIC(20,2),

    cost_local              NUMERIC(20,2),

    discount_percentage     NUMERIC(10,2),

    tax_percentage          NUMERIC(10,2),

    product_rating         NUMERIC(5,2),

    review_count            INTEGER,

    product_status          VARCHAR(50),

    stock_quantity          INTEGER,

    product_launch_date    DATE,

    effective_from         TIMESTAMP,
    effective_to            TIMESTAMP,

    is_current              BOOLEAN DEFAULT TRUE,

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_sessions (
    session_record_id       BIGSERIAL PRIMARY KEY,

    session_id              VARCHAR(150),

    customer_id             VARCHAR(100),

    session_start           TIMESTAMP,
    session_end             TIMESTAMP,

    session_duration_seconds INTEGER,

    country_name            VARCHAR(150),
    country_code            VARCHAR(3),

    region_name             VARCHAR(100),

    currency_code           VARCHAR(10),

    platform                VARCHAR(50),

    device_type             VARCHAR(100),

    operating_system        VARCHAR(100),

    browser                 VARCHAR(100),

    traffic_source          VARCHAR(255),

    traffic_medium          VARCHAR(100),

    campaign_id             VARCHAR(150),

    landing_page            TEXT,

    exit_page               TEXT,

    is_new_customer         BOOLEAN,

    is_new_session          BOOLEAN,

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_events (
    event_record_id          BIGSERIAL PRIMARY KEY,

    event_id                 VARCHAR(150),

    event_timestamp          TIMESTAMP NOT NULL,

    session_id               VARCHAR(150),

    customer_id              VARCHAR(100),

    product_id               VARCHAR(100),

    order_id                 VARCHAR(100),

    event_name               VARCHAR(100),

    event_category           VARCHAR(100),

    page_name                VARCHAR(255),

    page_url                 TEXT,

    referrer_url             TEXT,

    search_query             TEXT,

    product_position         INTEGER,

    quantity                 INTEGER,

    unit_price_local         NUMERIC(20,2),

    event_value_local        NUMERIC(20,2),

    local_currency            VARCHAR(10),

    country_name             VARCHAR(150),
    country_code             VARCHAR(3),

    region_name              VARCHAR(100),

    device_type              VARCHAR(100),

    platform                 VARCHAR(50),

    operating_system         VARCHAR(100),

    browser                  VARCHAR(100),

    traffic_source           VARCHAR(255),

    traffic_medium           VARCHAR(100),

    campaign_id              VARCHAR(150),

    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_orders (
    order_record_id          BIGSERIAL PRIMARY KEY,

    order_id                 VARCHAR(100),

    customer_id              VARCHAR(100),

    session_id               VARCHAR(150),

    order_timestamp          TIMESTAMP,

    order_status             VARCHAR(100),

    country_name             VARCHAR(150),
    country_code             VARCHAR(3),

    region_name              VARCHAR(100),

    local_currency           VARCHAR(10),

    subtotal_local           NUMERIC(20,2),

    discount_local           NUMERIC(20,2),

    shipping_local           NUMERIC(20,2),

    tax_local                NUMERIC(20,2),

    total_amount_local       NUMERIC(20,2),

    payment_method           VARCHAR(100),

    shipping_method          VARCHAR(100),

    warehouse_id             VARCHAR(100),

    estimated_delivery_date  DATE,

    actual_delivery_date     DATE,

    cancellation_date        TIMESTAMP,

    return_flag              BOOLEAN DEFAULT FALSE,

    refund_amount_local      NUMERIC(20,2),

    source_system            VARCHAR(100),

    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_order_items (
    order_item_record_id      BIGSERIAL PRIMARY KEY,

    order_item_id             VARCHAR(100),

    order_id                  VARCHAR(100),

    product_id                VARCHAR(100),

    seller_id                 VARCHAR(100),

    quantity                  INTEGER,

    unit_price_local          NUMERIC(20,2),

    discount_local            NUMERIC(20,2),

    tax_local                 NUMERIC(20,2),

    item_total_local          NUMERIC(20,2),

    local_currency             VARCHAR(10),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    fulfillment_type          VARCHAR(100),
	return_flag               BOOLEAN DEFAULT FALSE,

    return_quantity           INTEGER,

    refund_amount_local       NUMERIC(20,2),

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
	CREATE TABLE ecommerce_raw.raw_payments (
    payment_record_id         BIGSERIAL PRIMARY KEY,

    payment_id                VARCHAR(100),

    order_id                  VARCHAR(100),

    customer_id               VARCHAR(100),

    payment_timestamp         TIMESTAMP,

    payment_method            VARCHAR(100),

    payment_status            VARCHAR(100),

    payment_amount_local      NUMERIC(20,2),

    local_currency            VARCHAR(10),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    failure_reason            TEXT,

    refund_flag               BOOLEAN DEFAULT FALSE,

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_shipments (
    shipment_record_id        BIGSERIAL PRIMARY KEY,

    shipment_id               VARCHAR(100),

    order_id                  VARCHAR(100),

    warehouse_id              VARCHAR(100),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    carrier                   VARCHAR(150),

    shipping_method           VARCHAR(100),

    shipment_status           VARCHAR(100),

    shipped_timestamp         TIMESTAMP,

    estimated_delivery_date   DATE,

    actual_delivery_timestamp TIMESTAMP,

    delivery_attempts         INTEGER,

    delivery_country          VARCHAR(150),

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_reviews (
    review_record_id          BIGSERIAL PRIMARY KEY,

    review_id                 VARCHAR(100),

    customer_id               VARCHAR(100),

    product_id                VARCHAR(100),

    order_id                  VARCHAR(100),

    rating                    INTEGER,

    review_title              TEXT,

    review_text               TEXT,

    verified_purchase         BOOLEAN,

    helpful_votes             INTEGER,

    review_timestamp          TIMESTAMP,

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    sentiment                 VARCHAR(50),

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_inventory (
    inventory_record_id       BIGSERIAL PRIMARY KEY,

    inventory_id              VARCHAR(100),

    product_id                VARCHAR(100),

    warehouse_id              VARCHAR(100),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    inventory_date            DATE,

    stock_available           INTEGER,

    stock_reserved            INTEGER,

    stock_damaged             INTEGER,

    reorder_level             INTEGER,

    units_sold                INTEGER,

    units_returned            INTEGER,

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_campaigns (
    campaign_record_id        BIGSERIAL PRIMARY KEY,

    campaign_id               VARCHAR(150),

    campaign_name             VARCHAR(255),

    campaign_type             VARCHAR(100),

    channel                   VARCHAR(100),

    source                    VARCHAR(255),

    medium                    VARCHAR(100),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    start_date                DATE,

    end_date                  DATE,

    budget_local              NUMERIC(20,2),

    spend_local               NUMERIC(20,2),

    local_currency            VARCHAR(10),

    impressions               BIGINT,

    clicks                    BIGINT,

    conversions               BIGINT,

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,


    return_flag               BOOLEAN DEFAULT FALSE,

    return_quantity           INTEGER,

    refund_amount_local       NUMERIC(20,2),

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_payments (
    payment_record_id         BIGSERIAL PRIMARY KEY,

    payment_id                VARCHAR(100),

    order_id                  VARCHAR(100),

    customer_id               VARCHAR(100),

    payment_timestamp         TIMESTAMP,

    payment_method            VARCHAR(100),

    payment_status            VARCHAR(100),

    payment_amount_local      NUMERIC(20,2),

    local_currency            VARCHAR(10),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    failure_reason            TEXT,

    refund_flag               BOOLEAN DEFAULT FALSE,

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_shipments (
    shipment_record_id        BIGSERIAL PRIMARY KEY,

    shipment_id               VARCHAR(100),

    order_id                  VARCHAR(100),

    warehouse_id              VARCHAR(100),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    carrier                   VARCHAR(150),

    shipping_method           VARCHAR(100),

    shipment_status           VARCHAR(100),

    shipped_timestamp         TIMESTAMP,

    estimated_delivery_date   DATE,

    actual_delivery_timestamp TIMESTAMP,

    delivery_attempts         INTEGER,

    delivery_country          VARCHAR(150),

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_reviews (
    review_record_id          BIGSERIAL PRIMARY KEY,

    review_id                 VARCHAR(100),

    customer_id               VARCHAR(100),

    product_id                VARCHAR(100),

    order_id                  VARCHAR(100),

    rating                    INTEGER,

    review_title              TEXT,

    review_text               TEXT,

    verified_purchase         BOOLEAN,

    helpful_votes             INTEGER,

    review_timestamp          TIMESTAMP,

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    sentiment                 VARCHAR(50),

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_inventory (
    inventory_record_id       BIGSERIAL PRIMARY KEY,

    inventory_id              VARCHAR(100),

    product_id                VARCHAR(100),

    warehouse_id              VARCHAR(100),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    inventory_date            DATE,

    stock_available           INTEGER,

    stock_reserved            INTEGER,

    stock_damaged             INTEGER,

    reorder_level             INTEGER,

    units_sold                INTEGER,

    units_returned            INTEGER,

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ecommerce_raw.raw_campaigns (
    campaign_record_id        BIGSERIAL PRIMARY KEY,

    campaign_id               VARCHAR(150),

    campaign_name             VARCHAR(255),

    campaign_type             VARCHAR(100),

    channel                   VARCHAR(100),

    source                    VARCHAR(255),

    medium                    VARCHAR(100),

    country_code              VARCHAR(3),

    region_name               VARCHAR(100),

    start_date                DATE,

    end_date                  DATE,

    budget_local              NUMERIC(20,2),

    spend_local               NUMERIC(20,2),

    local_currency            VARCHAR(10),

    impressions               BIGINT,

    clicks                    BIGINT,

    conversions               BIGINT,

    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE ecommerce_raw.raw_geography       ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_currencies      ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_exchange_rates  ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_customers       ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_sellers         ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_products        ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_sessions        ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_events          ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_orders          ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_order_items     ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_payments        ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_shipments       ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_reviews         ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_inventory       ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
ALTER TABLE ecommerce_raw.raw_campaigns       ADD COLUMN IF NOT EXISTS created_by VARCHAR(150);
