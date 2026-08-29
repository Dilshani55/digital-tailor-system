# TailorAI — REST API Endpoint Documentation

All requests should have the `Content-Type: application/json` header unless uploading files. Protected routes require a valid JWT bearer token in the `Authorization` header:
`Authorization: Bearer <your-jwt-token>`

---

## 1. Authentication (`/api/auth`)

### POST `/api/auth/register`
Creates a new user account.
* **Payload**:
  ```json
  {
    "full_name": "Alice Smith",
    "email": "alice@example.com",
    "password": "securepassword123"
  }
  ```
* **Response (201 Created)**:
  ```json
  {
    "message": "Registration successful",
    "user_id": "64d0a1b2...",
    "full_name": "Alice Smith",
    "email": "alice@example.com"
  }
  ```

### POST `/api/auth/login`
Authenticates user credentials and returns a JWT access token.
* **Payload**:
  ```json
  {
    "email": "alice@example.com",
    "password": "securepassword123"
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "message": "Login successful",
    "token": "eyJhbGciOi...",
    "user": {
      "id": "64d0a1b2...",
      "full_name": "Alice Smith",
      "email": "alice@example.com"
    }
  }
  ```

### GET `/api/auth/profile` (Protected)
Retrieves the logged-in user profile.
* **Response (200 OK)**:
  ```json
  {
    "id": "64d0a1b2...",
    "full_name": "Alice Smith",
    "email": "alice@example.com",
    "created_at": "2026-08-26 01:30:14"
  }
  ```

---

## 2. Customer & Measurement Profiles (`/api/measurements`)

### POST `/api/measurements/` (Protected)
Creates a new client measurement profile.
* **Payload**:
  ```json
  {
    "client_name": "Jane Doe",
    "bust_cm": 88.0,
    "waist_cm": 70.0,
    "hip_cm": 94.0,
    "height_cm": 162.0,
    "fabric_type": "woven",
    "unit": "cm"
  }
  ```
* **Response (201 Created)**:
  ```json
  {
    "message": "Measurement profile created",
    "profile_id": "64d0b8c2..."
  }
  ```

### GET `/api/measurements/` (Protected)
Retrieves all customer measurement profiles for the logged-in user.
* **Response (200 OK)**:
  ```json
  {
    "total": 1,
    "profiles": [
      {
        "profile_id": "64d0b8c2...",
        "client_name": "Jane Doe",
        "bust_cm": 88.0,
        "waist_cm": 70.0,
        "hip_cm": 94.0,
        "height_cm": 162.0,
        "fabric_type": "woven",
        "created_at": "2026-08-26 01:31:00"
      }
    ]
  }
  ```

### GET `/api/measurements/{id}` (Protected)
Gets a single measurement profile.

### PUT `/api/measurements/{id}` (Protected)
Updates details of an existing profile.

### DELETE `/api/measurements/{id}` (Protected)
Removes a measurement profile.

---

## 3. Garment Image Upload (`/api/images`)

### POST `/api/images/upload` (Protected)
Uploads a lady's garment image file (`multipart/form-data`).
* **Form Field**: `image` (JPEG/PNG/WEBP, max 16MB)
* **Response (201 Created)**:
  ```json
  {
    "message": "Image uploaded successfully",
    "image_id": "64d0c9f1...",
    "filename": "img_178768014.png",
    "dimensions": { "width": 800, "height": 600 },
    "status": "uploaded — ready for analysis"
  }
  ```

### POST `/api/images/{id}/analyse` (Protected)
Runs the YOLOv8 model (or fallback heuristic service) on the uploaded image to detect styling features.
* **Response (200 OK)**:
  ```json
  {
    "message": "Image analysed successfully",
    "image_id": "64d0c9f1...",
    "detected_features": {
      "garment_type": "blouse",
      "neckline": "round neck",
      "sleeves": "short sleeve",
      "darts": "bust dart",
      "seams": "side seam",
      "is_mock": true
    },
    "confidence_score": 0.92,
    "status": "analysis complete — ready for pattern generation"
  }
  ```

---

## 4. Pattern Calculations (`/api/patterns`)

### POST `/api/patterns/generate` (Protected)
Drafts parametric 2D pattern piece block coordinates based on measurements and design features.
* **Payload**:
  ```json
  {
    "measurement_id": "64d0b8c2...",
    "image_id": "64d0c9f1...",
    "detected_features": {
      "garment_type": "blouse",
      "neckline": "round neck",
      "sleeves": "short sleeve",
      "darts": "bust dart",
      "seams": "side seam"
    }
  }
  ```
* **Response (201 Created)**:
  ```json
  {
    "message": "Pattern generated successfully",
    "pattern_id": "64d0d4e3...",
    "session_id": "64d0d4a1...",
    "garment_type": "blouse",
    "fabric_type": "woven",
    "pieces_count": 3,
    "pieces": [
      { "name": "Back Bodice", "width_cm": 24.5, "height_cm": 58.0, "seam_allowance_cm": 1.5 },
      { "name": "Front Bodice", "width_cm": 25.0, "height_cm": 58.0, "seam_allowance_cm": 1.5 },
      { "name": "Sleeve", "width_cm": 20.0, "height_cm": 25.0, "seam_allowance_cm": 1.5 }
    ],
    "measurements_used": { ... },
    "construction_notes": [ ... ]
  }
  ```

---

## 5. Nesting & PDF Export (`/api/export`)

### POST `/api/export/yardage/{pattern_id}` (Protected)
Runs the 2D nesting/bin-packing optimizer to arrange pattern pieces on the fabric roll width and computes minimum length.
* **Payload**:
  ```json
  {
    "fabric_width_cm": 114
  }
  ```
* **Response (200 OK)**:
  ```json
  {
    "message": "Yardage calculated successfully",
    "pattern_id": "64d0d4e3...",
    "fabric_width_cm": 114,
    "fabric_length_cm": 58.0,
    "yardage_metres": 0.58,
    "yardage_yards": 0.63,
    "utilisation_percent": 78.7,
    "waste_cm2": 1412.5,
    "total_pieces": 6
  }
  ```

### POST `/api/export/pdf/{pattern_id}` (Protected)
Generates the Winifred Aldrich drafting guide layout PDF.
* **Response (201 Created)**:
  ```json
  {
    "message": "PDF generated successfully",
    "export_id": "64d0e5b2...",
    "pattern_id": "64d0d4e3...",
    "filename": "pattern_64d0d4e3.pdf",
    "download_url": "/api/export/download/64d0e5b2"
  }
  ```

### GET `/api/export/download/{export_id}` (Protected)
Downloads the generated PDF file directly as an attachment.
