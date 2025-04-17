import os
from flask import Flask, request, jsonify
import asyncio
import uuid
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pymongo
from pymongo import MongoClient
from bson.binary import Binary, UUID_SUBTYPE
from shapely.geometry import Polygon
import osmnx as ox
import shutil
from utils.config import Config
from utils.route_planner_class import RoutePlanner
import os
from utils.stats import get_route_statistics


# Simplify the logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(Config.LOG_FILE)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info("Flask application started, logging initialized!")

# Ensure cache directory exists
os.makedirs(Config.CUSTOM_CACHE_DIR, exist_ok=True)
ox.settings.cache_folder = Config.CUSTOM_CACHE_DIR
ox.settings.use_cache = False
ox.settings.cache_only_mode = False

# MongoDB Connection
logger.info("Attempting to connect to MongoDB...")
client = MongoClient(Config.MONGO_URI)
db = client[Config.MONGO_DB]
jobs_collection = db['job_status']
routes_collection = db['result_routes']
logger.info("Connected to MongoDB successfully.")

executor = ThreadPoolExecutor(max_workers=4)
app = Flask(__name__)

# Keep only important log messages
@app.route("/start_job", methods=["POST"])
def start_job():
    try:
        data = request.get_json()
        # Validate start coordinates
        if "start" not in data:
            return jsonify({"error": "Missing required field: start"}), 400
        # Validate that either radius or polygon is provided
        if "radius" not in data and "polygon" not in data:
            return jsonify({"error": "Either radius or polygon must be provided"}), 400
        if "network_type" not in data:
            return jsonify({"error": "Missing required field: network_type"}), 400

        job_id1 = uuid.uuid4()
        job_id = str(job_id1)
        current_time = datetime.now(timezone.utc)

        job_document = {
            "id": Binary(job_id1.bytes, UUID_SUBTYPE),
            "returnCode": 1,
            "model_id": 5,
            "timeRunning": 0,
            "timeDuration": 0,
            "timeEstimate": 0,
            "timeStart": current_time,
            "timeEnd": None
        }

        jobs_collection.insert_one(job_document)
        logger.info("Started job %s", job_id)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_in_executor(executor, schedule_job, job_id, data)

        return jsonify({"job_id": job_id}), 202
    except Exception as e:
        logger.error("Failed to start job: %s", str(e))
        return jsonify({"error": "Failed to start job"}), 400


def schedule_job(job_id, data):
    logger.info("Processing job: %s", job_id)
    try:
        network_type = data.get("network_type", Config.TYPE_OF_MAP)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_job(job_id, data, network_type))
        logger.info("Job %s completed successfully", job_id)
        jobs_collection.update_one(
            {"id": Binary(uuid.UUID(job_id).bytes, UUID_SUBTYPE)},
            {"$set": {"returnCode": 0, "timeEnd": datetime.now(timezone.utc)}}
        )
    except Exception as e:
        logger.error("Error processing job %s: %s", job_id, str(e))
        jobs_collection.update_one(
            {"id": Binary(uuid.UUID(job_id).bytes, UUID_SUBTYPE)},
            {"$set": {"returnCode": 9, "error": str(e), "timeEnd": datetime.now(timezone.utc)}}
        )

async def process_job(job_id, data, network_type):
    try:
        start = data.get("start")
        radius = data.get("radius")
        polygon_coords = data.get("polygon")
        end = data.get("end")
        middle_points = data.get("middle_points", [])
        
        if not start:
            raise ValueError("Start location is required")
        
        start_location = (start["latitude"], start["longitude"])
        end_location = (end["latitude"], end["longitude"]) if end else None

        logger.info("Job %s: start location: %s, end location: %s, radius: %s, polygon: %s, middle points: %s", 
                   job_id, start_location, end_location, radius, polygon_coords, middle_points)

        def mongo_progress_tracker(progress_data):
            jobs_collection.update_one(
                {"id": Binary(uuid.UUID(job_id).bytes, UUID_SUBTYPE)}, 
                {"$set": progress_data}
            )
        
        planner = RoutePlanner(
            start_location=start_location,
            start_name="Start",
            end_location=end_location,
            end_name="End",
            radius_meters=radius,
            network_type=network_type
        )
        planner.set_progress_tracker(Binary(uuid.UUID(job_id).bytes, UUID_SUBTYPE), mongo_progress_tracker)
        
        if radius:
            if end_location:
                await planner.compute_routes_start_end_radius()
            else:
                await planner.compute_routes_start_radius()
        elif polygon_coords:
            polygon_points = [(pt['longitude'], pt['latitude']) for pt in polygon_coords]
            polygon = Polygon(polygon_points)
            if end_location:
                await planner.compute_routes_start_end_polygon(polygon)
            else:
                await planner.compute_routes_start_polygon(polygon)
        else:
            raise ValueError("Either radius or polygon coordinates must be provided")
        
        routes = planner.filter_routes_by_point(middle_points) if middle_points else planner.get_route_polylines()
        logger.info("Job %s: processed %d routes", job_id, len(routes))

        # Capture stats from get_route_statistics
        routes_stats, summary = get_route_statistics(planner)
        
        # Write per-route docs
        for idx, route in enumerate(routes):
            routes_collection.insert_one({
                "job_id": Binary(uuid.UUID(job_id).bytes, UUID_SUBTYPE),
                "route_id": idx + 1,
                "polyline": {"type": "LineString", "coordinates": route["polyline"]},
                "stats": routes_stats[idx]
            })
        
        # *** ADDED: insert overall summary into job_status ***
        jobs_collection.update_one(
            {"id": Binary(uuid.UUID(job_id).bytes, UUID_SUBTYPE)},
            {"$set": {"overall_stats": summary}}
        )
    
    except Exception as e:
        logger.error("Error in job %s: %s", job_id, str(e))
        raise

if __name__ == "__main__":
    logger.info("Starting Flask application on %s:%s", Config.FLASK_HOST, Config.FLASK_PORT)
    app.run(debug=Config.FLASK_DEBUG, host=Config.FLASK_HOST, port=Config.FLASK_PORT)
