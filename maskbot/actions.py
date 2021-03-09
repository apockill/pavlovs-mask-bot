from typing import Tuple
from time import sleep

from uf.wrapper.swift_api import SwiftAPI


def prompt_get_position(bot: SwiftAPI, prompt: str):
    """Prompt the user to move the robot to a relevant location"""
    bot.set_servo_detach(wait=True)
    input(f"Press Enter to record the {prompt} position")
    position = bot.get_position()
    position = [str(round(p)) for p in position]
    return position


def pickup(pos: Tuple[float, float, float],
           bot: SwiftAPI,
           max_down_distance=100,
           down_increment=-3):
    x, y, z = pos
    bot.set_position(x, y, z, relative=False, speed=25, wait=False)
    bot.set_pump(True)

    while bot.get_is_moving():
        pass

    bot.set_position(z=-100, relative=True, wait=True, speed=150)
    # Wait until the robot hits the next item (or hits the max_down_distance)
    for i in range(abs(max_down_distance // down_increment)):
        if bot.get_limit_switch():
            break
        bot.set_polar(
            r=0,
            h=down_increment,
            # 'Wiggle' the motion to make the limit switch trigger more easily
            s=[2, -2][i % 2 == 0],
            wait=True,
            relative=True,
            speed=150)

    else:
        print("The limit switch was never hit!")

    # Let the pump fully 'catch' the object
    sleep(0.5)

    # Move back up

    bot.set_position(x, y, 165, speed=150, relative=False, wait=True)
