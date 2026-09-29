# Venue-Capacity Feasibility Analysis for a University Timetabling Problem

## Abstract

A university timetable is a constrained assignment problem in which course occurrences must be placed into a finite set of weekly time slots and physical venues. Before invoking a full scheduling solver such as CP-SAT, it is useful to perform a cheap venue-capacity feasibility check.

The purpose of this check is deliberately narrow: it does not attempt to determine whether the complete timetable is feasible. Instead, it answers an earlier and simpler question:

> Does the scheduling scope have enough venue-time capacity to physically accommodate all required weekly course occurrences of each relevant occurrence type?

If this check fails, the complete scheduling problem cannot succeed regardless of lecturer availability, program conflicts, repeated-course distribution, or other constraints. The solver can therefore be skipped and the user can be given an immediate explanation of the capacity deficit.

For the timetable model considered here, teaching takes place in fixed two-hour intervals from 8:00 AM to 6:00 PM, Monday through Friday, except Friday 12:00 PM–2:00 PM, which is unavailable. Consequently, there are 24 usable weekly time slots.

The central formula is:

$$\boxed{O_k \leq T V_k}$$

for every independently constrained occurrence/venue class $k$, where:

- $O_k$ = required weekly occurrences of type $k$
- $T$ = number of usable weekly timetable slots
- $V_k$ = number of venues available to type $k$ within the current scheduling scope.

Equivalently, the capacity deficit is:

$$\boxed{D_k = O_k - T V_k}$$

and the problem fails this pre-check whenever:

$$D_k > 0$$

The model can be generalized to venue subtypes such as lecture halls, computer laboratories, science laboratories, or any other mutually restricted venue class.

---

## 1. Introduction

University timetabling is often described as a large constraint satisfaction or optimization problem. In a production system, a scheduling engine may need to consider:

- lecturer clashes;
- venue clashes;
- course occurrence distribution;
- practical/laboratory requirements;
- program and level conflicts;
- maximum lectures per day;
- lecturer availability;
- venue availability;
- locked timetable assignments;
- and numerous institutional preferences.

A constraint solver is appropriate for the complete problem.

However, not every scheduling request deserves a solver invocation.

Consider a scheduling scope with only two lecture halls and 24 usable weekly periods, while the courses collectively require 60 lecture occurrences. No arrangement of lecturers, courses, or other constraints can make the timetable fit into only:

$$2 \times 24 = 48$$

lecture-hall positions.

The problem is already impossible at the physical-capacity level.

This motivates a pre-solver capacity analysis.

The objective is not to solve the timetable. The objective is to cheaply identify a class of impossible problems before spending computational resources on the complete constraint model.

---

## 2. Scope of the Model

This paper uses a particular timetable representation.

### 2.1 Fixed timetable intervals

The timetable consists of fixed two-hour intervals:

- 8:00–10:00
- 10:00–12:00
- 12:00–2:00
- 2:00–4:00
- 4:00–6:00

for Monday through Friday.

Friday 12:00–2:00 is excluded because of Jummat prayer.

Therefore:

$$5 \times 5 = 25$$

nominal weekly periods exist, but one is unavailable:

$$25 - 1 = 24$$

Thus:

$$\boxed{T = 24}$$

usable weekly timetable slots.

The model should preferably represent these as an explicit set rather than merely relying on arithmetic:

$$\mathcal{T} = \{\text{Mon-8}, \text{Mon-10}, \ldots, \text{Fri-10}, \text{Fri-14}, \text{Fri-16}\}$$

with:

$$|\mathcal{T}| = 24$$

This representation makes future changes easy. If the institution later blocks another period, adds Saturday, or changes the timetable structure, the system can simply alter $\mathcal{T}$.

---

## 3. Occurrences, Not Weekly Hours

A critical modeling decision is that the system does not primarily represent teaching demand as weekly hours.

Instead, each course specifies how many times it must occur during the week.

For example:

| Course | Required weekly occurrences |
|---|---|
| CSC101 | 3 |
| MTH101 | 2 |
| GST111 | 2 |
| PHY101 Practical | 1 |

If:

$$r_c$$

is the required number of weekly occurrences for course $c$, then total occurrences are:

$$\boxed{O = \sum_{c \in C} r_c}$$

There is no need to convert these values from hours because one occurrence already corresponds to one fixed two-hour timetable slot.

Therefore, if the data contains 40 lecture occurrences and 2 practical occurrences, the demand is:

$$O_{\text{lecture}} = 40$$

and:

$$O_{\text{practical}} = 2$$

not a number derived from multiplying course hours.

---

## 4. Why Occurrence Type Matters

Every occurrence is associated with a course type such as:

- lecture
- practical

This distinction matters because the physical resources available to each occurrence type may differ.

For example:

- a lecture may require an ordinary lecture hall;
- a practical may require a laboratory;
- a computer practical may require a computer laboratory;
- a specialized practical may require a particular category of laboratory.

Consequently, all venues should not automatically be treated as one interchangeable pool.

Instead, occurrences are partitioned into resource-compatible classes.

Let:

$$K = \{k_1, k_2, \ldots, k_m\}$$

be the set of independently constrained occurrence/venue classes.

For the simplest system:

$$K = \{\text{lecture}, \text{practical}\}$$

Then:

$$O_{\text{lecture}}$$

is the number of lecture occurrences and:

$$O_{\text{practical}}$$

is the number of practical occurrences.

---

## 5. Venue Capacity

Suppose a scheduling scope has:

$$V_k$$

venues capable of hosting occurrence class $k$.

Every venue can host at most one occurrence in a particular timetable period.

Since there are:

$$T$$

usable periods in the week, one venue provides:

$$T$$

venue-time positions.

Therefore, $V_k$ interchangeable venues provide:

$$V_k T$$

venue-time positions.

Thus:

$$\boxed{C_k = T V_k}$$

where $C_k$ is the maximum weekly venue capacity for class $k$.

---

## 6. The Core Capacity Formula

The required demand must not exceed available capacity.

Therefore:

$$\boxed{O_k \leq C_k}$$

Substituting:

$$C_k = T V_k$$

gives the central equation:

$$\boxed{O_k \leq T V_k}$$

or:

$$\boxed{O_k \leq |\mathcal{T}| V_k}$$

This is the fundamental venue-capacity necessary condition.

For the current timetable:

$$T = 24$$

so:

$$\boxed{O_k \leq 24 V_k}$$

must hold for every independently constrained occurrence class.

---

## 7. Lecture and Practical Capacity

For the current two-category model, the equations become:

### Lecture capacity

$$\boxed{O_L \leq 24 V_L}$$

where:

- $O_L$ = lecture occurrences
- $V_L$ = accessible lecture halls.

### Practical capacity

$$\boxed{O_P \leq 24 V_P}$$

where:

- $O_P$ = practical occurrences
- $V_P$ = accessible practical/lab venues.

The problem passes the basic venue-capacity check only if both inequalities hold:

$$\boxed{O_L \leq 24 V_L \quad \land \quad O_P \leq 24 V_P}$$

---

## 8. Example: 15 Lecture Halls and 3 Labs

Consider a scheduling problem with:

- 15 lecture halls;
- 3 laboratories;
- 40 lecture occurrences;
- 2 practical occurrences.

The weekly lecture capacity is:

$$C_L = 15 \times 24$$

$$\boxed{C_L = 360}$$

The weekly practical capacity is:

$$C_P = 3 \times 24$$

$$\boxed{C_P = 72}$$

Demand is:

$$O_L = 40$$

and:

$$O_P = 2$$

Therefore:

$$40 \le 360$$

and:

$$2 \le 72$$

Both conditions pass.

The combined physical venue-time capacity is:

$$360 + 72 = 432$$

while total occurrence demand is:

$$40 + 2 = 42$$

Thus:

$$\boxed{42 < 432}$$

The scheduling problem passes this particular aggregate venue-capacity test.

This does not prove that the timetable is solvable. It only proves that the venue pool is not obviously too small under this capacity model.

---

## 9. Capacity Deficit

The inequality can be converted into a useful diagnostic quantity.

Define:

$$\boxed{D_k = O_k - T V_k}$$

where $D_k$ is the capacity deficit.

Three cases exist.

### Case 1: $D_k < 0$

There is spare capacity.

For example:

$$O_L = 40, \quad C_L = 360$$

gives:

$$D_L = 40 - 360 = -320$$

There are 320 unused lecture-hall positions at the aggregate level.

### Case 2: $D_k = 0$

The resource is exactly saturated:

$$O_k = T V_k$$

Every available venue-time position would have to be occupied.

### Case 3: $D_k > 0$

Demand exceeds capacity:

$$O_k > T V_k$$

The scheduling problem is impossible under the current venue pool.

This is a proof of infeasibility for the capacity model, not merely a warning.

---

## 10. Minimum Number of Required Venues

The equation can also be rearranged to determine how many venues are theoretically required.

Starting with:

$$O_k \leq T V_k$$

divide by $T$:

$$\frac{O_k}{T} \leq V_k$$

Since $V_k$ must be an integer:

$$\boxed{V_k^{\min} = \left\lceil \frac{O_k}{T} \right\rceil}$$

This tells the administrator the minimum number of interchangeable venues required to accommodate the total occurrence demand if every usable time slot can be exploited.

For example, if:

$$O_L = 50$$

then:

$$V_L^{\min} = \left\lceil \frac{50}{24} \right\rceil = 3$$

So at least three lecture halls are required under the aggregate model.

If only two exist:

$$2 \times 24 = 48 < 50$$

and the problem fails immediately.

---

## 11. Maximum Number of Occurrences Supported

The inverse calculation is:

$$\boxed{O_k^{\max} = T V_k}$$

For example, with 15 lecture halls:

$$O_L^{\max} = 24 \times 15 = 360$$

With 3 laboratories:

$$O_P^{\max} = 24 \times 3 = 72$$

This can be useful when displaying scheduling-resource statistics in an administrative interface.

---

## 12. Scheduling Scope and Venue Resolution

The capacity equation itself should not decide which venues belong to a department or faculty.

That should happen in a preceding venue-resolution stage.

The solver should receive a resolved set of allowed venues.

The organizational hierarchy can be represented as:

```text
School
├── Faculty A
│   ├── Department A1
│   └── Department A2
│
└── Faculty B
    ├── Department B1
    └── Department B2
```

Venue ownership can similarly exist at three levels:

- School-owned venue
- Faculty-owned venue
- Department-owned venue

For a department-level scheduling operation, the accessible venue set is:

$$\boxed{V(D) = V_{\text{department}}(D) \cup V_{\text{faculty}}(F(D)) \cup V_{\text{school}}}$$

where $F(D)$ is the faculty containing department $D$.

This means a department can use:

- its own departmental venues;
- venues owned by its faculty;
- school-owned venues.

It cannot automatically use venues owned by another faculty.

For faculty-level scheduling:

$$\boxed{V(F) = V_{\text{faculty}}(F) \cup V_{\text{school}}}$$

For school-level scheduling, assuming the school scheduler has authority over all relevant resources:

$$\boxed{V(S) = V_{\text{school}} \cup \bigcup_{F} V_{\text{faculty}}(F)}$$

The capacity equation is then applied to the resolved venue set.

---

## 13. Course Ownership Is Not Venue Access

A course's academic ownership must not determine venue access.

For example, a general course such as GST111 may be academically owned by a particular department while being offered to students across many departments.

The following concepts should therefore remain separate:

$$\boxed{\text{Course Ownership} \neq \text{Scheduling Scope} \neq \text{Venue Ownership} \neq \text{Venue Access}}$$

- **Course ownership** describes the academic administrative relationship.
- **Venue ownership** describes who owns a physical resource.
- **Scheduling scope** determines which resources participate in a particular scheduling operation.
- **Venue access** determines which venues are actually available to that operation.

The capacity formula only needs the final resolved set:

$$V_k(S)$$

---

## 14. Scope-Aware Capacity Formula

Let:

- $S$ = scheduling scope;
- $V(S)$ = venues accessible to the scope;
- $V_k(S)$ = accessible venues compatible with occurrence class $k$.

Then:

$$\boxed{C_k(S) = T \, |V_k(S)|}$$

and the feasibility pre-check becomes:

$$\boxed{O_k(S) \leq T \, |V_k(S)|}$$

for every relevant occurrence class $k$.

This is the cleanest way to incorporate scope.

The capacity checker does not need to know whether a venue became accessible because it was:

- department-owned;
- faculty-owned;
- school-owned;
- or otherwise explicitly authorized.

The venue-resolution service handles that.

---

## 15. Venue Compatibility Classes

The simple lecture/practical split may eventually be insufficient.

Suppose a university has:

- 15 ordinary lecture halls;
- 2 computer laboratories;
- 1 chemistry laboratory;
- 2 general laboratories.

If every practical can use every laboratory, one practical pool is enough:

$$V_P = 5$$

However, if a computer practical specifically requires a computer lab, the relevant pool is:

$$V_{\text{computer}} = 2$$

The capacity check becomes:

$$\boxed{O_{\text{computer}} \leq 24 V_{\text{computer}}}$$

Similarly, if chemistry practicals require chemistry laboratories:

$$\boxed{O_{\text{chemistry}} \leq 24 V_{\text{chemistry}}}$$

This leads to the generalized formula:

$$\boxed{\forall k \in K: \quad O_k \leq T \, |V_k|}$$

where $K$ contains every independently constrained venue/resource class.

---

## 16. A More General Compatibility Interpretation

An occurrence $o$ should have an eligible venue set:

$$A(o)$$

containing the venues that can physically host it.

For a simple occurrence type:

$$A(o) = V_{\text{lecture}}$$

or:

$$A(o) = V_{\text{practical}}$$

For a specialized occurrence:

$$A(o) = V_{\text{computer lab}}$$

The basic aggregate capacity check works perfectly when all occurrences in a class share the same compatible venue pool.

When individual occurrences have highly different eligible-venue sets, however, the simple sum may become too optimistic.

For example:

- Lab 1 → Computer practicals
- Lab 2 → Chemistry practicals
- Lab 3 → Computer + Chemistry

A simple statement that there are three labs would conceal this restriction.

In such cases, the system should partition the occurrences into meaningful compatibility classes before applying the equation.

---

## 17. Why the Formula Is a Necessary Condition, Not a Complete Solver

Passing:

$$O_k \leq T V_k$$

does not prove that a timetable exists.

It proves only that aggregate venue-time capacity is sufficient.

For example:

- 100 occurrences;
- 5 venues;
- 24 periods.

gives:

$$100 \le 120$$

so the capacity test passes.

But the timetable could still be impossible because all 100 occurrences might require the same lecturer, and that lecturer cannot teach 100 classes in the available week.

Similarly, other constraints may make the problem impossible:

- lecturer availability;
- program-level conflicts;
- daily teaching limits;
- course occurrence distribution;
- locked assignments;
- venue-specific restrictions;
- special institutional constraints.

Therefore:

$$\boxed{\text{Capacity pass} \not\Rightarrow \text{Timetable feasible}}$$

But:

$$\boxed{\text{Capacity fail} \Rightarrow \text{Timetable infeasible under the capacity model}}$$

This asymmetry is exactly why the check is valuable.

---

## 18. Why Repeated-Occurrence Constraints Do Not Belong in This Capacity Test

Suppose a course must occur three times weekly and its occurrences cannot be on:

- the same day;
- consecutive days.

Those rules matter to the actual timetable solver.

However, they do not change the total number of venue-time positions.

A three-occurrence course still requires:

$$3$$

venue assignments.

Therefore, for the narrow capacity question:

$$O_c = 3$$

regardless of how those three occurrences are distributed across the week.

The distribution rules should be checked later by the scheduling solver.

There is nevertheless an important edge case: if a course's occurrence requirements make it mathematically impossible to distribute across the available days, the preprocessor may optionally identify that as a separate structural error. That is a different check from venue capacity and should not be mixed into the venue-capacity equation.

---

## 19. Aggregate Capacity Versus Resource-Specific Capacity

It is tempting to calculate:

$$C_{\text{total}} = T (V_L + V_P)$$

For 15 lecture halls and 3 labs:

$$C_{\text{total}} = 24 (15 + 3) = 432$$

and compare:

$$O_{\text{total}} = 42$$

against:

$$432$$

This is useful as a broad statistic, but it is not sufficient.

Why?

Because lecture occurrences cannot necessarily use labs, and practical occurrences cannot necessarily use ordinary lecture halls.

Therefore the stronger check is:

$$\boxed{O_L \leq 24 V_L}$$

and:

$$\boxed{O_P \leq 24 V_P}$$

rather than only:

$$O_L + O_P \leq 24 (V_L + V_P)$$

The aggregate equation can hide shortages in a particular resource category.

---

## 20. Capacity Utilization

A useful derived statistic is utilization:

$$\boxed{U_k = \frac{O_k}{T V_k}}$$

where $U_k$ is the fraction of theoretical venue capacity consumed by occurrence class $k$.

For the 15-hall example:

$$U_L = \frac{40}{360} \approx 0.1111$$

or approximately:

$$\boxed{11.11\%}$$

For practicals:

$$U_P = \frac{2}{72} \approx 0.0278$$

or:

$$\boxed{2.78\%}$$

These figures are not predictions of actual timetable occupancy. They are simply utilization of the theoretical aggregate venue-time capacity.

They can be useful for administrative diagnostics.

---

## 21. Slack Capacity

Another useful measure is slack:

$$\boxed{S_k = T V_k - O_k}$$

For lecture halls:

$$S_L = 360 - 40 = 320$$

For practical venues:

$$S_P = 72 - 2 = 70$$

Thus:

- lecture capacity has 320 unused venue-time positions;
- practical capacity has 70 unused venue-time positions.

Again, this is aggregate slack, not guaranteed free periods after all timetable constraints are applied.

---

## 22. Algorithm

A production implementation can perform the capacity check in a few steps.

### Step 1 — Determine scheduling scope

Input:

- `scope_type`
- `scope_id`

For example:

```text
scope_type = DEPARTMENT
scope_id = CSC
```

### Step 2 — Resolve accessible venues

Use the organizational hierarchy and venue-access rules.

For department scope:

```text
department-owned venues
+ faculty-owned venues
+ school-owned venues
```

### Step 3 — Resolve usable timetable slots

Construct the actual weekly slot set.

For the current timetable:

```text
Monday:    5
Tuesday:   5
Wednesday: 5
Thursday:  5
Friday:    4
```

Therefore:

$$T = 24$$

### Step 4 — Read occurrence records

Do not derive occurrences from weekly hours.

Each occurrence record already represents one required weekly assignment.

### Step 5 — Group occurrences by venue/resource class

For example:

- lecture
- practical

or more specific classes if necessary.

### Step 6 — Count demand

For each class:

$$O_k = \text{count of occurrences of class } k$$

### Step 7 — Count compatible venues

For each class:

$$V_k = \text{count of accessible compatible venues}$$

### Step 8 — Calculate capacity

$$C_k = T V_k$$

### Step 9 — Compare

$$O_k \leq C_k$$

### Step 10 — Return a diagnostic

The result should identify:

- demand;
- capacity;
- utilization;
- slack;
- deficit;
- pass/fail.

---

## 23. Pseudocode

```text
function checkVenueCapacity(scheduleScope, occurrences, venues):

    slots = getUsableWeeklySlots()

    allowedVenues = resolveAllowedVenues(
        scheduleScope,
        venues
    )

    occurrenceGroups = groupByResourceClass(occurrences)

    results = []

    for each class in occurrenceGroups:

        demand = count(occurrenceGroups[class])

        compatibleVenues = filter(
            allowedVenues,
            venueSupports(class)
        )

        venueCount = count(compatibleVenues)

        capacity = len(slots) * venueCount

        deficit = demand - capacity

        utilization = demand / capacity
            if capacity > 0
            else infinity

        results.append({
            "class": class,
            "demand": demand,
            "venues": venueCount,
            "slots": len(slots),
            "capacity": capacity,
            "deficit": max(deficit, 0),
            "utilization": utilization,
            "passes": demand <= capacity
        })

    return {
        "passes": all(result.passes for result in results),
        "results": results
    }
```

---

## 24. Example Output

For the 15 lecture halls and 3 labs example, a backend response could look like:

```json
{
  "passes": true,
  "time_slots": 24,
  "classes": [
    {
      "type": "lecture",
      "occurrences": 40,
      "venues": 15,
      "capacity": 360,
      "utilization": 0.1111,
      "slack": 320,
      "deficit": 0,
      "passes": true
    },
    {
      "type": "practical",
      "occurrences": 2,
      "venues": 3,
      "capacity": 72,
      "utilization": 0.0278,
      "slack": 70,
      "deficit": 0,
      "passes": true
    }
  ]
}
```

If there were 400 lecture occurrences instead:

$$400 > 360$$

and the result should immediately report:

```json
{
  "passes": false,
  "type": "lecture",
  "occurrences": 400,
  "venues": 15,
  "capacity": 360,
  "deficit": 40
}
```

The scheduling engine should not be invoked because the venue-capacity condition has already failed.

---

## 25. What the Capacity Checker Should Not Do

The purpose of this component should remain deliberately narrow.

It should not attempt to solve:

### Lecturer conflicts

Whether:

> Lecturer A

can teach two occurrences simultaneously belongs to the timetable solver.

### Program conflicts

Whether:

> CSC 100L
> MTH 100L

can occur simultaneously is a separate constraint.

### Daily lecture limits

The rule:

$$\text{maximum 3 lectures/day}$$

does not affect the total number of venue-time positions and therefore does not belong in the basic venue-capacity equation.

### Repeated occurrence distribution

Whether a course's three occurrences can be distributed as:

> Monday / Wednesday / Friday

belongs to the actual scheduling model.

### Lecturer availability

This is another resource constraint but not part of venue capacity.

Keeping these concerns separate makes the architecture easier to understand and debug.

---

## 26. Important Limitation: The Formula Assumes Venue Interchangeability Within a Class

The formula:

$$O_k \leq T V_k$$

assumes that all $V_k$ venues are usable by all $O_k$ occurrences in class $k$.

If that assumption is false, the class must be subdivided.

For example:

```text
Lecture
├── General lecture
├── Large-capacity lecture
└── Specialized lecture
```

or:

```text
Practical
├── Computer practical
├── Chemistry practical
└── Physics practical
```

Then the formula is applied independently:

$$O_{\text{computer}} \leq 24 V_{\text{computer}}$$

$$O_{\text{chemistry}} \leq 24 V_{\text{chemistry}}$$

etc.

The general principle is:

> Create a separate capacity class whenever occurrences and venues do not share the same eligibility pool.

---

## 27. Relationship to CP-SAT

The capacity check should be placed before the CP-SAT scheduling model.

The overall architecture becomes:

```text
                    Scheduling Request
                           |
                           v
                  Resolve Scheduling Scope
                           |
                           v
                   Resolve Allowed Venues
                           |
                           v
                  Count Weekly Occurrences
                           |
                           v
                +-------------------------+
                | Venue Capacity Checker  |
                +-------------------------+
                     |             |
                   FAIL          PASS
                     |             |
                     v             v
             Explain deficit    Build CP-SAT
                                   model
                                     |
                                     v
                              Solve constraints
                                     |
                                     v
                              Timetable result
```

This has an important computational advantage.

If the capacity checker rejects the request, the expensive combinatorial search never starts.

---

## 28. Mathematical Summary

The complete basic model can be summarized with the following definitions.

### Usable weekly slots

$$\boxed{T = |\mathcal{T}|}$$

For the current timetable:

$$\boxed{T = 24}$$

### Required occurrences

$$\boxed{O_k = \sum_{o \in \mathcal{O}} I\big(\text{type}(o) = k\big)}$$

where $I(\cdot)$ is an indicator function.

### Accessible compatible venues

$$\boxed{V_k(S) = |\mathcal{V}_k(S)|}$$

where $S$ is the scheduling scope.

### Capacity

$$\boxed{C_k(S) = T \, V_k(S)}$$

### Capacity condition

$$\boxed{O_k \leq C_k(S)}$$

or:

$$\boxed{O_k \leq T \, V_k(S)}$$

### Deficit

$$\boxed{D_k = O_k - T \, V_k(S)}$$

### Minimum required venues

$$\boxed{V_k^{\min} = \left\lceil \frac{O_k}{T} \right\rceil}$$

### Utilization

$$\boxed{U_k = \frac{O_k}{T \, V_k(S)}}$$

### Overall pre-check

$$\boxed{\forall k \in K: \; O_k \leq T \, V_k(S)}$$

If any class fails:

$$\boxed{\exists k: \; O_k > T \, V_k(S) \Rightarrow \text{capacity-infeasible}}$$

If all classes pass:

$$\boxed{\forall k: \; O_k \leq T \, V_k(S) \not\Rightarrow \text{fully feasible timetable}}$$

It means only that the problem has survived the venue-capacity pre-check.

---

## 29. Worked Example

Assume:

- 24 usable weekly slots;
- 15 accessible lecture halls;
- 3 accessible laboratories;
- 40 lecture occurrences;
- 2 practical occurrences.

### Lecture

$$C_L = 24(15) = 360$$

$$O_L = 40$$

Therefore:

$$40 \leq 360$$

**Pass.**

Slack:

$$360 - 40 = 320$$

Utilization:

$$\frac{40}{360} \times 100 \approx 11.11\%$$

### Practical

$$C_P = 24(3) = 72$$

$$O_P = 2$$

Therefore:

$$2 \leq 72$$

**Pass.**

Slack:

$$72 - 2 = 70$$

Utilization:

$$\frac{2}{72} \times 100 \approx 2.78\%$$

### Overall capacity result

$$\boxed{\text{PASS}}$$

The venue pool is not the limiting factor for this particular problem under the stated capacity model.

---

## 30. Conclusion

The venue-capacity pre-check is intentionally much simpler than the full university timetabling problem.

Its purpose is not to predict whether CP-SAT will find a timetable. Its purpose is to detect an obvious physical impossibility before the scheduling engine is invoked.

The central idea is:

> Every required occurrence consumes one venue for one usable timetable period.

With $T$ usable weekly periods and $V_k$ compatible venues, the maximum number of occurrences that can be hosted by that resource class is:

$$\boxed{C_k = T V_k}$$

Therefore, for every independently constrained occurrence class:

$$\boxed{O_k \leq T V_k}$$

For the current timetable:

$$T = 24$$

so:

$$\boxed{O_k \leq 24 V_k}$$

This provides a fast, deterministic necessary-condition test.

The design should therefore separate three stages:

1. Resolve the scheduling scope and its allowed venues.
2. Perform the venue-capacity pre-check.
3. Only if it passes, construct and solve the complete timetable constraint model.

This separation keeps the capacity calculation mathematically clean, computationally cheap, and independent of the much more complicated constraints handled by the actual scheduling engine.
