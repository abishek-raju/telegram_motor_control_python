import hydra
import pyrootutils
from omegaconf import DictConfig
from typing import List, Optional, Tuple



pyrootutils.setup_root(__file__, indicator=".project-root", pythonpath=True)

from src import utils

from src.motor_control import motor_switch
from fastapi import FastAPI
import uvicorn
import logging
from pathlib import Path
from src.utils import pylogger, rich_utils
import time
import asyncio
from datetime import datetime,timedelta

log = pylogger.get_pylogger(__name__)




app = FastAPI()

@app.get("/")
async def read_root():
    return {"Message" : "Motor Controller"}

@app.get("/initialize_controller")
async def initialize_controller():
    log.info("Controller Initializer started")
    print("controller initialising")
    log.info("Controller Initializer completed")
    app.state.state_variable = "Initialized"
    return {"Message" : "Controller Initialized"}

@app.get("/start_motor")
async def start_motor():
    log.info("Motor start function executing")
    print("Motor started")
    log.info("Motor start function completed")
    app.state.state_variable = "Motor_Started"
    app.state.motor_start_time = datetime.now()
    app.state.state_variable = "Motor_Running"
    return {"Message" : "Motor Started","Datetime" : app.state.motor_start_time}

@app.get("/stop_motor")
def stop_motor():
    log.info("Motor stop function executing")
    print("Motor stopped")
    log.info("Motor stop function completed")
    app.state.state_variable = "Motor_Stopped"
    app.state.motor_stop_time = datetime.now()
    app.state.state_variable = "Motor_Stopped"
    return {"Message" : "Motor Stopped","Datetime" : app.state.motor_stop_time}

async def periodic():
    while True:
        # code to run periodically starts here
        log.info("Running monitoring now")
        if app.state._state:
            print(app.state._state)
            if app.state.state_variable == 'Motor_Running':
                difference_time = datetime.now() - app.state.motor_start_time
                minutes = divmod(difference_time.total_seconds(), 60)
                print('Total difference in minutes: ', minutes[0], 'minutes',
                                                minutes[1], 'seconds')
                if minutes[1] > 20:
                    log.info("Motor running for longer than 20secs")
                    stop_motor()
        
        # code to run periodically ends here
        # sleep for 3 seconds after running above code
        await asyncio.sleep(3)

@app.on_event("startup")
async def schedule_periodic():
    app.state.state_variable = "Power_Up"
    loop = asyncio.get_event_loop()
    loop.create_task(periodic())

@hydra.main(version_base="1.3", config_path="../configs", config_name="main.yaml")
def main(cfg: DictConfig) -> Optional[float]:

    # apply extra utilities
    # (e.g. ask for tags if none are provided in cfg, print cfg tree, etc.)
    utils.extras(cfg)
    uvicorn.run(app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    main()