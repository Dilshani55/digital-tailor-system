"""Crisp AHP weights and vector-normalised TOPSIS, independent of textile data.

Method references and project conventions: docs/fabric-ranking-algorithm.md.
No catalogue labels, default expert judgements or hand-assigned bonus points.
"""

import math

# Saaty & Vargas (2012) RI values, reproduced in Françozo et al. (2023), Table 2.
RANDOM_INDEX = {1: 0, 2: 0, 3: .52, 4: .89, 5: 1.11, 6: 1.25,
                7: 1.35, 8: 1.40, 9: 1.45, 10: 1.49}
MAX_CONSISTENCY_RATIO = .10


class RankingDataError(ValueError):
    """Incomplete or unsuitable research input; never silently replace it."""


def number(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RankingDataError(f"{label} must be a number.")
    try:
        value = float(value)
    except OverflowError as exc:
        raise RankingDataError(f"{label} is too large.") from exc
    if not math.isfinite(value) or value < minimum:
        raise RankingDataError(f"{label} must be finite and at least {minimum}.")
    return float(value)


def ahp_weights(matrix):
    """Principal eigenvector by power iteration; reject non-reciprocity or CR > .10."""
    if not isinstance(matrix, list) or not 2 <= len(matrix) <= 10:
        raise RankingDataError("AHP requires 2–10 criteria and a square comparison matrix.")
    n = len(matrix)
    if any(not isinstance(row, list) or len(row) != n for row in matrix):
        raise RankingDataError("AHP comparison matrix must be square.")
    a = [[number(x, "AHP comparison", 1 / 9 - 1e-10) for x in row] for row in matrix]
    for i in range(n):
        for j in range(n):
            if a[i][j] > 9 + 1e-10:
                raise RankingDataError("AHP comparisons must be within 1/9–9.")
            if i == j and not math.isclose(a[i][j], 1, rel_tol=1e-6):
                raise RankingDataError("AHP diagonal comparisons must equal 1.")
            if not math.isclose(a[i][j] * a[j][i], 1, rel_tol=1e-6):
                raise RankingDataError("AHP comparisons must be reciprocal.")
    weights = [1 / n] * n  # Iteration seed, not a fallback priority vector.
    for _ in range(10000):
        product = [sum(a[i][j] * weights[j] for j in range(n)) for i in range(n)]
        updated = [x / sum(product) for x in product]
        if max(abs(x - y) for x, y in zip(weights, updated)) < 1e-12:
            weights = updated
            break
        weights = updated
    else:
        raise RankingDataError("AHP eigenvector did not converge.")
    product = [sum(a[i][j] * weights[j] for j in range(n)) for i in range(n)]
    eigenvalue = sum(product[i] / weights[i] for i in range(n)) / n
    ci = max(0.0, (eigenvalue - n) / (n - 1))
    cr = ci / RANDOM_INDEX[n] if n > 2 else 0.0
    if cr > MAX_CONSISTENCY_RATIO + 1e-10:
        raise RankingDataError(f"AHP consistency ratio {cr:.4f} exceeds 0.10; revisit the judgements.")
    return {"weights": weights, "lambda_max": eigenvalue, "consistency_ratio": cr,
            "random_index": RANDOM_INDEX[n]}


def group_ahp(matrices):
    """Equal-participant geometric aggregation of individual judgements (AIJ)."""
    if not isinstance(matrices, list) or not matrices:
        raise RankingDataError("Recorded expert comparison matrices are required.")
    individual = [ahp_weights(matrix) for matrix in matrices]
    n = len(matrices[0])
    if any(len(matrix) != n for matrix in matrices):
        raise RankingDataError("All expert matrices must use the same ordered criteria.")
    aggregate = [[math.exp(sum(math.log(matrix[i][j]) for matrix in matrices) / len(matrices))
                  for j in range(n)] for i in range(n)]
    return {**ahp_weights(aggregate), "aggregated_matrix": aggregate,
            "individual_consistency_ratios": [r["consistency_ratio"] for r in individual]}


def topsis(values, weights, directions):
    """Euclidean distances to benefit/cost ideals; return closeness in [0, 1].

    An identical candidate set has no ideal separation: return None coefficients,
    rather than inventing a score. Constant columns contribute zero distance.
    """
    n = len(weights)
    if not n or len(directions) != n or any(d not in ("benefit", "cost") for d in directions):
        raise RankingDataError("Every TOPSIS criterion needs a benefit/cost direction.")
    w = [number(x, "TOPSIS weight") for x in weights]
    if any(x <= 0 for x in w) or not math.isclose(sum(w), 1, rel_tol=1e-8):
        raise RankingDataError("TOPSIS weights must be positive and sum to 1.")
    if not isinstance(values, list) or len(values) < 2:
        raise RankingDataError("At least two measured alternatives are required.")
    if any(not isinstance(row, list) or len(row) != n for row in values):
        raise RankingDataError("Every alternative needs every criterion value.")
    x = [[number(v, "Fabric criterion value") for v in row] for row in values]
    norms = [math.hypot(*(row[j] for row in x)) for j in range(n)]
    if any(not math.isfinite(norm) for norm in norms):
        raise RankingDataError("Fabric criterion values are too large to normalise.")
    normalised = [[row[j] / norms[j] if norms[j] else 0.0 for j in range(n)] for row in x]
    weighted = [[row[j] * w[j] for j in range(n)] for row in normalised]
    best, worst = [], []
    for j, direction in enumerate(directions):
        column = [row[j] for row in weighted]
        low, high = min(column), max(column)
        best.append(high if direction == "benefit" else low)
        worst.append(low if direction == "benefit" else high)
    separated = best != worst
    rows = []
    for i, row in enumerate(weighted):
        plus = math.hypot(*(row[j] - best[j] for j in range(n)))
        minus = math.hypot(*(row[j] - worst[j] for j in range(n)))
        rows.append({"closeness": minus / (plus + minus) if separated else None,
                     "distance_to_ideal": plus, "distance_to_negative_ideal": minus,
                     "normalised_values": normalised[i], "weighted_values": row})
    return {"alternatives": rows, "ideal": best, "negative_ideal": worst,
            "column_norms": norms, "discriminating": separated}
