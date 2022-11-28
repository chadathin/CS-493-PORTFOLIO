from flask import Blueprint, request, make_response
from google.cloud import datastore
import json
import constants
import verify
from json2html import *
from verify_jwt import verify_jwt, AuthError

client = datastore.Client()

bp = Blueprint('boats', __name__, url_prefix='/boats')

valid_mime_types = ["application/json", "text/html"]

@bp.route('', methods = ["GET", "POST", "DELETE"])
def boats_get_post():        
    if request.method == "POST":
        # To add a boat: Must have valid JWT, must have unique name
        try:
            # verify JWT
            payload = verify_jwt(request)
        except:
            # Client did not sent JSON
            res = make_response({"Error": "No valid JWT provided"})
            res.mimetype = 'application/json'
            res.status_code = 415
            return res

        try:
            
            content = request.get_json()
        except:
            # Client did not sent JSON
            res = make_response({"Error": "POST request must be JSON"})
            res.mimetype = 'application/json'
            res.status_code = 415
            return res

        # Check for uniqueness constraint
        q = client.query(kind=constants.boats)
        print("NAME:", content["name"])
        q.add_filter('name', '=', content['name'])
        result = q.fetch(limit = 1)

        for r in result:
            print(r)

        print(result.num_results)
        if result.num_results > 0:
            res = make_response({"Error": "A boat with that name already exists"})
            res.content_type = 'application/json'
            res.status_code = 403
            return res

        # Client accepts something server does not provide
        if 'application/json' not in request.accept_mimetypes:
            res = make_response({"Error": "POST response must be JSON"})
            res.mimetype = 'application/json'
            res.status_code = 406
            return res
        

        
        # If everything is hunky dory
        new_boat = datastore.entity.Entity(key=client.key(constants.boats))
        try:
            new_boat.update(
                {
                    "name": content["name"], 
                    "type": content["type"], 
                    "length": content["length"]
                }
            )
        except:
            return ({"Error": "The request object is missing at least one of the required attributes"}, 400)
        
        if not verify.verify_boat(new_boat):
            return ({"Error": "One or more attribute values do not meet specified criteria"}, 400)

        new_boat.update({
            "loads": [],
            "owner": None
        })
         
        client.put(new_boat)
        new_boat["id"] = new_boat.key.id
        new_boat["self"] = request.url_root + constants.boats + "/" + str(new_boat["id"])
        res = make_response(json.dumps(new_boat))
        res.mimetype = 'application/json'
        res.status_code = 201
        return (res)
    elif request.method == "GET":
        
        payload = verify_jwt(request)
        owner = payload['sub']
        
        get_next = False
        args = request.args
        if len(args) > 0:
            limit = int(args["limit"])
            offset = int(args["offset"])
        else:
            limit = 3
            offset = 0
        query = client.query(kind=constants.boats)
        query.add_filter("owner", "=", owner)
        boats = list(query.fetch(limit=limit+1, offset=offset))
        if len(boats) > limit:
            boats = boats[0:limit]
            get_next = True
        for boat in boats:
            boat["id"] = boat.key.id
            boat["self"] = request.base_url + "/"+str(boat.key.id)
        out = dict()
        out["owner"] = owner
        out["length"] = len(boats)
        if get_next:
            out["next"] = request.base_url + "?limit={}&offset={}".format(limit, offset+limit)

        out["boats"] = boats
        
        return (out, 200)
    else: 
        res = make_response({"Error": "Method not allowed.", "Allowed": ["GET", "POST"]})
        res.status_code = 405
        res.content_type = 'application/json'
        return res

@bp.route('/<boat_id>/users/<user_id>', methods = ["PUT", "PATCH", "DELETE"])
def associate_boat_user(boat_id, user_id):
    # Make a user the owner of a boat
    if request.method == "PUT" or request.method == "PATCH":
        # verify jwt
        payload = verify_jwt(request)

        # get the 'sub' from jwt
        owner = payload['sub']

        # Check if the boat exists
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        
        if boat is None:
            return({"Error": "No boat with this boat_id exists"}, 404)

        # Check if the user exists
        q = client.query(kind=constants.user)
        q.add_filter("sub", "=", user_id)
        users = list(q.fetch())
        if len(users) == 0:
            return ({"Error": "No user with this ID exists"}, 404)

        user = users[0]
        if boat['owner'] is not None:
            if boat['owner'] == owner:
                return ({"Error": "Hey, man, you already own this thing!"}, 403)
            elif boat['owner'] != owner:
                return ({"Error": "Someone else already owns this thing!"}, 401)

        # If everything, is OK, add 'owner' to boat
        boat.update({
            'owner': owner
        })
        
        user['boats'].append(boat.key.id)

        client.put(user)

        client.put(boat)
        boat["id"] = boat.key.id
        boat["self"] = request.host_url + 'boats/' + str(boat.key.id)
        res = make_response(boat)
        res.mimetype = 'application/json'
        res.status_code = 200
        return res
    elif request.method == "DELETE":
        # remove user_id from boat_id
        # verify jwt
        payload = verify_jwt(request)

        # make sure the boat exists
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        
        if boat is None:
            return({"Error": "No boat with this boat_id exists"}, 404)

        if boat['owner'] is None:
            return ({"Error": "No one seems to own that boat"}, 405)

        # make sure the 'sub' from jwt == 'owner' from boat['owner']
        if boat['owner'] != payload['sub']:
            return ({"Error": "Hey, man! You don't own that boat!"}, 403)

        else:
            # get the owner
            # Check if the user exists
            q = client.query(kind=constants.user)
            q.add_filter("sub", "=", user_id)
            users = list(q.fetch())
            if len(users) == 0:
                return ({"Error": "No user with this ID exists"}, 404)

            user = users[0]
            user['boats'].remove(boat.key.id)
            boat['owner'] = None
            client.put(user)
            client.put(boat)
            res = make_response(boat)
            res.status_code = 200
            res.mimetype = 'application/json'
            return (res)
    else:
        return ({"Error": "Method not recognized"})

@bp.route('/<boat_id>', methods = ["GET", "DELETE", "PUT", "PATCH"])
# GET, DELETE, or edit a specific boat
def boats_get_delete(boat_id):
    if request.method == "GET":
        # needs to return either JSON or HTML, depending on 'Accept'
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        
        if boat is None:
            return({"Error": "No boat with this boat_id exists"}, 404)
        
        boat["id"] = boat.key.id
        boat["self"] = request.url

        if 'application/json' in request.accept_mimetypes:
            res = make_response(json.dumps(boat))
            res.headers.set('Content-Type', 'application/json')
            res.status_code = 200
            return res
        elif 'text/html' in request.accept_mimetypes:
            res = make_response(json2html.convert(json = json.dumps(boat)))
            res.headers.set('Content-Type', 'text/html')
            res.status_code = 200
            return res

    elif request.method == "DELETE":
        # Delete the boat
        payload = verify_jwt(request)
        # Get the boat
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        
        if boat is None:
            return({"Error": "No boat with this boat_id exists"}, 404)

        # if the no one owns the boat, or the jwt['sub'] owns the boat
        # it can be deleted
        if boat['owner'] is None or boat['owner'] == payload['sub']:
            # TODO: REMOVE THIS BOAT FROM ALL LOADS ASSOCIATED WITH IT
            client.delete(boat_key)
            return('', 204)
        else:
            return ({"Error": "Sorry, you do not own this boat"}, 401)

    elif request.method == "PATCH":
         # ONLY GIVEN ATTRIBUTES MODIFIED, EXCEPT ID

        # Make sure the client accepts JSON
        if 'application/json' not in request.accept_mimetypes:
            res = make_response({"Error": "POST response must be JSON"})
            res.mimetype = 'application/json'
            res.status_code = 406
            return res
        # Get the request body, make sure that is also JSON
        try:
            content = request.get_json()
        except:
            # Client did not sent JSON
            res = make_response({"Error": "POST request must be JSON"})
            res.mimetype = 'application/json'
            res.status_code = 415
            return res

        # print(content)

        if "name" in content.keys():
            # Check for uniqueness constraint
            q = client.query(kind=constants.boats)
            q.add_filter('name', '=', content['name'])
            result = q.fetch(limit = 1)
            
            for r in result:
                print(r)

            if result.num_results > 0:
                res = make_response({"Error": "A boat with that name already exists"})
                res.content_type = 'application/json'
                res.status_code = 403
                return res

        # Get the boat
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        
        if boat is None:
            return({"Error": "No boat with this boat_id exists"}, 404)
        
        for att in content.keys():
            if att in boat.keys():
                boat[att] = content[att]
        client.put(boat)

        client.put(boat)
        boat["id"] = boat.key.id
        boat["self"] = request.url_root + constants.boats + "/" + str(boat["id"])
        res = make_response(json.dumps(boat))
        res.mimetype = 'application/json'
        # res.location = boat["self"]
        res.status_code = 200
        return (res)


    elif request.method == "PUT":
        # ALL ATTRIBUTES MODIFIED, EXCEPT ID
        # Make sure the client accepts JSON
        if 'application/json' not in request.accept_mimetypes:
            res = make_response({"Error": "POST response must be JSON"})
            res.mimetype = 'application/json'
            res.status_code = 406
            return res
        # Get the request body, make sure that is also JSON
        try:
            content = request.get_json()
        except:
            # Client did not sent JSON
            res = make_response({"Error": "POST request must be JSON"})
            res.mimetype = 'application/json'
            res.status_code = 415
            return res

        # Get the boat
        boat_key = client.key(constants.boats, int(boat_id))
        boat = client.get(key=boat_key)
        
        if boat is None:
            return({"Error": "No boat with this boat_id exists"}, 404)
        
        try:
            boat.update({
                "name": content["name"],
                "type": content["type"],
                "length": content["length"]
            })
        except:
            return ({"Error": "The request object is missing at least one of the required attributes"}, 400)

        if not verify.verify_boat(content):
            return ({"Error": "One or more attribute values do not meet specified criteria"}, 400)

        # Check for uniqueness constraint
        q = client.query(kind=constants.boats)
        print("NAME:", content["name"])
        q.add_filter('name', '=', content['name'])
        result = q.fetch(limit = 1)

        for r in result:
            print(r)

        print(result.num_results)
        if result.num_results > 0:
            res = make_response({"Error": "A boat with that name already exists"})
            res.content_type = 'application/json'
            res.status_code = 403
            return res

        

        client.put(boat)
        boat["id"] = boat.key.id
        boat["self"] = request.url_root + constants.boats + "/" + str(boat["id"])
        res = make_response(json.dumps(boat))
        res.mimetype = 'application/json'
        res.location = boat["self"]
        res.status_code = 303
        return (res)


    
