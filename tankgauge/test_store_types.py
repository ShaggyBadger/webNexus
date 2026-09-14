from django.db import IntegrityError, transaction
from django.test import TestCase

from tankgauge.models import StoreType


class StoreTypeTests(TestCase):
    def test_store_type_has_a_unique_name(self):
        store_type = StoreType.objects.create(name="7-Eleven")

        self.assertEqual(str(store_type), "7-Eleven")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StoreType.objects.create(name="7-Eleven")
