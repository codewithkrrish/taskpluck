"""taskpluck: pull action items out of meeting notes."""

from .cli import __version__
from .extract import ActionItem, extract_items

__all__ = ["ActionItem", "__version__", "extract_items"]
