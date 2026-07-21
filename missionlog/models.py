from django.db import models
from django.conf import settings


class FuelType(models.Model):
    """
    OPERATIONAL STANDARDIZATION:
    Prevents free-form typos (e.g. 'reg', 'REG', 'regular') and provides
    consistent operational color-coding across tactical interfaces.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Standardized name (e.g., Regular, Premium, Diesel).",
    )
    abbreviation = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        help_text="Short code for DMS tags and filenames (e.g., RUL, DSL, PUL).",
    )
    color_name = models.CharField(
        max_length=50, blank=True, null=True, help_text="Visual identifier name."
    )
    color_hex = models.CharField(
        max_length=7, blank=True, null=True, help_text="RGB Hex color (e.g., #8da35d)."
    )

    class Meta:
        verbose_name = "Fuel Type"
        verbose_name_plural = "Fuel Types"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Mission(models.Model):
    """
    TACTICAL MISSION LOG (ShiftData):
    The root operational entry for a single field agent's duty period.
    Tracks logistics metrics, mileage, pay-rate indicators, and cargo tasks.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="missions"
    )
    shift_start = models.DateTimeField(help_text="Duty log trigger time.")
    shift_end = models.DateTimeField(
        null=True, blank=True, help_text="Mission complete sign-off time."
    )

    # Mileage Tracking
    start_miles = models.IntegerField(
        null=True, blank=True, help_text="Starting vehicle odometer reading."
    )
    end_miles = models.IntegerField(
        null=True, blank=True, help_text="Ending vehicle odometer reading."
    )

    # Aggregated Stats
    total_stops = models.IntegerField(
        default=0, help_text="Count of individual stop events."
    )
    hours_on_duty = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total duty hours logged.",
    )
    hours_on_duty_not_driving = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total on-duty hours where the truck was not being driven.",
    )
    is_completed = models.BooleanField(
        default=False, help_text="True if Jocko 'Mission Complete' protocol executed."
    )

    notes = models.TextField(
        blank=True, null=True, help_text="General shift debrief observations."
    )

    class Meta:
        verbose_name = "Mission"
        verbose_name_plural = "Missions"
        ordering = ["-shift_start"]

    def __str__(self):
        local_start = self.shift_start.strftime("%Y-%m-%d @ %H:%M")
        status = "COMPLETED" if self.is_completed else "ACTIVE"
        return f"Mission of {local_start} [{status}] - {self.user.username}"

    @property
    def total_miles(self):
        if self.end_miles is not None and self.start_miles is not None:
            return self.end_miles - self.start_miles
        return 0


class OrderNumber(models.Model):
    """
    ORDER NUMBER LOG:
    The overarching job container. One order can contain multiple POs.
    """

    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name="order_numbers",
        help_text="Associated shift mission.",
    )
    order_number = models.CharField(
        max_length=100, help_text="Overarching Job/Order ID.", unique=True
    )

    class Meta:
        verbose_name = "Order Number"
        verbose_name_plural = "Order Numbers"

    def __str__(self):
        return f"Order #{self.order_number} (Mission: {self.mission.id})"


class PurchaseOrder(models.Model):
    """
    PURCHASE ORDER LOG (PoData):
    Represents a single commercial PO number containing multiple retail loads/deliveries.
    Now linked to an overarching OrderNumber.
    """

    order_parent = models.ForeignKey(
        OrderNumber,
        on_delete=models.CASCADE,
        related_name="purchase_orders",
        null=True,
        blank=True,
        help_text="Parent overarching order.",
    )
    po_number = models.IntegerField(
        help_text="Primary PO identifier from commercial invoice.", unique=True
    )

    class Meta:
        verbose_name = "Purchase Order"
        verbose_name_plural = "Purchase Orders"
        ordering = ["po_number"]

    def __str__(self):
        return f"PO #{self.po_number} (Order: {self.order_parent.order_number})"


class LoadDelivery(models.Model):
    """
    LOAD DELIVERY LOG (LoadData):
    Represents a specific volume delivery to a physical store.
    Captures high-precision BOL metrics, temperature adjustments, and tank chart stick depth levels.
    """

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="loads",
        help_text="Parent Purchase Order.",
    )
    fuel_type = models.ForeignKey(
        FuelType,
        on_delete=models.PROTECT,
        related_name="deliveries",
        help_text="Associated standardized fuel classification.",
    )
    store = models.ForeignKey(
        "tankgauge.Store",
        on_delete=models.PROTECT,
        related_name="deliveries",
        null=True,
        blank=True,
        help_text="Physical Store Location anchor.",
    )
    price_at_store = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Pump retail price at store.",
    )

    # BOL Intelligence
    gross_gal = models.IntegerField(
        null=True, blank=True, help_text="Gross volume (gallons) from BOL."
    )
    net_gal = models.IntegerField(
        null=True,
        blank=True,
        help_text="Net volume (gallons) from BOL adjusted for temperature.",
    )
    temp = models.FloatField(
        null=True, blank=True, help_text="Fuel temperature (Fahrenheit) logged on BOL."
    )
    grav = models.FloatField(
        null=True, blank=True, help_text="Specific gravity (GRAV) logged on BOL."
    )

    # Store Tank Status metrics
    start_inches = models.FloatField(
        null=True, blank=True, help_text="Opening physical stick measurement (inches)."
    )
    start_gallons = models.FloatField(
        null=True, blank=True, help_text="Opening volume (gallons)."
    )
    end_inches = models.FloatField(
        null=True, blank=True, help_text="Closing physical stick measurement (inches)."
    )
    end_gallons = models.FloatField(
        null=True, blank=True, help_text="Closing volume (gallons)."
    )

    class Meta:
        verbose_name = "Load Delivery"
        verbose_name_plural = "Load Deliveries"

    def __str__(self):
        store_lbl = self.store.store_num if self.store else "Unlisted Store"
        return f"Load {self.fuel_type} to Store {store_lbl} (PO: {self.purchase_order.po_number})"


class TruckFuelLog(models.Model):
    """
    TRUCK FUEL LOG:
    Allows multiple logs of fuel purchases made for the semi-truck itself during a single shift.
    """

    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name="fuel_logs",
        help_text="Parent shift mission.",
    )
    gallons = models.DecimalField(
        max_digits=10, decimal_places=3, help_text="Truck fuel gallons pumped."
    )
    price_per_gallon = models.DecimalField(
        max_digits=10, decimal_places=3, help_text="Pump cost per gallon."
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, help_text="System logged timestamp."
    )

    class Meta:
        verbose_name = "Truck Fuel Log"
        verbose_name_plural = "Truck Fuel Logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.gallons} gal at ${self.price_per_gallon}/gal (Mission ID: {self.mission.id})"
