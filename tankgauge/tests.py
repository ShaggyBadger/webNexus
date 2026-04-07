from django.test import TestCase
from tankgauge.models import Store, TankType, StoreTankMapping, TankChart
from tankgauge.logic.tank_lookup import get_store_and_preset_status, get_tank_mapping

class TankLookupTests(TestCase):
    def setUp(self):
        # Create a standard store
        self.store_std = Store.objects.create(
            store_num=6949,
            store_name="7-11 Standard Test",
            city="Test City",
            state="TS"
        )
        
        # Create another store
        self.store_other = Store.objects.create(
            store_num=1234,
            store_name="Other Store",
            city="Other City",
            state="OC"
        )
        
        # Create Tank Types
        self.tank_type_reg = TankType.objects.create(
            name="10K Gallon Regular",
            capacity=10000,
            max_depth=120
        )
        self.tank_type_dsl = TankType.objects.create(
            name="5K Gallon Diesel",
            capacity=5000,
            max_depth=90
        )
        
        # Create Mappings for 7-11 Standard
        StoreTankMapping.objects.create(
            store=self.store_std,
            tank_type=self.tank_type_reg,
            fuel_type="regular"
        )
        
        # Create Mappings for Other Store
        StoreTankMapping.objects.create(
            store=self.store_other,
            tank_type=self.tank_type_dsl,
            fuel_type="diesel"
        )

    def test_get_store_and_preset_status_std(self):
        store, is_preset = get_store_and_preset_status("7-11_STD")
        self.assertEqual(store.store_num, 6949)
        self.assertTrue(is_preset)

    def test_get_store_and_preset_status_normal(self):
        store, is_preset = get_store_and_preset_status("1234")
        self.assertEqual(store.store_num, 1234)
        self.assertFalse(is_preset)

    def test_get_store_and_preset_status_not_found(self):
        store, is_preset = get_store_and_preset_status("9999")
        self.assertNil = self.assertIsNone(store)
        self.assertFalse(is_preset)

    def test_get_tank_mapping_success(self):
        store = Store.objects.get(store_num=1234)
        mapping = get_tank_mapping(store, "diesel")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.tank_type.name, "5K Gallon Diesel")

    def test_get_tank_mapping_case_insensitive(self):
        store = Store.objects.get(store_num=1234)
        mapping = get_tank_mapping(store, "DIESEL")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.tank_type.name, "5K Gallon Diesel")

    def test_get_tank_mapping_not_found(self):
        store = Store.objects.get(store_num=1234)
        mapping = get_tank_mapping(store, "regular")
        self.assertIsNone(mapping)
