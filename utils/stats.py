import math
from geopy.distance import geodesic


def compute_route_distance(route, graph):
    """
    Calculate the total distance of a route.

    Returns:
        dict with:
            - total_distance (float): total distance in meters
    """
    total_distance = 0.0

    for u, v in zip(route, route[1:]):
        edge_data = graph.get_edge_data(u, v)
        length = None
        if edge_data:
            data = list(edge_data.values())[0]
            length = data.get('length')

        if length is None:
            coord_u = (graph.nodes[u]['y'], graph.nodes[u]['x'])
            coord_v = (graph.nodes[v]['y'], graph.nodes[v]['x'])
            length = geodesic(coord_u, coord_v).meters

        total_distance += length

    return {"total_distance": total_distance}


def compute_road_types(route, graph):
    """
    Count the occurrences of each highway type along the route.

    Returns:
        dict: keys are highway types, values are counts
    """
    highway_counts = {}
    for u, v in zip(route, route[1:]):
        edge_data = graph.get_edge_data(u, v)
        if not edge_data:
            continue
        data = list(edge_data.values())[0]
        highway = data.get('highway', 'undefined')
        if isinstance(highway, list):
            highway = highway[0]
        highway_counts[highway] = highway_counts.get(highway, 0) + 1
    return highway_counts


def compute_turn_count(route, graph, angle_threshold=30):
    """
    Count turns along the route based on an angle threshold.

    Returns:
        dict with:
            - turn_count (int)
    """
    def angle_between(p, q, r):
        v1 = (p[0] - q[0], p[1] - q[1])
        v2 = (r[0] - q[0], r[1] - q[1])
        ang1 = math.atan2(v1[1], v1[0])
        ang2 = math.atan2(v2[1], v2[0])
        ang = abs(math.degrees(ang2 - ang1))
        return ang if ang <= 180 else 360 - ang

    turns = 0
    for prev_id, curr_id, next_id in zip(route, route[1:], route[2:]):
        p = (graph.nodes[prev_id]['y'], graph.nodes[prev_id]['x'])
        q = (graph.nodes[curr_id]['y'], graph.nodes[curr_id]['x'])
        r = (graph.nodes[next_id]['y'], graph.nodes[next_id]['x'])
        if angle_between(p, q, r) > angle_threshold:
            turns += 1
    return {"turn_count": turns}


def get_route_statistics(route_planner):
    """
    Compute minimal route statistics for each route and overall.

    Returns:
        tuple:
            - individual_stats (list[dict]): each dict has total_distance, road_type, turn_count
            - overall_stats (dict): aggregated stats including longest and shortest route info
    """
    graph = route_planner.graph
    individual_stats = []

    # Compute stats per route
    for idx, route in enumerate(route_planner.unique_routes, start=1):
        dist = compute_route_distance(route, graph)["total_distance"]
        road_type = compute_road_types(route, graph)
        turn_cnt = compute_turn_count(route, graph)["turn_count"]
        individual_stats.append({
            "route_id": idx,
            "total_distance": dist,
            "road_type": road_type,
            "turn_count": turn_cnt
        })

    # Compute overall statistics
    overall_stats = {}
    if individual_stats:
        distances = [r["total_distance"] for r in individual_stats]
        shortest_distance = min(distances)
        longest_distance = max(distances)
        shortest_id = next(r["route_id"] for r in individual_stats if r["total_distance"] == shortest_distance)
        longest_id = next(r["route_id"] for r in individual_stats if r["total_distance"] == longest_distance)

        overall_stats = {
            "shortest_route": {
                "route_id": shortest_id,
                "distance": shortest_distance
            },
            "longest_route": {
                "route_id": longest_id,
                "distance": longest_distance
            }
        }

    return individual_stats, overall_stats
