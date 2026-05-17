"""Pure metric functions for outfit compatibility evaluation."""

from __future__ import annotations

from sklearn.metrics import roc_auc_score


def roc_auc(scores: list[float], labels: list[int]) -> float:
    """Compute ROC AUC from a list of scores and binary labels.

    Parameters
    ----------
    scores:
        Predicted compatibility scores (higher = more compatible).
    labels:
        Binary ground-truth labels (1 = compatible, 0 = incompatible).

    Returns
    -------
    float
        Area under the ROC curve.
    """
    return float(roc_auc_score(labels, scores))


def accuracy(predictions: list, targets: list) -> float:
    """Compute classification accuracy.

    Parameters
    ----------
    predictions:
        Predicted class labels or values.
    targets:
        Ground-truth class labels or values.

    Returns
    -------
    float
        Fraction of predictions that match targets exactly (0.0–1.0).
    """
    if not targets:
        return 0.0
    correct = sum(p == t for p, t in zip(predictions, targets, strict=True))
    return correct / len(targets)


def recall_at_k(
    ranked_per_query: list[list],
    relevant_per_query: list,
    k: int,
) -> float:
    """Compute Recall@K averaged over queries.

    For each query, checks whether the single relevant item appears in the
    top-K of the ranked candidate list.

    Parameters
    ----------
    ranked_per_query:
        List of ranked candidate lists, one per query. Each inner list is
        ordered from most to least relevant (index 0 = best).
    relevant_per_query:
        The single relevant item id for each query (parallel to
        ``ranked_per_query``).
    k:
        Cutoff rank.

    Returns
    -------
    float
        Fraction of queries where the relevant item appears in top-K.
    """
    if not ranked_per_query:
        return 0.0
    hits = sum(
        1
        for ranked, relevant in zip(ranked_per_query, relevant_per_query, strict=True)
        if relevant in ranked[:k]
    )
    return hits / len(ranked_per_query)
