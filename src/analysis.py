import os
import nltk
from typing import Any, Dict, List, Optional

from services import MongoService, SqlService

def _normalize_texts(pr_document: Dict[str, Any]) -> List[str]:
  texts: List[str] = []

  for field in ("title", "description"):
    value = pr_document.get(field)
    if isinstance(value, str) and value.strip() != "":
      texts.append(value.strip())

  for field in ("comments", "commit_messages"):
    values = pr_document.get(field, [])
    if isinstance(values, list):
      for value in values:
        if isinstance(value, str) and value.strip() != "":
          texts.append(value.strip())

  return texts

def _to_int(value: Any) -> Optional[int]:
  try:
    if value is None:
      return None
    return int(value)
  except (TypeError, ValueError):
    return None


def _sentiment_label(score: float) -> str:
  if score > 0:
    return "positive"
  if score < 0:
    return "negative"
  return "neutral"


def _score_to_float(score: Any) -> float:
  try:
    return float(score)
  except (TypeError, ValueError):
    if hasattr(score, "item"):
      return float(score.item())
    raise


def summarize_by_pr_type(sentiment_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  grouped: Dict[str, Dict[str, Any]] = {}

  for result in sentiment_results:
    pr_type = str(result.get("pr_type") or "unknown")
    if pr_type not in grouped:
      grouped[pr_type] = {
        "pr_type": pr_type,
        "text_count": 0,
        "positive_count": 0,
        "negative_count": 0,
        "neutral_count": 0,
      }

    grouped[pr_type]["text_count"] += int(result.get("text_count") or 0)
    grouped[pr_type]["positive_count"] += int(result.get("positive_texts") or 0)
    grouped[pr_type]["negative_count"] += int(result.get("negative_texts") or 0)
    grouped[pr_type]["neutral_count"] += int(result.get("neutral_texts") or 0)

  summary_rows: List[Dict[str, Any]] = []
  for pr_type in sorted(grouped.keys()):
    row = grouped[pr_type]
    total = row["text_count"]

    if total == 0:
      positive_pct = 0.0
      negative_pct = 0.0
      neutral_pct = 0.0
    else:
      positive_pct = (row["positive_count"] / total) * 100
      negative_pct = (row["negative_count"] / total) * 100
      neutral_pct = (row["neutral_count"] / total) * 100

    summary_rows.append(
      {
        "pr_type": pr_type,
        "text_count": total,
        "positive_pct": positive_pct,
        "negative_pct": negative_pct,
        "neutral_pct": neutral_pct,
      }
    )

  return summary_rows


def print_summary_table(summary_rows: List[Dict[str, Any]]) -> None:
  headers = ["pr_type", "texts_analyzed", "% positive", "% negative", "% neutral"]
  rows = [
    [
      str(row["pr_type"]),
      str(row["text_count"]),
      f"{row['positive_pct']:.2f}%",
      f"{row['negative_pct']:.2f}%",
      f"{row['neutral_pct']:.2f}%",
    ]
    for row in summary_rows
  ]

  all_rows = [headers] + rows
  widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]

  def _format_row(values: List[str]) -> str:
    return " | ".join(values[i].ljust(widths[i]) for i in range(len(values)))

  print(_format_row(headers))
  print("-+-".join("-" * w for w in widths))
  for row in rows:
    print(_format_row(row))


def summarize_by_repository_and_type(sentiment_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  pr_type_columns = ["test_including", "test_excluding", "no_production_code"]
  grouped: Dict[str, Dict[str, Dict[str, int]]] = {}

  for result in sentiment_results:
    repository_name = str(result.get("repository_name") or "unknown")
    pr_type = str(result.get("pr_type") or "unknown")

    if repository_name not in grouped:
      grouped[repository_name] = {}

    if pr_type not in grouped[repository_name]:
      grouped[repository_name][pr_type] = {
        "text_count": 0,
        "positive_count": 0,
        "negative_count": 0,
        "neutral_count": 0,
      }

    grouped[repository_name][pr_type]["text_count"] += int(result.get("text_count") or 0)
    grouped[repository_name][pr_type]["positive_count"] += int(result.get("positive_texts") or 0)
    grouped[repository_name][pr_type]["negative_count"] += int(result.get("negative_texts") or 0)
    grouped[repository_name][pr_type]["neutral_count"] += int(result.get("neutral_texts") or 0)

  rows: List[Dict[str, Any]] = []
  for repository_name in sorted(grouped.keys()):
    row: Dict[str, Any] = {"repository_name": repository_name}

    for pr_type in pr_type_columns:
      counts = grouped[repository_name].get(pr_type, {
        "text_count": 0,
        "positive_count": 0,
        "negative_count": 0,
        "neutral_count": 0,
      })
      total = counts["text_count"]

      if total == 0:
        row[pr_type] = (0.0, 0.0, 0.0)
      else:
        row[pr_type] = (
          (counts["positive_count"] / total) * 100,
          (counts["negative_count"] / total) * 100,
          (counts["neutral_count"] / total) * 100,
        )

    rows.append(row)

  return rows


def print_repository_type_table(rows: List[Dict[str, Any]]) -> None:
  headers = [
    "Repository",
    "test-incl (pos/neg/neu)",
    "test-excl (pos/neg/neu)",
    "non-prod (pos/neg/neu)",
  ]

  def _format_triplet(value: Any) -> str:
    pos, neg, neu = value
    return f"{pos:.2f}% / {neg:.2f}% / {neu:.2f}%"

  table_rows = [
    [
      str(row["repository_name"]),
      _format_triplet(row["test_including"]),
      _format_triplet(row["test_excluding"]),
      _format_triplet(row["no_production_code"]),
    ]
    for row in rows
  ]

  all_rows = [headers] + table_rows
  widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]

  def _format_row(values: List[str]) -> str:
    return " | ".join(values[i].ljust(widths[i]) for i in range(len(values)))

  print(_format_row(headers))
  print("-+-".join("-" * w for w in widths))
  for row in table_rows:
    print(_format_row(row))


def analyze_sentiment_per_pull_request(analysis_function) -> List[Dict[str, Any]]:
  sql_service = SqlService()
  mongo_service = MongoService()

  sql_rows = sql_service.get_all()
  mongo_docs = mongo_service.get_all()

  mongo_by_github_id: Dict[int, Dict[str, Any]] = {}
  mongo_by_internal_id: Dict[int, Dict[str, Any]] = {}

  for document in mongo_docs:
    github_id = _to_int(document.get("pull_request_id"))
    if github_id is not None:
      mongo_by_github_id[github_id] = document

    internal_id = _to_int(document.get("internal_pull_request_id"))
    if internal_id is not None:
      mongo_by_internal_id[internal_id] = document

  results: List[Dict[str, Any]] = []

  for row in sql_rows:
    github_id = _to_int(row.get("github_pull_request_id"))
    internal_id = _to_int(row.get("pull_request_id"))

    document = None
    if github_id is not None:
      document = mongo_by_github_id.get(github_id)
    if document is None and internal_id is not None:
      document = mongo_by_internal_id.get(internal_id)

    if document is None:
      results.append(
        {
          "repository_name": row.get("repository_name"),
          "pull_request_id": internal_id,
          "github_pull_request_id": github_id,
          "pr_type": row.get("pr_type"),
          "text_count": 0,
          "positive_texts": 0,
          "negative_texts": 0,
          "neutral_texts": 0,
          "average_sentiment": None,
        }
      )
      continue

    texts = _normalize_texts(document)
    if not texts:
      average_sentiment = None
      positive_texts = 0
      negative_texts = 0
      neutral_texts = 0
    else:
      scores = [
        _score_to_float(analysis_function(text))
        for text in texts
      ]
      average_sentiment = sum(scores) / len(scores)
      positive_texts = sum(1 for score in scores if _sentiment_label(score) == "positive")
      negative_texts = sum(1 for score in scores if _sentiment_label(score) == "negative")
      neutral_texts = sum(1 for score in scores if _sentiment_label(score) == "neutral")

    results.append(
      {
        "repository_name": row.get("repository_name"),
        "pull_request_id": internal_id,
        "github_pull_request_id": github_id,
        "pr_type": row.get("pr_type"),
        "text_count": len(texts),
        "positive_texts": positive_texts,
        "negative_texts": negative_texts,
        "neutral_texts": neutral_texts,
        "average_sentiment": average_sentiment,
      }
    )

  return results

if __name__ == "__main__":
  method = os.getenv("ANALYSIS_METHOD", "SentiCR").strip()
  
  sentiment_results: List[Dict[str, Any]] = []
  
  if method == "SentiCR":
    nltk.download("punkt_tab", quiet=True)
    nltk.download("punkt", quiet=True)
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)
    nltk.download('universal_tagset', quiet=True)

    print("training model")
    from SentiCR import SentiCR
    sentiment_analyzer = SentiCR()
    print("finished training")

    sentiment_results = analyze_sentiment_per_pull_request(sentiment_analyzer.get_sentiment_polarity)
  elif method == "VADER":
    from nltk.sentiment import SentimentIntensityAnalyzer

    nltk.download("vader_lexicon", quiet=True)
    sentiment_analyzer = SentimentIntensityAnalyzer()

    def vader_sentiment(text: str) -> float:
      scores = sentiment_analyzer.polarity_scores(text)
      return scores["compound"]

    sentiment_results = analyze_sentiment_per_pull_request(vader_sentiment)
  else:
    print(f"Unknown ANALYSIS_METHOD '{method}', skipping sentiment analysis.")

  summary_rows = summarize_by_pr_type(sentiment_results)
  print_summary_table(summary_rows)
  print("")
  repository_rows = summarize_by_repository_and_type(sentiment_results)
  print_repository_type_table(repository_rows)