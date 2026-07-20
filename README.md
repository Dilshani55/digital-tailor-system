# AI-Assisted Web-Based Digital Tailor System for Custom Clothing Fit and Fabric Waste Reduction

**Student:** D N M Vitharana | Index: 28404  
**Supervisor:** Mr. Anton Jayakody  
**Programme:** BSc. (Hons) in Software Engineering — NSBM Green University  

---

## 📌 Overview

This research project aims to build a web-based system that uses Artificial Intelligence to automate the process of generating custom garment patterns and calculating the exact amount of fabric needed — replacing traditional manual tailoring methods.

Today, custom garment creation relies heavily on manual body measurement, manual fabric estimations, and paper drafting. This process depends heavily on tailor experience, leads to fabric over-cut and waste, and is inaccessible to non-expert users who discover garment designs online. This system solves all three problems by automating garment feature extraction, 2D drafting block generation, fabric nesting optimization, and downloadable PDF pattern generation.

---

## ⚙️ System Architecture & Workflow

1. **Garment Feature Extraction (Vision AI)**
   - Upload a single front-view photo of a lady's casual garment (blouses, T-shirts, crop tops).
   - **YOLOv8** model (trained on DeepFashion2 dataset) detects structural features: neckline type, sleeve shape, dart locations, seam placements.

2. **Parametric Pattern Drafting**
   - Inputs: Detected features + user body measurements (bust, waist, hip, height).
   - Python parametric algorithm generates 2D drafting blocks according to **Winifred Aldrich's Metric Pattern Cutting** standards.

3. **Fabric Waste Minimization (2D Nesting)**
   - 2D nesting algorithm arranges pattern pieces on a virtual fabric roll/rectangle.
   - Computes minimum required yardage to minimize textile off-cuts.

4. **PDF Pattern & Guide Generation**
   - **ReportLab** generates a professional, print-ready PDF drafting guide and pattern for tailor or DIY assembly.

---

## 🛠 Tech Stack

- **Computer Vision / AI**: YOLOv8, DeepFashion2 Dataset
- **Drafting & Geometry Engine**: Python Parametric Algorithm (Winifred Aldrich Metric Pattern Standards)
- **Nesting Engine**: 2D Combinatorial Nesting Algorithm
- **PDF Generation**: ReportLab
- **Frontend**: React
- **Backend API**: Flask (Python)
- **Database**: MongoDB

---

## 🎯 Research Scope & Significance

- **Scope**: Ladies' casual garments (blouses, T-shirts, crop tops) from a single front-view photo.
- **Novelty**: Integrates Computer Vision (feature detection), Applied Fashion Geometry (Aldrich parametric drafting), and Combinatorial Optimization (fabric nesting) into a single end-to-end web pipeline.
- **Environmental Impact**: Reduces fabric off-cut waste at the custom tailoring stage, promoting sustainable practices in fashion software engineering.
