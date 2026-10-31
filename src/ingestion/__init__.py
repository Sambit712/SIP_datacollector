"""Multi-source data ingestion engine package."""

from .base import BaseIngestor
from .deduplicator import Deduplicator
from .reddit_collector import RedditCollector
from .review_collector import ReviewCollector
from .doc_collector import DocCollector
from .news_collector import NewsCollector
from .csv_importer import CsvImporter

__all__ = [
    "BaseIngestor",
    "Deduplicator",
    "RedditCollector",
    "ReviewCollector",
    "DocCollector",
    "NewsCollector",
    "CsvImporter",
]
