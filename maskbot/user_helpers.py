import sys
from pathlib import Path

import logging

from brainframe.api import BrainFrameAPI, bf_codecs

# Links for helpful logs
DOWNLOADS = "https://aotu.ai/docs/downloads/"
ADD_STREAM_DOCS = "https://aotu.ai/docs/user_guide/streams/"
GETTING_STARTED = "https://aotu.ai/docs/getting_started/"
MASKLESS_ALARM_NAME = "Maskless Person Detected!"
MASKED_ALARM_NAME = "Masked Person Detected!"


def ensure_directory_structure(sounds_dir: Path):
    verify_paths = [
        (sounds_dir / "good", "*.mp3"),
        (sounds_dir / "bad", "*.mp3")
    ]
    for path, file_glob in verify_paths:
        path = path.absolute()
        assert path.is_dir(), \
            f"The path {path} could not be found!"
        assert len(list(path.glob(file_glob))), \
            f"There were no '{file_glob}' files found in {path}!"


def ensure_brainframe_environment(api: BrainFrameAPI):
    """Warn the user about a misconfigured environment"""
    logging.info("Connecting to server...")
    try:
        api.wait_for_server_initialization(timeout=3)
    except TimeoutError:
        logging.error("The server could not be connected to at "
                      f"{api._server_url}.\n"
                      "If you have not started a BrainFrame server, please "
                      f"follow the instructions at {GETTING_STARTED}.\n"
                      f"If you have started a server, you can configure the "
                      f"URL the script connects to using the '--server-url' "
                      f"flag.")
        sys.exit(-1)

    # Validate that a stream has been created
    streams = api.get_stream_configurations()
    if len(streams) == 0:
        logging.error("The must be at least one stream configured on the "
                      "system!\nUse the BrainFrame Client to add a stream. A "
                      "guide on how to do this can be found here: "
                      f"{ADD_STREAM_DOCS}")
        sys.exit(-1)

    # Ensure that alerts exist for mask detection. If none do, create them.
    for stream in streams:
        screen_zone = next(z for z in api.get_zones(stream.id)
                           if z.name == bf_codecs.Zone.FULL_FRAME_ZONE_NAME)
        try:
            _ = next(a for a in screen_zone.alarms
                     if a.name == MASKLESS_ALARM_NAME)
        except StopIteration:
            logging.warning(f"Adding missing '{MASKLESS_ALARM_NAME}' alarm "
                            f"to stream {stream.name}")
            test_type = bf_codecs.ZoneAlarmCountCondition.TestType.GREATER_THAN
            intersection_type = bf_codecs.IntersectionPointType.BOTTOM
            maskless_alarm = bf_codecs.ZoneAlarm(
                name=MASKLESS_ALARM_NAME,
                zone_id=screen_zone.id,
                rate_conditions=[],
                use_active_time=False,
                active_start_time=None,
                active_end_time=None,
                count_conditions=[
                    bf_codecs.ZoneAlarmCountCondition(
                        test=test_type,
                        check_value=0,
                        with_class_name="face",
                        with_attribute=bf_codecs.Attribute(
                            category="mask",
                            value="not_wearing_mask"),
                        window_duration=4,
                        window_threshold=0.5,
                        intersection_point=intersection_type, )])
            api.set_zone_alarm(maskless_alarm)

        try:
            _ = next(a for a in screen_zone.alarms
                     if a.name == MASKED_ALARM_NAME)
        except StopIteration:
            masked_alarm = bf_codecs.ZoneAlarm(
                name=MASKED_ALARM_NAME,
                zone_id=screen_zone.id,
                rate_conditions=[],
                use_active_time=False,
                active_start_time=None,
                active_end_time=None,
                count_conditions=[
                    bf_codecs.ZoneAlarmCountCondition(
                        test=test_type,
                        check_value=0,
                        with_class_name="face",
                        with_attribute=bf_codecs.Attribute(
                            category="mask",
                            value="wearing_mask"),
                        window_duration=4,
                        window_threshold=0.5,
                        intersection_point=intersection_type, )])
            api.set_zone_alarm(masked_alarm)

    # Validate that the appropriate capsules are loaded
    capsules = api.get_capsules()
    try:
        _ = next(c for c in capsules
                 if "face" in c.capability.detections)
    except StopIteration:
        logging.error("There must be a capsule loaded that is capable of "
                      "detecting faces! Capsules can be downloaded at "
                      f"{DOWNLOADS}. Some capsules that can work include:"
                      "\n\t- Detector Face Fast (for GPU machines)"
                      "\n\t- Detector Face Openvino (performs well on CPU)")
        sys.exit(-1)

    try:
        _ = next(c for c in capsules
                 if "mask" in c.capability.attributes.keys()
                 and "face" in c.output_type.detections)
    except StopIteration:
        logging.error("There must be a capsule loaded that is capable of "
                      "classifying masks on faces! Capsules can be downloaded "
                      f"at {DOWNLOADS}. The recommended capsule is:"
                      f"\n\t- Classifier Mask Openvino")
        sys.exit(-1)
