"""
Utility functions for Study Buddy application.
"""

import os
import json
import re
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def cleanup_temp_file(filepath: str) -> None:
    """Clean up temporary uploaded files."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Cleaned up temporary file: {filepath}")
    except Exception as e:
        logger.warning(f"Failed to clean up {filepath}: {e}")

def create_temp_filename(original_name: str) -> str:
    """Create a unique temporary filename to avoid conflicts."""
    timestamp = int(time.time())
    return f"temp_{timestamp}_{original_name}"

def extract_first_json_array(text: str) -> List[Dict[str, Any]]:
    """Extract first valid JSON array from free-form text."""
    try:
        # Remove code fences if present
        if text.strip().startswith("```"):
            cleaned = text.strip().strip("`\n ")
            if cleaned.startswith("json\n"):
                cleaned = cleaned[len("json\n"):]
            text = cleaned.strip("`\n ")
        
        # Fast regex attempt for an array block
        match = re.search(r"\[.*\]", text, flags=re.DOTALL)
        candidates = []
        if match:
            candidates.append(match.group(0))
        
        # Also try scanning for balanced brackets in case multiple blocks exist
        start = None
        depth = 0
        for i, ch in enumerate(text):
            if ch == '[':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == ']':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        candidates.append(text[start:i+1])
                        break
        
        # Try to parse candidates
        for cand in candidates:
            try:
                return json.loads(cand)
            except Exception:
                continue
        
        # Last resort: try plain json
        return json.loads(text)
    except Exception as e:
        logger.error(f"Failed to extract JSON from text: {e}")
        raise ValueError(f"Could not parse quiz data: {e}")

def process_message_with_citations(message, filename: str = "uploaded document") -> str:
    """Processes a chat message and formats citations."""
    try:
        message_content = message.content[0].text
        annotations = message_content.annotations if hasattr(message_content, "annotations") else []
        citations = []
        
        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(annotation.text, f" [{index + 1}]")
            
            if hasattr(annotation, "file_citation"):
                file_citation = annotation.file_citation
                
                # Handle different possible attribute names for the quote
                quote_text = getattr(file_citation, "quote", None)
                if not quote_text:
                    quote_text = getattr(file_citation, "text", "cited text")
                citations.append(f'[{index + 1}] {quote_text} from {filename}')
                
            elif hasattr(annotation, "file_path"):
                citations.append(f'[{index + 1}] Click [here](#) to download {filename}')
        
        full_response = message_content.value + "\n\n" + "\n".join(citations)
        return full_response
        
    except Exception as e:
        logger.error(f"Failed to process message citations: {e}")
        # Return original message if citation processing fails
        return message.content[0].text.value if hasattr(message.content[0], "text") else str(message.content[0])

def validate_file_type(filename: str, supported_extensions: set) -> bool:
    """Validate if a file type is supported."""
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext in supported_extensions

def get_file_size_mb(file_size_bytes: int) -> float:
    """Convert file size from bytes to MB."""
    return round(file_size_bytes / (1024 * 1024), 1) 