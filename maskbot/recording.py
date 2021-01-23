import logging
import json
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Callable, List, Optional

import desert
from uf.wrapper.swift_api import SwiftAPI


@dataclass
class RobotState:
    x: float
    y: float
    z: float
    pump: bool
    time: float

    def distance(self, other: 'RobotState') -> float:
        return ((other.x - self.x) ** 2
                + (other.y - self.y) ** 2
                + (other.z - self.z) ** 2) ** 0.5

    def __eq__(self, other) -> bool:
        if not isinstance(other, RobotState):
            return super().__eq__(other)

        # Compare everything except time
        my_dict = self.__dict__.copy()
        other_dict = other.__dict__.copy()
        my_dict.pop("time")
        other_dict.pop("time")
        return my_dict == other_dict


robot_state_schema = desert.schema(RobotState)


class RobotRecording:
    def __init__(self, bot: SwiftAPI, positions=None):
        self._positions: List[RobotState] = positions or []
        self.bot = bot

    def play(self, max_speed=150):
        last_pos = self._positions[0]

        # Get to the recording start position
        self.bot.set_position(last_pos.x, last_pos.y, last_pos.z,
                              wait=True, speed=100)
        self.bot.set_pump(False)

        # Replay the recording
        for new_pos in self._positions[1:]:
            distance = last_pos.distance(new_pos)
            duration = new_pos.time - last_pos.time
            speed = min(distance / duration, max_speed)
            print("Duration", duration, "Speed", speed)
            print(new_pos)
            self.bot.set_position(
                int(new_pos.x),
                int(new_pos.y),
                int(new_pos.y),
                wait=True, speed=speed)
            if last_pos.pump != new_pos.pump:
                self.bot.set_pump(new_pos.pump)
            last_pos = new_pos

    @classmethod
    def create(cls,
               bot: SwiftAPI,
               callback: Optional[Callable[..., bool]] = None) \
            -> 'RobotRecording':
        """Records robot movements and saves them to a file in JSON format.
        :param callback: When this callback returns True, the recording stops.
            If no callback is set, the recording only finishes when the program
            receives a SIGINT.
        :return: The recording
        """
        callback = callback or (lambda: True)
        recording = cls(bot)

        bot.set_pump(False)
        pump = False

        start_time = time()
        last_state = None

        print("Move the robot to a position in which you would like to create "
              "a waypoint, then press 'Enter'. To activate the pump, simply "
              "hold down the suction cup while also pressing enter.")
        print("Enter 'q' to finish recording")
        while input("Press 'Enter' to record waypoint") != "q":
            x, y, z = bot.get_position()

            # The limit switch toggles the pump
            if bot.get_limit_switch():
                pump = not pump
                bot.set_pump(pump)

            new_state = RobotState(x=x, y=y, z=z, pump=pump,
                                   time=time() - start_time)
            if last_state == new_state:
                continue

            last_state = new_state
            recording._add_state(new_state)
            print(new_state)

        logging.info("Finishing recording.")

        return recording

    def _add_state(self, pos: RobotState):
        self._positions.append(pos)

    @classmethod
    def load_from_file(cls, bot: SwiftAPI, path: Path):
        positions = path.read_text("utf-8")
        positions = robot_state_schema.loads(positions, many=True)
        return cls(bot, positions=positions)

    def save_to_file(self, path: Path):
        positions = robot_state_schema.dumps(self._positions, many=True)
        path.write_text(positions, encoding="utf-8")
