import os
import re
import math
import nltk
from collections import Counter
from typing import Any, Dict, List, Optional

from services import MongoService, SqlService

def normalize_texts(pr_document: Dict[str, Any]) -> List[str]:
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

def to_int(value: Any) -> Optional[int]:
  try:
    if value is None:
      return None
    return int(value)
  except (TypeError, ValueError):
    return None


def sentiment_label(score: float) -> str:
  if score > 0:
    return "positive"
  if score < 0:
    return "negative"
  return "neutral"


def score_to_float(score: Any) -> float:
  try:
    return float(score)
  except (TypeError, ValueError):
    if hasattr(score, "item"):
      return float(score.item())
    raise


def calculate_stop_words(
  pull_request_texts: List[Dict[str, Any]],
  top_n: int = 500,
) -> List[str]:
  documents: List[List[str]] = []

  for row in pull_request_texts:
    texts = row.get("texts") or []
    for text in texts:
      if not isinstance(text, str):
        continue
      words = re.findall(r"[a-zA-Z']+", text.lower())
      if words:
        documents.append(words)

  document_count = len(documents)

  term_counts_by_document: List[Counter[str]] = []
  document_frequency: Counter[str] = Counter()

  for words in documents:
    term_counts = Counter(words)
    term_counts_by_document.append(term_counts)
    document_frequency.update(term_counts.keys())

  idf_by_word: Dict[str, float] = {}
  for word, df in document_frequency.items():
    idf_by_word[word] = math.log((1 + document_count) / (1 + df)) + 1.0

  tfidf_sum_by_word: Dict[str, float] = {}
  term_total_counts: Counter[str] = Counter()

  for term_counts in term_counts_by_document:
    token_total = sum(term_counts.values())
    if token_total == 0:
      continue

    for word, count in term_counts.items():
      tf = count / token_total
      tfidf_sum_by_word[word] = tfidf_sum_by_word.get(word, 0.0) + (tf * idf_by_word[word])
      term_total_counts[word] += count

  ranked_words = sorted(
    tfidf_sum_by_word.items(),
    key=lambda item: (item[1], -document_frequency[item[0]], -term_total_counts[item[0]], item[0]),
  )

  calculated_stop_words = set(word for word, _ in ranked_words[:top_n]) 

  from nltk.corpus import stopwords
  nltk.download("stopwords", quiet=True)
  stop_words = list(set(stopwords.words("english")))
  stop_words.extend(calculated_stop_words)
  
  return list(set(stop_words))


def remove_stop_words_from_pull_request_texts(
  pull_request_texts: List[Dict[str, Any]],
  stop_words: List[str],
) -> List[Dict[str, Any]]:
  stop_word_set = {word.lower() for word in stop_words}
  cleaned_pull_request_texts: List[Dict[str, Any]] = []

  for row in pull_request_texts:
    texts = row.get("texts") or []
    cleaned_texts: List[str] = []

    for text in texts:
      if not isinstance(text, str):
        continue

      words = re.findall(r"[a-zA-Z']+", text.lower())
      filtered_words = [word for word in words if word not in stop_word_set]
      cleaned_texts.append(" ".join(filtered_words))

    cleaned_row = dict(row)
    cleaned_row["texts"] = cleaned_texts
    cleaned_pull_request_texts.append(cleaned_row)

  return cleaned_pull_request_texts

def summarize_common_keywords(
  pull_request_texts: List[Dict[str, Any]],
  top_n: int = 20,
) -> List[Dict[str, Any]]:
  keyword_counter: Counter[str] = Counter()

  for row in pull_request_texts:
    texts = row.get("texts") or []
    for text in texts:
      if not isinstance(text, str):
        continue
      words = re.findall(r"[a-zA-Z']+", text.lower())
      keyword_counter.update(words)

  total_keywords = sum(keyword_counter.values())
  if total_keywords == 0:
    return []

  return [
    {
      "keyword": keyword,
      "count": count,
      "frequency_pct": (count / total_keywords) * 100,
    }
    for keyword, count in keyword_counter.most_common(top_n)
  ]

def summarize_common_keywords_by_group(
  pull_request_texts: List[Dict[str, Any]],
  group_field: str,
  top_n: int = 10,
) -> List[Dict[str, Any]]:
  grouped_counters: Dict[str, Counter[str]] = {}

  for row in pull_request_texts:
    group_value = str(row.get(group_field) or "unknown")
    if group_value not in grouped_counters:
      grouped_counters[group_value] = Counter()

    texts = row.get("texts") or []
    for text in texts:
      if not isinstance(text, str):
        continue
      words = re.findall(r"[a-zA-Z']+", text.lower())
      grouped_counters[group_value].update(words)

  rows: List[Dict[str, Any]] = []
  for group_value in sorted(grouped_counters.keys()):
    counter = grouped_counters[group_value]
    top_keywords = [
      f"{keyword} ({count})"
      for keyword, count in counter.most_common(top_n)
    ]
    rows.append(
      {
        group_field: group_value,
        "top_keywords": ", ".join(top_keywords),
      }
    )

  return rows


def print_keyword_summary_table(rows: List[Dict[str, Any]]) -> None:
  headers = ["keyword", "count", "frequency"]
  table_rows = [
    [
      str(row["keyword"]),
      str(row["count"]),
      f"{row['frequency_pct']:.2f}%",
    ]
    for row in rows
  ]

  all_rows = [headers] + table_rows
  widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]

  def format_row(values: List[str]) -> str:
    return " | ".join(values[i].ljust(widths[i]) for i in range(len(values)))

  print(format_row(headers))
  print("-+-".join("-" * w for w in widths))
  for row in table_rows:
    print(format_row(row))


def print_group_keyword_table(rows: List[Dict[str, Any]], group_field: str) -> None:
  headers = [group_field, "top_keywords"]
  table_rows = [
    [
      str(row[group_field]),
      str(row["top_keywords"]),
    ]
    for row in rows
  ]

  all_rows = [headers] + table_rows
  widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]

  def format_row(values: List[str]) -> str:
    return " | ".join(values[i].ljust(widths[i]) for i in range(len(values)))

  print(format_row(headers))
  print("-+-".join("-" * w for w in widths))
  for row in table_rows:
    print(format_row(row))

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

  def format_row(values: List[str]) -> str:
    return " | ".join(values[i].ljust(widths[i]) for i in range(len(values)))

  print(format_row(headers))
  print("-+-".join("-" * w for w in widths))
  for row in rows:
    print(format_row(row))

def summarize_by_repository_and_type(sentiment_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  pr_type_columns = ["test_including", "test_excluding", "no_production_code"]
  grouped: Dict[str, Dict[str, Dict[str, int]]] = {}

  for result in sentiment_results:
    repository_name = str(result.get("repository_name"))
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

  def format_triplet(value: Any) -> str:
    pos, neg, neu = value
    return f"{pos:.2f}% / {neg:.2f}% / {neu:.2f}%"

  table_rows = [
    [
      str(row["repository_name"]),
      format_triplet(row["test_including"]),
      format_triplet(row["test_excluding"]),
      format_triplet(row["no_production_code"]),
    ]
    for row in rows
  ]

  all_rows = [headers] + table_rows
  widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]

  def format_row(values: List[str]) -> str:
    return " | ".join(values[i].ljust(widths[i]) for i in range(len(values)))

  print(format_row(headers))
  print("-+-".join("-" * w for w in widths))
  for row in table_rows:
    print(format_row(row))


def build_pull_request_texts() -> List[Dict[str, Any]]:
  sql_service = SqlService()
  mongo_service = MongoService()

  sql_rows = sql_service.get_all()
  mongo_docs = mongo_service.get_all()

  mongo_by_github_id: Dict[int, Dict[str, Any]] = {}
  mongo_by_internal_id: Dict[int, Dict[str, Any]] = {}

  for document in mongo_docs:
    github_id = to_int(document.get("pull_request_id"))
    if github_id is not None:
      mongo_by_github_id[github_id] = document

    internal_id = to_int(document.get("internal_pull_request_id"))
    if internal_id is not None:
      mongo_by_internal_id[internal_id] = document

  pull_request_texts: List[Dict[str, Any]] = []

  for row in sql_rows:
    github_id = to_int(row.get("github_pull_request_id"))
    internal_id = to_int(row.get("pull_request_id"))

    document = None
    if github_id is not None:
      document = mongo_by_github_id.get(github_id)
    if document is None and internal_id is not None:
      document = mongo_by_internal_id.get(internal_id)

    texts: List[str] = []
    if document is not None:
      texts = normalize_texts(document)

    pull_request_texts.append(
      {
        "repository_name": row.get("repository_name"),
        "pull_request_id": internal_id,
        "github_pull_request_id": github_id,
        "pr_type": row.get("pr_type"),
        "texts": texts,
      }
    )

  return pull_request_texts


def analyze_sentiment_per_pull_request(
  pull_request_texts: List[Dict[str, Any]],
  analysis_function,
) -> List[Dict[str, Any]]:
  results: List[Dict[str, Any]] = []

  for row in pull_request_texts:
    texts = row.get("texts") or []
    if not texts:
      average_sentiment = None
      positive_texts = 0
      negative_texts = 0
      neutral_texts = 0
    else:
      scores = [
        score_to_float(analysis_function(text))
        for text in texts
      ]
      average_sentiment = sum(scores) / len(scores)
      positive_texts = sum(1 for score in scores if sentiment_label(score) == "positive")
      negative_texts = sum(1 for score in scores if sentiment_label(score) == "negative")
      neutral_texts = sum(1 for score in scores if sentiment_label(score) == "neutral")

    results.append(
      {
        "repository_name": row.get("repository_name"),
        "pull_request_id": row.get("pull_request_id"),
        "github_pull_request_id": row.get("github_pull_request_id"),
        "pr_type": row.get("pr_type"),
        "text_count": len(texts),
        "positive_texts": positive_texts,
        "negative_texts": negative_texts,
        "neutral_texts": neutral_texts,
        "average_sentiment": average_sentiment,
      }
    )

  return results

def sentiment_analysis(method: str, pull_request_texts: List[Dict[str, Any]]): 
  sentiment_results: List[Dict[str, Any]] = []

  if method == "SentiCR":
    nltk.download("punkt_tab", quiet=True)
    nltk.download("punkt", quiet=True)
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)
    nltk.download('universal_tagset', quiet=True)

    from SentiCR import SentiCR
    sentiment_analyzer = SentiCR()

    sentiment_results = analyze_sentiment_per_pull_request(
      pull_request_texts,
      sentiment_analyzer.get_sentiment_polarity,
    )
  elif method == "VADER":
    from nltk.sentiment import SentimentIntensityAnalyzer

    nltk.download("vader_lexicon", quiet=True)
    sentiment_analyzer = SentimentIntensityAnalyzer()

    def vader_sentiment(text: str) -> float:
      scores = sentiment_analyzer.polarity_scores(text)
      return scores["compound"]

    sentiment_results = analyze_sentiment_per_pull_request(
      pull_request_texts,
      vader_sentiment,
    )
  
  summary_rows = summarize_by_pr_type(sentiment_results)
  print_summary_table(summary_rows)
  print("")
  repository_rows = summarize_by_repository_and_type(sentiment_results)
  print_repository_type_table(repository_rows)


def keyword_analysis(pull_request_texts: List[Dict[str, Any]]) -> None:
  stop_words = calculate_stop_words(pull_request_texts)
  pull_request_texts = remove_stop_words_from_pull_request_texts(pull_request_texts, stop_words)

  keyword_rows = summarize_common_keywords(pull_request_texts)
  print("")
  print("Top keywords across all pull requests")
  print_keyword_summary_table(keyword_rows)

  keyword_by_pr_type_rows = summarize_common_keywords_by_group(
    pull_request_texts,
    "pr_type",
  )
  
  print("")
  print("Top keywords by pr_type")
  print_group_keyword_table(keyword_by_pr_type_rows, "pr_type")

if __name__ == "__main__":
  method = os.getenv("ANALYSIS_METHOD", "SentiCR").strip()
  pull_request_texts = build_pull_request_texts()

  sentiment_analysis(method, pull_request_texts)

  keyword_analysis(pull_request_texts)
