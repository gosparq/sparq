# -----------------------------------------------------------------------------
# sparQ - Connect Module Emoji Utils
#
# Emoji shortcode to unicode mapping and conversion utilities.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import re

# Common emoji shortcodes (Slack-compatible)
EMOJI_MAP = {
    # Smileys
    ":smile:": "\U0001F604",
    ":grin:": "\U0001F600",
    ":joy:": "\U0001F602",
    ":rofl:": "\U0001F923",
    ":smiley:": "\U0001F603",
    ":wink:": "\U0001F609",
    ":blush:": "\U0001F60A",
    ":heart_eyes:": "\U0001F60D",
    ":kissing_heart:": "\U0001F618",
    ":thinking:": "\U0001F914",
    ":neutral_face:": "\U0001F610",
    ":unamused:": "\U0001F612",
    ":sweat:": "\U0001F613",
    ":pensive:": "\U0001F614",
    ":confused:": "\U0001F615",
    ":upside_down:": "\U0001F643",
    ":sunglasses:": "\U0001F60E",
    ":nerd:": "\U0001F913",
    ":cry:": "\U0001F622",
    ":sob:": "\U0001F62D",
    ":angry:": "\U0001F620",
    ":rage:": "\U0001F621",
    ":scream:": "\U0001F631",
    ":flushed:": "\U0001F633",
    ":sleeping:": "\U0001F634",
    ":mask:": "\U0001F637",
    ":smirk:": "\U0001F60F",
    ":stuck_out_tongue:": "\U0001F61B",
    ":grimacing:": "\U0001F62C",
    ":partying_face:": "\U0001F973",
    # Gestures
    ":thumbsup:": "\U0001F44D",
    ":+1:": "\U0001F44D",
    ":thumbsdown:": "\U0001F44E",
    ":-1:": "\U0001F44E",
    ":clap:": "\U0001F44F",
    ":wave:": "\U0001F44B",
    ":pray:": "\U0001F64F",
    ":muscle:": "\U0001F4AA",
    ":point_up:": "\u261D\uFE0F",
    ":point_down:": "\U0001F447",
    ":ok_hand:": "\U0001F44C",
    ":v:": "\u270C\uFE0F",
    ":raised_hands:": "\U0001F64C",
    ":fist:": "\u270A",
    ":punch:": "\U0001F44A",
    ":handshake:": "\U0001F91D",
    # Hearts
    ":heart:": "\u2764\uFE0F",
    ":broken_heart:": "\U0001F494",
    ":blue_heart:": "\U0001F499",
    ":green_heart:": "\U0001F49A",
    ":yellow_heart:": "\U0001F49B",
    ":purple_heart:": "\U0001F49C",
    ":sparkling_heart:": "\U0001F496",
    ":orange_heart:": "\U0001F9E1",
    # Objects & Symbols
    ":fire:": "\U0001F525",
    ":star:": "\u2B50",
    ":sparkles:": "\u2728",
    ":zap:": "\u26A1",
    ":sunny:": "\u2600\uFE0F",
    ":cloud:": "\u2601\uFE0F",
    ":umbrella:": "\u2614",
    ":snowflake:": "\u2744\uFE0F",
    ":coffee:": "\u2615",
    ":pizza:": "\U0001F355",
    ":beer:": "\U0001F37A",
    ":cake:": "\U0001F370",
    ":gift:": "\U0001F381",
    ":tada:": "\U0001F389",
    ":balloon:": "\U0001F388",
    ":trophy:": "\U0001F3C6",
    ":medal:": "\U0001F3C5",
    ":rocket:": "\U0001F680",
    ":airplane:": "\u2708\uFE0F",
    ":car:": "\U0001F697",
    ":phone:": "\U0001F4F1",
    ":computer:": "\U0001F4BB",
    ":email:": "\U0001F4E7",
    ":memo:": "\U0001F4DD",
    ":book:": "\U0001F4D6",
    ":bulb:": "\U0001F4A1",
    ":hammer:": "\U0001F528",
    ":wrench:": "\U0001F527",
    ":key:": "\U0001F511",
    ":lock:": "\U0001F512",
    ":bell:": "\U0001F514",
    ":eyes:": "\U0001F440",
    ":speech_balloon:": "\U0001F4AC",
    ":thought_balloon:": "\U0001F4AD",
    # Status & Symbols
    ":check:": "\u2705",
    ":white_check_mark:": "\u2705",
    ":x:": "\u274C",
    ":warning:": "\u26A0\uFE0F",
    ":question:": "\u2753",
    ":exclamation:": "\u2757",
    ":100:": "\U0001F4AF",
    ":poop:": "\U0001F4A9",
    ":money:": "\U0001F4B0",
    ":dollar:": "\U0001F4B5",
    ":chart:": "\U0001F4C8",
    ":calendar:": "\U0001F4C5",
    ":clock:": "\U0001F55C",
    # Animals
    ":dog:": "\U0001F436",
    ":cat:": "\U0001F431",
    ":unicorn:": "\U0001F984",
    ":bug:": "\U0001F41B",
    ":bee:": "\U0001F41D",
}


def convert_shortcodes(text: str) -> str:
    """Convert emoji shortcodes to unicode emojis."""
    pattern = r":([a-zA-Z0-9_+-]+):"

    def replace_shortcode(match: re.Match[str]) -> str:
        shortcode = match.group(0)  # includes colons
        return EMOJI_MAP.get(shortcode, shortcode)

    return re.sub(pattern, replace_shortcode, text)


def get_emoji_list() -> list[dict]:
    """Get list of all available emojis for the picker."""
    return [{"shortcode": k, "emoji": v} for k, v in EMOJI_MAP.items()]
