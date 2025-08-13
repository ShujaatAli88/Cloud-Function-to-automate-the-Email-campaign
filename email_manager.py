from google.cloud import bigquery
import requests
import time
from config import Config
from bq_handler import google_handler
from log_handler import logger
import json
import csv
import io
from datetime import datetime
from campaigns_handler import campaign_main


class ColdEmailManager:
    def __init__(self):
        self.returned_data = google_handler()
        self.client = self.returned_data["client"]
        self.batch_id = self.returned_data["batch_id"]

        self.PROJECT_ID = Config.PROJECT_ID
        self.SMARTLEAD_API_KEY = Config.SMARTLEAD_API_KEY

        # Now a list of dicts: [{"id": <int|str>, "name": <str>}, ...]
        self.ACTIVE_CAMPAIGNS = campaign_main() or []

        # Optional throttling knobs (already in your Config)
        self.EMAIL_LIMIT = getattr(Config, "EMAIL_LIMIT", 0)         # 0 or None = no limit
        self.WAIT_SECONDS = getattr(Config, "WAIT_SECONDS", 0)       # wait between API calls
        self.DATASET = Config.DATASET
        self.TABLE = Config.TABLE

    def fetch_contacts_from_smartlead(self, campaign_id):
        """
        Fetch CSV export for a single campaign and return parsed list of dicts.
        """
        logger.info(f"Fetching contacts from Smartlead API for campaign_id={campaign_id}")
        try:
            url = (
                f"https://server.smartlead.ai/api/v1/campaigns/"
                f"{campaign_id}/leads-export?api_key={self.SMARTLEAD_API_KEY}"
            )
            headers = {"accept": "text/plain"}
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            decoded_content = response.content.decode("utf-8", errors="replace")
            csv_reader = csv.DictReader(io.StringIO(decoded_content))
            contacts = list(csv_reader)

            # Optional: cap how many rows to process (useful in early testing)
            if self.EMAIL_LIMIT and isinstance(self.EMAIL_LIMIT, int) and self.EMAIL_LIMIT > 0:
                contacts = contacts[: self.EMAIL_LIMIT]

            logger.info(f"✅ Parsed {len(contacts)} contacts from CSV export (campaign {campaign_id})")

            # Persist a small debug artifact per campaign
            try:
                with open(f"contacts_{campaign_id}.json", "w", encoding="utf-8") as f:
                    json.dump(contacts, f, indent=2, ensure_ascii=False)
            except Exception as write_err:
                logger.warning(f"Could not write contacts_{campaign_id}.json: {write_err}")

            return contacts

        except requests.HTTPError as e:
            logger.error(f"❌ HTTP error fetching contacts for {campaign_id}: {e} - {getattr(e, 'response', None) and e.response.text}")
            return []
        except requests.RequestException as e:
            logger.error(f"❌ Request error while fetching contacts for {campaign_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ General error while parsing CSV for {campaign_id}: {e}")
            return []

    def batch_update_bigquery(self, contact_updates, campaign_id):
        """
        Batch update BigQuery for a single campaign's contacts.
        Sets Campaign_ID to the provided campaign_id.
        """
        logger.info(f"🔄 Performing batch update for {len(contact_updates)} contacts in BigQuery (campaign {campaign_id})")

        if not contact_updates:
            logger.warning("⚠️ No contacts to update for this campaign.")
            return

        try:
            # Prepare UNNEST rows; sanitize single quotes
            def _clean(v):
                if v is None:
                    return ""
                return str(v).replace("'", "")

            rows = ",".join(
                "STRUCT('{email}' AS email, '{date}' AS date, '{status}' AS email_status, '{sr_no}' AS sr_no, '{email_validity}' AS email_validity)".format(
                    email=_clean(item.get('email')),
                    date=_clean(item.get('date')),
                    status=_clean(item.get('email_status') or "Sent"),
                    sr_no=_clean(item.get('Sr_No')),
                    email_validity=_clean(item.get('Email_Validity', 'Valid')),
                )
                for item in contact_updates
            )

            query = f"""
            UPDATE `{self.PROJECT_ID}.{self.DATASET}.{self.TABLE}` T
            SET 
                Email_status = updates.email_status,
                Campaign_ID = "{str(campaign_id).replace('"', '')}",
                Date = updates.date,
                Sr_No = updates.sr_no,
                email_validity = updates.email_validity
            FROM UNNEST([
                {rows}
            ]) AS updates
            WHERE T.email_address = updates.email
            """

            self.client.query(query).result()
            logger.info(f"✅ Batch update completed successfully for campaign {campaign_id}")

        except Exception as e:
            logger.error(f"❌ Error during batch update for campaign {campaign_id}: {e}")

    def _transform_contacts_to_updates(self, contacts):
        """
        Convert Smartlead CSV rows into updates for BigQuery.
        """
        updates = []
        for contact in contacts:
            email = contact.get("email")
            sequence = contact.get("last_email_sequence_sent")
            raw_date = contact.get("created_at")
            email_status = contact.get("category") or contact.get("status")

            try:
                sequence_number = int(sequence) if sequence is not None else 0
            except (ValueError, TypeError):
                sequence_number = 0

            try:
                parsed_date = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S.%fZ").date().isoformat()
            except Exception as e:
                logger.warning(f"⚠️ Could not parse date for {email}: {raw_date} — {e}")
                parsed_date = datetime.today().date().isoformat()

            # Only update if an email was sent (sequence > 0)
            if email and sequence_number > 0:
                updates.append({
                    "email": email,
                    "date": parsed_date,
                    "email_status": email_status or "Sent",
                    "Sr_No": sequence_number,
                    "Email_Validity": contact.get("Email_Validity", "Valid"),
                })

        return updates

    def run_campaigns(self):
        """
        Iterate over all active campaigns, fetch contacts, and update BigQuery per campaign.
        """
        logger.info(f"Starting Smartlead pull batch: {self.batch_id}")

        if not isinstance(self.ACTIVE_CAMPAIGNS, list) or len(self.ACTIVE_CAMPAIGNS) == 0:
            logger.warning("No active campaigns found to process.")
            return

        logger.info(f"Active campaigns detected: {self.ACTIVE_CAMPAIGNS}")

        for idx, campaign in enumerate(self.ACTIVE_CAMPAIGNS, start=1):
            campaign_id = campaign.get("id")
            campaign_name = campaign.get("name")

            if not campaign_id:
                logger.warning(f"Skipping an entry without 'id': {campaign}")
                continue

            logger.info(f"\n=== [{idx}/{len(self.ACTIVE_CAMPAIGNS)}] Processing Campaign: '{campaign_name}' (ID: {campaign_id}) ===")

            try:
                contacts = self.fetch_contacts_from_smartlead(campaign_id)
                logger.info(f"📥 Pulled {len(contacts)} contacts from Smartlead for campaign {campaign_id}")

                updates = self._transform_contacts_to_updates(contacts)
                logger.info(f"🧾 Prepared {len(updates)} updates for BigQuery (campaign {campaign_id})")

                if updates:
                    self.batch_update_bigquery(updates, campaign_id)
                else:
                    logger.info(f"No qualifying updates for campaign {campaign_id} (no sent steps).")

            except Exception as e:
                logger.error(f"Error processing campaign {campaign_id}: {e}")

            # Optional small pause to be gentle to the API
            if self.WAIT_SECONDS and self.WAIT_SECONDS > 0:
                logger.info(f"Sleeping {self.WAIT_SECONDS}s before next campaign...")
                time.sleep(self.WAIT_SECONDS)


def main_executor():
    """Entry point for pulling Smartlead contacts from ALL active campaigns and updating BigQuery."""
    manager = ColdEmailManager()
    manager.run_campaigns()