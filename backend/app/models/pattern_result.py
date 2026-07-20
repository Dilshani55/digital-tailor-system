class PatternResultModel:
    def __init__(self, user_id, design_image_id, drafting_block_data, nesting_efficiency, required_fabric_yardage):
        self.user_id = user_id
        self.design_image_id = design_image_id
        self.drafting_block_data = drafting_block_data
        self.nesting_efficiency = nesting_efficiency
        self.required_fabric_yardage = required_fabric_yardage

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "design_image_id": self.design_image_id,
            "drafting_block_data": self.drafting_block_data,
            "nesting_efficiency": self.nesting_efficiency,
            "required_fabric_yardage": self.required_fabric_yardage
        }
