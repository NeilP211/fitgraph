-- FitGraph database schema
-- Idempotent: safe to run multiple times (IF NOT EXISTS throughout)

CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------------ users ---
CREATE TABLE IF NOT EXISTS users (
    id         serial PRIMARY KEY,
    email      text UNIQUE NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- ------------------------------------------------------------------ items ---
CREATE TABLE IF NOT EXISTS items (
    id                text PRIMARY KEY,
    title             text,
    description       text,
    semantic_category text,
    tags              text[],
    search_doc        tsvector,
    image_path        text,
    created_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS items_search_doc_gin ON items USING GIN (search_doc);

-- -------------------------------------------------------- item_embeddings ---
CREATE TABLE IF NOT EXISTS item_embeddings (
    item_id       text PRIMARY KEY REFERENCES items (id) ON DELETE CASCADE,
    embedding     vector(256),
    model_version text
);

CREATE INDEX IF NOT EXISTS item_embeddings_hnsw
    ON item_embeddings
    USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------- outfits ---
CREATE TABLE IF NOT EXISTS outfits (
    id         serial PRIMARY KEY,
    user_id    int REFERENCES users (id),
    name       text,
    created_at timestamptz DEFAULT now()
);

-- ------------------------------------------------------------- outfit_items ---
CREATE TABLE IF NOT EXISTS outfit_items (
    outfit_id int  REFERENCES outfits (id) ON DELETE CASCADE,
    item_id   text REFERENCES items (id),
    position  int,
    PRIMARY KEY (outfit_id, item_id)
);

-- --------------------------------------------------------------- ratings ---
CREATE TABLE IF NOT EXISTS ratings (
    id               serial PRIMARY KEY,
    user_id          int REFERENCES users (id),
    query_item_id    text,
    suggested_item_id text,
    rating           int,
    model_version    text,
    created_at       timestamptz DEFAULT now()
);

-- --------------------------------------------------------- model_versions ---
CREATE TABLE IF NOT EXISTS model_versions (
    version    text PRIMARY KEY,
    path       text,
    val_auc    double precision,
    is_active  boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);
