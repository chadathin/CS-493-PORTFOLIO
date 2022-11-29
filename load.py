from flask import Blueprint, request, make_response
from google.cloud import datastore
import json
import constants
import verify
from json2html import *
from verify_jwt import verify_jwt, AuthError

client = datastore.Client()

bp = Blueprint('loads', __name__, url_prefix='/loads')

@bp.route('', methods = ["GET", "POST"])
def load_get_post():
    # Add a new load!
    if request.method == "POST":
        content = request.get_json()
        new_load = datastore.entity.Entity(key=client.key(constants.loads))
        try:
            new_load.update(
                {
                    "volume": content["volume"], 
                    "item": content["item"],
                    "creation_date": content["creation_date"],
                    "carrier": None
                }
            )
            
        except:
            return ({"Error": "The request object is missing at least one of the required attributes"}, 400)
        
        client.put(new_load)
        new_load["id"] = new_load.key.id
        new_load["self"] = request.url_root + constants.loads + "/" + str(new_load["id"])
        return (json.dumps(new_load), 201)
    
    elif request.method == "GET":
        get_next = False
        args = request.args
        print(args)
        if len(args) > 0:
            limit = int(args["limit"])
            offset = int(args["offset"])
        else:
            limit = 3
            offset = 0
        query = client.query(kind=constants.loads)
        loads = list(query.fetch(limit=limit+1, offset=offset))
        if len(loads) > limit:
            get_next = True
            loads = loads[0:limit]
        for load in loads:
            load["id"] = load.key.id
            load["self"] = request.base_url + "/"+str(load.key.id)
        out = dict()
        out["length"] = len(loads)

        if get_next:
            out["next"] = request.base_url + "?limit={}&offset={}".format(limit, offset+limit)

        out["loads"] = loads
        
        return (out, 200)
    
@bp.route('/<load_id>', methods = ["GET", "DELETE"])
def loads_get_delete(load_id):
    if request.method == "GET":
        load_key = client.key(constants.loads, int(load_id))
        load = client.get(key=load_key)
        if load is None:
            return({"Error": "No load with this load_id exists"}, 404)
        load["id"] = load.key.id
        load["self"] = request.url
        # load["carrier"] = request.host_url+"boats/"+load["carrier"]
        res = make_response(json.dumps(load))
        res.status_code = 200
        res.mimetype = 'application/json'
        return (res)
    elif request.method == "DELETE":
        # Get the load
        load_key = client.key(constants.loads, int(load_id))
        load = client.get(key=load_key)
        if load is None:
            return({"Error": "No load with this load_id exists"}, 404)
        # remove the load from it's 'carrier' if it is loaded
        carrier_id = int(load["carrier"]["id"])
        if carrier_id is not None:
            boat_key = client.key(constants.boats, carrier_id)
            boat = client.get(key=boat_key)
            
            print(boat.key.id)
            print(boat["loads"])
            print(len(boat["loads"]))
            
            for i in range(len(boat["loads"])):
                print("i: ",boat["loads"][i]["id"])
                if boat["loads"][i]["id"] == int(load_id):
                    del boat["loads"][i]
                    client.put(boat)
                    break
        client.delete(load_key)
        return ('', 204)