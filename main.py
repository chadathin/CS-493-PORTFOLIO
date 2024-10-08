"""
AUTHOR: Chad C Boehm
CLASS: CS 493 - Cloud Application Development
TERM: Fall 2022
ASSIGN: Portfolio Project
"""

from google.cloud import datastore
from flask import \
    Flask, \
    request, \
    jsonify, \
    _request_ctx_stack, \
    render_template, \
    redirect, \
    session, \
    url_for,\
    make_response
import requests
import constants

from functools import wraps
import json

from urllib.request import urlopen
from urllib.parse import urlencode, quote_plus

from flask_cors import cross_origin
from jose import jwt

import json
from os import environ as env
from werkzeug.exceptions import HTTPException

from dotenv import load_dotenv, find_dotenv
from authlib.integrations.flask_client import OAuth

from verify_jwt import AuthError, verify_jwt


import user, boat, load

app = Flask(__name__)
app.register_blueprint(user.bp)
app.register_blueprint(boat.bp)
app.register_blueprint(load.bp)

app.secret_key = constants.APP_SECRET_KEY

client = datastore.Client()

BOATS = "boats"

# need to add something to commit

# Update the values of the following 3 variables
CLIENT_ID = constants.CLIENT_ID
CLIENT_SECRET = constants.CLIENT_SECRET
DOMAIN = constants.DOMAIN
# For example
# DOMAIN = 'fall21.us.auth0.com'

@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response

oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    api_base_url="https://" + DOMAIN,
    access_token_url="https://" + DOMAIN + "/oauth/token",
    authorize_url="https://" + DOMAIN + "/authorize",
    client_kwargs={
        'scope': 'openid profile email'
    },
    server_metadata_url=f'https://{constants.DOMAIN}/.well-known/openid-configuration'
)




# ===================================== TESTING / DEBUGGING ROUTES =====================================
# Decode the JWT supplied in the Authorization header
@app.route('/decode', methods=['GET'])
def decode_jwt():
    payload = verify_jwt(request)
    print("SUB: ", payload["sub"])
    return payload          
        

# Generate a JWT from the Auth0 domain and return it
# Request: JSON body with 2 properties with "username" and "password"
#       of a user registered with this Auth0 domain
# Response: JSON with the JWT as the value of the property id_token
@app.route('/login', methods=['POST'])
def login_user():
    content = request.get_json()
    username = content["username"]
    password = content["password"]
    body = {'grant_type':'password','username':username,
            'password':password,
            'client_id':CLIENT_ID,
            'client_secret':CLIENT_SECRET
           }
    headers = { 'content-type': 'application/json' }
    url = 'https://' + DOMAIN + '/oauth/token'
    r = requests.post(url, json=body, headers=headers)
    return r.text, 200, {'Content-Type':'application/json'}

# ===================================== LOGIN / LOGOUT ROUTES =====================================

@app.route('/user_login')
def user_login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route('/')
def welcome():
    return render_template("login.html")


@app.route('/success')
def success():
    tok = session.get('user')
    print("sub: {}".format(tok['userinfo']['sub']))

    q = client.query(kind=constants.user)
    q.add_filter('sub', '=', tok['userinfo']['sub'])
    result = list(q.fetch(limit = 1))
    print(result)

    if len(result) == 1:
        logger_inner = result[0]
        logger_inner.update({
            "id_token": tok["id_token"]
        })
        client.put(logger_inner)
        first = False
    else:

        logger_inner = datastore.entity.Entity(key=client.key(constants.user))
        logger_inner.update({
            "id_token" : tok["id_token"],
            "sub" : tok["userinfo"]["sub"],
            "email" : tok["userinfo"]["email"],
            "name" : tok["userinfo"]["nickname"],
            "boats": []
        })
        first = True
        
    # send user info to DB (if they don't exist...)
    # Check for uniqueness constraint
    
        client.put(logger_inner)

    return render_template("success.html", session=session.get('user'), pretty=logger_inner, first=first)


@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token
    return redirect("/success")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + constants.DOMAIN
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("welcome", _external=True),
                "client_id": constants.CLIENT_ID,
            },
            quote_via=quote_plus,
        )
    )

# ===================================== USABILITY ROUTES =====================================

# Create a boat if the Authorization header contains a valid JWT
'''
@app.route('/boats', methods=['POST', 'GET'])
def boats_post():
    if request.method == 'POST':
        payload = verify_jwt(request)
        content = request.get_json()
        new_boat = datastore.entity.Entity(key=client.key(constants.boats))
        new_boat.update({
            "name": content["name"], 
            "type": content["type"],
            "length": content["length"],
            "public": content["public"],
            "owner": payload["sub"]
        })
        
        client.put(new_boat)
        new_boat["id"] = new_boat.key.id
        res = make_response(new_boat)
        res.status_code = 201
        return res
    elif request.method == 'GET':
        try:
             # If there is a valid auth, return all boats belonging to 'sub'
            payload = verify_jwt(request)
            owner = payload['sub']
            
            query = client.query(kind=constants.boats)
            query.add_filter("owner", "=", owner)
            boat_list = list(query.fetch())
            for boat in boat_list:
                boat['id'] = boat.key.id
            out = dict()
            out["Length"] = len(boat_list)
            out["Owner"] = owner
            out["Boats"] = boat_list
            res = make_response(out)
            res.status_code = 200
            return res
        except:
            # If there is no auth or invalid auth -> return all public boats
            query = client.query(kind=constants.boats)
            query.add_filter("public", "=", True)
            boat_list = list(query.fetch())
            for boat in boat_list:
                boat['id'] = boat.key.id
            out = dict()
            out["Length"] = len(boat_list)
            out["Public"] = boat_list
            res = make_response(out)
            res.status_code = 200
            return res
            
    
    else:
        return jsonify(error='Method not recogonized')

@app.route('/owners/<owner_id>/boats', methods = ["GET"])
def get_owner_boats(owner_id):
    # Get all PUBLIC boats owned by owner_id
    # Doesn't really matter if JWT is valid, invalid, or even present
    # So, I'm not even going to test for it. If an owner doesn't
    # exist, it will just give an empty array
    query = client.query(kind=constants.boats)
    query.add_filter("owner", "=", owner_id)
    query.add_filter("public", "=", True)
    boat_list = list(query.fetch())
    for boat in boat_list:
        boat['id'] = boat.key.id
    out = dict()
    out["Length"] = len(boat_list)
    out["Owner"] = owner_id
    out["Boats"] = boat_list
    res = make_response(out)
    res.status_code = 200
    return res
    
@app.route("/boats/<boat_id>", methods = ["DELETE"])
def get_rid_of_it(boat_id):
    if request.method == 'DELETE':
        try:
            # If the JWT is valid -> get boat -> compare sub and owner
            payload = verify_jwt(request)
            owner = payload['sub']
            boat_key = client.key(constants.boats, int(boat_id))
            boat = client.get(key=boat_key)
            if boat is None:
                return ({"Error": "No boat with this boat_id exists."}, 403)
            
            if payload['sub'] != boat['owner']:
                return ({"Error": "This boat belongs to someone else."}, 403)
            
            elif payload['sub'] == boat['owner']:
                # Good to go!
                client.delete(boat_key)
                return('', 204)
        except:
            return ({"code": "invalid_header",
                        "description":
                            "Invalid header. "
                            "Use an RS256 signed JWT Access Token"}, 401)
            
'''
if __name__ == '__main__':
    app.run(host='localhost', port=8080, debug=True)

