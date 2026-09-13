CREATE SCHEMA IF NOT EXISTS metadata;


CREATE TABLE IF NOT EXISTS metadata.dataset_metadata (
    dataset_id              UUID PRIMARY KEY,

    dataset_name            VARCHAR(255) NOT NULL,
    dataset_version         VARCHAR(50),

    generation_run_id       UUID,

    source_type             VARCHAR(50) DEFAULT 'synthetic',

    faker_version           VARCHAR(100),
    python_version          VARCHAR(100),

    random_seed             BIGINT,

    target_size_bytes       BIGINT,
    actual_size_bytes       BIGINT,

    start_date              DATE,
    end_date                DATE,

    total_tables            INTEGER,
    total_records           BIGINT,
    total_files             BIGINT,
    total_partitions        BIGINT,

    generation_status       VARCHAR(50),

    error_status            BOOLEAN DEFAULT FALSE,
    error_details           TEXT,

    generation_start        TIMESTAMP,
    generation_end          TIMESTAMP,

    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS metadata.generation_runs (
    generation_run_id       UUID PRIMARY KEY,

    dataset_id              UUID,

    run_number              INTEGER,

    started_at              TIMESTAMP,
    completed_at             TIMESTAMP,

    status                  VARCHAR(50),

    target_size_bytes       BIGINT,
    generated_size_bytes    BIGINT,

    total_records           BIGINT,

    error_message           TEXT,

    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS metadata.table_metadata (
    table_id                BIGSERIAL PRIMARY KEY,

    dataset_id              UUID,

    table_name              VARCHAR(255) NOT NULL,

    total_record_count      BIGINT DEFAULT 0,

    total_file_count        BIGINT DEFAULT 0,

    total_size_bytes        BIGINT DEFAULT 0,

    min_timestamp           TIMESTAMP,

    max_timestamp           TIMESTAMP,

    null_count              BIGINT DEFAULT 0,

    unique_count            BIGINT DEFAULT 0,

    generation_status       VARCHAR(50),

    validation_status       VARCHAR(50),

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(dataset_id, table_name)
);


CREATE TABLE IF NOT EXISTS metadata.column_metadata (
    column_id               BIGSERIAL PRIMARY KEY,

    table_name              VARCHAR(255),

    column_name             VARCHAR(255),

    data_type               VARCHAR(100),

    nullable                BOOLEAN,

    is_primary_key          BOOLEAN DEFAULT FALSE,

    is_foreign_key          BOOLEAN DEFAULT FALSE,

    referenced_table        VARCHAR(255),

    referenced_column       VARCHAR(255),

    generated_by            VARCHAR(255),

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS metadata.partition_metadata (
    partition_id            BIGSERIAL PRIMARY KEY,

    dataset_id              UUID,

    table_name              VARCHAR(255),

    partition_year          INTEGER,

    partition_month         INTEGER,

    file_path               TEXT,

    file_format             VARCHAR(20),

    file_size_bytes         BIGINT,

    record_count            BIGINT,

    min_timestamp           TIMESTAMP,

    max_timestamp           TIMESTAMP,

    checksum_sha256         VARCHAR(64),

    generation_status       VARCHAR(50) DEFAULT 'GENERATED',

    validation_status       VARCHAR(50) DEFAULT 'PENDING',

    upload_status           VARCHAR(50) DEFAULT 'PENDING',

    upload_started_at       TIMESTAMP,

    upload_completed_at     TIMESTAMP,

    error_message           TEXT,

    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(
        dataset_id,
        table_name,
        partition_year,
        partition_month
    )
);