import requests
from config import Config
from log_handler import logger

def fetch_campaigns():
    logger.info("Fetching Active campaigns from Smartlead API..")
    try:
        SMARTLEAD_API_KEY = Config.SMARTLEAD_API_KEY
        url = f"https://server.smartlead.ai/api/v1/campaigns/?api_key={SMARTLEAD_API_KEY}"
        headers = {"accept": "application/json"}

        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an error for bad status codes
        return response
    except Exception as error:
        logger.error(f"Error fetching campaigns: {error}")
        return None

def get_campaign_status(all_campaigns_api_response):
    """
    Check the status of campaigns and return a list of all active campaign IDs and names.
    """
    logger.info("Checking campaign status..")
    try:
        json_data_list = all_campaigns_api_response.json()
        active_campaigns = []

        for json_data in json_data_list:
            if json_data.get("status") == "ACTIVE":
                campaign_id = json_data.get("id")
                campaign_name = json_data.get("name")
                logger.info(f"Campaign '{campaign_name}' (ID: {campaign_id}) is active.")
                active_campaigns.append({
                    "id": campaign_id,
                    "name": campaign_name
                })

        if not active_campaigns:
            logger.info("No active campaigns found.")
        return active_campaigns

    except Exception as error:
        logger.error(f"Error processing campaign data: {error}")
        return []

def campaign_main():
    all_campaigns_api_response = fetch_campaigns()
    if all_campaigns_api_response:
        active_campaigns = get_campaign_status(all_campaigns_api_response)
        logger.info(f"Active Campaigns: {active_campaigns}")
        return active_campaigns
    else:
        logger.error("No campaigns fetched.")
        return []

# Example Usage
if __name__ == "__main__":
    campaign_main()
