import random
from typing import Tuple

from .chromosome import Chromosome


def uniform_crossover(
    parent_a: Chromosome,
    parent_b: Chromosome,
) -> Tuple[Chromosome, Chromosome]:
    """
    Uniform crossover: for each occurrence gene, randomly chooses whether
    child 1 inherits from parent A or parent B (and vice-versa for child 2).
    Preserves structural occurrence validity.
    """
    n = len(parent_a)
    child_a_genes = []
    child_b_genes = []

    for i in range(n):
        if random.random() < 0.5:
            child_a_genes.append(parent_a[i])
            child_b_genes.append(parent_b[i])
        else:
            child_a_genes.append(parent_b[i])
            child_b_genes.append(parent_a[i])

    return Chromosome(child_a_genes), Chromosome(child_b_genes)


def two_point_crossover(
    parent_a: Chromosome,
    parent_b: Chromosome,
) -> Tuple[Chromosome, Chromosome]:
    """
    Two-point crossover between parents.
    """
    n = len(parent_a)
    if n < 3:
        return uniform_crossover(parent_a, parent_b)

    pt1 = random.randint(1, n - 2)
    pt2 = random.randint(pt1 + 1, n - 1)

    child_a_genes = list(parent_a[:pt1]) + list(parent_b[pt1:pt2]) + list(parent_a[pt2:])
    child_b_genes = list(parent_b[:pt1]) + list(parent_a[pt1:pt2]) + list(parent_b[pt2:])

    return Chromosome(child_a_genes), Chromosome(child_b_genes)

