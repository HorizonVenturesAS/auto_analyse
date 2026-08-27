"""Reproduserbar konkurrentanalyse for retail crawl-data."""

from .analysis import AnalysisResult, analyze_file
from .config import AppConfig, load_config
from .report import build_report

__all__ = ["AnalysisResult", "AppConfig", "analyze_file", "build_report", "load_config"]
__version__ = "0.1.0"
