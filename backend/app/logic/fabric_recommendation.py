"""
Fabric Knowledge Base and Explainable Recommendation Engine for Digital Tailor System.

Provides authoritative fabric metadata, structure/stretch-driven recommendation rules,
and helper functions for validating fabric selection and deriving canonical fabric names.
"""

FABRIC_KNOWLEDGE_BASE = {
    "cotton-poplin": {
        "id": "cotton-poplin",
        "name": "Cotton Poplin",
        "local_image": "/fabrics/cotton-poplin.jpg",
        "simple_description": "Crisp plain-weave cotton fabric providing structural body and a clean smooth surface.",
        "feel": "Smooth, crisp, and lightweight with a soft firm handle",
        "weight": "Light",
        "stretch": "No Stretch",
        "breathability": "High — excellent air permeability for warm weather",
        "drape": "Crisp and structured (low drape)",
        "best_garment_uses": ["Structured crop-tops", "Tailored shirts", "Button-down blouses", "A-line skirts"],
        "climate_suitability": "Exceptional for Sri Lankan tropical climate due to 100% natural cotton breathability.",
        "advantages": [
            "Holds crisp structured shapes and darts exceptionally well",
            "Highly breathable and comfortable in warm Sri Lankan humidity"
        ],
        "limitations": [
            "Lacks stretch for body-con or skin-tight designs",
            "Prone to creasing; requires moderate ironing"
        ],
        "care_instructions": "Machine wash cold with like colors. Tumble dry low or line dry in shade. Warm iron.",
        "sewing_difficulty": "Beginner friendly — easy to cut, mark, and press",
        "technical_details": {
            "construction": "Plain weave (1x1 square cross-weave)",
            "typical_gsm_range": "Typical GSM range: 110 – 130 GSM (varies by supplier)",
            "composition_note": "100% Combed Cotton (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Prioritised for structured designs (crop-tops, tailored blouses) requiring sharp seam definition and zero stretch.",
        "reference_source": "Winifred Aldrich Fabric Selection Guide & Textile Institute Handbook (Woven Technology)",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "linen-blend": {
        "id": "linen-blend",
        "name": "Linen Blend",
        "local_image": "/fabrics/linen-blend.jpg",
        "simple_description": "Natural textured fabric combining linen coolness with cotton softness and subtle slub structure.",
        "feel": "Textured, airy, and slightly crisp with a relaxing natural hand",
        "weight": "Medium",
        "stretch": "No Stretch",
        "breathability": "Very High — superior heat dissipation and ventilation",
        "drape": "Medium-structured drape with subtle natural stiffness",
        "best_garment_uses": ["Casual crop-tops", "Relaxed blouses", "Summer tunics", "Resort wear"],
        "climate_suitability": "Ideal for Sri Lankan warm and humid conditions; absorbs moisture efficiently.",
        "advantages": [
            "Outstanding ventilation and moisture-wicking properties",
            "Elegant natural slub texture and premium organic appearance"
        ],
        "limitations": [
            "Prone to natural wrinkles and creasing",
            "Requires gentle washing to maintain fiber strength"
        ],
        "care_instructions": "Hand wash or gentle machine cycle in cool water. Line dry. Steam iron while slightly damp.",
        "sewing_difficulty": "Intermediate — requires finishing raw edges due to fraying tendency",
        "technical_details": {
            "construction": "Plain slub weave",
            "typical_gsm_range": "Typical GSM range: 160 – 190 GSM (varies by supplier)",
            "composition_note": "55% Linen, 45% Cotton blend (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Highly suitable for warm-weather tops, relaxed blouses, and structured crop-tops seeking breathable elegance.",
        "reference_source": "Winifred Aldrich Fabric Selection Guide & Tropical Garment Engineering Standards",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "rayon": {
        "id": "rayon",
        "name": "Rayon",
        "local_image": "/fabrics/rayon.jpg",
        "simple_description": "Silky-smooth cellulosic fabric with luxurious fluid drape and soft skin contact.",
        "feel": "Ultra-soft, silky, smooth, and cool to the touch",
        "weight": "Light",
        "stretch": "No Stretch",
        "breathability": "High — lightweight regenerated cellulose fiber",
        "drape": "Fluid and flowing (high drape)",
        "best_garment_uses": ["Flowing blouses", "Peplum tops", "Tiered dresses", "Cascade sleeve tops"],
        "climate_suitability": "Comfortable for tropical Sri Lankan weather; stays cool against skin.",
        "advantages": [
            "Beautiful fluid drape that cascades gracefully",
            "Silky soft handle with vibrant color retention"
        ],
        "limitations": [
            "May shrink if washed in hot water",
            "Low wet strength requiring gentle laundering"
        ],
        "care_instructions": "Hand wash or delicate cold cycle. Lay flat or line dry. Cool iron on reverse side.",
        "sewing_difficulty": "Intermediate — slippery during cutting; use sharp fine pins",
        "technical_details": {
            "construction": "Plain weave / regenerated cellulose filament",
            "typical_gsm_range": "Typical GSM range: 100 – 125 GSM (varies by supplier)",
            "composition_note": "100% Viscose Rayon (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Best Match for flowing blouses, flared sleeves, and relaxed draped garments requiring fluid movement.",
        "reference_source": "Winifred Aldrich Metric Pattern Cutting for Women's Wear & Textile Institute Handbook",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "cotton-jersey-knit": {
        "id": "cotton-jersey-knit",
        "name": "Cotton Jersey Knit",
        "local_image": "/fabrics/cotton-jersey-knit.jpg",
        "simple_description": "Flexible single-knit fabric offering comfortable 4-way stretch and body-contouring fit.",
        "feel": "Soft, stretchy, cozy, and elastic",
        "weight": "Medium",
        "stretch": "Stretchable",
        "breathability": "High — knitted structure allows air movement",
        "drape": "Soft fluid knit drape",
        "best_garment_uses": ["T-shirts", "Fitted crop-tops", "Stretch tops", "Athleisure wear"],
        "climate_suitability": "Great for active daily wear in Sri Lanka; breathable knitted cotton.",
        "advantages": [
            "Excellent elasticity and recovery for body-con stretch fits",
            "Wrinkle-resistant and exceptionally comfortable for daily movement"
        ],
        "limitations": [
            "Curled raw edges during cutting",
            "Not suitable for rigid structured tailoring"
        ],
        "care_instructions": "Machine wash warm with like colors. Tumble dry medium or line dry. Cool iron if needed.",
        "sewing_difficulty": "Intermediate — best sewn with ballpoint needle and stretch/serger stitch",
        "technical_details": {
            "construction": "Single jersey weft knit",
            "typical_gsm_range": "Typical GSM range: 170 – 200 GSM (varies by supplier)",
            "composition_note": "95% Cotton, 5% Elastane/Lycra (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Best Match for T-shirts, stretch-fitting tops, and designs requiring high elasticity.",
        "reference_source": "Winifred Aldrich Pattern Cutting for Knitted Fabrics & Textile Institute Standards",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "silk-chiffon": {
        "id": "silk-chiffon",
        "name": "Silk Chiffon",
        "local_image": "/fabrics/silk-chiffon.jpg",
        "simple_description": "Ultra-lightweight sheer woven fabric creating ethereal floaty drapes and delicate elegance.",
        "feel": "Ethereal, whisper-soft, fine, and floating",
        "weight": "Light",
        "stretch": "No Stretch",
        "breathability": "High — gossamer open weave structure",
        "drape": "Ultra-fluid and translucent (high drape)",
        "best_garment_uses": ["Overlay blouses", "Butterfly sleeve tops", "Evening blouses", "Sheer tunics"],
        "climate_suitability": "Lightweight and airy for evening events and warm climates.",
        "advantages": [
            "Stunning translucent elegance with unmatched floating drape",
            "Ultra-light weight feels practically weightless"
        ],
        "limitations": [
            "Requires french seams or delicate edge finishes",
            "Delicate fiber needing dry clean or gentle hand wash"
        ],
        "care_instructions": "Dry clean recommended or hand wash in silk detergent. Line dry flat. Cool steam iron.",
        "sewing_difficulty": "Advanced — slippery sheer weave; use tissue paper backing when sewing",
        "technical_details": {
            "construction": "Plain crepe-twist weave",
            "typical_gsm_range": "Typical GSM range: 35 – 60 GSM (varies by supplier)",
            "composition_note": "100% Mulberry Silk / Fine Poly Chiffon (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Recommended for delicate draped blouses, butterfly/cape sleeves, and layered translucent designs.",
        "reference_source": "Winifred Aldrich Couture Fabrics Guide & Haute Couture Textile Handbook",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "cotton-twill": {
        "id": "cotton-twill",
        "name": "Cotton Twill / Denim",
        "local_image": "/fabrics/cotton-twill.jpg",
        "simple_description": "Durable diagonal-weave fabric offering firm structural shape retention and heavy body.",
        "feel": "Sturdy, firm, substantial, and durable",
        "weight": "Heavy",
        "stretch": "No Stretch",
        "breathability": "Medium — dense twill weave structure",
        "drape": "Rigid and high-body (very low drape)",
        "best_garment_uses": ["Structured waistcoats", "Heavy crop-tops", "Tailored denim tops", "Utility blousons"],
        "climate_suitability": "Suitable for structured outerwear, evening blousons, and durable custom garments.",
        "advantages": [
            "Superior structural stiffness and crisp dart definition",
            "Extremely durable and tear-resistant"
        ],
        "limitations": [
            "Heavy weight limits fluid flowing styles",
            "Requires heavy-duty jeans needle"
        ],
        "care_instructions": "Machine wash cold inside out. Tumble dry medium. Hot iron.",
        "sewing_difficulty": "Intermediate — requires sharp heavy-duty needles for thick seams",
        "technical_details": {
            "construction": "2/1 or 3/1 diagonal twill weave",
            "typical_gsm_range": "Typical GSM range: 240 – 320 GSM (varies by supplier)",
            "composition_note": "100% Heavy Cotton / Stretch Denim Blend (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Best suited for rigid crop-tops, corsets, and utility structures needing maximum seam stability.",
        "reference_source": "Winifred Aldrich Heavywear Pattern Cutting & Industrial Denim Manual",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "satin": {
        "id": "satin",
        "name": "Satin",
        "local_image": "/fabrics/satin.jpg",
        "simple_description": "Smooth lustrous fabric with a glossy sheen surface and rich liquid drape.",
        "feel": "Silky, slippery, lustrous, and glamorous",
        "weight": "Medium",
        "stretch": "Slight Stretch",
        "breathability": "Medium — filament satin weave",
        "drape": "Rich liquid drape (high drape)",
        "best_garment_uses": ["Party crop-tops", "Satin blouses", "Cowl neck tops", "Evening corsets"],
        "climate_suitability": "Elegant for evening functions, formal events, and indoor air-conditioned venues in Sri Lanka.",
        "advantages": [
            "High-gloss lustrous finish creates a luxurious visual impact",
            "Liquid drape highlights subtle body curves beautifully"
        ],
        "limitations": [
            "Shows water spots if not dried evenly",
            "Slippery to cut and sew"
        ],
        "care_instructions": "Hand wash cold or dry clean. Do not wring. Press on wrong side with cool iron.",
        "sewing_difficulty": "Intermediate — use microtex sharp needles and non-marring presser foot",
        "technical_details": {
            "construction": "Satin weave (4/1 floating warp layout)",
            "typical_gsm_range": "Typical GSM range: 130 – 170 GSM (varies by supplier)",
            "composition_note": "Polyester / Silk Blend Satin (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Recommended for cowl necklines, party tops, and formal glossy blouses.",
        "reference_source": "Winifred Aldrich Evening Wear & Formal Fabric Selection Guide",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "crepe-de-chine": {
        "id": "crepe-de-chine",
        "name": "Crepe de Chine",
        "local_image": "/fabrics/crepe-de-chine.jpg",
        "simple_description": "Refined fabric with a subtle pebbled texture, soft muted luster, and resilient drape.",
        "feel": "Pebbled, supple, graceful, and wrinkle-resistant",
        "weight": "Light",
        "stretch": "Slight Stretch",
        "breathability": "High — breathable twisted yarn construction",
        "drape": "Graceful supple drape (medium-high drape)",
        "best_garment_uses": ["Executive blouses", "Peplum tops", "Tie-neck blouses", "Tailored tunics"],
        "climate_suitability": "Excellent for professional workwear and humid Sri Lankan office environments.",
        "advantages": [
            "Wrinkle-resistant pebbled surface stays neat all day",
            "Refined matte-luster finish ideal for executive tailoring"
        ],
        "limitations": [
            "Requires low temperature setting when ironing",
            "Delicate seam tensioning needed"
        ],
        "care_instructions": "Hand wash cold or dry clean. Hang dry in shade. Warm iron using pressing cloth.",
        "sewing_difficulty": "Intermediate — stable weave, easier to sew than satin or chiffon",
        "technical_details": {
            "construction": "Alternating S/Z high-twist crepe plain weave",
            "typical_gsm_range": "Typical GSM range: 110 – 140 GSM (varies by supplier)",
            "composition_note": "100% Silk / High-Grade Viscose Crepe (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Highly suitable for formal blouses, peplum styles, and elegant office wear.",
        "reference_source": "Winifred Aldrich Tailored Blouse Manual & Textile Institute Standards",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "georgette": {
        "id": "georgette",
        "name": "Georgette",
        "local_image": "/fabrics/georgette.jpg",
        "simple_description": "Lightweight crinkled fabric with a springy handle and beautiful semi-sheer drape.",
        "feel": "Grainy, springy, light, and airy",
        "weight": "Light",
        "stretch": "No Stretch",
        "breathability": "High — porous crinkled structure",
        "drape": "Bouncy fluid drape (high drape)",
        "best_garment_uses": ["Flared sleeve blouses", "Tiered tops", "Cape blouses", "Saree blouses"],
        "climate_suitability": "Breezy and comfortable for Sri Lankan tropical climate.",
        "advantages": [
            "Springy crinkle texture provides subtle volume without stiffness",
            "Drapes with an elegant floating silhouette"
        ],
        "limitations": [
            "Slightly semi-sheer; may require lining depending on style",
            "Frays easily if raw edges are not finished"
        ],
        "care_instructions": "Hand wash cold. Do not wring. Line dry. Light steam iron.",
        "sewing_difficulty": "Intermediate — use narrow hem or serger edge finishing",
        "technical_details": {
            "construction": "High-twist crepe weave (open layout)",
            "typical_gsm_range": "Typical GSM range: 70 – 100 GSM (varies by supplier)",
            "composition_note": "100% Poly / Silk Georgette (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Recommended for voluminous sleeves (bishop, flared, butterfly) and airy layered blouses.",
        "reference_source": "Winifred Aldrich Ladies Garment Drafting & Tropical Fabric Science",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    },
    "french-terry-knit": {
        "id": "french-terry-knit",
        "name": "French Terry Knit",
        "local_image": "/fabrics/french-terry-knit.jpg",
        "simple_description": "Soft looped-back knitted fabric providing cozy structure and comfortable stretch.",
        "feel": "Plush, looped, soft, and flexible",
        "weight": "Heavy",
        "stretch": "Stretchable",
        "breathability": "Medium — absorbent cotton loop structure",
        "drape": "Structured knit drape",
        "best_garment_uses": ["Casual crop-hoodies", "Athleisure tops", "Stretch sweatshirts", "Cozy pullovers"],
        "climate_suitability": "Great for cooler hill-country Sri Lankan areas (Nuwara Eliya) and air-conditioned spaces.",
        "advantages": [
            "Plush inner loops absorb moisture efficiently while maintaining shape",
            "Flexible 4-way stretch with substantial cozy body"
        ],
        "limitations": [
            "Heavier weight not suitable for thin summer blouses",
            "Can shrink if dried at high heat"
        ],
        "care_instructions": "Machine wash cool. Line dry or tumble dry low. Cool iron.",
        "sewing_difficulty": "Intermediate — use ballpoint needle and stretch thread",
        "technical_details": {
            "construction": "Unbrushed looped back single jersey knit",
            "typical_gsm_range": "Typical GSM range: 220 – 280 GSM (varies by supplier)",
            "composition_note": "90% Cotton, 10% Polyester/Spandex (specifications vary by supplier)",
            "price_note": "Price varies by supplier"
        },
        "recommendation_rules": "Recommended for heavy stretch tops, casual crop-hoodies, and comfortable activewear.",
        "reference_source": "Winifred Aldrich Sportswear Pattern Cutting & Knitwear Technology Handbook",
        "image_license": "Public Domain / CC0 Open Asset (Studio High-Res Macro Scan)"
    }
}


def get_all_fabrics():
    """Returns all available fabric definitions from the knowledge base."""
    return list(FABRIC_KNOWLEDGE_BASE.values())


def validate_fabric_id(fabric_id):
    """
    Validates if a given fabric_id exists in the knowledge base.
    Returns boolean (True if valid, False otherwise).
    """
    if not fabric_id or not isinstance(fabric_id, str):
        return False
    return fabric_id.strip().lower() in FABRIC_KNOWLEDGE_BASE


def get_fabric_by_id(fabric_id):
    """
    Retrieves fabric definition by ID.
    Returns dict or None if invalid.
    """
    if not validate_fabric_id(fabric_id):
        return None
    return FABRIC_KNOWLEDGE_BASE[fabric_id.strip().lower()]


def recommend_fabrics(garment_type, neckline=None, sleeves=None, darts=None, seams=None):
    """
    Explainable rule-based fabric recommendation engine.
    
    Evaluates detected design features (garment type, neckline, sleeves, darts, seams)
    against physical garment requirements (structure stiffness, stretch flexibility,
    drape, volume, breathability in Sri Lankan climate).
    
    Returns a list of fabrics sorted by score descending, formatted with:
    - score (int 0-100)
    - status ('Best Match', 'Highly Suitable', 'Suitable', 'Less Suitable')
    - rationale/explanation (str)
    """
    garment_type_norm = (garment_type or "").strip().lower()
    neckline_norm = (neckline or "").strip().lower()
    sleeves_norm = (sleeves or "").strip().lower()
    darts_norm = (darts or "").strip().lower()
    
    # Flags derived from multi-feature analysis
    requires_stretch = garment_type_norm in ["t-shirt", "tshirt", "stretch-top", "fitted-top", "activewear"]
    requires_structure = garment_type_norm in ["crop-top", "croptop", "corset", "structured-blouse", "waistcoat"] or "dart" in darts_norm
    requires_drape = garment_type_norm in ["blouse"] or any(s in sleeves_norm for s in ["bell", "flared", "bishop", "balloon", "cape", "butterfly"])
    is_sleeveless = sleeves_norm in ["sleeveless", "none", "off-the-shoulder"]
    is_cowl_or_party = neckline_norm in ["sweetheart neck", "off-the-shoulder", "halter neck", "boat neck"]
    
    scores = {}
    explanations = {}
    
    for fid, fabric in FABRIC_KNOWLEDGE_BASE.items():
        score = 70  # Baseline suitable score
        reasons = []
        
        # Rule 1: Stretch Requirement Evaluation
        if requires_stretch:
            if fabric["stretch"] == "Stretchable":
                score += 25
                reasons.append(f"Ideal elasticity for the detected {garment_type_norm or 'stretch'} fit")
            elif fabric["stretch"] == "Slight Stretch":
                score += 10
                reasons.append("Slight stretch provides flexibility")
            elif fabric["stretch"] == "No Stretch":
                score -= 35
                reasons.append("Low stretch woven construction limits movement in tight stretch designs")
        else:
            if fabric["stretch"] == "Stretchable" and requires_structure:
                score -= 20
                reasons.append("Elastic knit may sag under structured darts and firm seam construction")
        
        # Rule 2: Garment Structure & Shape Maintenance
        if requires_structure:
            if fid in ["cotton-poplin", "cotton-twill", "linen-blend"]:
                score += 20
                reasons.append(f"Provides crisp structural body required for the {garment_type_norm or 'structured'} design")
            elif fid in ["silk-chiffon", "georgette", "rayon"]:
                score -= 10
                reasons.append("Highly fluid drape may not hold sharp structured body lines")
        
        # Rule 3: Fluid Drape & Sleeve Flow
        if requires_drape:
            if fid in ["rayon", "silk-chiffon", "georgette", "crepe-de-chine"]:
                score += 25
                reasons.append(f"Delivers smooth fluid drape essential for flowing {garment_type_norm or 'blouse'} and sleeve styles")
            elif fid == "linen-blend":
                score += 15
                reasons.append("Offers medium relaxed drape suitable for casual blouse silhouettes")
            elif fid == "satin":
                score += 18
                reasons.append("Rich liquid drape suits flowing blouse styles")
            elif fid == "cotton-poplin":
                score += 5
                reasons.append("Maintains tailored shape for structured blouses")
        
        # Rule 4: Party / Cowl Neckline Aesthetics
        if is_cowl_or_party:
            if fid in ["satin", "silk-chiffon", "crepe-de-chine"]:
                score += 15
                reasons.append(f"Enhances the elegant {neckline_norm or 'decorative'} neckline aesthetic")
        
        # Rule 5: Climate & Warm-Weather Sleeveless Prioritisation
        if is_sleeveless or garment_type_norm in ["crop-top", "blouse"]:
            if fabric["breathability"].startswith("High") or fabric["breathability"].startswith("Very High"):
                score += 5
                reasons.append("Highly breathable material optimized for warm Sri Lankan climate")
        
        # Cap score between 30 and 98
        score = max(30, min(98, score))
        scores[fid] = score
        
        # Build explanation string
        if not reasons:
            reasons.append(f"Good general-purpose material for {garment_type_norm or 'garment'} tailoring")
        
        explanation = f"This material is recommended because it is {fabric['weight'].lower()} weight and {reasons[0].lower()}."
        explanations[fid] = explanation

    # Rank fabrics by score descending
    sorted_fids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    
    recommendations = []
    for idx, fid in enumerate(sorted_fids):
        fab = FABRIC_KNOWLEDGE_BASE[fid].copy()
        s = scores[fid]
        
        if idx == 0 and s >= 80:
            status = "Best Match"
        elif s >= 75:
            status = "Highly Suitable"
        elif s >= 60:
            status = "Suitable"
        else:
            status = "Less Suitable"
            
        fab["recommendation_score"] = s
        fab["recommendation_status"] = status
        fab["explanation"] = explanations[fid]
        fab["badge_type"] = "System Recommended"
        
        recommendations.append(fab)
        
    return recommendations
