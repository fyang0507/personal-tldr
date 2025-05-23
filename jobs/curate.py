"""
[GENERATED BY CURSOR]
This script curates processed content based on user preferences defined in curator.toml.
It categorizes content into must-see, might-be-interested, and skip categories
using LLM-based content evaluation against the user's interest profile.
"""

import os
import json
import re
from datetime import datetime
from utils.logging_config import logger
from services.llm import api_text_completion
from utils.toml_loader import load_toml_file


def parse_duration_to_seconds(duration_str):
    """
    Parse a duration string like "1h 30m" or "45s" to seconds.
    
    Args:
        duration_str: String representation of duration (e.g., "1h 30m", "45s", "2m 15s")
        
    Returns:
        int: Total seconds
    """
    # If already an integer, return it
    if isinstance(duration_str, int):
        return duration_str
    
    # If it's a string that can be directly converted to int, do so
    if isinstance(duration_str, str) and duration_str.isdigit():
        return int(duration_str)
    
    # Otherwise parse the time format
    total_seconds = 0
    
    # Extract hours
    hour_match = re.search(r'(\d+)h', duration_str)
    if hour_match:
        total_seconds += int(hour_match.group(1)) * 3600
    
    # Extract minutes
    minute_match = re.search(r'(\d+)m', duration_str)
    if minute_match:
        total_seconds += int(minute_match.group(1)) * 60
    
    # Extract seconds
    second_match = re.search(r'(\d+)s', duration_str)
    if second_match:
        total_seconds += int(second_match.group(1))
    
    # If no matches found but it's a numeric string, treat as seconds
    if total_seconds == 0 and duration_str.strip():
        try:
            return int(duration_str)
        except ValueError:
            logger.warning(f"Could not parse duration: {duration_str}, using 0")
            return 0
    
    return total_seconds


def load_curator_config():
    """Load the curator configuration from the TOML file."""
    config = load_toml_file("prompts/curator.toml")
    return config["curator"]["system"], config["curator"]["model"]


def get_llm_curation(processed_data):
    """
    Get content curation recommendations from LLM.
    
    Args:
        processed_data (list): List of processed content items
        
    Returns:
        dict: Raw LLM response with content categorization
    """
    # Load curator configuration
    system_prompt, model = load_curator_config()
    
    # Prepare the user message with the processed data
    user_message = json.dumps(processed_data, indent=2)
    
    # Call the completion API
    response = api_text_completion(model, system_prompt, user_message)
    
    try:
        # Parse the response as JSON
        curated_content = json.loads(response)
        return curated_content
    except json.JSONDecodeError:
        logger.error("Failed to parse curator response as JSON")
        logger.error(f"Response:\n{response}")
        return None


def parse_curation_response(curated_content, processed_data):
    """
    Parse and process the LLM curation response.
    
    Args:
        curated_content (dict): The raw LLM curation response
        processed_data (list): Original processed content items
        
    Returns:
        dict: Processed curation results with full content items
    """
    if not curated_content:
        return None
        
    # Replace indices with actual data
    result = {
        "must_see": [],
        "might_be_interested": [],
        "you_may_skip": []
    }
    
    # Process must_see items
    for item in curated_content.get("must_see", []):
        try:
            index = int(item["idx"])
            if 0 <= index < len(processed_data):
                content_item = processed_data[index].copy()
                content_item["reason"] = item["reason"]
                result["must_see"].append(content_item)
            else:
                logger.warning(f"Index {index} out of range for must_see")
        except (ValueError, KeyError) as e:
            logger.warning(f"Error processing must_see item: {e}")
    
    # Process might_be_interested items
    for item in curated_content.get("might_be_interested", []):
        try:
            index = int(item["idx"])
            if 0 <= index < len(processed_data):
                content_item = processed_data[index].copy()
                content_item["reason"] = item["reason"]
                result["might_be_interested"].append(content_item)
            else:
                logger.warning(f"Index {index} out of range for might_be_interested")
        except (ValueError, KeyError) as e:
            logger.warning(f"Error processing might_be_interested item: {e}")
    
    # Process skip items
    for item in curated_content.get("you_may_skip", []):
        try:
            index = int(item["idx"])
            if 0 <= index < len(processed_data):
                content_item = processed_data[index].copy()
                content_item["reason"] = item["reason"]
                result["you_may_skip"].append(content_item)
            else:
                logger.warning(f"Index {index} out of range for you_may_skip")
        except (ValueError, KeyError) as e:
            logger.warning(f"Error processing you_may_skip item: {e}")
    
    return result


def curate_content(processed_data):
    """
    Curate content using LLM based on user preferences.
    
    Args:
        processed_data (list): List of processed content items
        
    Returns:
        dict: Curated content categorized into must_see, might_be_interested, and skip
    """
    # Get curation from LLM
    curated_content = get_llm_curation(processed_data)
    
    # Parse and process the response
    result = parse_curation_response(curated_content, processed_data)
    
    return result


def main():
    """Main function to curate processed content."""
    # Get today's date in the format YYYY-MM-DD
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Define file paths
    processed_results_path = f"data/processed_results_{today}.json"
    curated_results_path = f"data/curated_results_{today}.json"
    
    # Check if processed results file exists
    if not os.path.exists(processed_results_path):
        logger.error(f"Error: {processed_results_path} does not exist.")
        return
    
    # Load processed results
    with open(processed_results_path, 'r', encoding='utf-8') as f:
        processed_results = json.load(f)
    
    logger.info(f"Curating {len(processed_results)} processed items")
    
    # Curate content
    curated_results = curate_content(processed_results)
    
    if curated_results:
        # Save curated results
        with open(curated_results_path, 'w', encoding='utf-8') as f:
            json.dump(curated_results, f, ensure_ascii=False, indent=2)
        
        must_see_count = len(curated_results.get("must_see", []))
        might_be_interested_count = len(curated_results.get("might_be_interested", []))
        you_may_skip_count = len(curated_results.get("you_may_skip", []))
        
        # Calculate duration sums with proper time parsing
        must_see_duration = sum(parse_duration_to_seconds(item['duration'])
                              for item in curated_results.get('must_see', []))
        might_be_interested_duration = sum(parse_duration_to_seconds(item['duration'])
                                        for item in curated_results.get('might_be_interested', []))
        you_may_skip_duration = sum(parse_duration_to_seconds(item['duration'])
                                  for item in curated_results.get('you_may_skip', []))
        
        # Format durations as hours and minutes for display
        def format_duration(seconds):
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        
        logger.info(f"Curated {len(processed_results)} items into:")
        logger.info(f"- Must see: {must_see_count} items, total duration: {format_duration(must_see_duration)}")
        logger.info(f"- Might be interested: {might_be_interested_count} items, total duration: {format_duration(might_be_interested_duration)}")
        logger.info(f"- You may skip: {you_may_skip_count} items, total duration: {format_duration(you_may_skip_duration)}")
        logger.info(f"Results saved to {curated_results_path}")
    else:
        logger.error("Curation failed")


if __name__ == "__main__":
    main()
