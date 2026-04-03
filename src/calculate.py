import datetime
import os
import re
from typing import Any, Dict, Iterator

from dotenv import load_dotenv
from datetime import datetime, timezone
from models import Repository, PullRequest, File
from services import GithubService, CsvService

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_AUTH_TOKEN")
githubService = GithubService(GITHUB_TOKEN)
csvService = CsvService()

def convert_to_datetime(date: str) -> datetime:
    if date.endswith('Z'):
        parsed = datetime.fromisoformat(date.replace('Z', '+00:00'))
    else:
        parsed = datetime.fromisoformat(date)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed

def calculate_test_engagement_ratio(merged_prs: Iterator[PullRequest], info: Dict[str, Any]):
    count_touches_tests = 0
    count_touches_production = 0

    for pr in merged_prs:
        if pr.get('touches_test_files') == 'True' and pr.get('touches_production_files') == 'True':
            count_touches_tests += 1
        if pr.get('touches_production_files') == 'True':
            count_touches_production += 1

    ter = (count_touches_tests / count_touches_production) if count_touches_production > 0 else None

    info['test_engagement_ratio'] = ter
    info['count_touches_tests'] = count_touches_tests
    info['count_touches_production'] = count_touches_production

def which_files_were_touched(pr: PullRequest) -> Dict[str, bool]:
    touches_test_files = False
    touches_production_files = False

    try:
        files: list[File] = githubService.get_files(pr)

        for f in files:
            if f.is_test_file():
                touches_test_files = True
            elif f.is_production_file():
                touches_production_files = True

            if touches_test_files and touches_production_files:
                break
    except Exception as e:
        csvService.write_error_log(f"Error processing PR #{pr.number} in repo {pr.base.repo.full_name}: {str(e)}")

    return {'touches_test_files': touches_test_files, 'touches_production_files': touches_production_files}

def get_merged_prs(repo: Repository, 
                   start_date: datetime = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), 
                   end_date: datetime = datetime(2025, 12, 1, 0, 0, tzinfo=timezone.utc)):

    try:
        prs: Iterator[PullRequest] = githubService.get_pull_requests(repo, state='closed')
    except Exception as e:
        csvService.write_error_log(f"Error fetching PRs for repo {repo.full_name}: {str(e)}")
        return

    for pr in prs:
        try:
            # Already been processed
            # Not merged
            if pr.merge_commit_sha is None:
                data = {
                        'repo_name': repo.get_sanitized_name(),
                        'number': pr.number,
                        'touches_test_files': False,
                        'touches_production_files': False,
                        'notes': 'not merged'
                        }
                # TODO: write to sql
                # csvService.save_csv_row(checkpoint_path, data)
                continue

            if pr.merged_at is None:
                merged_at = convert_to_datetime(pr.closed_at)
            else:
                merged_at = convert_to_datetime(pr.merged_at)
            
            # Before start date
            if merged_at < start_date:
                break
            # Within date range
            elif start_date <= merged_at <= end_date:
                results = which_files_were_touched(pr)
                data = {
                        'repo_name': repo.get_sanitized_name(),
                        'number': pr.number,
                        'touches_test_files': results['touches_test_files'],
                        'touches_production_files': results['touches_production_files'],
                        'notes': None
                        }
                # TODO: write to sql
                # csvService.save_csv_row(checkpoint_path, data)
        except Exception as e:
            csvService.write_error_log(f"Error processing PR #{pr.number} in repo {repo.full_name}: {str(e)}")
    
def get_repo_full_name(url: str) -> str:
    match = re.search(r'github\.com/([^/?]+/[^/?]+)', url)
    if match:
        return match.group(1)
    return ""

if __name__ == "__main__":
    repos = ['']
    
    for repo_info in repos:
        repo_name = get_repo_full_name(repo_info['GitHub'])
        repo = githubService.get_repository(repo_name)

        if repo is None:
            continue

        info = repo.to_dict()

        get_merged_prs(repo)
            
        merged_prs = []

        calculate_test_engagement_ratio(merged_prs, info)

        csvService.save_csv_row('output.csv', info)

        print(f"Processed repo: {repo_name} with score: {info['test_engagement_ratio']}.")

    print("Done processing all repositories.")