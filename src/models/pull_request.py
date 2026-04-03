from typing import Dict, Any


class User:
    def __init__(self, data: Dict[str, Any]):
        self.login = data.get("login")
        self.id = data.get("id")
        self.node_id = data.get("node_id")
        self.avatar_url = data.get("avatar_url")
        self.url = data.get("url")
        self.html_url = data.get("html_url")
        self.type = data.get("type")
        self.site_admin = data.get("site_admin")


class Label:
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.node_id = data.get("node_id")
        self.name = data.get("name")
        self.description = data.get("description")
        self.color = data.get("color")
        self.default = data.get("default")


class Milestone:
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.node_id = data.get("node_id")
        self.number = data.get("number")
        self.state = data.get("state")
        self.title = data.get("title")
        self.description = data.get("description")
        self.creator = User(data["creator"]) if data.get("creator") else None
        self.open_issues = data.get("open_issues")
        self.closed_issues = data.get("closed_issues")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self.closed_at = data.get("closed_at")
        self.due_on = data.get("due_on")


class License:
    def __init__(self, data: Dict[str, Any]):
        self.key = data.get("key")
        self.name = data.get("name")
        self.spdx_id = data.get("spdx_id")
        self.url = data.get("url")
        self.html_url = data.get("html_url")


class Repository:
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.full_name = data.get("full_name")
        self.private = data.get("private")
        self.owner = User(data["owner"]) if data.get("owner") else None
        self.description = data.get("description")
        self.fork = data.get("fork")
        self.html_url = data.get("html_url")
        self.default_branch = data.get("default_branch")
        self.topics = data.get("topics", [])
        self.license = License(data["license"]) if data.get("license") else None


class BranchRef:
    def __init__(self, data: Dict[str, Any]):
        self.label = data.get("label")
        self.ref = data.get("ref")
        self.sha = data.get("sha")
        self.user = User(data["user"]) if data.get("user") else None
        self.repo = Repository(data["repo"]) if data.get("repo") else None


class Team:
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.node_id = data.get("node_id")
        self.name = data.get("name")
        self.slug = data.get("slug")
        self.description = data.get("description")
        self.privacy = data.get("privacy")
        self.permission = data.get("permission")


class PullRequest:
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.number = data.get("number")
        self.state = data.get("state")
        self.locked = data.get("locked")
        self.title = data.get("title")
        self.body = data.get("body")
        self.user = User(data["user"]) if data.get("user") else None

        self.labels = [Label(l) for l in data.get("labels", [])]
        self.milestone = Milestone(data["milestone"]) if data.get("milestone") else None

        self.assignee = User(data["assignee"]) if data.get("assignee") else None
        self.assignees = [User(u) for u in data.get("assignees", [])]

        self.requested_reviewers = [
            User(u) for u in data.get("requested_reviewers", [])
        ]
        self.requested_teams = [
            Team(t) for t in data.get("requested_teams", [])
        ]

        self.head = BranchRef(data["head"]) if data.get("head") else None
        self.base = BranchRef(data["base"]) if data.get("base") else None

        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self.closed_at = data.get("closed_at")
        self.merged_at = data.get("merged_at")

        self.merge_commit_sha = data.get("merge_commit_sha")
        self.author_association = data.get("author_association")
        self.draft = data.get("draft")
        self.auto_merge = data.get("auto_merge")
