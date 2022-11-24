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