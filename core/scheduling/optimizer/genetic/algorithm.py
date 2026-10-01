import random
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from ..evaluation.evaluator import EvaluationResult, evaluate
from ..models.problem import SchedulingProblem
from .chromosome import Chromosome
from .crossover import uniform_crossover
from .mutation import constraint_aware_mutation, mutate
from .population import create_initial_population
from .repair import final_repair_pass, repair_chromosome
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


def _identify_conflicted_indices(
    chromosome: Chromosome,
    problem: SchedulingProblem,
) -> List[int]:
    """
    Finds indices of genes involved in conflicts (venue double-booking,
    student cohort clash, lecturer clash, day clash).
    """
    assignments = chromosome.assignments
    conflicted: Set[int] = set()

    # 1. Day clashes
    course_days: Dict[Tuple[int | str, str], int] = {}
    for idx, a in enumerate(assignments):
        key = (a.course_id, a.slot.day)
        if key in course_days:
            conflicted.add(idx)
            conflicted.add(course_days[key])
        else:
            course_days[key] = idx

    # 2. Slot-based clashes (venue, student, lecturer)
    slot_map: Dict[str, List[int]] = defaultdict(list)
    for idx, a in enumerate(assignments):
        slot_map[a.slot.slot_id].append(idx)

    for slot_id, indices in slot_map.items():
        if len(indices) < 2:
            continue

        # Venues
        venues_in_slot: Dict[int | str, int] = {}
        for idx in indices:
            vid = assignments[idx].venue_id
            if vid in venues_in_slot:
                conflicted.add(idx)
                conflicted.add(venues_in_slot[vid])
            else:
                venues_in_slot[vid] = idx

        # Students & Lecturers
        n = len(indices)
        for i in range(n):
            idx1 = indices[i]
            a1 = assignments[idx1]
            conflicts_graph = problem.student_conflict_graph.get(a1.course_id, set())
            for j in range(i + 1, n):
                idx2 = indices[j]
                a2 = assignments[idx2]
                if a2.course_id in conflicts_graph:
                    conflicted.add(idx1)
                    conflicted.add(idx2)
                # Lecturer clash
                if set(a1.occurrence.lecturer_ids) & set(a2.occurrence.lecturer_ids):
                    conflicted.add(idx1)
                    conflicted.add(idx2)

    return list(conflicted)


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

    # Auto-scale defaults adaptively if problem scale is large (e.g. faculty scope)
    total_occ = len(problem.occurrences)
    if config.population_size == 60 and total_occ > 150:
        config.population_size = min(120, max(80, total_occ // 3))
    if config.max_generations == 150 and total_occ > 150:
        config.max_generations = 250
        config.patience = 45

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

            # Crossover (respecting crossover_rate)
            if random.random() < config.crossover_rate:
                child_a, child_b = uniform_crossover(parent_a, parent_b)
            else:
                child_a, child_b = parent_a.clone(), parent_b.clone()

            # Mutation
            child_a = mutate(child_a, problem, mutation_rate=config.mutation_rate)
            child_b = mutate(child_b, problem, mutation_rate=config.mutation_rate)

            # Targeted conflict-aware mutation
            conflicted_a = _identify_conflicted_indices(child_a, problem)
            if conflicted_a:
                child_a = constraint_aware_mutation(child_a, problem, conflicted_a)

            conflicted_b = _identify_conflicted_indices(child_b, problem)
            if conflicted_b:
                child_b = constraint_aware_mutation(child_b, problem, conflicted_b)

            # Optional Repair
            if config.enable_repair:
                child_a = repair_chromosome(child_a, problem)
                child_b = repair_chromosome(child_b, problem)

            new_population.append(child_a)
            if len(new_population) < config.population_size:
                new_population.append(child_b)

        population = new_population

    elapsed = time.time() - start_time

    # Final deterministic repair pass to resolve any remaining hard conflicts
    if config.enable_repair and best_chromosome is not None:
        best_chromosome = final_repair_pass(best_chromosome, problem)

    # Final independent deterministic evaluation with full conflict details
    final_eval = evaluate(best_chromosome.assignments, problem, collect_details=True)

    return best_chromosome, final_eval, gen, elapsed
