"""
[GENERATED BY CURSOR]
This script implements the second phase of the two-phase content retrieval approach:
1. Reads content requests generated by filter.py (content_request_[date].json)
2. For each content request, fetches full content details using connector-specific get_latest_update_details
3. Outputs complete content data to raw_results_[date].json for preprocessing

This approach minimizes API usage by only fetching content for filtered items
that passed the first phase check.
"""

import json
import os
from datetime import datetime
from utils.logging_config import logger
import asyncio # Added for async operations

# Import connector classes for getting full content details
from connectors.sources.youtube import YoutubeConnector # Changed: Corrected class name
from connectors.sources.podcast import PodcastConnector
from connectors.sources.bilibili import BilibiliConnector
from connectors.sources.website.pipeline import WebsiteConnector # Ensure this path is correct
# from connectors.website.pipeline import prepare_website_processing_config # Removed

async def fetch_content_by_type(content_request: dict): # Changed to async
    """
    Fetch full content details by calling the appropriate connector function.
    
    Args:
        content_request (dict): The content request metadata
        
    Returns:
        dict: Full content details or None if retrieval fails
    """
    content_type = content_request.get('type')
    channel = content_request.get('channel')
    source_url = content_request.get('source_url') # For website
    uid = content_request.get('uid') # For Bilibili, if needed by constructor

    logger.info(f"Fetching content for {content_type}:{channel}")
    
    try:
        if content_type == 'youtube':
            # YoutubeConnector takes channel and optional duration_min. API key is handled internally.
            # Assuming duration_min is default or not needed for get_latest_update_details context.
            connector = YoutubeConnector(channel=channel)
            return await connector.get_latest_update_details()
            
        elif content_type == 'podcast':
            connector = PodcastConnector(podcast_name=channel) 
            return await connector.get_latest_update_details() # Added await
            
        elif content_type == 'bilibili':
            connector = BilibiliConnector(channel=channel, uid=uid)
            return await connector.get_latest_update_details() # Added await
            
        elif content_type == 'website':
            if not source_url:
                logger.error(f"Missing 'source_url' in content_request for website channel: {channel}. Cannot fetch content.")
                return None
            
            # Assuming WebsiteConnector is initialized with channel and source_url
            connector = WebsiteConnector(channel=channel, source_url=source_url)
            return await connector.get_latest_update_details() # Added await

        else:
            logger.error(f"Unsupported content type: {content_type}")
            return None
            
    except ValueError as e: # Catch init errors like missing API key for Youtube
        logger.error(f"Initialization error for {content_type}:{channel}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching content for {content_type}:{channel}: {e}", exc_info=True)
        return None


async def main(): # Changed to async
    """Main function to fetch full content for all content requests."""

    today = datetime.now().strftime("%Y-%m-%d")
    content_request_path = f"data/content_request_{today}.json"
    raw_results_path = f"data/raw_results_{today}.json"
    
    if not os.path.exists(content_request_path):
        logger.error(f"Error: {content_request_path} does not exist.")
        return
        
    with open(content_request_path, 'r', encoding='utf-8') as f:
        content_requests = json.load(f)
        
    if not content_requests:
        logger.info("No content requests found. Nothing to fetch.")
        with open(raw_results_path, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        return
        
    logger.info(f"Found {len(content_requests)} content requests to process concurrently.")
    
    raw_results = []
    success_count = 0
    failure_count = 0
    
    # Create a list of tasks to run concurrently
    tasks = []
    for request in content_requests:
        tasks.append(fetch_content_by_type(request))
    
    # Run all tasks concurrently
    # fetch_content_by_type handles exceptions internally and returns None on failure.
    # If an exception were to escape fetch_content_by_type and asyncio.gather(..., return_exceptions=False) (default),
    # gather would raise the first exception it encounters.
    # With return_exceptions=True, it would return exceptions as results.
    # Since our function returns None on error, we don't need return_exceptions=True here.
    logger.info(f"Starting concurrent fetching for {len(tasks)} tasks...")
    all_results_details = await asyncio.gather(*tasks)
    logger.info("Concurrent fetching complete.")

    # Process the results
    for i, content_details in enumerate(all_results_details):
        request = content_requests[i] # Get the original request for context
        channel = request.get('channel')
        content_type = request.get('type')

        if content_details:
            raw_results.append(content_details)
            success_count += 1
            logger.info(f"Successfully fetched content for {channel} - {content_type} (from concurrent tasks)")
        else:
            failure_count += 1
            logger.warning(f"Failed to fetch content for {channel} - {content_type} (from concurrent tasks)")
            
    with open(raw_results_path, 'w', encoding='utf-8') as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Raw results saved to {raw_results_path}")
    
    if failure_count > 0:
        logger.warning(f"Failed to fetch {failure_count} items")
        logger.info(f"Fetched {success_count}/{len(content_requests)} content items")
    else:
        logger.success(f"Successfully fetched {success_count}/{len(content_requests)} content items")


if __name__ == "__main__":
    asyncio.run(main()) # Changed to asyncio.run