from django.test import SimpleTestCase, TestCase

from genericcharts.pipeline.dataclasses import SelectionSpec
from genericcharts.pipeline.package import build_package_data
from genericcharts.pipeline.selectors import (
    select_generated_tanks,
    select_official_charts,
    select_stores,
)
from siteintel.models import Location, LocationType
from tankgauge.models import (
    Store,
    StoreTankMapping,
    TankChart,
    TankEstimation,
    TankType,
    VirtualTankEstimation,
    StoreType,
)


class SelectionSpecTests(SimpleTestCase):
    def test_state_and_store_numbers_are_normalized(self):
        spec = SelectionSpec(state="  nc ", store_numbers=[12, 4, 12])

        self.assertEqual(spec.state, "NC")
        self.assertEqual(spec.store_numbers, (4, 12))
        self.assertFalse(spec.is_full)

    def test_full_is_the_default_selection(self):
        self.assertTrue(SelectionSpec().is_full)
        self.assertTrue(SelectionSpec(state="FULL").is_full)

    def test_package_scope_key_is_canonical_and_order_independent(self):
        self.assertEqual(
            SelectionSpec(state="nc", store_numbers=[12, 4, 12]).package_scope_key,
            "north-carolina-stores-4-12",
        )
        self.assertEqual(
            SelectionSpec(state="North Carolina").package_scope_key,
            "north-carolina",
        )
        self.assertEqual(SelectionSpec().package_scope_key, "full")


class GenericChartSelectorTests(TestCase):
    def setUp(self):
        self.north_store = Store.objects.create(
            store_num=101,
            riso_num=1001,
            store_name="North Fuel",
            state="NC",
            store_type="Exxon",
            city="Raleigh",
        )
        self.virginia_store = Store.objects.create(
            store_num=202,
            store_name="Virginia Fuel",
            state="VA",
            store_type="Mobil",
            city="Richmond",
        )
        self.tank_type = TankType.objects.create(
            name="12k96",
            capacity=12000,
            max_depth=96,
        )
        self.exxon_type = StoreType.objects.create(name="Exxon")
        self.mobil_type = StoreType.objects.create(name="Mobil")
        self.mapping = StoreTankMapping.objects.create(
            store=self.north_store,
            tank_type=self.tank_type,
            fuel_type="Regular",
            tank_index=1,
        )
        TankEstimation.objects.create(
            tank_mapping=self.mapping,
            radius=48,
            length=100,
            confidence=0.9,
            sample_count=10,
            algorithm_version="test",
            is_active=True,
        )
        VirtualTankEstimation.objects.create(
            store=self.north_store,
            fuel_type="Regular",
            tank_index=1,
            radius=40,
            length=90,
            confidence=1.0,
            sample_count=20,
            algorithm_version="virtual-test",
            is_active=True,
        )
        VirtualTankEstimation.objects.create(
            store=self.virginia_store,
            fuel_type="Diesel",
            tank_index=2,
            radius=36,
            length=80,
            confidence=0.7,
            sample_count=8,
            algorithm_version="virtual-test",
            is_active=True,
        )

    def test_state_filter_is_case_insensitive_and_returns_dataclasses(self):
        stores = select_stores(SelectionSpec(state="north carolina"))

        self.assertEqual([store.store_number for store in stores], [101])
        self.assertEqual(stores[0].tanks[0].tank_type_name, "12k96")
        self.assertEqual(stores[0].tanks[0].capacity_gallons, 12000)

    def test_state_filter_matches_abbreviation_and_full_name_variants(self):
        Store.objects.create(store_num=303, state="north carolina")
        Store.objects.create(store_num=304, state="no")

        stores = select_stores(SelectionSpec(state="NC"))

        self.assertEqual([store.store_number for store in stores], [101, 303, 304])

    def test_full_and_store_allowlist_are_supported(self):
        all_stores = select_stores(SelectionSpec())
        allowlisted = select_stores(SelectionSpec(store_numbers=(202,)))

        self.assertEqual([store.store_number for store in all_stores], [101, 202])
        self.assertEqual([store.store_number for store in allowlisted], [202])

    def test_store_type_ids_filter_existing_store_text_values(self):
        stores = select_stores(SelectionSpec(store_type_ids=(self.exxon_type.id,)))

        self.assertEqual([store.store_number for store in stores], [101])

    def test_non_store_location_types_are_excluded(self):
        rack_type = LocationType.objects.create(name="Fuel Rack")
        yard_type = LocationType.objects.create(name="Yard")
        rack_location = Location.objects.create(name="Rack", location_type=rack_type)
        yard_location = Location.objects.create(name="Yard", location_type=yard_type)
        Store.objects.create(store_num=303, state="NC", location=rack_location)
        Store.objects.create(store_num=304, state="NC", location=yard_location)

        stores = select_stores(SelectionSpec())

        self.assertEqual([store.store_number for store in stores], [101, 202])

    def test_mapped_geometry_wins_over_virtual_geometry(self):
        tanks = select_generated_tanks(SelectionSpec(state="NC"))

        self.assertEqual(len(tanks), 1)
        self.assertEqual(tanks[0].source, "mapped_estimation")
        self.assertEqual(tanks[0].radius_inches, 48.0)
        self.assertEqual(tanks[0].curve[-1].depth_inches, 96)

    def test_virtual_geometry_is_used_for_unmapped_tanks(self):
        tanks = select_generated_tanks(SelectionSpec(state="VA"))

        self.assertEqual(len(tanks), 1)
        self.assertEqual(tanks[0].source, "virtual_estimation")
        self.assertEqual(tanks[0].tank_index, 2)

    def test_invalid_mapped_geometry_allows_virtual_fallback(self):
        TankEstimation.objects.filter(tank_mapping=self.mapping).update(radius=0)

        tanks = select_generated_tanks(SelectionSpec(state="NC"))

        self.assertEqual(len(tanks), 1)
        self.assertEqual(tanks[0].source, "virtual_estimation")

    def test_official_charts_follow_selected_tank_types_and_stores(self):
        TankChart.objects.create(
            tank_type=self.tank_type,
            inches=1,
            gallons=10,
            tank_name="12k96",
            is_official=True,
        )
        TankChart.objects.create(
            store=self.virginia_store,
            tank_index=2,
            inches=1,
            gallons=20,
            tank_name="VA custom",
            is_official=True,
        )

        charts = select_official_charts(SelectionSpec(state="NC"))

        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0].tank_name, "12k96")


class GenericChartPackageTests(TestCase):
    def test_package_preserves_multiple_unindexed_mappings(self):
        store = Store.objects.create(store_num=7900, state="NC", city="Aberdeen")
        tank_type = TankType.objects.create(name="12k91", capacity=12000, max_depth=91)
        for fuel_type in ("regular", "diesel", "kerosene"):
            StoreTankMapping.objects.create(
                store=store,
                tank_type=tank_type,
                fuel_type=fuel_type,
                tank_index=None,
            )

        package = build_package_data(
            selection=SelectionSpec(store_numbers=(7900,)),
            volume_gap_percent=3,
            near_duplicate_tolerance_percent=1,
            outlier_multiplier=2,
        )

        self.assertEqual(
            sorted(entry.fuel_type for entry in package.store_map[store.id].values()),
            ["diesel", "kerosene", "regular"],
        )
