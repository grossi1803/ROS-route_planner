#!/usr/bin/env python

import math
import sys
import os
import logging
from geopy.distance import geodesic
import networkx as nx
import osmnx as ox
import statistics
from utils.config import Config

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(Config.LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(file_formatter)
console_handler.flush = sys.stdout.flush
logger.addHandler(console_handler)

logger.info("Stats module loaded, logging initialized!")

# Ensure cache directory exists
os.makedirs(Config.CUSTOM_CACHE_DIR, exist_ok=True)
ox.settings.cache_folder = Config.CUSTOM_CACHE_DIR
ox.settings.use_cache = False
ox.settings.cache_only_mode = False

# ------------------------ FUNZIONI PER STATISTICHE INDIVIDUALI ------------------------

def compute_route_distance(route, route_planner):
    """
    Calcola la distanza totale della rotta e restituisce anche una lista con la distanza di ogni segmento.
    Ritorna: total_distance, segment_distances list.
    """
    total_distance = 0.0
    segment_distances = []
    for i in range(len(route) - 1):
        u, v = route[i], route[i + 1]
        edge_data = route_planner.graph.get_edge_data(u, v)
        segment_length = None

        if edge_data:
            # Per i MultiGraphs, edge_data è un dizionario: prendi il primo elemento disponibile.
            data = list(edge_data.values())[0]
            if 'length' in data:
                segment_length = data['length']

        if segment_length is None:
            node_u = route_planner.graph.nodes[u]
            node_v = route_planner.graph.nodes[v]
            coord_u = (node_u['y'], node_u['x'])
            coord_v = (node_v['y'], node_v['x'])
            segment_length = geodesic(coord_u, coord_v).meters

        segment_distances.append(segment_length)
        total_distance += segment_length

    return total_distance, segment_distances

def log_total_distance(route, route_planner):
    """
    Logga la distanza totale della rotta e restituisce il valore.
    """
    total_distance, _ = compute_route_distance(route, route_planner)
    logger.info("Total distance: %.2f meters", total_distance)
    return total_distance

def log_road_types(route, route_planner):
    """
    Logga le tipologie di strade (highways) presenti lungo la rotta.
    """
    highway_counts = {}
    for i in range(len(route) - 1):
        u, v = route[i], route[i + 1]
        edge_data = route_planner.graph.get_edge_data(u, v)
        if edge_data:
            data = list(edge_data.values())[0]
            highway = data.get('highway', 'undefined')
            if isinstance(highway, list):
                highway = highway[0]
            highway_counts[highway] = highway_counts.get(highway, 0) + 1
    logger.info("Road types along the route: %s", highway_counts)

def log_turn_stats(route, route_planner):
    """
    Rileva e logga il numero di svolte e l'angolo medio delle svolte lungo la rotta.
    Una svolta viene considerata se l'angolo calcolato supera i 30°.
    """
    turns = 0
    turn_angles = []
    
    def angle_between(p, q, r):
        v1 = (p[0] - q[0], p[1] - q[1])
        v2 = (r[0] - q[0], r[1] - q[1])
        angle1 = math.atan2(v1[1], v1[0])
        angle2 = math.atan2(v2[1], v2[0])
        angle = math.degrees(angle2 - angle1)
        angle = (angle + 360) % 360
        if angle > 180:
            angle = 360 - angle
        return angle

    for i in range(1, len(route) - 1):
        prev_node = route_planner.graph.nodes[route[i - 1]]
        curr_node = route_planner.graph.nodes[route[i]]
        next_node = route_planner.graph.nodes[route[i + 1]]
        p = (prev_node['y'], prev_node['x'])
        q = (curr_node['y'], curr_node['x'])
        r = (next_node['y'], next_node['x'])
        a = angle_between(p, q, r)
        if a > 30:
            turns += 1
            turn_angles.append(a)
    
    logger.info("Detected turns: %d", turns)
    # Se vuoi loggare anche l'angolo medio, puoi decommentare la seguente riga:
    # avg_turn = sum(turn_angles) / len(turn_angles) if turn_angles else 0
    # logger.info("Average turn angle: %.2f degrees", avg_turn)

# ------------------------ STATISTICHE AGGREGATE ------------------------

def log_overall_routes_stats(route_planner):
    """
    Calcola e logga le statistiche aggregate per tutte le rotte:
      - Identifica la rotta più corta e la più lunga (in base alla distanza totale).
    """
    routes_stats = []
    for idx, route in enumerate(route_planner.unique_routes):
        total_distance, _ = compute_route_distance(route, route_planner)
        routes_stats.append({
            'route_number': idx + 1,
            'route': route,
            'distance': total_distance
        })
    
    if not routes_stats:
        logger.info("No routes available for overall statistics.")
        return

    avg_distance = sum(stat['distance'] for stat in routes_stats) / len(routes_stats)
    
    shortest_route = min(routes_stats, key=lambda x: x['distance'])
    longest_route = max(routes_stats, key=lambda x: x['distance'])

    logger.info("========== OVERALL ROUTE STATISTICS ==========")
    logger.info("Number of routes: %d", len(routes_stats))
    logger.info("Average route distance: %.2f meters", avg_distance)
    logger.info("Shortest route: Route %d with %.2f meters", shortest_route['route_number'], shortest_route['distance'])
    logger.info("Shortest route details (node sequence): %s", shortest_route['route'])
    logger.info("Longest route: Route %d with %.2f meters", longest_route['route_number'], longest_route['distance'])
    logger.info("Longest route details (node sequence): %s", longest_route['route'])
    logger.info("========== END OVERALL ROUTE STATISTICS ==========")

# ------------------------ FUNZIONE PRINCIPALE ------------------------

def log_all_route_stats(route_planner):
    """
    Chiama le funzioni per loggare solo le seguenti statistiche:
      - Total distance (per ciascuna rotta)
      - Road type (per ciascuna rotta)
      - Detected turns (per ciascuna rotta)
      - Overall: Shortest and Longest route con i dettagli specifici.
    """
    logger.info("========== BEGIN ROUTE STATISTICS ==========")
    
    # Logga le statistiche per ogni rotta.
    for idx, route in enumerate(route_planner.unique_routes):
        logger.info("========== ROUTE %d ==========", idx + 1)
        total_distance = log_total_distance(route, route_planner)
        log_road_types(route, route_planner)
        log_turn_stats(route, route_planner)
    
    # Logga le statistiche aggregate per tutte le rotte.
    log_overall_routes_stats(route_planner)
    
    logger.info("========== END ROUTE STATISTICS ==========")

# ------------------------ END OF SCRIPT ------------------------

