import logging
import shutil
import datetime
import os


def init_logger(log_file="foodshare.log"):
    # app events go to foodshare.log with time and level (no client names in here, NFR-05)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=log_file,
        filemode="a",
    )
    print(f"Logging configured. Outputting to {log_file}")


def backup_data(data_path="data/foodshare.json", backup_dir="data/backups"):
    # daily backup copy of the data file (NFR-12)
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filepath = os.path.join(backup_dir, f"foodshare_backup_{timestamp}.json")

    try:
        shutil.copy(data_path, backup_filepath)
        logging.info(f"Data successfully backed up to {backup_filepath}")
        return True
    except Exception as e:
        logging.error(f"Failed to create backup: {e}")
        return False
