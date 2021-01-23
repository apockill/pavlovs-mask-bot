import logging
import itertools
import random
from pathlib import Path
from argparse import ArgumentParser
from typing import Tuple
from time import time, sleep

from brainframe.api import BrainFrameAPI, bf_codecs
from uf.wrapper.swift_api import SwiftAPI

from maskbot import user_helpers
from maskbot.sound import play_sound
from maskbot import actions
from maskbot import RobotRecording

DEFAULT_ZONE = bf_codecs.Zone.FULL_FRAME_ZONE_NAME
HOME_POS = (150, 0, 150)
DEBOUNCE_SECONDS = 3


def respond_to_person(
        sound_file: Path,
        position: Tuple[float, float, float],
        bot: SwiftAPI,
        throw_position: Tuple[float, float, float] = None,
        throw_speed: int = 125):
    """Plays back a random robot recording"""

    bot.set_position(*HOME_POS, speed=100, wait=True)  # TODO: set wait=False

    # Play the sound byte
    print("Playing", sound_file)
    play_sound(sound_file)

    # Run the prerecorded robot movement
    actions.pickup(pos=position, bot=bot)

    bot.set_position(*HOME_POS, speed=30, wait=True)
    if throw_position:
        bot.set_position(*throw_position, speed=throw_speed, wait=True)

    bot.set_pump(False)

    sleep(1)
    bot.set_position(*HOME_POS, speed=50, wait=True)


def main():
    parser = ArgumentParser()
    parser.add_argument("-u", "--server-url", default="http://localhost",
                        help="URL of the BrainFrame server")
    parser.add_argument("--snack-position", default=None, nargs=3, type=float,
                        help="The x, y, z coordinates of the snack pile. If "
                             "not sent, the user will be prompted.")
    parser.add_argument("--mask-position", default=None, nargs=3, type=float,
                        help="The x, y, z coordinates of the mask pile. If "
                             "not sent, the user will be prompted.")
    parser.add_argument("-s", "--sounds-dir", default=Path("sound_effects"),
                        type=Path,
                        help="A directory with different robot recordings")
    parser.add_argument("-z", "--relevant-zone-name", default="Screen")
    args = parser.parse_args()

    api = BrainFrameAPI(args.server_url)

    user_helpers.ensure_directory_structure(args.sounds_dir)
    user_helpers.ensure_brainframe_environment(api)

    bot = SwiftAPI()
    bot.reset()
    bot.set_position(*HOME_POS, speed=100, wait=True)

    snack_position = (args.snack_position
                      or actions.prompt_get_position(bot, "Snack Pile"))
    mask_position = (args.mask_position
                     or actions.prompt_get_position(bot, "Mask Pile"))
    good_sounds = itertools.cycle(
        sorted((args.sounds_dir / "good").glob("*.mp3")))
    bad_sounds = itertools.cycle(
        sorted((args.sounds_dir / "bad").glob("*.mp3")))

    alarm_id_to_name = {
        a.id: a.name
        for a in api.get_zone_alarms()
        if a.name in [user_helpers.MASKED_ALARM_NAME,
                      user_helpers.MASKLESS_ALARM_NAME]
    }
    """A cache of an alarms id mapped to it's human readable name"""

    responded_to_alerts = set()
    """A set of alert_id's that the robot has 'responded' to"""

    last_reaction_tstamp = 0
    try:
        for packet in api.get_zone_status_stream():
            # Get all current alerts from all streams
            ongoing_alerts = itertools.chain.from_iterable(
                zone_statuses[DEFAULT_ZONE].alerts
                for zone_statuses in packet.values())

            # Filter out alerts that aren't valid to be reacted to
            reactable_alerts = [
                a for a in ongoing_alerts
                if a.id not in responded_to_alerts
                   and a.alarm_id in alarm_id_to_name.keys()
                   and a.start_time - last_reaction_tstamp >= DEBOUNCE_SECONDS
            ]

            # print([(a.start_time - last_reaction_tstamp >= DEBOUNCE_SECONDS,
            #         a.id not in responded_to_alerts,
            #         a.alarm_id in alarm_id_to_name.keys())
            #        for a in ongoing_alerts])

            if len(reactable_alerts) != 1:
                continue

            # Choose an alert to react to
            chosen_alert = reactable_alerts[0]

            name = alarm_id_to_name[chosen_alert.alarm_id]

            if name == user_helpers.MASKED_ALARM_NAME:
                respond_to_person(
                    sound_file=next(good_sounds),
                    position=snack_position,
                    bot=bot)
            elif name == user_helpers.MASKLESS_ALARM_NAME:
                respond_to_person(
                    sound_file=next(bad_sounds),
                    position=mask_position,
                    bot=bot,
                    throw_position=(200, 0, 30))
            responded_to_alerts.add(chosen_alert.id)
            last_reaction_tstamp = time()
    except KeyboardInterrupt:
        logging.warning("Closing program")


if __name__ == "__main__":
    main()
