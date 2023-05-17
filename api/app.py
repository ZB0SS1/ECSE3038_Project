from fastapi import FastAPI, Request
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
import re
import requests
import datetime
import pydantic
import motor.motor_asyncio
import pytz

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
db = client.iot_platform
sensor_readings = db['sensor_readings']
data = db['data']



# Initialize Nominatim API
geolocator = Nominatim(user_agent="MyApp")

location = geolocator.geocode("Hyderabad")


def get_sunset():
    user_latitude =  location.latitude
    user_longitude = location.longitude

    sunset_api_endpoint = f'https://api.sunrise-sunset.org/json?lat={user_latitude}&lng={user_longitude}'

    sunset_api_response = requests.get(sunset_api_endpoint)
    sunset_api_data = sunset_api_response.json()

    sunset_time = datetime.datetime.strptime(sunset_api_data['results']['sunset'], '%I:%M:%S %p').time()
    
    return datetime.datetime.strptime(str(sunset_time),"%H:%M:%S")

current_date = datetime.date.today()
now_time = datetime.datetime.now(pytz.timezone('Jamaica')).time()
datetime2 = datetime.datetime.strptime(str(now_time),"%H:%M:%S.%f")

temperature = 28




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



@app.get('/graph')
async def graph(request: Request):
    size = int(request.query_params.get('size'))
    readings = await data.find().to_list(size)
    data_reading = []
    for reading in readings:
        temperature = reading.get("temperature")
        presence = reading.get("presence")
        current_time = reading.get("current_time")

        if temperature and presence and current_time:
            data_reading.append({
                "temperature": temperature,
                "presence": presence,
                "datetime": current_time
            })

    return data_reading

@app.put('/settings')
async def get_sensor_readings(request: Request):
    state = await request.json()
    #final_sunset_time = str(get_sunset())
    user_temp = state["user_temp"]
    user_light = state["user_light"]
    light_time_off = state["light_duration"]
    global temperature 
    temperature = int(user_temp)

    if user_light == "sunset":
        user_light_scr = get_sunset()
    else:
        user_light_scr = datetime.datetime.strptime(user_light, "%H:%M:%S")
    
    new_user_light = user_light_scr + parse_time(light_time_off)

    output = {
        "user_temp": user_temp,
        "user_light": str(user_light_scr.time()),
        "light_time_off": str(new_user_light.time())
        }
    new_settings = await sensor_readings.insert_one(output)
    created_settings = await sensor_readings.find_one({"_id":new_settings.inserted_id})
    return created_settings




@app.put("/temperature")
async def toggle(request: Request): 
    state = await request.json()
    global temperature
    state["light"] = ((datetime2 < get_sunset()+ parse_time("8h")) & (state["presence"] == "1" ))
    state["fan"] = ((float(state["temperature"]) >= temperature) & (state["presence"]=="1"))
    state["current_time"]= datetime.datetime.now()

    new_settings = await data.insert_one(state)
    new_obj = await data.find_one({"_id":new_settings.inserted_id}) 
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
            "current_time": datetime.datetime.now()
        }

    return last_entry
