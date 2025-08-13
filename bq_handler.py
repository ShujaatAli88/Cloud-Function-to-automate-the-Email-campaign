from google.cloud import bigquery
from google.oauth2 import service_account
from config import Config
from datetime import datetime
from log_handler import logger
import pandas as pd

def google_handler():
    logger.info("Initializing BigQuery client")
    credentials = service_account.Credentials.from_service_account_file(
        "wholesaling-data-warehouse-cd2929689ac2.json"
    )

    client = bigquery.Client(project=Config.PROJECT_ID, credentials=credentials)
    batch_id = "Batch_" + datetime.now().strftime("%Y_%m_%d_%H%M")

    return {
        "client": client,
        "batch_id": batch_id,
    }



##### Manual Handling of Invalid Email.......
def invalidate_emails_from_csv():
    """
    Reads a CSV file, matches 'email' values against BigQuery records,
    and updates Email_status = 'Invalid' for matches. Logs affected row count.
    """
    logger.info("Starting email invalidation process...")

    # Initialize BigQuery client
    bq = google_handler()
    client = bq["client"]

    # Load emails from CSV
    df = pd.read_csv("new_records_not_in_farooq_catch_all_z706CdD.csv")
    if 'email_address' not in df.columns:
        raise ValueError("CSV must contain an 'email' column")

    email_list = df['email_address'].dropna().str.lower().unique().tolist()

    if not email_list:
        logger.warning("No valid emails found in the CSV.")
        return

    # Prepare BigQuery update
    full_table_id = f"{Config.PROJECT_ID}.{Config.DATASET}.{Config.TABLE}"
    email_str = ', '.join([f"'{email}'" for email in email_list])

    query = f"""
        UPDATE `{full_table_id}`
        SET 
            Email_status = 'Email Not Sent',
            email_validity = 'Catch all'
        WHERE LOWER(email_address) IN ({email_str})
    """

    logger.info(f"Running update query for {len(email_list)} emails...")

    # Execute the update
    query_job = client.query(query)
    query_job.result()  # Wait for it to complete

    affected_rows = query_job.num_dml_affected_rows
    logger.info(f"✅ Email_status updated to 'Invalid' for {affected_rows} matching records.")

if __name__ == "__main__":
    invalidate_emails_from_csv()
