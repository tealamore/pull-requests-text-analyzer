import os
from typing import Any, Dict, Iterator
import csv

class CsvService:
    def read_csv(self, path: str) -> Iterator[Dict[str, Any]]:
        if not os.path.exists(path):
            return 

        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row