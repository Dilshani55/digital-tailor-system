from mongoengine import Document, ReferenceField, FloatField, StringField, DateTimeField
from datetime import datetime, timezone
from app.models.user import User
from app.models.pattern_result import PatternResult

# Where a traditional estimate came from. Kept as a closed list so the study data can be grouped.
ESTIMATE_SOURCES = ("tailor", "manual_calculation", "shop_rule_of_thumb", "other")


class FabricComparison(Document):
    """
    Evaluation instrument (proposal §4.4 / §4.6.2): one traditional fabric estimate for a saved
    pattern, entered by a person, next to the system's estimate for the SAME fabric width and
    cutting mode. The system values are recomputed by the real nesting code when the entry is made;
    the traditional value is exactly what was entered. Nothing here is estimated or defaulted.
    """
    meta = {'collection': 'fabric_comparisons', 'indexes': ['user_id', 'pattern_id']}

    user_id = ReferenceField(User, required=True)
    pattern_id = ReferenceField(PatternResult, required=True)

    fabric_width_cm = FloatField(required=True)
    cutting_mode = StringField(required=True)                 # auto | folded | open, as requested
    system_cutting_mode = StringField(required=True)          # mode the nesting actually used
    system_purchase_m = FloatField(required=True)             # purchasing_recommended_m
    system_layout_length_cm = FloatField(required=True)       # marker length
    system_utilisation_percent = FloatField()

    traditional_estimate_m = FloatField(required=True)
    estimate_source = StringField(required=True, choices=ESTIMATE_SOURCES)
    estimator_label = StringField(max_length=40)              # pseudonym such as "Tailor A" — no real names
    notes = StringField(max_length=500)

    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    # Derived only from the two stored numbers above.
    @property
    def difference_m(self):
        return round(self.traditional_estimate_m - self.system_purchase_m, 3)

    @property
    def relative_difference_percent(self):
        return round(100.0 * self.difference_m / self.traditional_estimate_m, 1)
