import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from ..evaluation.evaluator import EvaluationResult, evaluate
from ..models.problem import SchedulingProblem
from .chromosome import Chromosome
from .crossover import uniform_crossover
from .mutation import mutate
from .population import create_initial_population
from .repair import repair_chromosome
from .selection import tournament_selection


@dataclass
class OptimizerConfig:
    """
    Hyperparameters and runtime settings for the Genetic Algorithm optimizer.
    """

    population_size: int = 60
    max_generations: int = 150
    elitism_count: int = 2
    tournament_size: int = 3
    mutation_rate: float = 0.08
    crossover_rate: float = 0.85
    patience: int = 35
    enable_repair: bool = True


def run_genetic_algorithm(
    problem: SchedulingProblem,
    config: Optional[OptimizerConfig] = None,
    progress_callback: Optional[Callable[[int, int, EvaluationResult], None]] = None,
) -> Tuple[Chromosome, EvaluationResult, int, float]:
    """
    Executes the genetic algorithm to find an optimal or best-available weekly timetable.
    Returns:
      (best_chromosome, best_evaluation, generations_run, elapsed_seconds)
    """
    if config is None:
        config = OptimizerConfig()

    start_time = time.time()

    # If problem has 0 occurrences, return empty
    if not problem.occurrences:
        empty_chrome = Chromosome([])
        empty_eval = evaluate([], problem)
        return empty_chrome, empty_eval, 0, 0.0

    # 1. Create initial population
    population = create_initial_population(
        problem,
        population_size=config.population_size,
        heuristic_ratio=0.8,
    )

    best_chromosome: Optional[Chromosome] = None
    best_evaluation: Optional[EvaluationResult] = None
    generations_without_improvement = 0

    for gen in range(1, config.max_generations + 1):
        # 2. Evaluate entire population
        evaluations: List[EvaluationResult] = [
            evaluate(chrome.assignments, problem) for chrome in population
        ]

        # 3. Find current generation best
        gen_best_idx = min(
            range(len(population)),
            key=lambda i: evaluations[i].lexicographic_rank,
        )
        gen_best_chrome = population[gen_best_idx]
        gen_best_eval = evaluations[gen_best_idx]

        # Update global best
        if (
            best_evaluation is None
            or gen_best_eval.lexicographic_rank < best_evaluation.lexicographic_rank
        ):
            best_chromosome = gen_best_chrome.clone()
            best_evaluation = gen_best_eval
            generations_without_improvement = 0
        else:
            generations_without_improvement += 1

        # Notify progress callback
        if progress_callback:
            progress_callback(gen, config.max_generations, best_evaluation)

        # 4. Check early termination conditions
        # (a) Zero hard conflicts reached
        if best_evaluation.is_feasible:
            # If zero hard conflicts and zero capacity penalty, we are optimal
            if best_evaluation.is_optimal:
                break
            # If feasible, give a few more generations to reduce capacity penalty if possible
            if generations_without_improvement >= 10:
                break

        # (b) Stagnation termination
        if generations_without_improvement >= config.patience:
            break

        # 5. Build next generation with Elitism
        new_population: List[Chromosome] = []

        # Elitism: sort population by lexicographic rank and preserve top N
        sorted_indices = sorted(
            range(len(population)),
            key=lambda i: evaluations[i].lexicographic_rank,
        )
        for e_idx in range(min(config.elitism_count, len(population))):
            new_population.append(population[sorted_indices[e_idx]].clone())

        # Generate offspring
        while len(new_population) < config.population_size:
            parent_a = tournament_selection(
                population, evaluations, tournament_size=config.tournament_size
            )
            parent_b = tournament_selection(
                population, evaluations, tournament_size=config.tournament_size
            )

            # Crossover
            child_a, child_b = uniform_crossover(parent_a, parent_b)

            # Mutation
            child_a = mutate(child_a, problem, mutation_rate=config.mutation_rate)
            child_b = mutate(child_b, problem, mutation_rate=config.mutation_rate)

            # Optional Repair
            if config.enable_repair:
                child_a = repair_chromosome(child_a, problem)
                child_b = repair_chromosome(child_b, problem)

            new_population.append(child_a)
            if len(new_population) < config.population_size:
                new_population.append(child_b)

        population = new_population

    elapsed = time.time() - start_time

    # Final independent deterministic evaluation with full conflict details
    final_eval = evaluate(best_chromosome.assignments, problem, collect_details=True)

    return best_chromosome, final_eval, gen, elapsed

