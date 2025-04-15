import sys
import osmnx as ox
import networkx as nx
import time
import asyncio
from geopy.distance import geodesic
import math
import folium
import os
from folium import Circle, PolyLine, Polygon as FoliumPolygon
import shutil
import logging
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

logger.info("Flask application started, logging initialized!")

# Ensure cache directory exists
os.makedirs(Config.CUSTOM_CACHE_DIR, exist_ok=True)
ox.settings.cache_folder = Config.CUSTOM_CACHE_DIR
ox.settings.use_cache = False
ox.settings.cache_only_mode = False

sys.stdout.flush()

class RoutePlanner:
    def __init__(self, start_location, start_name, network_type, end_location=None, end_name=None, radius_meters=None):
        self.start_location = start_location
        self.start_name = start_name
        self.end_location = end_location
        self.end_name = end_name
        self.radius_km = radius_meters / 1000 if radius_meters else None
        self.graph = None
        self.unique_routes = []
        self.job_id = None
        self.progress_tracker = None
        self.network_type = network_type

    def set_progress_tracker(self, job_id, progress_tracker):
        """
        Set up progress tracking for this planner.
        """
        self.job_id = job_id
        self.progress_tracker = progress_tracker

    def update_progress(self, completed_routes, total_routes, start_time):
        """
        Update the progress using the provided tracker.
        """
        if not self.job_id or not self.progress_tracker:
            return

        elapsed_time = time.time() - start_time
        avg_time_per_route = elapsed_time / completed_routes if completed_routes > 0 else 0
        remaining_routes = total_routes - completed_routes
        estimated_time_remaining = avg_time_per_route * remaining_routes

        progress_data = {
            "timeRunning": completed_routes,
            "timeDuration": total_routes,
            "timeEstimate": estimated_time_remaining
        }
        
        # Call the progress tracker function
        self.progress_tracker(progress_data)

    def fetch_graph_radius(self):
        if not self.radius_km:
            logger.error("Radius is required to fetch the graph.")
            raise ValueError("Radius is required to fetch the graph.")

        logger.info("Fetching graph for location %s with radius %.2f km", self.start_location, self.radius_km)

        logger.info("Network type: %s", self.network_type)
        logger.info(f"Truncate by edge: {TRUNCATE_EDGE}")
        logger.info(f"Simplify: {SIMPLIFY}")
        logger.info(f"Retain: {RETAIN}")
        try:
            graph = ox.graph_from_point(
                self.start_location,
                dist=self.radius_km * 1000,
                network_type=self.network_type.lower(), 
                simplify = True,
                truncate_by_edge = False, 
                retain_all = False
            )
            if not graph:
                raise ValueError("Graph fetch returned None.")

            self.graph = graph  # Explicitly assign graph here
            logger.info("Graph fetched: %d nodes, %d edges", len(self.graph.nodes), len(self.graph.edges))
        except Exception as e:
            logger.error("Error fetching graph: %s", str(e), exc_info=True)
            self.graph = None
            raise

    def fetch_graph_polygon(self, polygon):
        """
        Fetch a road network graph for the provided polygon.
        """
        logger.info("Network type: %s", self.network_type)
        logger.info(f"Truncate by edge: {Config.TRUNCATE_EDGE}")
        logger.info(f"Simplify: {Config.SIMPLIFY}")
        logger.info(f"Retain: {Config.RETAIN}")
        try:
            self.graph = ox.graph_from_polygon(
                polygon,
                network_type=self.network_type.lower(),
                simplify=bool(Config.SIMPLIFY), 
                truncate_by_edge= bool(Config.TRUNCATE_EDGE),
                retain_all=bool(Config.RETAIN)
            )

            if not self.graph:
                logger.error("Failed to fetch graph for polygon")
                raise ValueError("Failed to fetch graph. Please verify the polygon.")

        except Exception as e:
            logger.error("Error fetching graph: %s", str(e))
            self.graph = None

    async def compute_routes_start_radius(self):
        if not self.radius_km:
            raise ValueError("Radius is required for local route computation.")

        if not self.graph:
            self.fetch_graph_radius()

        start_node = ox.distance.nearest_nodes(self.graph, self.start_location[1], self.start_location[0])
        logger.info("Computing routes from start node...")
        self.unique_routes = []  # Initialize unique routes list
        seen_routes = set()  # Track unique routes
        start_time = time.time()
        total_nodes = len(self.graph.nodes)
        completed_nodes = 0

        for target_node in self.graph.nodes:
            if target_node != start_node:
                try:
                    routes = list(nx.all_simple_paths(self.graph, source=start_node, target=target_node))  # Added cutoff to limit path length
                    for route in routes:
                        route_tuple = tuple(route)  # Convert route to tuple for hashing
                        if route_tuple not in seen_routes:
                            self.unique_routes.append(route)
                            seen_routes.add(route_tuple)
                except nx.NetworkXNoPath:
                    pass
                finally:
                    completed_nodes += 1
                    self.update_progress(completed_nodes, total_nodes, start_time)

        logger.info("Found %d unique routes", len(self.unique_routes))

    async def compute_routes_start_end_radius(self):
        """
        Compute all unique routes between start and end points using a radius.
        """
        if not self.end_location:
            raise ValueError("End location is required to compute routes between start and end points.")

        if not self.graph:
            self.fetch_graph_radius()

        start_node = ox.distance.nearest_nodes(self.graph, self.start_location[1], self.start_location[0])
        end_node = ox.distance.nearest_nodes(self.graph, self.end_location[1], self.end_location[0])

        logger.info("Finding all possible simple paths between start and end nodes...")
        try:
            start_time = time.time()  # Start timing the route finding
            all_routes = list(nx.all_simple_paths(self.graph, source=start_node, target=end_node))
            self.update_progress(1, 1, start_time)  # Update progress once all routes are found
        except nx.NetworkXNoPath:
            logger.info("No path found between start and end nodes.")
            self.unique_routes = []
            return

        logger.info("Found %d possible routes. Removing duplicates...", len(all_routes))
        seen_routes = set()
        for route in all_routes:
            route_set = frozenset(route)
            if route_set not in seen_routes:
                self.unique_routes.append(route)
                seen_routes.add(route_set)

        logger.info("%d unique routes found.", len(self.unique_routes))

    async def compute_routes_start_polygon(self, polygon):
        """
        Compute all unique routes starting from the given start location within a specified polygon.
        """
        if not polygon:
            raise ValueError("Polygon is required for local route computation.")

        self.fetch_graph_polygon(polygon)

        if not self.graph:
            raise ValueError("Graph could not be fetched for the given polygon.")

        start_node = ox.distance.nearest_nodes(self.graph, self.start_location[1], self.start_location[0])

        logger.info("Computing routes from start node within the polygon...")
        seen_routes = set()  # Track unique routes
        start_time = time.time()
        total_nodes = len(self.graph.nodes)
        completed_nodes = 1

        for target_node in self.graph.nodes:
            if target_node != start_node:
                try:
                    routes = list(nx.all_simple_paths(self.graph, source=start_node, target=target_node))  # Added cutoff to limit path length
                    for route in routes:
                        route_tuple = tuple(route)  # Convert route to tuple for hashing
                        if route_tuple not in seen_routes:
                            self.unique_routes.append(route)
                            seen_routes.add(route_tuple)
                except nx.NetworkXNoPath:
                    pass
                finally:
                    completed_nodes += 1
                    self.update_progress(completed_nodes, total_nodes, start_time)

        logger.info("Found %d unique routes", len(self.unique_routes))

    async def compute_routes_start_end_polygon(self, polygon):
        """
        Compute all unique routes between start and end points within a given polygon.
        """
        if not self.end_location:
            raise ValueError("End location is required to compute routes between start and end points.")

        self.fetch_graph_polygon(polygon)

        if not self.graph:
            self.fetch_graph_polygon(polygon)

        start_node = ox.distance.nearest_nodes(self.graph, self.start_location[1], self.start_location[0])
        end_node = ox.distance.nearest_nodes(self.graph, self.end_location[1], self.end_location[0])

        logger.info("Finding all possible simple paths between start and end nodes within the polygon...")
        try:
            start_time = time.time()  # Start timing the route finding
            all_routes = list(nx.all_simple_paths(self.graph, source=start_node, target=end_node))
            self.update_progress(1, 1, start_time)  # Update progress once all routes are found
        except nx.NetworkXNoPath:
            logger.info("No path found between start and end nodes within the polygon.")
            self.unique_routes = []
            return

        logger.info("Found %d possible routes. Removing duplicates...", len(all_routes))
        seen_routes = set()
        for route in all_routes:
            route_set = frozenset(route)
            if route_set not in seen_routes:
                self.unique_routes.append(route)
                seen_routes.add(route_set)

        logger.info("%d unique routes found.", len(self.unique_routes))

    def filter_routes_by_point(self, middle_points):
        """
        Filter routes that pass through all specified middle points.
        """
        try:
            if not isinstance(middle_points, list):
                raise ValueError("middle_points must be a list of dictionaries with 'latitude' and 'longitude' keys.")

            for point in middle_points:
                if not isinstance(point, dict) or 'latitude' not in point or 'longitude' not in point:
                    raise ValueError(f"Invalid middle point format: {point}")

            # Find the nearest nodes for all middle points
            target_nodes = [
                ox.distance.nearest_nodes(self.graph, point['longitude'], point['latitude'])
                for point in middle_points
            ]

            # Filter routes that pass through all target nodes
            filtered_routes = [
                route for route in self.unique_routes
                if all(target_node in route for target_node in target_nodes)
            ]
            logger.info("Number of filtered routes: %d", len(filtered_routes))

            self.unique_routes = filtered_routes
            return self.get_route_polylines()

        except Exception as e:
            logger.error("Error in filter_routes_by_points: %s", str(e))
            raise

    def get_route_polylines(self):
        """
        Return the polyline (list of coordinates) for each route.
        """
        if not self.graph:
            raise ValueError("Graph is not loaded. Cannot generate polylines.")

        route_polylines = []
        for idx, route in enumerate(self.unique_routes):
            path_coords = []
            for u, v in zip(route[:-1], route[1:]):
                # Get edge data including geometry
                edge_data = self.graph.get_edge_data(u, v)
                if edge_data and 'geometry' in edge_data[0]:
                    # Extract all points from the LineString geometry
                    points = list(edge_data[0]['geometry'].coords)
                    # Convert to (lat, lon) format and extend path
                    path_coords.extend([(y, x) for x, y in points])
                else:
                    # Fallback to node coordinates if no geometry
                    path_coords.append((self.graph.nodes[u]['y'], self.graph.nodes[u]['x']))
                    path_coords.append((self.graph.nodes[v]['y'], self.graph.nodes[v]['x']))
            
            # Remove duplicate consecutive points
            cleaned_coords = [path_coords[0]]
            for coord in path_coords[1:]:
                if coord != cleaned_coords[-1]:
                    cleaned_coords.append(coord)
            
            route_polylines.append({
                "route_id": idx + 1,
                "polyline": cleaned_coords
            })

        return route_polylines
