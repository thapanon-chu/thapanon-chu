# 🚚 Round 1: Qualification Round — Universal VRP & VRPTW Solver

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![Google OR-Tools](https://img.shields.io/badge/Google%20OR--Tools-9.8+-red?logo=google)](https://developers.google.com/optimization)
[![TSPLIB Optimality Gap](https://img.shields.io/badge/Optimality%20Gap-0.00%25%20(Proven)-brightgreen)](#3-benchmark-verification--mathematical-proofs)
[![Architecture](https://img.shields.io/badge/Architecture-Modular%205--Layer-orange)](#2-code-architecture--modular-engine)

> **Competition:** AI Hackathon Route Optimization 2026 — Qualification Round  
> **Mission Focus:** Universal Capacitated Vehicle Routing Problem (CVRP) & Vehicle Routing with Time Windows (VRPTW)  
> **Status:** **Qualified with Perfect Score (100% Optimal Benchmark Verification & Custom First-Mile Case)**

---

## 📌 Executive Summary

The Qualification Round challenged participants to design a robust, universal optimization solver capable of solving both classical academic benchmarks (**TSPLIB CVRP**) and realistic industrial constraints (**VRPTW with Heterogeneous Fleets and Variable Time Windows**).

Our team engineered `Universal_VRP_Solver.py`, an industrial-grade, single-file solver powered by **Google OR-Tools Routing Library**, augmented with **Guided Local Search (GLS)** metaheuristics and a **Modular 5-Layer Architecture**.

### 🌟 Key Highlights
- **0.00% Optimality Gap**: Achieved the proven mathematical global optimum on standard Augerat benchmark instances (`A-n32-k5`, `B-n31-k5`, `P-n40-k5`) in $\le 10$ seconds.
- **Dual-Mode Engine**: Automatically switches between pure **CVRP** (distance minimization) and **VRPTW** (multi-dimensional time window compliance + heterogeneous vehicle capacities) based on input schema.
- **Real-World Case Study (FM01)**: Designed and solved an agricultural first-mile aggregation scenario with 29 nodes, mixed vehicle sizes, and tight delivery deadlines.
- **Interactive Visual Reporting**: Includes standalone HTML visualizers and vector route plots for immediate operational auditing.

---

## 🏛️ Code Architecture & Modular Engine

The solver follows a clean, decoupled 5-layer design ensuring zero boilerplate, high maintainability, and microservice readiness:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Data Ingestion Layer                                                │
│    - parse_vrp_file()       : TSPLIB format parser (.vrp)              │
│    - load_advanced_config() : Real-world constraints parser (.json)    │
├────────────────────────────────────────────────────────────────────────┤
│ 2. Spatial Matrix Engine                                               │
│    - compute_euclidean_matrix() : 2D coordinates to Euclidean distance │
├────────────────────────────────────────────────────────────────────────┤
│ 3. OR-Tools Routing Model Builder                                      │
│    - RoutingIndexManager    : Node index <-> Solver index mapping      │
│    - RoutingModel           : Decision variables & Transit callbacks   │
│    - AddDimension()         : Cumulative Capacity & Time Window checks │
├────────────────────────────────────────────────────────────────────────┤
│ 4. Search & Metaheuristic Engine                                       │
│    - FirstSolutionStrategy  : PATH_CHEAPEST_ARC (Greedy Insertion)     │
│    - LocalSearchMetaheuristic: GUIDED_LOCAL_SEARCH (GLS Penalty)       │
│    - Deterministic Guard    : Strict 10-second search time budget      │
├────────────────────────────────────────────────────────────────────────┤
│ 5. Extraction & Evaluation Layer                                       │
│    - extract_solution()     : Assignment parsing to structured dict    │
│    - format_console_output(): Terminal ANSI report generation          │
│    - calculate_gap()        : TSPLIB ground-truth optimality gap check │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📐 Mathematical Formulation

The core solver models the routing optimization as a Mixed Integer Linear Programming (MILP) problem solved via Constraint Programming & Local Search:

### Objective Function
Minimize total fleet transit cost across all active vehicles:
$$\min \sum_{k \in K} c_k \sum_{(i,j) \in A} d_{ij} \cdot x_{ijk}$$

### Primary Constraints
1. **Node Degree / Service Guarantee:**
   $$\sum_{k \in K} \sum_{j \in V, j \neq i} x_{ijk} = 1 \quad \forall i \in C$$
2. **Vehicle Capacity Limit:**
   $$\sum_{i \in C} q_i \cdot \sum_{j \in V, j \neq i} x_{ijk} \le Q_k \quad \forall k \in K$$
3. **Time Window Adherence:**
   $$ready_i \le t_i \le due_i \quad \forall i \in V$$
4. **Subtour Elimination & Depot Return:**
   $$\sum_{j \in C} x_{0jk} = \sum_{j \in C} x_{j(n+1)k} \le 1 \quad \forall k \in K$$

---

## 📊 Benchmark Verification & Mathematical Proofs

The solver was rigorously evaluated against classical Augerat benchmark instances and our custom real-world case:

| Benchmark Instance | Problem Class | Nodes / Fleet | Best Known Optimum (BKS) | Our Solver Result | Optimality Gap | Search Runtime | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **A-n32-k5** | CVRP (Set A) | 32 / 5 | **784** | **784** | **0.00%** | 10.03 s | **MATCH (OPTIMAL)** |
| **B-n31-k5** | CVRP (Set B) | 31 / 5 | **672** | **672** | **0.00%** | 10.01 s | **MATCH (OPTIMAL)** |
| **P-n40-k5** | CVRP (Set P) | 40 / 5 | **458** | **458** | **0.00%** | 10.04 s | **MATCH (OPTIMAL)** |
| **FM01-n29-k6** | VRPTW + Mixed Fleet | 29 / 6 | Custom Case | **488** | Feasible Min | 10.02 s | **VALIDATED** |

### Visual Route Solutions
Summary chart showing all route topologies and vehicle allocations:
![Benchmark and Case Results](results/Benchmark&Case_Results.png)

*(Individual high-resolution plots for [A-n32-k5](results/A-n32-k5_Result.png), [B-n31-k5](results/B-n31-k5_Result.png), and [P-n40-k5](results/P-n40-k5_Result.png) are stored in the `results/` folder).*

---

## 📂 Directory Layout

```text
01_Qualification_Round/
├── README.md                          # Technical overview & benchmark proof (this document)
├── code/
│   ├── Universal_VRP_Solver.py        # Core single-file VRP/VRPTW solver
│   └── requirements.txt               # Dependencies (ortools>=9.8.3296)
├── benchmarks/
│   ├── A-n32-k5.vrp                   # TSPLIB Set A benchmark
│   ├── B-n31-k5.vrp                   # TSPLIB Set B benchmark
│   ├── P-n40-k5.vrp                   # TSPLIB Set P benchmark
│   ├── FM01-n29-k6.vrp                # Agricultural first-mile aggregation topology
│   └── FM01-optional.json             # Heterogeneous fleet & customer time windows
├── results/
│   ├── Benchmark_and_Proofs_Report.html # Interactive HTML report with interactive proof tables
│   ├── Benchmark&Case_Results.png     # Full benchmark summary plot
│   ├── A-n32-k5_Result.png            # Route plot for Set A
│   ├── B-n31-k5_Result.png            # Route plot for Set B
│   ├── P-n40-k5_Result.png            # Route plot for Set P
│   └── benchmark_proofs/              # Raw console execution verification logs (.txt)
├── docs/
│   ├── Route_Optimization_Slides.pdf  # Qualification pitch deck
│   ├── FM01_First_Mile_Case_Summary.pdf # Mission 3 case study report
│   └── Case 1-2.pdf                   # Mission 1 formulation & proof evidence
└── submission_archive/
    └── Universal_VRP_Solver_Submission.zip # Official submitted zip archive
```

---

## 🚀 How to Run & Verify

### 1. Installation
```bash
pip install -r code/requirements.txt
```

### 2. Standard Benchmark Mode (TSPLIB CVRP)
Run any standard `.vrp` instance (default time limit: 10s):
```bash
python code/Universal_VRP_Solver.py benchmarks/A-n32-k5.vrp
python code/Universal_VRP_Solver.py benchmarks/B-n31-k5.vrp
python code/Universal_VRP_Solver.py benchmarks/P-n40-k5.vrp
```

### 3. Advanced VRPTW Mode with Configuration File
Pass `--config` to activate time window validation and heterogeneous vehicle capacity:
```bash
python code/Universal_VRP_Solver.py benchmarks/FM01-n29-k6.vrp --config benchmarks/FM01-optional.json
```

### 4. Interactive Report Viewing
Open `results/Benchmark_and_Proofs_Report.html` in any web browser to view the interactive proof tables and route layouts.
