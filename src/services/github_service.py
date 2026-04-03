import time
from typing import Iterator
import requests

from models import Repository, PullRequest, File
from services.csv_service import CsvService

csvService = CsvService()

class GithubService:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def _safe_request(self, url: str, verb: str, params=None, json=None) -> requests.Response:
        while True:
            r = requests.request(verb, url, headers=self.headers, params=params, json=json)
    
            if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                sleep_for = max(reset - time.time(), 0) + 5
                print(f"[RateLimit] sleeping {sleep_for:.0f}s until reset...")
                time.sleep(sleep_for)
                continue
            elif r.status_code in (500, 502, 503, 504):
                print(f"[ServerError] {r.status_code}, retrying in 10s...")
                time.sleep(10)
                continue
            elif r.status_code != 200:
                print(f"[Error] HTTP {r.status_code} for {url} | params={params}")
                raise Exception(f"HTTP {r.status_code} Error")
            return r

    def get_repository(self, full_name: str) -> Repository | None:
        if full_name.strip() == "":
            return None
                
        url = f"https://api.github.com/graphql"

        query = """
            query($owner: String!, $name: String!) {
                repository(owner: $owner, name: $name) {
                    nameWithOwner
                    stargazerCount
                    forkCount
                    watchers {
                    totalCount
                    }
                }
            }
        """
        
        try:
            owner, repo = full_name.split("/")
            
            variables = {
                "owner": owner,
                "name": repo
            }

            payload = {
                "query": query,
                "variables": variables
            }

            response = self._safe_request(url, verb="post", json=payload)
        except Exception as e:
            csvService.write_error_log(f"Error fetching repository {full_name} : {str(e)}")
            return None

        if response is None or not response.json():
            return None
        
        if 'errors' in response.json():
            csvService.write_error_log(f"Error in GraphQL response for repository {full_name}: {response.json()['errors']}")
            return None
        
        return Repository(response.json()['data']['repository'])

    def get_pull_requests(self, repo: Repository, state: str = "all", per_page: int = 100, page: int = 1) -> Iterator[PullRequest]:
        url = f"https://api.github.com/repos/{repo.full_name}/pulls"

        while True:
            params = {
                "state": state,
                "per_page": per_page,
                "page": page
            }

            try:
                response = self._safe_request(url, verb="get", params=params)
            except Exception:
                csvService.write_error_log(f"Error fetching pull requests for repo {repo.full_name} with params {params}")
                break

            if response is None or not response.json() or type(response.json()) is not list:
                break
            
            pr_list = response.json()

            for pr_data in pr_list:
                yield PullRequest(pr_data)

            page += 1

    def get_files(self, pr: PullRequest, per_page: int = 100, page: int = 1) -> Iterator[File]:
        url = f"https://api.github.com/repos/{pr.base.repo.full_name}/pulls/{pr.number}/files"

        while True:
            params = {
                "per_page": per_page,
                "page": page
            }

            try:
                response = self._safe_request(url, verb="get", params=params)
            except Exception:
                csvService.write_error_log(f"Error fetching pull requests for repo {pr.base.repo.full_name} with params {params}")
                break

            if response is None or type(response.json()) is not list:
                break
            
            file_list = response.json()

            if not file_list:
                break

            for file_data in file_list:
                yield File(file_data)

            page += 1