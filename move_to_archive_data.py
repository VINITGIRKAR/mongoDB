from pymongo import MongoClient
from datetime import datetime, timedelta
import configparser
import os
import traceback


def archive_old_data():
    try:
        # Load config file path from environment variable or use default
        config_path = os.getenv("NEXTWAVE_CONFIG_PATH", "C:/NextWave/config.ini")

        if not os.path.exists(config_path):
            raise ValueError(f"Config file not found at: {config_path}")
            #raise ValueError("Config File Not Found at:", config_path)

        # Load configuration
        config = configparser.ConfigParser()
        config.read(config_path)

        cron_type = "ARCHIVE_MONGO_DATA"

        # Read config values
        datalake_type = config.get("DATA_LAKE", "type")
        datalake_host = config.get("DATA_LAKE", "host")
        datalake_port = config.get("DATA_LAKE", "port")
        datalake_db = config.get("DATA_LAKE", "db")
        source_coll = config.get(cron_type, "source_collection")
        destination_coll = config.get(cron_type, "destination_collection")
        time_diff = int(config.get(cron_type, "time_period"))

        # Connect to MongoDB
        with MongoClient(
            f"{datalake_type}://{datalake_host}:{datalake_port}/",
            connectTimeoutMS=10000,
            serverSelectionTimeoutMS=10000,
        ) as mongo_client:
            db_client = mongo_client[datalake_db]

            if source_coll not in db_client.list_collection_names():
                raise ValueError(f"Source collection {source_coll} does not exist")

            source_collection = db_client[source_coll]
            archive_collection = db_client[destination_coll]

            threshold_date = datetime.utcnow() - timedelta(days=time_diff)
            threshold_date_str = threshold_date.date().strftime("%Y-%m-%d")

            print(f"Threshold date for archiving: {threshold_date_str}")

            batch_size = 1000
            total_archived = 0

            while True:
                cursor = source_collection.find(
                    {"batch_date": {"$lte": threshold_date_str}}
                ).limit(batch_size)

                batch = list(cursor)
                if not batch:
                    break

                try:
                    archive_collection.insert_many(batch, ordered=False)
                except Exception as e:
                    if "duplicate key error" not in str(e).lower():
                        raise
                    print("Skipped duplicate documents during archiving")

                # Delete the archived documents from the source collection
                # ids_to_delete = [doc["_id"] for doc in batch]
                # source_collection.delete_many({"_id": {"$in": ids_to_delete}})

                # Uncomment the following line if you want to keep the documents in the source collection
                # instead of deleting them after archiving.
                ids_not_to_delete = [doc["_id"] for doc in batch]
                source_collection.insert_many({"_id": {"$in": ids_not_to_delete}})

                total_archived += len(batch)
                print(f"Archived {len(batch)} documents in this batch...")

            if total_archived > 0:
                print(f" Successfully archived {total_archived} documents.")
            else:
                print(" No documents found to archive.")

    except Exception as e:
        error_msg = f" Error in archive_old_data: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)


if __name__ == "__main__":
    archive_old_data()
