-- E-commerce schema, designed to create realistic ambiguity:
--   - "best customer" -> undefined by what metric (revenue? order count? recency?)
--   - "recent orders"  -> undefined time range
--   - "name"           -> exists on both customers and products (column collision)
--   - "top category"   -> undefined by revenue vs. units sold

CREATE TABLE customers (
    customer_id     SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT UNIQUE NOT NULL,
    signup_date     DATE NOT NULL,
    region          TEXT
);

CREATE TABLE categories (
    category_id     SERIAL PRIMARY KEY,
    name            TEXT NOT NULL
);

CREATE TABLE products (
    product_id      SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    category_id     INTEGER REFERENCES categories(category_id),
    price           NUMERIC(10, 2) NOT NULL,
    cost            NUMERIC(10, 2) NOT NULL
);

CREATE TABLE orders (
    order_id        SERIAL PRIMARY KEY,
    customer_id     INTEGER REFERENCES customers(customer_id),
    order_date      TIMESTAMP NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled', 'returned'))
);

CREATE TABLE order_items (
    order_item_id   SERIAL PRIMARY KEY,
    order_id        INTEGER REFERENCES orders(order_id),
    product_id      INTEGER REFERENCES products(product_id),
    quantity        INTEGER NOT NULL,
    unit_price      NUMERIC(10, 2) NOT NULL
);

-- Helpful indexes for query patterns you'll actually hit
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_products_category ON products(category_id);
