"""
Locked workflow step 5 — select drafting block from garment + fabric.
"""

WOVEN_BODICE = "woven_bodice"
KNIT_BODICE = "knit_bodice"

BLOCK_LABELS = {
    WOVEN_BODICE: "Woven bodice block",
    KNIT_BODICE: "Knit bodice block",
}


def select_drafting_block(garment_type, fabric_type):
    """
    Garment + fabric → drafting block family.

    Rules (locked workflow):
      Blouse              → Woven bodice block
      T-shirt             → Knit bodice block
    """
    garment = (garment_type or "blouse").strip().lower()
    fabric = (fabric_type or "woven").strip().lower()

    is_knit_fabric = fabric in ("knit", "stretch-knit")

    if garment == "t-shirt":
        block = KNIT_BODICE
    elif garment == "blouse":
        # Blouse is always woven construction even if a soft fabric is chosen
        block = WOVEN_BODICE
    else:
        block = KNIT_BODICE if is_knit_fabric else WOVEN_BODICE

    return {
        "block_id": block,
        "block_label": BLOCK_LABELS[block],
        "garment_type": garment,
        "fabric_type": fabric,
        "is_knit_block": block == KNIT_BODICE,
        "allow_darts": block == WOVEN_BODICE,
        "add_neckband": garment == "t-shirt" and block == KNIT_BODICE,
        "add_armhole_facing": False,  # set later when sleeve is sleeveless
    }
