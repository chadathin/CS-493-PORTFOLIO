from flask import Blueprint, request, make_response
from google.cloud import datastore
import json
import constants
from verify_jwt import AuthError, verify_jwt
client = datastore.Client()

bp = Blueprint('users', __name__, url_prefix='/users')

@bp.route("", methods = ["GET", "POST"])
def get_post_users():
    if request.method == "GET":
        # Unprotected; return all users. Does NOT need to be paginated
        q = client.query(kind=constants.user)
        users = list(q.fetch())
        for user in users:
            user["id"] = user.key.id
            user["self"] = request.base_url + "/"+str(user.key.id)
        out = dict()
        out["length"] = len(users)
        out["users"] = users
        return (out, 200)
    else:
        return ({"Error": "Unsupported method"}, 500)
        
        
    
@bp.route("/<user_id>", methods = ["GET"])
def get_user(user_id):
    if request.method == "GET":
        q = client.query(kind = constants.user)
        q.add_filter('sub', '=', user_id)
        result = list(q.fetch(limit=1))
        if len(result) == 0:
            return ({"Error": "User not found"}, 404)
        for user in result:
            user["id"] = user.key.id
            user["self"] = request.base_url
        user = json.dumps(result[0])
            
        res = make_response(user)
        res.mimetype = 'application/json'
        res.status_code = 200
        return res
