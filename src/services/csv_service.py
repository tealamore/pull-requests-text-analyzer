import os
from datetime import datetime
from typing import Any, Dict, Iterator
import csv


class CsvService:
    def write_error_log(self, message: str) -> None:
        os.makedirs("logs", exist_ok=True)
        with open("logs/error_log.txt", "a") as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")

    def read_csv(self, path: str) -> Iterator[Dict[str, Any]]:
        if not os.path.exists(path):
            return 

        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row

    def save_csv_row(self, path: str, info: dict) -> None:
        field_names = list(info.keys())
        file_exists = os.path.isfile(path) and os.path.getsize(path) > 0
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        with open(path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=field_names)
            if not file_exists:
                writer.writeheader()
            writer.writerow(info)
