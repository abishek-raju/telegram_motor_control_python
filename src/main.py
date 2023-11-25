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
from fastapi_utils.tasks import repeat_every
import schedule
import arrow

from telegram.ext.commandhandler import CommandHandler
from telegram.ext.updater import Updater
from telegram.ext.dispatcher import Dispatcher
from telegram.update import Update
from telegram.ext.callbackcontext import CallbackContext
from telegram.bot import Bot
import asyncio
import time
from pathlib import Path
import RPi.GPIO as GPIO

def initialize_gpio(cfg):
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(cfg.blink_pin,GPIO.OUT)
    GPIO.output(cfg.blink_pin,GPIO.HIGH)

def is_raspberrypi():
    try:
        return Path("/etc/rpi-issue").exists()
    except Exception as e:
        print(e)
        pass
    return False

running_on_pi = is_raspberrypi()

if running_on_pi:
    from smbus import SMBus
    addr = 0x8
    bus = SMBus(3)
    print("Running on PI")
else:
    bus = None
    print("Running on Non PI device")

log = pylogger.get_pylogger(__name__)



app = FastAPI()

def get_voltage_current(bus,run_on_pi = False):
    if run_on_pi:
    #     while True:
        try:
            data_from_arduino = bus.read_i2c_block_data(addr,2)
        except Exception as e:
            print(e)
            return None,None
        print(data_from_arduino)
#         data_in_string = ""
#         for i in data_from_arduino:
#             if i != 255:
#                 #print(chr(i))
#                 data_in_string+=chr(i)
#     #     print(data_in_string)
        voltage, current = data_from_arduino[0],data_from_arduino[1]
        try:
            #print(int(float(voltage)),int(float(current)))
            return int(voltage),int(current)
        except Exception as e:
            print(e)
            #print(voltage,current)
            return voltage,current
    else:
        return None,None


@app.get("/")
def read_root():
    return {"Message" : "Motor Controller"}

@app.get("/initialize_controller")
def initialize_controller():
    # log.info("Controller Initializer started")
    # print("controller initialising")
    log.info("Controller Initializer completed")
    app.state.state_variable = "Initialized"
    return {"Message" : "Controller Initialized"}

def idle_state():
    # log.info("Controller Initializer started")
    # print("controller initialising")
    log.info("Controller in Idle state")
    app.state.state_variable = "Idle"
    return {"Message" : "Controller in Idle"}

@app.get("/start_motor")
def start_motor():
    if app.state.state_variable == "Idle":
        log.info("Motor start function executing")
        print("Motor started")
        log.info("Motor start function completed")
        app.state.state_variable = "Motor_Started"
        app.state.motor_start_time = datetime.now()
        app.state.state_variable = "Motor_Running"
        return {"Message" : "Motor Started","Datetime" : app.state.motor_start_time}
    else:
        return {"Message" : "Motor Start Failed. Controller not in Idle State","Datetime" : datetime.now()}

@app.get("/stop_motor")
def stop_motor():
    if app.state.state_variable == "Motor_Running":
        # log.info("Motor stop function executing")
        # print("Motor stopped")
        log.info("Motor stop function completed")
        app.state.state_variable = "Motor_Stopped"
        app.state.motor_stop_time = datetime.now()
        return {"Message" : "Motor Stopped","Datetime" : app.state.motor_stop_time}
    else:
        return {"Message" : "Motor Stop Failed. Controller not in Motor Running State","Datetime" : datetime.now()}

# async def periodic():
#     while True:
#         # code to run periodically starts here
#         # log.info("Running monitoring now")
#         if app.state._state:
#             # print(app.state._state)
#             if app.state.state_variable == 'Motor_Running':
#                 difference_time = datetime.now() - app.state.motor_start_time
#                 minutes = divmod(difference_time.total_seconds(), 60)
#                 # print('Total difference in minutes: ', minutes[0], 'minutes',
#                 #                                 minutes[1], 'seconds')
#                 if minutes[1] > 20:
#                     log.info("Motor running for longer than 20secs")
#                     stop_motor()
        
#         # code to run periodically ends here
#         # sleep for 3 seconds after running above code
#         await asyncio.sleep(3)
@app.on_event("startup")
@repeat_every(seconds=5)  # 20 Seconds
def monitor_run():
    if app.state._state:
        app.state.voltage,app.state.current = get_voltage_current(bus,running_on_pi)
        log.info(f"Voltage {app.state.voltage} Current {app.state.current}")
        # log.info(app.state._state)
        if app.state.state_variable == 'Initialized':
            idle_state()
            log.info(f"Motor moved to idle state")
            blink_led(1,app.cfg.blink_pin)
        if app.state.state_variable == 'Idle':
            log.info(f"Motor in idle state")
            blink_led(2,app.cfg.blink_pin)
        if app.state.state_variable == 'Motor_Running':
            difference_time = datetime.now() - app.state.motor_start_time
            minutes = divmod(difference_time.total_seconds(), 60)
            # print('Total difference in minutes: ', minutes[0], 'minutes',
            #                                 minutes[1], 'seconds')
            app.state.motor_running_time = difference_time.total_seconds()
            log.info(f"Motor running for {app.state.motor_running_time} secs")

            if app.state.motor_running_time >  app.cfg.motor_duration:
                stop_motor()
            blink_led(3,app.cfg.blink_pin)
        if app.state.state_variable == 'Motor_Stopped':
            log.info(f"Motor stopped")
            idle_state()
            log.info(f"Motor moved to idle state")
            blink_led(4,app.cfg.blink_pin)
        delay = 3 # For 10 secs delay 
        close_time = time.time()+delay
        while True:
            if time.time() > close_time:
                break
            app.state.updater.start_polling()
        app.state.updater.stop()
    schedule.run_pending()


def schedule_motor_start(cfg):
    for trigger in cfg["motor_start_time"]["motor_on_time"]:
        datetime_trigger = arrow.get(trigger).datetime
        if datetime_trigger.year == 9999:
            schedule.every().day.at(f"{datetime_trigger.hour}:{datetime_trigger.minute}").do(start_motor)
        else:
            pass


def blink_led(n,pinLED):
    for i in range(n):
        print(f"Blink {i} times")
        GPIO.output(pinLED,GPIO.LOW)
        time.sleep(0.5)
        GPIO.output(pinLED,GPIO.HIGH)
        time.sleep(0.5)
        

@app.on_event("startup")
def startup():
    app.state.state_variable = "Power_Up"
    log.info("Controller powered up and running")
    schedule_motor_start(app.cfg)
    initialize_controller()
    # loop = asyncio.get_event_loop()
    # loop.create_task(periodic())
    app.state.updater = Updater("6096336644:AAEHgGIQLTrj3CH7A231oEi-T-7ydsAjy80",
                  use_context=True)
    app.state.dispatcher: Dispatcher = app.state.updater.dispatcher
    # register a handler (here command handler)
    # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.dispatcher.html#telegram.ext.Dispatcher.add_handler
    app.state.dispatcher.add_handler(
        # it can accept all the telegram.ext.Handler, CommandHandler inherits Handler class
        # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.commandhandler.html#telegram-ext-commandhandler
        CommandHandler("mtron", telegram_start))
    
    app.state.dispatcher.add_handler(
        # it can accept all the telegram.ext.Handler, CommandHandler inherits Handler class
        # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.commandhandler.html#telegram-ext-commandhandler
        CommandHandler("mtroff", telegram_stop))

    app.state.dispatcher.add_handler(
        # it can accept all the telegram.ext.Handler, CommandHandler inherits Handler class
        # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.commandhandler.html#telegram-ext-commandhandler
        CommandHandler("sts", telegram_status))
    

    app.state.updater.bot.send_message(chat_id = "987260580" ,text="Powered Up")
    

def telegram_start(update: Update, context: CallbackContext):
    """
    the callback for handling start command
    """
    # getting the bot from context
    # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.bot.html#telegram-bot
    bot: Bot = context.bot

    start_motor()
    # sending message to the chat from where it has received the message
    # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.bot.html#telegram.Bot.send_message
    bot.send_message(chat_id=update.effective_chat.id,
                     text="You have just entered start command")

def telegram_stop(update: Update, context: CallbackContext):
    """
    the callback for handling stop command
    """
    # getting the bot from context
    # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.bot.html#telegram-bot
    bot: Bot = context.bot

    stop_motor()
    # sending message to the chat from where it has received the message
    # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.bot.html#telegram.Bot.send_message
    bot.send_message(chat_id=update.effective_chat.id,
                     text="You have just entered stop command")

def telegram_status(update: Update, context: CallbackContext):
    """
    the callback for handling status command
    """
    # getting the bot from context
    # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.bot.html#telegram-bot
    bot: Bot = context.bot
    status = str(controller_status())
    
    # sending message to the chat from where it has received the message
    # documentation: https://python-telegram-bot.readthedocs.io/en/latest/telegram.bot.html#telegram.Bot.send_message
    bot.send_message(chat_id=update.effective_chat.id,
                     text=status)


@app.get("/sts")
def controller_status():
    if app.state.state_variable == "Idle":
        # log.info("Motor stop function executing")
        # print("Motor stopped")
        message = app.state.state_variable
        message = message + f"Voltage {app.state.voltage} Current {app.state.current}"
        return {"Message" : message,"Datetime" : datetime.now()}
        
    elif app.state.state_variable == "Motor_Running":
        # log.info("Motor stop function executing")
        # print("Motor stopped")
        message = app.state.state_variable
        message = message + f" for {app.state.motor_running_time} secs"
        message = message + f"Voltage {app.state.voltage} Current {app.state.current}"
        return {"Message" : message,"Datetime" : datetime.now()}
    else:
        return {"Message" : "Could not fetch the status","Datetime" : datetime.now()}
  


@hydra.main(version_base="1.3", config_path="../configs", config_name="main.yaml")
def main(cfg: DictConfig) -> Optional[float]:

    # apply extra utilities
    # (e.g. ask for tags if none are provided in cfg, print cfg tree, etc.)
    utils.extras(cfg)
    app.cfg = cfg
    initialize_gpio(cfg)
    uvicorn.run(app, host="0.0.0.0", port=8003)

if __name__ == "__main__":
    main()
