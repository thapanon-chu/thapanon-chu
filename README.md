[⬅️ Back to Main Portfolio](../../README.md)

<div id="top"></div>

# CPAC Ready-Mixed Concrete (RMC) AI Dispatch Optimizer
> Autonomous, multi-pass route and dispatch optimization engine solving perishable concrete logistics under urban traffic congestion, continuous-pour constraints, and chemical slump-life limits.

<p>
  <a href="01_Grand_Finals/dashboard_and_viz/dashboard_champion.html"><img src="https://img.shields.io/badge/Live_Dashboard-238636?style=for-the-badge&logoColor=white" /></a>
  <a href="https://img.shields.io/badge/SLA_Pass-54%2F54_(100%25)-brightgreen?style=for-the-badge" /></a>
  <a href="https://img.shields.io/badge/Runtime-0.65s-red?style=for-the-badge" /></a>
  <a href="../../README.md"><img src="https://img.shields.io/badge/Back_to_Portfolio-21262d?style=for-the-badge&logoColor=white" /></a>
</p>

---

<div id="code-structure"></div>

## Code File Structure <a href="#top" align="right"><sub>[ ▲ Back to Top ]</sub></a>

```text
ai-concrete-logistics-optimizer/
├── 01_Grand_Finals/                 # Core Dispatch Engine (CPAC Ready-Mixed Concrete)
│   ├── code/
│   │   ├── solve.py                 # CLI interface for automated day and hidden-set evaluation
│   │   ├── master_solver.py         # Multi-pass resilient dispatch optimizer (0.65s runtime)
│   │   ├── aiconcrete.py            # Domain data structures, travel matrix models & event simulator
│   │   └── evaluate.py              # Official competition scoring and SLA validation harness
│   ├── data/                        # Operational datasets (Common specs, Day 1 to Day 4 traffic/orders)
│   │   ├── common/                  # Plant coordinates, fleet limits, customer contracts
│   │   ├── day1_weekday/            # Baseline weekday operations
│   │   ├── day2_school_opening/     # Morning school zone congestion scenario
│   │   ├── day3_festival/           # Festival road closures and detour scenario
│   │   └── day4_holiday/            # Weekend operational schedule
│   ├── out/                         # Verified solution sets (plan.csv, order_changes.csv, production_plan.csv)
│   ├── dashboard_and_viz/           # HTML5 interactive dispatcher timeline & financial waterfall
│   │   └── dashboard_champion.html  # Standalone visual audit tool (Gantt chart & cold-joint monitor)
│   ├── presentation_and_pitch/      # Executive pitch deck (PDF/PPTX), 5-min script & defense guide
│   └── strategy_and_docs/           # Competition rules, problem formulations & data books
├── 02_Qualification_Round/          # Preliminary: Universal VRP Solver (Google OR-Tools)
│   ├── code/                        # Universal_VRP_Solver.py (CVRP/VRPTW with Guided Local Search)
│   ├── benchmarks/                  # TSPLIB instances (A-n32-k5, B-n31-k5, P-n40-k5) & custom case
│   └── results/                     # Optimal routing plots & logs (0.00% optimality gap verified)
├── .gitignore                       # Python environment and build exclusions
└── README.md                        # Master repository overview & executive scorecard
```

---

### Jump to Topic:
- [Code File Structure](#code-structure)
- [Overview & Architecture](#overview-showcase)
- [Problem & Objectives](#problem-objectives)
- [Tech Stack & Tools](#tech-stack)
- [Key Features](#key-features)
- [Business Impact & Results](#business-impact)
- [Challenges & Solutions](#challenges-solutions)
- [How to Run & Setup](#how-to-run)

---

<div id="overview-showcase"></div>

## Overview & Architecture <a href="#top" align="right"><sub>[ ▲ Back to Top ]</sub></a>

Ready-Mixed Concrete (RMC) dispatching is a time-critical, perishable scheduling problem where scheduling latency directly ruins the physical product. The engine processes order requests, batching plant constraints, truck fleet positions, and time-dependent travel matrices to generate production and routing schedules in sub-second time.

### Operational Execution Pipeline

```text
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                            INPUT DATASETS (CSV)                             │
 │  - Customer Orders & SLA Tiers (G1-G7)  - Plant Capacities & Batch Lines    │
 │  - Truck Fleet Specs & Starting Points  - Time-Dependent Congestion Matrices│
 └──────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ 1. DYNAMIC PRE-PROCESSING & SHIFT HEURISTICS                                │
 │    - Evaluates travel times against time-dependent traffic windows          │
 │    - Identifies road closure choke points (school zones 07:30-08:30)        │
 │    - Proactively negotiates valid departure shifts for lower-tier orders    │
 └──────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ 2. DUAL-STREAM WORKLOAD BALANCER                                            │
 │    - Detects parallel pours requiring concurrent mixer streams              │
 │    - Splits streams across complementary batching plants                    │
 │    - Eliminates plant batching queue bottlenecks and line starvation        │
 └──────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ 3. 4-PASS RESILIENT DISPATCH ENGINE                                         │
 │    ├─ Pass 1: Strict Window Match (±15 min of customer request)             │
 │    ├─ Pass 2: Flow Relaxation (Expands window, locks pour gap < 45 min)     │
 │    ├─ Pass 3: Cross-Plant Fleet Relocation (Pulls idle mixers from depot)   │
 │    └─ Pass 4: Deterministic Fallback (Guaranteed execution, zero unserved)  │
 └──────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ 4. SIMULATION VALIDATION & ARTIFACT GENERATION                              │
 │    - Enforces Slump Life (< 120 min) and Cold Joint (< 45 min) limits       │
 │    - Zero production boost line cost optimization (-฿46,300/day saved)      │
 │    - Emits: plan.csv | order_changes.csv | production_plan.csv              │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

<div id="problem-objectives"></div>

## Problem & Objectives <a href="#top" align="right"><sub>[ ▲ Back to Top ]</sub></a>

> **The Problem:** Ready-Mixed Concrete undergoes irreversible hydration once mixed with water at the batching plant. If a mixer truck is delayed in traffic beyond its **120-minute slump life**, the concrete hardens inside the drum, destroying both the batch and the truck. Furthermore, if consecutive mixer deliveries to the same construction site exceed a **45-minute interval**, a **cold joint** forms between concrete layers, compromising structural integrity and risking building failure.

**The Objectives:**
- **Zero Critical Violations:** Eliminate all cold joints ($> 45$ min interval) and slump-life expirations ($> 120$ min) across all customer sites.
- **100% Contract SLA Compliance:** Meet on-time delivery and continuous green pour requirements across all seven customer priority tiers (Grade G1 "Blue Diamond" down to Grade G7 "Basic").
- **Maximize Net Contribution:** Optimize production scheduling to maximize operating profit after accounting for raw materials, transport fuel, empty fleet relocation, truck waiting, and plant overtime costs.
- **Zero Plant Overtime Boost:** Satisfy daily customer volume strictly within regular plant batching capacity, avoiding costly extra production line penalties.
- **Sub-Second Execution:** Finish daily schedule computation in $\le 1$ second (competition budget: 5 minutes) to ensure immediate applicability on unknown test sets.

---

<div id="tech-stack"></div>

## Tech Stack & Tools <a href="#top" align="right"><sub>[ ▲ Back to Top ]</sub></a>

**Core Technologies:**
`Python 3.10+` `Standard Library (Zero Pip Dependencies)` `Operations Research` `Heuristic Search` `HTML5 / Canvas`

- **Core Engine:** Written in pure Python without third-party dependencies (`collections`, `heapq`, `dataclasses`, `datetime`, `math`, `csv`, `json`) for portability and zero deployment overhead.
- **Evaluation Harness:** Official event simulation kernel (`evaluate.py`) validating physical truck kinematics, batching queues, and contractual penalties.
- **Audit Dashboard:** Single-file interactive HTML5 dashboard providing Gantt timelines, cold joint interval monitors, and financial waterfall breakdowns.
- **Preliminary Benchmark Stack:** Google OR-Tools Routing Engine (Constraint Programming + Guided Local Search) for the qualification round.

---

<div id="key-features"></div>

## Key Features <a href="#top" align="right"><sub>[ ▲ Back to Top ]</sub></a>

- **Dynamic Shift Heuristics (Proactive Window Adjustment):**  
  Analyzes time-dependent travel matrices to identify peak congestion windows (e.g., 07:30–08:30 school runs). For non-critical site orders, the algorithm calculates safe arrival shifts within contractual limits, bypassing road bottlenecks without incurring tardiness penalties.

- **Dual-Stream Workload Allocator:**  
  Large construction projects require concurrent delivery streams. The allocator detects high-volume orders and routes streams to distinct batching plants (e.g., Plant P01 for Stream A, Plant P02 for Stream B), preventing single-plant batching line queues.

- **Zero-Boost Cost Optimization:**  
  Rather than opening expensive temporary production lines (+฿46,300/day penalty fee), the engine redistributes load start sequences to match regular plant throughput, protecting the net margin while maintaining a 100% SLA pass rate.

- **4-Pass Resilient Dispatch Architecture:**  
  Implements a tiered heuristic fallback:
  1. *Pass 1 (Strict Window)*: Targets delivery within $\pm 15$ minutes of request.
  2. *Pass 2 (Continuous Flow)*: Expands delivery windows while strictly preserving the $< 45$-minute pour gap.
  3. *Pass 3 (Fleet Relocation)*: Reallocates idle trucks from adjacent plants to prevent delivery gaps.
  4. *Pass 4 (Deterministic Fallback)*: Guarantees 100% order assignment with zero unserved loads and zero code crashes.

- **Interactive Executive Dispatcher Dashboard:**  
  A standalone, dependency-free HTML5 visualizer showing fleet Gantt charts, cold-joint warning indicators (Green $< 30$ min, Yellow $30$–$45$ min, Red $> 45$ min), and a financial waterfall decomposition.

---

<div id="business-impact"></div>

## Business Impact & Results <a href="#top" align="right"><sub>[ ▲ Back to Top ]</sub></a>

| Metric | Day 1 (Weekday) | Day 2 (School Opening) | Day 3 (Festival Closure) | Day 4 (Holiday Weekend) | Total / Combined |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **SLA Checks Passed** | **14 / 14** | **14 / 14** | **14 / 14** | **12 / 12** | **54 / 54 (100%)** |
| **Net Contribution** | **฿534,659** | **฿346,668** | **฿381,616** | **฿232,473** | **฿1,495,416** |
| **Cold Joints ($> 45$ min)** | **0** | **0** | **0** | **0** | **0 (Zero)** |
| **Rejected / Failed Loads** | **0** | **0** | **0** | **0** | **0 (Zero)** |
| **Loads Dispatched** | 193 loads | 134 loads | 143 loads | 75 loads | **545 loads** |
| **Fleet Travel Distance** | 5,409 km | 4,518 km | 4,917 km | 2,536 km | **17,380 km** |
| **Carbon Emissions** | 4,595 kg CO₂ | 3,840 kg CO₂ | 4,179 kg CO₂ | 2,156 kg CO₂ | **14,770 kg CO₂** |
| **Solver Runtime** | **0.65 s** | **0.58 s** | **0.62 s** | **0.42 s** | **Avg ~0.57 s** |

- **Zero Ruined Batches:** 100% compliance with the 120-minute slump life eliminated all scrapped concrete and vehicle drum damage.
- **-445 kg CO₂ Reduction:** Optimized empty-truck routing and zero dumped concrete prevented unnecessary clinker production and excess vehicle mileage.
- **฿46,300 Daily Savings:** Native baseline production utilization avoided all supplementary line expansion charges.

---

<div id="challenges-solutions"></div>

## Challenges & Solutions <a href="#top" align="right"><sub>[ ▲ Back to Top ]</sub></a>

- **Challenge 1: Severe Traffic Spikes from School Openings and Festival Roadblocks**  
  - *Context:* Morning school rush (07:30–08:30) and urban festival closures caused travel times between plants and sites to surge by over 200%, threatening the 120-minute slump life limit.  
  - *Solution:* Implemented a backward-looking shift heuristic that detects congestion windows and negotiates valid delivery shifts for lower-priority orders. This avoided peak traffic without breaching contract terms, leaving clear transit windows for high-priority G1 clients.

- **Challenge 2: Batching Tower Queuing on Concurrent Pours**  
  - *Context:* Large construction sites often request two mixer trucks simultaneously every 20 minutes, causing severe batching queue delays at single-line plants.  
  - *Solution:* Built an automated stream-splitting mechanism that routes parallel streams to complementary plants. The solver staggers production starts based on differing travel times, ensuring both streams arrive at the job site synchronized.

- **Challenge 3: Offline Robustness on Unknown Test Instances (Hidden Day 5)**  
  - *Context:* The competition required the solver to run offline on unknown datasets within a 5-minute timeout, with zero human intervention and zero reliance on external solvers.  
  - *Solution:* Engineered the core algorithm in standard-library Python using deterministic priority queues and multi-pass fallbacks. The engine finishes in 0.65 seconds—450 times faster than the allotted limit—with guaranteed convergence and zero runtime exceptions.

---

<div id="how-to-run"></div>

## How to Run & Setup <a href="#top" align="right"><sub>[ ▲ Back to Top ]</sub></a>

### 1. Clone Repository
```bash
git clone https://github.com/thapanon-chu/ai-concrete-logistics-optimizer.git
cd ai-concrete-logistics-optimizer/01_Grand_Finals
```

### 2. Run Daily Solver (Zero External Dependencies)
```bash
# Solves Day 1 (Weekday scenario) and generates plan.csv, order_changes.csv, production_plan.csv
python code/solve.py data/day1_weekday out/day1
```

### 3. Evaluate Solution Against Official Competition Harness
```bash
python code/evaluate.py data/day1_weekday out/day1/plan.csv \
  --changes out/day1/order_changes.csv \
  --production out/day1/production_plan.csv
```

### 4. Batch Verification Across All 4 Operational Days
```bash
python -c "
import subprocess, sys
days = [('day1_weekday', 'day1'), ('day2_school_opening', 'day2'), ('day3_festival', 'day3'), ('day4_holiday', 'day4')]
for data_folder, out_folder in days:
    subprocess.run([sys.executable, 'code/solve.py', f'data/{data_folder}', f'out/{out_folder}'])
    subprocess.run([sys.executable, 'code/evaluate.py', f'data/{data_folder}', f'out/{out_folder}/plan.csv', '--changes', f'out/{out_folder}/order_changes.csv', '--production', f'out/{out_folder}/production_plan.csv'])
"
```

---

<p align="center">
  <a href="#top"><b>▲ Back to Top</b></a> &nbsp;&bull;&nbsp; 
  <a href="../../README.md"><b>⬅️ Back to Main Portfolio</b></a>
</p>
