# Route Planner Service

A Python-based microservice for generating and analyzing multiple routing options with OpenStreetMap data. The service computes distance, road-type distribution, and turn counts for each route and provides overall summaries.

---

## Table of Contents
1. [Features](#features)
2. [API Reference](#api-reference)
3. [Data Models](#data-models)
4. [Setup & Installation](#setup--installation)
5. [Usage Examples](#usage-examples)
6. [Error Handling](#error-handling)
7. [Performance Considerations](#performance-considerations)
8. [Monitoring & Logging](#monitoring--logging)
9. [Security](#security)
10. [License](#license)
11. [Support](#support)

---

## Features

### Flexible Route Generation
- **Radius-based**: Explore from a starting point with optional target endpoint.
- **Polygon-based**: Constrain routes within custom polygons.
- **Waypoints**: Filter or direct routes through specified intermediate points.
- **Network Types**: Support for `drive`, `walk`, `bike`, or `all`.

### Detailed Analytics
- **Distance**: Total distance per route, shortest/longest identification.
- **Road Types**: Count of highway classifications (e.g., `motorway`, `residential`).
- **Turns**: Number of turns exceeding a configurable angle threshold (default 30°).
- **Summaries**: Aggregate stats including average distance, number of routes.

### Technical Highlights
- Asynchronous computation powered by `asyncio` and `ThreadPoolExecutor`.
- MongoDB integration for job status and route results.
- Progress tracking hooks for real-time updates.
- Modular design: separate planning, statistics, and API layers.

---

## API Reference

### `POST /start_job`
Starts a new routing job.

**Request Body** (JSON):
```json
{
  "start": { "latitude": 42.42, "longitude": 12.11 },
  "radius": 500,                    // required if no polygon
  "polygon": [                     // required if no radius
    { "latitude": 42.42, "longitude": 12.11 },
    ...
  ],
  "end": { "latitude": 42.45, "longitude": 12.14 }, // optional
  "middle_points": [                // optional
    { "latitude": 42.43, "longitude": 12.12 }
  ],
  "network_type": "drive"        // required: drive|walk|bike|all
}
```

**Successful Response** (202 Accepted):
```json
{ "job_id": "<uuid>" }
```

**Usage**: Use the returned `job_id` to query status or retrieve results.

---

## Data Models

### Job Status (`job_status` collection)
| Field           | Type      | Description                              |
|-----------------|-----------|------------------------------------------|
| `id`            | Binary    | UUID of the job                         |
| `returnCode`    | Int       | `1`=running, `0`=success, `-1`=failed   |
| `timeStart`     | Date      | UTC timestamp when job started          |
| `timeEnd`       | Date      | UTC timestamp when job ended            |
| `overall_stats` | Object    | Aggregated route summary (see below)    |

### Route Results (`result_routes` collection)
| Field          | Type    | Description                                     |
|----------------|---------|-------------------------------------------------|
| `job_id`       | Binary  | UUID reference to job                          |
| `route_id`     | Int     | 1-based index of the route                     |
| `polyline`     | GeoJSON | `LineString` of lat/lon pairs                  |
| `stats`        | Object  | `{ total_distance, road_type, turn_count }`     |

### `overall_stats` Schema
```json
{
  "number_of_routes": 3,
  "average_distance": 1250.5,
  "shortest_route": { "route_id": 2, "distance": 850.3 },
  "longest_route":  { "route_id": 1, "distance": 1600.7 }
}
```

---

## Setup & Installation

**Prerequisites:**
- Python 3.11+
- MongoDB 4.4+
- 2GB RAM, 10GB disk

```bash
# Clone repo
git clone https://github.com/your-org/route-planner.git
cd route-planner
# Create env
python -m venv venv && source venv/bin/activate
# Install deps
pip install -r requirements.txt
```

### Configuration
Create a `.env` file:
```ini
MONGO_URI=mongodb://user:pass@host:27017/
MONGO_DB=route_planner
LOG_DIR=/var/log/route_planner
CUSTOM_CACHE_DIR=/var/cache/route_planner
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
```

---

## Usage Examples

**Simple Radius Route**
```bash
curl -X POST http://localhost:5000/start_job \
  -H "Content-Type: application/json" \
  -d '{"start": {"latitude": 42.42,"longitude":12.11},"radius":500,"network_type":"drive"}'
```

**Polygon with Waypoints**
```bash
curl -X POST http://localhost:5000/start_job \
  -H "Content-Type: application/json" \
  -d '{
    "start": {"latitude":42.42,"longitude":12.11},
    "polygon":[{"latitude":42.42,"longitude":12.11},...],
    "middle_points":[{"latitude":42.43,"longitude":12.12}],
    "network_type":"walk"
  }'
```

---

## Error Handling

| HTTP Code | Condition                   | Response Body                 |
|-----------|-----------------------------|-------------------------------|
| 400       | Validation error            | `{ "error": "..." }`      |
| 404       | No routes found             | `{ "error": "no routes" }`|
| 500       | Internal server error       | `{ "error": "..." }`      |

---

## Performance Considerations
- **Radius < 5km** for best performance
- **Max waypoints: 5**
- **Polygon vertices < 10**
- Schedule weekly cache cleanup

---

## Monitoring & Logging
- **Logs:** `LOG_DIR/app.log`
- **Metrics:** integrate with Prometheus/Grafana as needed

---

## Security
- Enable **HTTPS** in production
- Configure **MongoDB auth** and IP whitelisting
- Implement **rate-limiting** (e.g., nginx or API gateway)

---

## License
MIT License. See [LICENSE](LICENSE).

---

## Support
For questions or bug reports, please open an issue or contact the team at support@example.com.

