"""
[GENERATED BY CURSOR]
This script processes and filters content updates from various sources.

Workflow in the two-phase approach:
1. Loads cached results from connector_cache.py (metadata only from first phase)
2. Filters against current entries to identify new content
3. Deduplicates updated entries to keep only the latest entry per channel
4. Checks for stale subscriptions that haven't been updated in 30+ days
5. Exports filtered results to a content_request_[date].json file
6. Updates the current entries list with new content

When running in GitHub Actions, it reads from and writes to a GitHub Gist instead
of local files, allowing for persistent state between workflow runs.
"""

import json
from datetime import datetime
import os
from utils.logging_config import logger
from dotenv import load_dotenv
from services.gist import read_from_gist, update_gist
from utils.connector_cache import ConnectorCache

def is_github_actions_env():
    return os.getenv("GITHUB_ACTIONS") == "true"

def deduplicate_current_entries(current_entries):
    """
    Deduplicate current entries to keep only the latest entry for each channel.
    Returns a new list with one entry per channel (the one with the latest published_at date).
    """
    # Dictionary to keep track of the latest entry for each channel
    latest_entries = {}
    
    # Iterate through all entries to find the latest for each channel
    for entry in current_entries:
        channel = entry['channel']
        published_at = entry['published_at']
        
        if channel not in latest_entries or published_at > latest_entries[channel]['published_at']:
            latest_entries[channel] = entry
    
    # Convert dictionary values back to a list
    deduplicated_entries = list(latest_entries.values())
    
    logger.info(f"Deduplicated from {len(current_entries)} to {len(deduplicated_entries)} entries")
    return deduplicated_entries

def check_stale_subscriptions(deduplicated_entries, days_threshold=30):
    """
    Check if any subscriptions haven't been updated for more than the specified number of days.
    Logs an error for each subscription that is older than the threshold.
    """
    today = datetime.now().date()
    stale_count = 0
    
    for entry in deduplicated_entries:
        channel = entry['channel']
        published_at = entry['published_at']
        
        # Convert the published_at string to a datetime object
        try:
            # Assuming published_at is in ISO format (YYYY-MM-DD)
            published_date_str = published_at.split('T')[0] if 'T' in published_at else published_at
            last_update_date = datetime.fromisoformat(published_date_str).date()
            
            # Calculate the difference in days (ensure it's an integer)
            delta = today - last_update_date
            days_since_update = delta.days
            
            if days_since_update > days_threshold:
                logger.warning(f"Subscription '{channel}' hasn't been updated for {days_since_update} days (last update: {published_at})")
                stale_count += 1
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing date for channel '{channel}': {e}")
    
    if stale_count > 0:
        logger.warning(f"Found {stale_count} stale subscriptions (older than {days_threshold} days)")
    else:
        logger.info(f"All subscriptions are up to date (updated within {days_threshold} days)")
    
    return stale_count

def filter_new_entries(latest_retrieval, current_entries):
    """
    Filter raw results to keep only new entries that are not in current_entries.
    Returns a tuple of (new_entries, updated_current_entries).
    """
    # Create a set of (channel, published_at) tuples from current entries for efficient lookup
    current_set = {(entry['channel'], entry['published_at']) for entry in current_entries}
    
    # Filter raw results to keep only new entries
    new_entries = []
    for item in latest_retrieval:
        channel = item['channel']
        published_at = item['published_at']
        
        # Check if this entry is not in current_entries
        if (channel, published_at) not in current_set:
            new_entries.append(item)
            # Add the new entry to current_entries
            current_entries.append({
                'channel': channel,
                'published_at': published_at
            })
            logger.info(f"Adding {channel} on {published_at}")
        else:
            logger.info(f"Skipping {channel} on {published_at} because it already exists")
    
    return new_entries, current_entries

def load_latest_updates(today):
    """
    Load raw results from connector cache files created during the first phase.
    Returns the raw results data combined from all cache files.
    """
    cache = ConnectorCache()
    cache_dir = cache.cache_dir
    
    if not cache_dir.exists():
        logger.error(f"Error: Cache directory {cache_dir} does not exist.")
        return None
    
    # Find all cache files for today's date
    date_str = today
    cache_files = list(cache_dir.glob(f"*_{date_str}.json"))
    
    if not cache_files:
        logger.error(f"Error: No cache files found for date {date_str}.")
        return None
    
    # Load and combine all cache files
    latest_retrieval = []
    for cache_file in cache_files:
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                # If the cache data is a single item (not a list), wrap it in a list
                if isinstance(cache_data, dict):
                    latest_retrieval.append(cache_data)
                elif isinstance(cache_data, list):
                    latest_retrieval.extend(cache_data)
                logger.info(f"Loaded cache data from {cache_file.name}")
        except Exception as e:
            logger.error(f"Error loading cache file {cache_file}: {e}")
    
    if not latest_retrieval:
        logger.warning(f"No raw results found in cache for date {date_str}.")
        
    logger.info(f"Loaded {len(latest_retrieval)} entries from cache files.")
    return latest_retrieval

def save_content_requests(new_entries, today):
    """Save filtered results to a content request file"""
    # Ensure the data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Define path for content request file
    content_request_path = f"data/content_request_{today}.json"
    
    # Write filtered results to a new file
    with open(content_request_path, 'w', encoding='utf-8') as f:
        json.dump(new_entries, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Content requests saved to {content_request_path}")

def load_current_entries(is_github=False):
    """
    Load current entries from either Gist (GitHub Actions) or local file.
    
    Args:
        is_github (bool): Whether running in GitHub Actions environment
        
    Returns:
        list: Current entries or empty list if loading fails
    """
    if is_github:
        # Get Gist ID and GitHub token from environment variables
        gist_id = os.getenv("GIST_ID")
        gist_token = os.getenv("GIST_TOKEN")
        
        if not gist_id:
            logger.error("Missing GIST_ID in environment variables")
            return []
        
        # Load current entries from Gist
        try:
            current_entries = read_from_gist(gist_id, gist_token, "current.json")
            logger.info(f"Loaded {len(current_entries)} entries from Gist")
            return current_entries
        except Exception as e:
            logger.error(f"Error reading from gist: {e}")
            return []
    else:
        # Define file path for current entries
        current_path = "data/current.json"
        
        # Check if current.json exists
        if not os.path.exists(current_path):
            logger.error(f"Error: {current_path} does not exist.")
            return []
        
        # Load current entries
        try:
            with open(current_path, 'r', encoding='utf-8') as f:
                current_entries = json.load(f)
            logger.info(f"Loaded {len(current_entries)} entries from {current_path}")
            return current_entries
        except Exception as e:
            logger.error(f"Error loading {current_path}: {e}")
            return []

def save_current_entries(updated_entries, is_github=False):
    """
    Save updated current entries to either Gist (GitHub Actions) or local file.
    
    Args:
        updated_entries (list): Updated list of current entries
        is_github (bool): Whether running in GitHub Actions environment
        
    Returns:
        bool: Success or failure
    """
    if is_github:
        # Get Gist ID and GitHub token from environment variables
        gist_id = os.getenv("GIST_ID")
        gist_token = os.getenv("GIST_TOKEN")
        
        if not gist_id:
            logger.error("Missing GIST_ID in environment variables")
            return False
        
        # Update file in the gist
        try:
            files_data = {
                "current.json": {
                    "content": json.dumps(updated_entries, ensure_ascii=False, indent=2)
                },
            }
            update_gist(gist_id, gist_token, files_data)
            logger.info("Updated gist with current entries")
            return True
        except Exception as e:
            logger.error(f"Error updating gist: {e}")
            return False
    else:
        # Define file path for current entries
        current_path = "data/current.json"
        
        # Update current.json with the new entries
        try:
            with open(current_path, 'w', encoding='utf-8') as f:
                json.dump(updated_entries, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated {current_path} with {len(updated_entries)} entries")
            return True
        except Exception as e:
            logger.error(f"Error saving to {current_path}: {e}")
            return False

def main():
    """Main function to filter content updates."""
    # Get today's date in the format YYYY-MM-DD
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Load environment variables
    load_dotenv()
    
    # Check if running in GitHub Actions
    is_github = is_github_actions_env()
    env_name = "GitHub Actions" if is_github else "local development"
    logger.info(f"Running in {env_name} environment")
    
    # Load latest update cache (metadata only from the first phase)
    latest_retrieval = load_latest_updates(today)
    if latest_retrieval is None or len(latest_retrieval) == 0:
        logger.warning("No cached content found to process.")
        return
    
    # Load current entries
    current_entries = load_current_entries(is_github)
    
    # Filter raw results and get updated current entries
    new_entries, updated_current_entries = filter_new_entries(latest_retrieval, current_entries)
    
    # Deduplicate current entries after filtering
    deduplicated_entries = deduplicate_current_entries(updated_current_entries)
    
    # Check for stale subscriptions in the deduplicated entries
    check_stale_subscriptions(deduplicated_entries)
    
    # Save filtered results as content requests locally
    save_content_requests(new_entries, today)
    
    # Save updated current entries
    save_current_entries(deduplicated_entries, is_github)
    
    logger.info(f"Identified {len(new_entries)} new entries requiring content retrieval out of {len(latest_retrieval)} total.")

if __name__ == "__main__":
    main()
