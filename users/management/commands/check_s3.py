"""
Management command to verify S3 storage is configured and reachable.

Usage:
    python manage.py check_s3

Performs a full round-trip against the *default* (media) storage backend:
write -> read back -> build public URL -> delete. Also prints the resolved
storage/config so misconfigurations are obvious before deploying.
"""

import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage, storages
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verify that S3 (or the active default storage) works end-to-end."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Do not delete the test file after a successful upload.",
        )

    def handle(self, *args, **options):
        use_s3 = getattr(settings, "USE_S3", False)
        backend = default_storage.__class__.__name__

        self.stdout.write(self.style.MIGRATE_HEADING("Storage configuration"))
        self.stdout.write(f"  USE_S3            = {use_s3}")
        self.stdout.write(f"  default backend   = {backend}")
        self.stdout.write(f"  MEDIA_URL         = {settings.MEDIA_URL}")
        self.stdout.write(f"  STATIC_URL        = {settings.STATIC_URL}")

        if use_s3:
            bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
            region = getattr(settings, "AWS_S3_REGION_NAME", None)
            domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
            self.stdout.write(f"  bucket            = {bucket}")
            self.stdout.write(f"  region            = {region}")
            self.stdout.write(f"  custom_domain     = {domain}")
            if not all([bucket, getattr(settings, "AWS_ACCESS_KEY_ID", None),
                        getattr(settings, "AWS_SECRET_ACCESS_KEY", None)]):
                raise CommandError(
                    "USE_S3 is True but AWS credentials/bucket are not fully set. "
                    "Check AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, "
                    "AWS_STORAGE_BUCKET_NAME."
                )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "  USE_S3 is False -> testing local filesystem storage. "
                    "Set USE_S3=True to validate the real bucket."
                )
            )

        test_name = f"_s3_healthcheck/{uuid.uuid4().hex}.txt"
        payload = b"findmyworker s3 healthcheck"

        self.stdout.write(self.style.MIGRATE_HEADING("\nRound-trip test"))
        try:
            saved_name = default_storage.save(test_name, ContentFile(payload))
            self.stdout.write(self.style.SUCCESS(f"  write OK -> {saved_name}"))

            with default_storage.open(saved_name) as fh:
                read_back = fh.read()
            if read_back != payload:
                raise CommandError("Read-back content does not match what was written.")
            self.stdout.write(self.style.SUCCESS("  read  OK -> content matches"))

            url = default_storage.url(saved_name)
            self.stdout.write(self.style.SUCCESS(f"  url   OK -> {url}"))

            if options["keep"]:
                self.stdout.write(self.style.WARNING("  delete skipped (--keep)"))
            else:
                default_storage.delete(saved_name)
                self.stdout.write(self.style.SUCCESS("  delete OK"))
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Storage round-trip failed: {exc!r}")

        try:
            static_backend = storages["staticfiles"].__class__.__name__
            self.stdout.write(f"\n  staticfiles backend = {static_backend}")
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"  staticfiles backend check skipped: {exc!r}"))

        self.stdout.write(self.style.SUCCESS("\n✓ Storage is working."))
