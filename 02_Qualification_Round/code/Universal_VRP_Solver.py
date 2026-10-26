import math
import re
import sys
import os
import json
import argparse
import time
from typing import List, Tuple, Dict, Any
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# =====================================================================
# AI Hackathon Route Optimization 2026 - Universal VRP Solver
# โค้ดนี้ถูกออกแบบมาเพื่อรองรับตั้งแต่โจทย์ CVRP พื้นฐาน (ทำ Gap 0%)
# ไปจนถึงโจทย์ระดับสูงในโลกจริง เช่น Time Windows, รถ EV, สินค้าหมดอายุ
# =====================================================================

def compute_euclidean_distance(p1, p2):
    """
    คำนวณระยะทางแบบเส้นตรง (Euclidean Distance) ระหว่าง 2 พิกัด
    และปัดเศษเป็นจำนวนเต็ม เพื่อให้ตรงกับมาตรฐานสากลของ TSPLIB
    """
    return round(math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2))

def parse_vrp_file(filepath: str) -> Dict[str, Any]:
    """
    ฟังก์ชันสกัดข้อมูลอัจฉริยะ (Dynamic Parser)
    อ่านไฟล์โจทย์ .vrp โดยไม่อาศัยการฝังตัวเลขตายตัว (No Hardcoding)
    ทำให้สามารถรองรับไฟล์โจทย์หน้าตาแบบใดก็ได้
    """
    data = {
        'name': '',
        'capacity': 0,
        'num_vehicles': 0,
        'optimal_value': None,
        'coordinates': {},
        'demands': {},
        'depot': 1 # ค่าเริ่มต้น ให้จุดที่ 1 เป็นโกดัง (Depot)
    }
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # --- ดึงข้อมูลหน้าปก (Metadata) ---
    match = re.search(r'NAME\s*:\s*(.*)', content)
    if match: data['name'] = match.group(1).strip()
    
    # ดึงความจุสูงสุดของรถ
    match = re.search(r'CAPACITY\s*:\s*(\d+)', content)
    if match: data['capacity'] = int(match.group(1))
    
    # พยายามดึงจำนวนรถจากชื่อไฟล์ (เช่น -k5 หมายถึง รถ 5 คัน)
    k_match = re.search(r'-k(\d+)', data['name'])
    if k_match: data['num_vehicles'] = int(k_match.group(1))
    
    # อ่านคำใบ้เฉลย (Optimal Value) (ถ้ามี) เพื่อเตรียมเอาไปคำนวณ Gap % ตอนจบ
    comment_match = re.search(r'COMMENT\s*:\s*(.*)', content)
    if comment_match:
        comment = comment_match.group(1)
        truck_match = re.search(r'[Tt]rucks?\s*:\s*(\d+)', comment)
        if truck_match: data['num_vehicles'] = int(truck_match.group(1))
        opt_match = re.search(r'[Oo]ptimal [Vv]alue\s*:\s*(\d+)', comment)
        if opt_match: data['optimal_value'] = int(opt_match.group(1))
            
    # ถ้าโจทย์ไม่ได้บอกจำนวนรถมา ให้เผื่อไว้ 10 คัน
    if data['num_vehicles'] == 0: data['num_vehicles'] = 10
        
    # --- ดึงข้อมูลตารางดิบ (Raw Data) ---
    lines = content.split('\n')
    parsing_coords = False
    parsing_demands = False
    parsing_depot = False
    
    # loop อ่าน จนเจอ NODE DEMAND DEPOT
    for line in lines:
        line = line.strip()
        if not line or line == 'EOF': continue
        
        # สลับสวิตช์การอ่านเมื่อเจอหัวข้อ (Section) ที่ต้องการ
        if line.startswith('NODE_COORD_SECTION'):
            parsing_coords, parsing_demands, parsing_depot = True, False, False
            continue
        elif line.startswith('DEMAND_SECTION'):
            parsing_coords, parsing_demands, parsing_depot = False, True, False
            continue
        elif line.startswith('DEPOT_SECTION'):
            parsing_coords, parsing_demands, parsing_depot = False, False, True
            continue
            
        # เก็บพิกัดแกน X, Y ของแต่ละ Node จาก NODE_COORD_SECTION
        if parsing_coords:
            parts = line.split()
            if len(parts) >= 3:
                data['coordinates'][int(parts[0])] = (float(parts[1]), float(parts[2]))
        # เก็บความต้องการสินค้าของแต่ละ Node จาก DEMAND_SECTION
        elif parsing_demands:
            parts = line.split()
            if len(parts) >= 2:
                data['demands'][int(parts[0])] = int(parts[1])
        # ยืนยันจุดหมายเลขใดคือโกดัง (อ่านหมายเลข Node ที่เป็น Depot)
        elif parsing_depot:
            parts = line.split()
            if parts and int(parts[0]) != -1:
                data['depot'] = int(parts[0])
                
    return data

def build_data_model(vrp_data: Dict[str, Any], config_path: str = None) -> Tuple[Dict[str, Any], List[int]]:
    """
    ฟังก์ชัน "ล่ามแปลภาษา" (Data Transformer)
    แปลงข้อมูลดิบ ให้กลายเป็น "ตารางโครงสร้าง (Matrix)" ที่สมองกลของ OR-Tools เข้าใจ
    รวมถึงควบรวมเงื่อนไขพิเศษจากไฟล์ .json (ถ้ามี)
    """
    data = {}
    sorted_nodes = sorted(list(vrp_data['coordinates'].keys()))
    
    # 1. สร้างตารางระยะทาง (Distance Matrix) จับคู่ทุกจุดเข้าด้วยกัน
    data['distance_matrix'] = []
    for i in sorted_nodes:
        row = []
        for j in sorted_nodes:
            if i == j: row.append(0)
            else: row.append(compute_euclidean_distance(vrp_data['coordinates'][i], vrp_data['coordinates'][j]))
        data['distance_matrix'].append(row)
        
    # จัดเรียงออเดอร์ของลูกค้าให้เป็น Array แถวตอนเรียงหนึ่ง
    data['demands'] = [vrp_data['demands'].get(i, 0) for i in sorted_nodes]
    data['num_vehicles'] = vrp_data['num_vehicles']
    
    # หาลำดับ (Index) ของโกดัง โดยคอมพิวเตอร์จะนับจุดแรกเป็นเลข 0 เสมอ (0-indexing)
    data['depot'] = sorted_nodes.index(vrp_data['depot'])
    
    # --- ค่าเริ่มต้นสำหรับโจทย์ VRP ทั่วไป ---
    data['vehicle_capacities'] = [vrp_data['capacity']] * vrp_data['num_vehicles']
    data['vehicle_costs'] = [1] * vrp_data['num_vehicles'] # ต้นทุนรถทุกคันเท่ากัน
    data['time_windows'] = []
    data['service_times'] = [0] * len(sorted_nodes)
    data['max_time_per_route'] = 0
    
    # --- ดึงความเงื่อนไขเสริม (Advanced Constraints) จากไฟล์ JSON (ถ้ามี)---
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            # ถ้ามีข้อมูลรถสเปกต่างกัน (Heterogeneous Fleet) ให้เขียนทับของเดิม
            if 'num_vehicles' in cfg: data['num_vehicles'] = cfg['num_vehicles']
            if 'vehicle_capacities' in cfg: data['vehicle_capacities'] = cfg['vehicle_capacities']
            if 'vehicle_costs' in cfg: data['vehicle_costs'] = cfg['vehicle_costs']
            if 'time_windows' in cfg: data['time_windows'] = cfg['time_windows']
            if 'service_times' in cfg: data['service_times'] = cfg['service_times']
            if 'max_time_per_route' in cfg: data['max_time_per_route'] = cfg['max_time_per_route']
            
    return data, sorted_nodes

def format_route_string(stops: List[str], max_width: int = 75, indent: str = "          -> ") -> str:
    """จัดรูปแบบเส้นทางให้ตัดขึ้นบรรทัดใหม่อย่างสวยงาม ไม่แตกหรือขาดกลางคำ"""
    lines = []
    current_line = []
    current_len = 10
    for stop in stops:
        stop_len = len(stop) + 4
        if current_line and (current_len + stop_len > max_width):
            lines.append(" -> ".join(current_line))
            current_line = [stop]
            current_len = len(indent) + len(stop)
        else:
            current_line.append(stop)
            current_len += stop_len
    if current_line:
        lines.append(" -> ".join(current_line))
    return f"\n{indent}".join(lines)

def solve_universal_vrp(vrp_file: str, config_file: str = None, time_limit: int = 10):
    """
    ฟังก์ชัน "สมองกล" (The Optimizer) ทำหน้าที่แก้โจทย์ CVRP อย่างครอบคลุม
    ใช้ Google OR-Tools ในการหาเส้นทางที่ประหยัดที่สุด ภายใต้ข้อจำกัดต่างๆ (Capacity, Time Windows, Heterogeneous Fleet)
    """
    vrp_data = parse_vrp_file(vrp_file)
    data, node_mapping = build_data_model(vrp_data, config_file)
    
    total_customers = len(data['demands']) - 1
    total_demand = sum(data['demands'])
    config_name = os.path.basename(config_file) if config_file else "None (Standard TSPLIB Benchmark)"
    
    has_time_windows = len(data['time_windows']) > 0
    strategy_display = "PARALLEL_CHEAPEST_INSERTION + GUIDED_LOCAL_SEARCH" if has_time_windows else "PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH"
    
    print("\n" + "=" * 78)
    print("                  UNIVERSAL LOGISTICS ROUTE OPTIMIZER")
    print("=" * 78)
    print(f" [Problem File]      : {os.path.basename(vrp_file)}")
    print(f" [Total Nodes]       : {len(node_mapping)} (Depot: Node {vrp_data['depot']}, Customers: {total_customers})")
    print(f" [Total Demand]      : {total_demand} units")
    print(f" [Available Fleet]   : {data['num_vehicles']} vehicles")
    print(f" [Advanced Config]   : {config_name}")
    print(f" [Search Strategy]   : {strategy_display}")
    print(f" [Time Limit]        : {time_limit} seconds")
    print("-" * 78)
    print("[*] Initializing distance matrix and constraints...")
    print("[*] Searching for optimal routing solution...")

    start_time = time.time()
    
    # สร้างตัวจัดการเส้นทางของ Google OR-Tools
    manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']), data['num_vehicles'], data['depot'])
    routing = pywrapcp.RoutingModel(manager)

    # ================= 1. กฎระยะทาง และ ต้นทุนรถ (Heterogeneous Fleet) =================
    vehicle_callbacks = []
    for vehicle_id in range(data['num_vehicles']):
        def vehicle_cost_callback(from_index, to_index, v_id=vehicle_id):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            dist = data['distance_matrix'][from_node][to_node]
            # เอาระยะทาง ไปคูณกับ 'ตัวคูณต้นทุน' ของรถแต่ละประเภท (เช่น รถ EV คูณ 1, รถน้ำมัน คูณ 3)
            return int(dist * data['vehicle_costs'][v_id])
        
        cb_index = routing.RegisterTransitCallback(vehicle_cost_callback)
        routing.SetArcCostEvaluatorOfVehicle(cb_index, vehicle_id)
        vehicle_callbacks.append(cb_index)

    # ================= 2. กฎความจุสินค้า (Capacity Constraints) =================
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]
        
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index, 
        0, 
        data['vehicle_capacities'], # ดึงรายการความจุของรถทุกคันมาตั้งเป็นเพดานห้ามเกิน
        True, 
        'Capacity'
    )

    # ================= 3. กฎควบคุมเวลาจัดส่ง (Time Windows & Perishability) =================
    has_time_windows = len(data['time_windows']) > 0
    has_max_time = data['max_time_per_route'] > 0
    
    # หากโจทย์มีเรื่องข้อจำกัดด้านเวลาเข้ามาเกี่ยวข้อง
    if has_time_windows or has_max_time:
        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # เวลาที่ใช้จริง = เวลาจอดลงของ + เวลาเดินทางบนถนน
            service = data['service_times'][from_node]
            travel = data['distance_matrix'][from_node][to_node]
            return service + travel

        time_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.AddDimension(
            time_callback_index,
            1000 if has_time_windows else 0,  # อนุญาตให้รถมาถึงก่อนเวลาและจอดรอ (Waiting Time) ได้ หากยังไม่ถึงรอบเวลาเข้ารับของ
            data['max_time_per_route'] if has_max_time else 9999999, # ป้องกันสินค้าเน่าเสีย / ห้ามทำเกินเวลา
            not has_time_windows,  
            'Time'
        )
        
        # # หากมีการระบุ Time Window ของแต่ละ Node (หรือ Seller) โปรแกรมจะทำการล็อคกรอบเวลาให้บริการ
        if has_time_windows:
            time_dimension = routing.GetDimensionOrDie('Time')
            for idx in range(len(node_mapping)):
                if idx >= len(data['time_windows']): break 
                if idx == data['depot']: continue
                time_window = data['time_windows'][idx]
                index = manager.NodeToIndex(idx)
                time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])
                
            # ตั้งเวลาเปิด-ปิดของศูนย์รวบรวมพัสดุ (Depot/Hub) ให้ครอบคลุมรอบวิ่งของรถทุกคัน
            for i in range(data['num_vehicles']):
                routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(routing.Start(i)))
                routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(routing.End(i)))

    # ================= ตั้งค่าอัลกอริทึม (Solve) =================
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    if has_time_windows:
        # สำหรับโจทย์ Time Windows หนาแน่น การแทรกเส้นทางแบบคู่ขนาน (Parallel Insertion) ป้องกันการติดหล่มเวลา
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    else:
        # สำหรับโจทย์เน้นระยะทางทั่วไป (Benchmark Mode) ใช้ Path Cheapest Arc จะทำ Gap ได้ต่ำที่สุด
        search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.FromSeconds(time_limit)

    solution = routing.SolveWithParameters(search_parameters)
    elapsed_time = time.time() - start_time

    # ================= สรุปและรายงานผลลัพธ์ (Output) =================
    if solution:
        print(f"[+] Optimization Finished: Solution found in {elapsed_time:.2f} seconds!\n")
        print("=" * 78)
        print("                            ROUTE ASSIGNMENTS")
        print("=" * 78)
        total_dist = 0
        total_cost = 0
        used_vehicles = 0
        
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            route_dist = 0
            route_load = 0
            stops = []
            
            cap = data['vehicle_capacities'][vehicle_id]
            multiplier = data['vehicle_costs'][vehicle_id]
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                real_node = node_mapping[node_index]
                route_load += data['demands'][node_index]
                
                if has_time_windows or has_max_time:
                    time_dim = routing.GetDimensionOrDie('Time')
                    t_var = time_dim.CumulVar(index)
                    stops.append(f"Node {real_node} [Time: {solution.Min(t_var)}]")
                else:
                    if node_index == data['depot'] and len(stops) == 0:
                        stops.append(f"Depot {real_node}")
                    else:
                        stops.append(f"Node {real_node}")
                    
                prev_index = index
                index = solution.Value(routing.NextVar(index))
                route_dist += data['distance_matrix'][manager.IndexToNode(prev_index)][manager.IndexToNode(index)]
                
            # เดินทางกลับถึงโกดัง
            node_index = manager.IndexToNode(index)
            real_node = node_mapping[node_index]
            if has_time_windows or has_max_time:
                time_dim = routing.GetDimensionOrDie('Time')
                t_var = time_dim.CumulVar(index)
                stops.append(f"Depot {real_node} [Time: {solution.Min(t_var)}]")
            else:
                stops.append(f"Depot {real_node}")
                
            # แสดงเฉพาะรถคันที่ถูกนำมาใช้งาน
            if route_dist > 0:
                used_vehicles += 1
                route_cost_display = route_dist * multiplier
                total_dist += route_dist
                total_cost += route_cost_display
                
                load_pct = (route_load / cap * 100) if cap > 0 else 0
                formatted_route = format_route_string(stops, max_width=75)
                print(f"[Vehicle {vehicle_id}] (Capacity: {cap} | Cost Multiplier: {multiplier}x)")
                print(f"  Route : {formatted_route}")
                print(f"  Stats : Load: {route_load}/{cap} ({load_pct:.1f}%) | Distance: {route_dist} | Cost: {route_cost_display:.1f}\n")
                
        print("=" * 78)
        print("                           PERFORMANCE SUMMARY")
        print("=" * 78)
        print(f"  Execution Status     : SUCCESS (Feasible Solution Found)")
        print(f"  Solve Time           : {elapsed_time:.2f} seconds")
        print(f"  Vehicles Utilized    : {used_vehicles} / {data['num_vehicles']}")
        print(f"  Total Distance       : {total_dist}")
        print(f"  Total Objective Cost : {total_cost:.1f}")
        
        # คำนวณความแม่นยำ (Gap %) หากโจทย์ไม่ได้ตั้งค่าซับซ้อนจนเพี้ยนจากโครงสร้างเดิม
        if vrp_data['optimal_value'] and not config_file:
            optimal = vrp_data['optimal_value']
            gap = ((total_dist - optimal) / optimal) * 100
            print(f"  Benchmark Optimal    : {optimal}")
            print(f"  Optimality Gap       : {gap:.2f}%")
            if gap <= 5.0:
                print("  Performance Rating   : EXCELLENT (Gap <= 5%)")
            elif gap <= 10.0:
                print("  Performance Rating   : GOOD (Gap <= 10%)")
            else:
                print("  Performance Rating   : ACCEPTABLE")
        print("=" * 78 + "\n")
    else:
        print(f"\n[-] Optimization FAILED: No solution found within {time_limit}s.")
        print("    (Check if capacity or time window constraints are overly tight)\n")

# =====================================================================
# ตัวอย่างการใช้งานผ่าน Terminal (Command Line)
# 
# 1. รันโหมดปกติ (Mission 2): 
#    python Universal_VRP_Solver.py A-n32-k5.vrp
#
# 2. รันโหมดขั้นสูงแบบ E-commerce (Mission 3):
#    python Universal_VRP_Solver.py FM01-n29-k6.vrp --config FM01-optional.json
#
# 3. กำหนดเวลาให้ AI คิดค้นหาเส้นทาง (เช่น 30 วินาที):
#    python Universal_VRP_Solver.py FM01-n29-k6.vrp --config FM01-optional.json --time 30
# =====================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Universal Logistics VRP Solver')
    parser.add_argument('file', help='Path to .vrp file')
    parser.add_argument('--config', type=str, default=None, help='Optional path to advanced .json config')
    parser.add_argument('--time', type=int, default=10, help='Time limit in seconds')
    args = parser.parse_args()
    
    if os.path.exists(args.file):
        solve_universal_vrp(args.file, args.config, args.time)
    else:
        print(f"Error: File not found at {args.file}")
