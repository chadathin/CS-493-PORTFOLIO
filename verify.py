boat_list = [
    "deck boat",
    "hydroplane",
    "submarine",
    "row boat",
    "life boat",
    "tug boat",
    "fishing boat",
    "dingy",
    "pontoon",
    "house boat",
    "kayak",
    "canoe",
    "catamaran",
    "sailboat",
    "motorboat",
    "ferry",
    "container ship",
    "tanker",
    "cruise ship",
    "yacht"
]

valid_letters = 'abcdefghijklmnopqrstuvwxyz '

def is_string(input_string: str):
    return type(input_string) is type("test")

def is_int(input_int: int):
    return type(input_int) is type(1)

def verify_boat_type(boat_type: str):
    # make sure it's a string
    if not is_string(boat_type):
        return False

    # make sure it's an approved boat type
    if boat_type.lower() in boat_list:
        return True
    return False

def verify_boat_length(boat_length: int):
    if type(boat_length) is not type(1):
        return False
    
    if (boat_length < 1) or (boat_length > 1504):
        return False
    
    return True

def verify_boat_name(boat_name: str):
    if not is_string(boat_name):
        return False
    name = boat_name.lower()
    # name must be 8 <= len <= 32 characters long
    if (len(boat_name) < 8) or (len(boat_name)  > 32):
        return False
    for l in name:
        if l not in valid_letters:
            return False
    return True

def verify_request_body(req_body: dict):
    keys = req_body.keys()
    if len(keys) != 3:
        return False
    if ("name" not in keys) or ("type" not in keys) or ("length" not in keys):
        return False
    return True
    
def verify_boat(boat: dict):
    if verify_request_body(boat) and \
        verify_boat_name(boat["name"]) and \
        verify_boat_length(boat["length"]) and \
        verify_boat_type(boat["type"]):
        return True
    else:
        return False