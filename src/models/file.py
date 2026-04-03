from typing import Any


class File:
    production_file_extensions = ['.py', '.js', '.java', '.ts', '.tsx', '.jsx', '.vue']

    def __init__(self, data: dict[str, Any]):
        self.filename = data.get("filename")

    def is_test_file(self) -> bool:
        lower_filename = self.filename.lower()
        return 'test' in lower_filename or 'spec' in lower_filename
    
    def is_production_file(self) -> bool:
        return any(self.filename.endswith(ext) for ext in self.production_file_extensions) \
                and not self.is_test_file()