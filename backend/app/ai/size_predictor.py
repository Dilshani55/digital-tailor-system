class SizePredictor:
    def estimate_standard_size(self, measurements):
        """
        Estimates standard garment size based on bust, waist, hip measurements.
        """
        bust = measurements.get('bust', 88)
        if bust < 84:
            return 'XS'
        elif bust < 92:
            return 'S'
        elif bust < 100:
            return 'M'
        elif bust < 108:
            return 'L'
        else:
            return 'XL'
