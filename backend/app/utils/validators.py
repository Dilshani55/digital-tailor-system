def validate_measurements(data):
    required_keys = ['bust', 'waist', 'hip', 'height']
    errors = []
    for key in required_keys:
        if key not in data or not isinstance(data[key], (int, float)):
            errors.append(f"Invalid or missing measurement for '{key}'")
    return len(errors) == 0, errors
