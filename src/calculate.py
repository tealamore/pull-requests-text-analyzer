import os
from typing import Any, Dict

from models import Repository, PullRequest
from services import GithubService, CsvService, MongoService, SqlService

GITHUB_TOKEN = str(os.getenv("GITHUB_AUTH_TOKEN") or "").strip()
githubService = GithubService(GITHUB_TOKEN)
csvService = CsvService()
mongoService: MongoService | None = None
sqlService: SqlService | None = None

def as_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def csv_repo_name_to_full_name(repo_name: str) -> str:
    if "/" in repo_name:
        return repo_name

    parts = repo_name.split("_", 1)
    if len(parts) != 2:
        return repo_name

    return f"{parts[0]}/{parts[1]}"

def get_pr_type(touches_test_files: bool, touches_production_files: bool) -> str:
    if touches_test_files and touches_production_files:
        return "test_including"
    if touches_production_files:
        return "test_excluding"
    return "no_production_code"

def save_pull_request_data(repo: Repository, pr: PullRequest, pr_type: str) -> None:
    global mongoService, sqlService

    try:
        if mongoService is None:
            mongoService = MongoService()
        if sqlService is None:
            sqlService = SqlService()

        comments = githubService.get_pull_request_comments(pr)
        commit_messages = githubService.get_pull_request_commit_messages(pr)

        github_pull_request_id = pr.number if pr.number is not None else pr.id
        if github_pull_request_id is None:
            print(
                f"Skipping PR with missing GitHub id in repo {repo.full_name}"
            )
            return

        sqlService.save_pull_request_mapping(
            repository_name=repo.get_sanitized_name(),
            github_pull_request_id=int(github_pull_request_id),
            pr_type=pr_type,
        )

        mongoService.save({
            'repo_name': repo.get_sanitized_name(),
            'internal_pull_request_id': github_pull_request_id,
            'pull_request_id': github_pull_request_id,
            'title': pr.title,
            'description': pr.body,
            'comments': comments,
            'commit_messages': commit_messages,
        })
    except Exception as e:
        print(f"Error saving PR data for PR #{pr.number} in repo {repo.full_name}: {str(e)}")


def process_prs_csv(csv_path: str) -> None:
    rows = csvService.read_csv(csv_path)

    repo_cache: Dict[str, Repository | None] = {}

    for row in rows:
        repo_name = str(row.get("repo_name", "")).strip()
        pull_request_number_raw = str(row.get("number", "")).strip()

        if repo_name == "" or pull_request_number_raw == "":
            print(f"Skipping malformed CSV row: {row}")
            continue

        try:
            pull_request_number = int(pull_request_number_raw)
        except ValueError:
            print(f"Skipping row with invalid PR number: {row}")
            continue

        full_repo_name = csv_repo_name_to_full_name(repo_name)

        if full_repo_name not in repo_cache:
            print(f"Loading repository data for {full_repo_name} from GitHub...")
            repo_cache[full_repo_name] = githubService.get_repository(full_repo_name)

        repo = repo_cache[full_repo_name]
        if repo is None:
            print(f"Could not load repository {full_repo_name}")
            continue

        pr = githubService.get_pull_request(repo, pull_request_number)
        if pr is None:
            print(f"Could not load pull request #{pull_request_number} for {full_repo_name}")
            continue

        touches_test_files = as_bool(row.get("touches_test_files"))
        touches_production_files = as_bool(row.get("touches_production_files"))
        pr_type = get_pr_type(touches_test_files, touches_production_files)

        save_pull_request_data(repo, pr, pr_type)
        print(f"Processed PR #{pull_request_number} for {full_repo_name}: type={pr_type}")

if __name__ == "__main__":
    csv_path = os.getenv("PRS_CSV_PATH", "src/data/prs.csv")
    skip = bool(os.getenv("SHOULD_SKIP", False))
    if not skip:
        process_prs_csv(csv_path)
        print("Done processing PRs from CSV.")
    else:
        print("Skipping execution.")