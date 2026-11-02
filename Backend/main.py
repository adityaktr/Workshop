from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
import logic
from logic import RequestError

db.init_db()

app = FastAPI(title="Inverter Load Manager")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApplianceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    wattage: int = Field(gt=0)
    priority: int = Field(ge=1)


def run(fn):
    try:
        return fn()
    except RequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message}) from exc


@app.get("/appliances")
def list_appliances():
    return logic.list_appliances()


@app.post("/appliances", status_code=201)
def create(body: ApplianceIn):
    appliance = run(lambda: logic.create_appliance(body.name, body.wattage, body.priority))
    return {"message": f"Registered {appliance['name']}. It is off.", "appliance": appliance}


@app.delete("/appliances/{appliance_id}")
def delete(appliance_id: int):
    appliance = run(lambda: logic.delete_appliance(appliance_id))
    return {"message": f"Deleted {appliance['name']}.", "appliance": appliance}

@app.get("/appliances/running")
def list_running_appliances():
    return logic.list_running_appliances()

@app.get("/appliances/shed")
def list_shed_appliances():
    return logic.list_shed_appliances()

@app.get("/appliances/wattage")
def running_wattage():
    return {"total_wattage": logic.total_running_wattage()}

@app.post("/appliances/{appliance_id}/on")
def turn_on(appliance_id: int):
    return run(lambda: logic.turn_on(appliance_id))

@app.post("/appliances/{appliance_id}/off")
def turn_off(appliance_id: int):
    return run(lambda: logic.turn_off(appliance_id))