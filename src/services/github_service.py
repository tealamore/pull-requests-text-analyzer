import time
from typing import Any, Dict, Iterator, List
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
            print(f"Error fetching repository {full_name} : {str(e)}")
            return None

        if response is None or not response.json():
            return None
        
        if 'errors' in response.json():
            print(f"Error in GraphQL response for repository {full_name}: {response.json()['errors']}")
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
                print(f"Error fetching pull requests for repo {repo.full_name} with params {params}")
                break

            if response is None or not response.json() or type(response.json()) is not list:
                break
            
            pr_list = response.json()

            for pr_data in pr_list:
                yield PullRequest(pr_data)

            page += 1

    def get_pull_request(self, repo: Repository, number: int) -> PullRequest | None:
        url = f"https://api.github.com/repos/{repo.full_name}/pulls/{number}"

        try:
            response = self._safe_request(url, verb="get")
        except Exception:
            print(
                f"Error fetching pull request #{number} for repo {repo.full_name}"
            )
            return None

        if response is None or type(response.json()) is not dict:
            return None

        return PullRequest(response.json())

    def _get_repo_full_name_from_pr(self, pr: PullRequest) -> str:
        if pr.base is not None and pr.base.repo is not None and pr.base.repo.full_name:
            return pr.base.repo.full_name
        return ""

    def get_files(self, pr: PullRequest, per_page: int = 100, page: int = 1) -> Iterator[File]:
        repo_full_name = self._get_repo_full_name_from_pr(pr)
        if repo_full_name == "":
            return

        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr.number}/files"

        while True:
            params = {
                "per_page": per_page,
                "page": page
            }

            try:
                response = self._safe_request(url, verb="get", params=params)
            except Exception:
                print(f"Error fetching pull requests for repo {repo_full_name} with params {params}")
                break

            if response is None or type(response.json()) is not list:
                break
            
            file_list = response.json()

            if not file_list:
                break

            for file_data in file_list:
                yield File(file_data)

            page += 1

    def _get_paginated_json(self, url: str, params: Dict[str, Any] | None = None) -> Iterator[Dict[str, Any]]:
        page = 1

        while True:
            request_params = dict(params or {})
            request_params["per_page"] = request_params.get("per_page", 100)
            request_params["page"] = page

            response = self._safe_request(url, verb="get", params=request_params)

            if response is None or type(response.json()) is not list:
                break

            items = response.json()
            if not items:
                break

            for item in items:
                yield item

            page += 1

    def get_pull_request_comments(self, pr: PullRequest) -> List[str]:
        repo_full_name = self._get_repo_full_name_from_pr(pr)
        if repo_full_name == "":
            return []

        review_comments_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr.number}/comments"

        comments: List[str] = []

        try:
            for comment in self._get_paginated_json(review_comments_url):
                body = comment.get("body")
                if body:
                    comments.append(body)
        except Exception:
            print(
                f"Error fetching comments for PR #{pr.number} in repo {repo_full_name}"
            )

        return comments

    def get_pull_request_commit_messages(self, pr: PullRequest) -> List[str]:
        repo_full_name = self._get_repo_full_name_from_pr(pr)
        if repo_full_name == "":
            return []

        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr.number}/commits"

        messages: List[str] = []

        try:
            for commit in self._get_paginated_json(url):
                commit_data = commit.get("commit", {})
                message = commit_data.get("message")
                if message:
                    messages.append(message)
        except Exception:
            print(
                f"Error fetching commit messages for PR #{pr.number} in repo {repo_full_name}"
            )

        return messages