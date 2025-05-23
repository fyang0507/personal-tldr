"""
[GENERATED BY CURSOR]
Reading Time Estimation Utility

This module provides functionality to estimate the reading time of multilingual Markdown content.
It supports both English and Chinese text, calculating reading time based on word/character count 
after removing Markdown formatting elements such as code blocks, links, and headings.

The default reading speeds are set to 200 words per minute for English and 150 characters 
per minute for Chinese text. These values can be adjusted as needed.
"""

import re
from utils.logging_config import logger

def process_markdown_text(md_text: str) -> str:
    """
    Process Markdown text by removing formatting elements for reading time estimation.
    
    Args:
        md_text: The Markdown content as a string.
        
    Returns:
        Cleaned text with Markdown formatting removed.
    """
    text = md_text

    # --- 1. Remove Markdown noise ---
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)      # code fences
    text = re.sub(r'`[^`]*`', '', text)                         # inline code
    
    # First remove image markdown - ![text](url)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    
    # Then handle regular markdown links - [text](url)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    
    text = re.sub(r'https?://\S+|www\.\S+', '', text)           # raw URLs
    text = re.sub(r'^[#>*\-\+]\s*', '', text, flags=re.MULTILINE)  # heading/list markers
    text = text.replace('*', '').replace('_', '')               # emphasis
            
    return text

def estimate_read_time(
    text: str,
    wpm_en: int = 200,
    cpm_zh: int = 850,
    debug: bool = False
) -> str:
    """
    Estimate mixed-language (English + Chinese) reading time for processed text.

    Args:
        text: The processed text content with Markdown formatting removed.
        wpm_en: Reading speed for English (words per minute). Default: 200.
        cpm_zh: Reading speed for Chinese (characters per minute). Default: 850.
        debug: Whether to log debug information.

    Returns:
        A string formatted as 'X m Y s' representing minutes and seconds.
    """
    # --- 2. Count English words ---
    english_words = re.findall(r'\b[a-zA-Z]+\b', text)
    num_en = len(english_words)

    # --- 3. Count Chinese characters ---
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    num_zh = len(chinese_chars)

    # --- 4. Compute reading time ---
    secs_en = (num_en / wpm_en) * 60 if num_en else 0
    secs_zh = (num_zh / cpm_zh) * 60 if num_zh else 0

    if debug:
        logger.info(f"num_en: {num_en}, num_zh: {num_zh}")
        logger.info(f"secs_en: {secs_en}, secs_zh: {secs_zh}")

    total_secs = secs_en + secs_zh

    mins = int(total_secs // 60)
    secs = int(round(total_secs % 60))

    return f"{mins}m {secs}s"


if __name__ == "__main__":
    # Reading file now separated from computation
    with open('data/36kr/content/蜜雪冰城多风光_海底捞就多落寞-36氪.md', 'r', encoding='utf-8') as f:
        md_text = f.read()
    
    # Process the text first
    processed_text = process_markdown_text(md_text, debug=True)
    with open('data/debug_read_time_estimate.md', 'w', encoding='utf-8') as f:
        f.write(processed_text)
    
    # Then estimate reading time
    read_time = estimate_read_time(processed_text, debug=True)
    logger.info(read_time)