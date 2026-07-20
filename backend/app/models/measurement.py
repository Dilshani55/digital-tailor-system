class MeasurementModel:
    def __init__(self, user_id, bust, waist, hip, height, unit='cm'):
        self.user_id = user_id
        self.bust = bust
        self.waist = waist
        self.hip = hip
        self.height = height
        self.unit = unit

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "bust": self.bust,
            "waist": self.waist,
            "hip": self.hip,
            "height": self.height,
            "unit": self.unit
        }
