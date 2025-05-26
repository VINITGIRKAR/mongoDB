Perfect — here's a **combined and production-ready script** that:

### ✅ Handles both:

1. **Archiving old data** from a source collection to an archive collection.
2. **Deleting old archived data** based on a retention period.

---

## 🔧 Features:

* Modular functions: `archive_old_data()` and `delete_old_archived_data()`
* Configuration-driven via `config.ini`
* Uses `logging` (not `print`)
* Supports optional `dry_run` mode for archiving

---

## 📝 Combined Script: `archive_and_delete_mongo_data.py`

```python
import os
import logging
import configparser
from datetime import datetime, timedelta
from pymongo import MongoClient
import traceback

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def load_config(config_path=None):
    config_path = config_path or os.getenv("NEXTWAVE_CONFIG_PATH", "C:/NextWave/config.ini")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at: {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path)
    return config

def connect_to_mongo(datalake_type, host, port, db_name):
    client = MongoClient(
        f"{datalake_type}://{host}:{port}/",
        connectTimeoutMS=10000,
        serverSelectionTimeoutMS=10000
    )
    return client[db_name]

def archive_old_data(config):
    try:
        cron_type = "ARCHIVE_MONGO_DATA"
        datalake_type = config.get("DATA_LAKE", "type")
        datalake_host = config.get("DATA_LAKE", "host")
        datalake_port = config.get("DATA_LAKE", "port")
        datalake_db = config.get("DATA_LAKE", "db")

        source_coll = config.get(cron_type, "source_collection")
        destination_coll = config.get(cron_type, "destination_collection")
        time_diff = int(config.get(cron_type, "time_period"))
        dry_run = config.getboolean(cron_type, "dry_run", fallback=False)

        db = connect_to_mongo(datalake_type, datalake_host, datalake_port, datalake_db)

        if source_coll not in db.list_collection_names():
            logging.warning(f"Source collection '{source_coll}' does not exist. Skipping archiving.")
            return

        source_collection = db[source_coll]
        archive_collection = db[destination_coll]

        threshold_date = datetime.utcnow() - timedelta(days=time_diff)
        logging.info(f"Archiving documents older than: {threshold_date.isoformat()}")

        batch_size = 1000
        total_archived = 0

        while True:
            cursor = source_collection.find(
                {"batch_date": {"$lte": threshold_date}}
            ).limit(batch_size)

            batch = list(cursor)
            if not batch:
                break

            try:
                archive_collection.insert_many(batch, ordered=False)
            except Exception as e:
                if "duplicate key error" not in str(e).lower():
                    raise
                logging.warning("Skipped duplicates during archiving")

            ids_to_delete = [doc["_id"] for doc in batch]
            if not dry_run:
                source_collection.delete_many({"_id": {"$in": ids_to_delete}})
            else:
                logging.info(f"Dry-run: Skipped deleting {len(ids_to_delete)} documents")

            total_archived += len(batch)
            logging.info(f"Archived {len(batch)} documents this batch...")

        logging.info(f"Archived total of {total_archived} documents.")

    except Exception:
        logging.error("Error in archive_old_data", exc_info=True)

def delete_old_archived_data(config):
    try:
        cron_type = "ARCHIVE_DELETION_MONGO_DATA"
        datalake_type = config.get("DATA_LAKE", "type")
        datalake_host = config.get("DATA_LAKE", "host")
        datalake_port = config.get("DATA_LAKE", "port")
        datalake_db = config.get("DATA_LAKE", "db")
        destination_coll = config.get(cron_type, "destination_collection")
        delete_after_days = int(config.get(cron_type, "delete_after_days", fallback="365"))

        db = connect_to_mongo(datalake_type, datalake_host, datalake_port, datalake_db)

        if destination_coll not in db.list_collection_names():
            logging.warning(f"Destination collection '{destination_coll}' does not exist. Nothing to delete.")
            return

        archive_collection = db[destination_coll]
        threshold_date = datetime.utcnow() - timedelta(days=delete_after_days)

        logging.info(f"Deleting archived documents older than: {threshold_date.isoformat()}")

        result = archive_collection.delete_many({"batch_date": {"$lte": threshold_date}})
        logging.info(f"Deleted {result.deleted_count} documents from archive")

    except Exception:
        logging.error("Error in delete_old_archived_data", exc_info=True)

if __name__ == "__main__":
    try:
        config = load_config()
        archive_old_data(config)
        delete_old_archived_data(config)
    except Exception:
        logging.error("❌ Failed to execute archiving/deletion", exc_info=True)
```

---

## 🧾 Sample `config.ini`

```ini
[DATA_LAKE]
type = mongodb
host = localhost
port = 27017
db = my_database

[ARCHIVE_MONGO_DATA]
source_collection = raw_data
destination_collection = archive_data
time_period = 30
dry_run = false

[ARCHIVE_DELETION_MONGO_DATA]
destination_collection = archive_data
delete_after_days = 365
```

---

## ✅ How to Use

Run via terminal or scheduler:

```bash
python archive_and_delete_mongo_data.py
```

Optionally set the config path:

```bash
export NEXTWAVE_CONFIG_PATH=/path/to/config.ini
```

---

Would you like me to help:

* Package this as a CLI tool (`argparse`)?
* Deploy it via cron/Task Scheduler?
* Log to a file or external service (e.g., AWS S3 or ELK stack)?
