# Command to run with the Radius, Start Point, End Point (Optional) and Middle Points (Optional)
 
curl -X POST http://127.0.0.1:4000/compute_routes_radius \
-H "Content-Type: application/json" \
-d '{
    "radius": 200,
    "start": {"latitude": 42.42626794837496, "longitude": 12.112142752621084},
    "end": {},
    "middle_points": []
}' |  python3 -m json.tool
 
# Command to run with the Polygon, Start Point, End Point (Optional) and Middle Points (Optional)
 
curl -X POST http://127.0.0.1:4000/compute_routes_polygon \
-H "Content-Type: application/json" \
-d '{
    "polygon": [
        {"latitude": 42.426883263509616, "longitude": 12.109261884975314},
        {"latitude": 42.42839699369467, "longitude": 12.112309547810716},
        {"latitude": 42.42669404466632, "longitude": 12.114488484323877},
        {"latitude": 42.42469669982139, "longitude": 12.112508927622379},
        {"latitude": 42.424570549589426, "longitude": 12.109660644598637}
    ],
    "start": {"latitude": 42.42626794837496, "longitude": 12.112142752621084},
    "end": {},
    "middle_points": []
}' |  python3 -m json.tool
