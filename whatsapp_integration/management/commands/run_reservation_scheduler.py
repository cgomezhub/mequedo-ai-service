
import time
import os
import requests
import logging
import certifi
from datetime import datetime
from django.core.management.base import BaseCommand
from pymongo import MongoClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Runs the reservation expiration scheduler (Polling MongoDB)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            'Starting Reservation Scheduler...'))

        # Connect to MongoDB
        try:
            client = MongoClient(os.getenv("DATABASE_URL"),
                                 tlsCAFile=certifi.where())
            db = client.get_database(os.getenv("MONGODB_DB_NAME", "test"))
            tasks_collection = db.get_collection("ScheduledTask")
            self.stdout.write(self.style.SUCCESS(
                '✅ Connected to MongoDB (ScheduledTask)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'❌ Failed to connect to MongoDB: {e}'))
            return

        while True:
            try:
                # Find pending tasks that are due (executeAt <= now)
                now = datetime.utcnow()

                due_tasks = list(tasks_collection.find({
                    "status": "pending",
                    "executeAt": {"$lte": now}
                }))

                if due_tasks:
                    self.stdout.write(
                        f"--- Found {len(due_tasks)} due tasks at {now} ---")

                for task in due_tasks:

                    reservation_id = task.get("reservationId")
                    callback_url = task.get("callbackUrl")
                    task_id = task.get("_id")

                    self.stdout.write(
                        f"⏰ Processing Task {task_id} for Reservation {reservation_id}...")

                    # Call the Next.js API
                    try:
                        # Use the shared secret token
                        secret_token = os.getenv(
                            "MEQUEDO_SECRET_TOKEN", "RESERVATION_SECRET_123")
                        payload = {"reservationId": reservation_id,
                                   "secretToken": secret_token}

                        logger.info(
                            f"Sending callback to {callback_url} with secret ending in ...{secret_token[-3:]}")
                        response = requests.post(
                            callback_url, json=payload, timeout=10)

                        if response.status_code in [200, 404, 400]:
                            # 200 = OK, 404 = Res not found (maybe deleted), 400 = invalid
                            # We mark as completed to avoid infinite loop
                            tasks_collection.update_one(
                                {"_id": task_id},
                                {"$set": {"status": "completed", "processedAt": datetime.utcnow(
                                ), "response": response.text}}
                            )
                            self.stdout.write(self.style.SUCCESS(
                                f"✅ Callback success for {reservation_id}"))
                        else:
                            # 500 error, maybe retry later? For now mark as failed
                            tasks_collection.update_one(
                                {"_id": task_id},
                                {"$set": {"status": "failed", "processedAt": datetime.utcnow(
                                ), "error": f"Status {response.status_code}"}}
                            )
                            self.stdout.write(self.style.ERROR(
                                f"❌ Callback failed: {response.status_code}"))

                    except Exception as req_err:
                        self.stdout.write(self.style.ERROR(
                            f"❌ Network error: {req_err}"))
                        # Mark failed or retry count could be implemented here
                        tasks_collection.update_one(
                            {"_id": task_id},
                            {"$set": {
                                "status": "error", "processedAt": datetime.utcnow(), "error": str(req_err)}}
                        )

                # Sleep for 60 seconds before next check
                time.sleep(60)

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Stopping scheduler..."))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Loop Error: {e}"))
                time.sleep(60)
