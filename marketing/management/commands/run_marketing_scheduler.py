"""Phase 2 seam — marketing publish scheduler (NOT active in Phase 1).

This command is intentionally a stub. Phase 1 ends at a reviewable ``draft``;
publishing to Instagram/YouTube is gated behind Meta App Review and is deferred.

When Phase 2 lands, model this on
``whatsapp_integration/management/commands/run_reservation_scheduler.py``:

    1. Poll the shared ``ScheduledTask`` collection for documents with
       ``type == "marketing_publish"`` whose ``scheduledAt`` (mirrored from the
       ``MarketingContent.scheduledAt`` field already written by the async view)
       is due.
    2. For each due task, load the approved ``MarketingContent`` doc, then call
       ``InstagramService.create_media_container(composedImageUrl, caption)``
       followed by ``InstagramService.publish_media(creation_id)``
       (both already implemented in ``marketing/services.py``).
    3. On success, set ``MarketingContent.status = "published"``; on failure,
       record the error and leave the task for retry.

Credentials must be masked in logs (same pattern as the reservation scheduler).
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "[Phase 2 stub] Will poll ScheduledTask for 'marketing_publish' and publish via InstagramService."

    def handle(self, *args, **options):
        # TODO(Phase 2): Implement polling + InstagramService.publish_media once
        # Meta App Review approves the publishing permissions. See module docstring.
        self.stdout.write(self.style.WARNING(
            "run_marketing_scheduler is a Phase 2 stub and performs no publishing yet."))
        logger.info("run_marketing_scheduler invoked while still a Phase 1 stub; no-op.")
