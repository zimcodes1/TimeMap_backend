import random
from typing import List

from ..evaluation.evaluator import EvaluationResult
from .chromosome import Chromosome


def tournament_selection(
    population: List[Chromosome],
    evaluations: List[EvaluationResult],
    tournament_size: int = 3,
) -> Chromosome:
    """
    Tournament selection: randomly samples k chromosomes and returns
    the one with the best (lowest) lexicographic rank / highest fitness.
    """
    n = len(population)
    indices = random.sample(range(n), min(tournament_size, n))

    # Compare by lexicographic rank (smaller is better) or fitness (higher is better)
    best_idx = min(indices, key=lambda i: evaluations[i].lexicographic_rank)
    return population[best_idx]

