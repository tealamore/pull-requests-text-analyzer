import os
from typing import Any, Dict, List, Optional

from pymongo import MongoClient


class MongoService:
	def __init__(self, uri: Optional[str] = None, database_name: Optional[str] = None) -> None:
		self.uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
		self.database_name = database_name or os.getenv("MONGODB_DATABASE", "pull_requests")
		self.collection_name = os.getenv("MONGODB_COLLECTION", "pull_request_results")
		self.client = MongoClient(self.uri)
		self.database = self.client[self.database_name]
		self.collection = self.database[self.collection_name]

	def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
		pull_request_id = record.get("pull_request_id")
		document_id = record.get("_id") or f"{record.get('repo_name')}_{pull_request_id}"
		document = {
			"_id": document_id,
			"pull_request_id": pull_request_id,
			"title": record.get("title"),
			"description": record.get("description"),
			"comments": record.get("comments", []),
			"commit_messages": record.get("commit_messages", []),
		}

		self.collection.replace_one({"_id": document_id}, document, upsert=True)
		document["_id"] = str(document["_id"])
		return document

	def get_all(self) -> List[Dict[str, Any]]:
		documents: List[Dict[str, Any]] = []

		for item in self.collection.find(
			{},
			{
				"_id": 1,
				"pull_request_id": 1,
				"title": 1,
				"description": 1,
				"comments": 1,
				"commit_messages": 1,
			},
		):
			document = dict(item)
			document["_id"] = str(document["_id"])
			documents.append(document)

		return documents

