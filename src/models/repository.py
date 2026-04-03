from typing import Any, Dict


class Repository:
    def __init__(self, data: Dict[str, Any]):
        self.full_name = data.get("nameWithOwner")
        self.stargazers_count = data.get("stargazerCount")
        self.forks_count = data.get("forkCount")
        self.watchers_count = data.get("watchers", {}).get("totalCount", -1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "full_name": self.full_name,
            "stargazers_count": self.stargazers_count,
            "forks_count": self.forks_count,
            "watchers_count": self.watchers_count,
        }

    def get_sanitized_name(self) -> str:
        return self.full_name.replace('/', '_')
    
    def get_checkpoint_path(self) -> str:
        return f"data/{self.get_sanitized_name()}.csv"