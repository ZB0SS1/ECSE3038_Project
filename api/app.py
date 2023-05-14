from fastapi import FastAPI, Request
from pymongo import MongoClient
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import re
import requests
import datetime
import pydantic
import motor.motor_asyncio
import pytz

app = FastAPI()


origins = [
    "https://simple-smart-hub-client.netlify.app/",
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
db = client.iot_platform
sensor_readings = db['sensor_readings']



# Initialize Nominatim API
geolocator = Nominatim(user_agent="MyApp")

location = geolocator.geocode("Hyderabad")



user_latitude =  location.latitude
user_longitude = location.longitude

sunset_api_endpoint = f'https://api.sunrise-sunset.org/json?lat={user_latitude}&lng={user_longitude}'

sunset_api_response = requests.get(sunset_api_endpoint)
sunset_api_data = sunset_api_response.json()

current_date = datetime.date.today()
sunset_time = datetime.datetime.strptime(sunset_api_data['results']['sunset'], '%I:%M:%S %p').time()
now_time = datetime.datetime.now(pytz.timezone('Jamaica')).time()


datetime1 = datetime.datetime.strptime(str(sunset_time),"%H:%M:%S")
datetime2 = datetime.datetime.strptime(str(now_time),"%H:%M:%S.%f")



# Check if the user has chosen the sunset option for turning on the lights
user_set_sunset_option = True  # Assume the user has chosen the sunset option for this example

if user_set_sunset_option:
    # Compare the current time to the sunset time and turn on the lights if the current time is later than the sunset time
    current_time = datetime.datetime.now().time()

        # Turn on the lights
        # Code for turning on the lights goes here





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



@app.get("/")
async def home():
    return {"message": "ECSE3038 - Project"}

@app.get('/graph?size={n}')
async def get_sensor_readings(request: Request, n: int):
    readings = await sensor_readings.find().to_list(n)
    result = []
    for reading in readings:
        result.append({
            'id': str(reading['_id']),
            'temperature': reading['user_temp'],
            'presence': reading['presence'],
            'timestamp': reading['timestamp'].isoformat(),
        })
    return readings


@app.put('/settings')
async def get_sensor_readings(request: Request):
    state = await request.json()
    #final_sunset_time = str(get_sunset())
    user_temp = state["user_temp"]
    user_light = state["user_light"]
    light_time_off = state["light_duration"]

    user_light_scr = datetime.datetime.strptime(user_light, "%H:%M:%S")
    new_user_light = user_light_scr + parse_time(light_time_off)

    output = {
        "user_temp": user_temp,
        "user_light": user_light,
        "light_time_off": str(new_user_light.time())
        }
    new_settings = await sensor_readings.insert_one(output)
    created_settings = await sensor_readings.find_one({"_id":new_settings.inserted_id})
    return created_settings


@app.get("/api/state")
async def get_state():
  state = await sensor_readings.find_one({"tobe": "updated"})
  
  state["fan"] = (float(state["temperature"]) >= 28.0) 
  state["light"] = (datetime1<datetime2)

  if state == None:
    return {"fan": False, "light": False}
  return state