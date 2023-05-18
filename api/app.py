import re
import requests
import datetime
import pydantic
import motor.motor_asyncio
import pytz
from bson import ObjectId
from fastapi import FastAPI, Request
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()


origins = [
    "https://simple-smart-hub-client.netlify.app",
    "http://127.0.0.1:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


pydantic.json.ENCODERS_BY_TYPE[ObjectId] = str

client = motor.motor_asyncio.AsyncIOMotorClient("mongodb+srv://IOT_CLASS:iotclass@cluster0.irzkjxq.mongodb.net/?retryWrites=true&w=majority")
db = client.ECSE3038_Project
settings = db['settings']
data = db['data']



regex = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')

def parse_time(time_str):
    parts = regex.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)


# Initialize Nominatim API to get 
geolocator = Nominatim(user_agent="MyApp")
location = geolocator.geocode("Hyderabad")


def get_sunset():
    user_latitude =  location.latitude
    user_longitude = location.longitude

    sunset_api_endpoint = f'https://api.sunrise-sunset.org/json?lat={user_latitude}&lng={user_longitude}&date=today'

    sunset_api_response = requests.get(sunset_api_endpoint)
    sunset_api_data = sunset_api_response.json()

    sunset_time = datetime.strptime(sunset_api_data['results']['sunset'], '%I:%M:%S %p').time()
    
    utc_to_ja = parse_time("5h")

    return datetime.strptime(str(sunset_time),"%H:%M:%S") - utc_to_ja 

def get_current_time():
    jamaica_ptz = pytz.timezone('Jamaica')
    now_time = datetime.now(jamaica_ptz).time()
    return datetime.strptime(str(now_time),"%H:%M:%S.%f")



@app.get("/")
async def home():
    return {"message": "ECSE3038 - Project"}



@app.get('/graph')
async def graph(request: Request):
    size = int(request.query_params.get('size'))
    readings = await data.find().sort('_id', -1).limit(size).to_list(size)

    data_reading = []
    
    for reading in readings:
        temperature = reading.get("temperature")
        presence = reading.get("presence")
        if presence == "1":
            presence1 = True
        else:
            presence1 = False
        upload_time = reading.get("current_time")

        data_reading.append({
            "temperature": temperature,
            "presence": presence1,
            "datetime": upload_time
        })

    return data_reading

@app.put('/settings')
async def put_parameters(request: Request):
    state = await request.json()
    user_temp = state["user_temp"]
    user_light = state["user_light"]
    light_time_off = state["light_duration"]

    if user_light == "sunset":
        user_light_scr = get_sunset()
    else:
        user_light_scr = datetime.strptime(user_light, "%H:%M:%S")

    new_user_light = user_light_scr + parse_time(light_time_off)

    output = {
        "user_temp": user_temp,
        "user_light": str(user_light_scr.time()),
        "light_time_off": str(new_user_light.time())
    }

    obj = await settings.find().sort('_id', -1).limit(1).to_list(1)

    if obj:
        await settings.update_one({"_id": obj[0]["_id"]}, {"$set": output})
        new_obj = await settings.find_one({"_id": obj[0]["_id"]})
    else:
        new = await settings.insert_one(output)
        new_obj = await settings.find_one({"_id": new.inserted_id})

    return new_obj



@app.post("/info")
async def toggle(request: Request):
    state = await request.json()

    param = await settings.find().sort('_id', -1).limit(1).to_list(1)
    
    temperature = param[0]["user_temp"]

    current_time = get_current_time()  # Call the function to get the current time
    user_light = datetime.strptime(param[0]["user_light"], "%H:%M:%S")
    light_time_off = datetime.strptime(param[0]["light_time_off"], "%H:%M:%S")

    state["light"] = (
        (user_light < current_time < light_time_off and state["presence"] == "1")
    )
    state["fan"] = (float(state["temperature"]) >= temperature and state["presence"] == "1")
    state["current_time"] = datetime.now()

    new_settings = await data.insert_one(state)
    new_obj = await data.find_one({"_id": new_settings.inserted_id})
    return new_obj



#retreves last entry
@app.get("/state")
async def get_state():
    last_entry = await data.find().sort('_id', -1).limit(1).to_list(1)

    if not last_entry:
        return {
            "presence": False,
            "fan": False,
            "light": False,
            "current_time": datetime.now()
        }

    return last_entry
