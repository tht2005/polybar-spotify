#!/usr/bin/env python

import sys
import dbus
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    '-t',
    '--trunclen',
    type=int,
    metavar='trunclen'
)
parser.add_argument(
    '-f',
    '--format',
    type=str,
    metavar='custom format',
    dest='custom_format'
)
parser.add_argument(
    '-p',
    '--playpause',
    type=str,
    metavar='play-pause indicator',
    dest='play_pause'
)
parser.add_argument(
    '--font',
    type=str,
    metavar='the index of the font to use for the main label',
    dest='font'
)
parser.add_argument(
    '--playpause-font',
    type=str,
    metavar='the index of the font to use to display the playpause indicator',
    dest='play_pause_font'
)
parser.add_argument(
    '-q',
    '--quiet',
    action='store_true',
    help="if set, don't show any output when the current song is paused",
    dest='quiet',
)

args = parser.parse_args()


def fix_string(string):
    # corrects encoding for the python version used
    if sys.version_info.major == 3:
        return string
    else:
        return string.encode('utf-8')

def formated_string_findAll_element(name):
    length = len(name)
    # find all the character that appear
    # this code assume that the formated string is valid
    is_element = [ 0 ] * length
    i = 0
    while i < length:
        if name[i] != '%':
            is_element[i] = 1
            i += 1
            continue
        i += 1
        assert (i < length) and (name[i] == '{')
        while (i < length) and (name[i] != '}'):
            i += 1
        assert (i < length) and (name[i] == '}')
        i += 1
    return is_element

def formated_string_len(name):
    a = formated_string_findAll_element(name)
    cnt = 0
    length = len(name)
    for i in range(length):
        if a[i]:
            cnt += 1
    return cnt

def resize_formated_string(name, newlength):
    a = formated_string_findAll_element(name)
    formated_length = formated_string_len(name)
    cnt_popback = formated_length - newlength

    i = len(name) - 1
    while (i >= 0) and (cnt_popback > 0):
        while (i >= 0) and (a[i] == 0):
            i -= 1
        a[i] = 2
        i -= 1
        cnt_popback -= 1
    res = ""
    for i in range(len(name)):
        if (a[i] == 0) or (a[i] == 1):
            res += name[i]
    return res

def truncate(name, trunclen):
    if formated_string_len(name) > trunclen:
        #name = "%{T1}Feryquitous%{T-}: %{T1}Shakah%{T-}"
        #name = name[:trunclen]
        #=> name = "%{T1}Feryquitous%{T-}: %{T1}Shakah%"
        #=> display: Feryquitous%
        #=> display error (symbol % appear on the display)
        name = resize_formated_string(name, trunclen)
        name += '...'
        if ('(' in name) and (')' not in name):
            name += ')'
    return name

# Default parameters
output = fix_string(u'{play_pause} {artist}: {song}')
trunclen = 35
play_pause = fix_string(u'\u25B6,\u23F8') # first character is play, second is paused

label_with_font = '%{{T{font}}}{label}%{{T-}}'
font = args.font
play_pause_font = args.play_pause_font

quiet = args.quiet

# parameters can be overwritten by args
if args.trunclen is not None:
    trunclen = args.trunclen
if args.custom_format is not None:
    output = args.custom_format
if args.play_pause is not None:
    play_pause = args.play_pause

try:
    session_bus = dbus.SessionBus()
    spotify_bus = session_bus.get_object(
        'org.mpris.MediaPlayer2.spotify',
        '/org/mpris/MediaPlayer2'
    )

    spotify_properties = dbus.Interface(
        spotify_bus,
        'org.freedesktop.DBus.Properties'
    )

    metadata = spotify_properties.Get('org.mpris.MediaPlayer2.Player', 'Metadata')
    status = spotify_properties.Get('org.mpris.MediaPlayer2.Player', 'PlaybackStatus')

    # Handle play/pause label

    play_pause = play_pause.split(',')

    if status == 'Playing':
        play_pause = play_pause[0]
    elif status == 'Paused':
        play_pause = play_pause[1]
    else:
        play_pause = str()

    if play_pause_font:
        play_pause = label_with_font.format(font=play_pause_font, label=play_pause)

    # Handle main label

    artist = fix_string(metadata['xesam:artist'][0]) if metadata['xesam:artist'] else ''
    song = fix_string(metadata['xesam:title']) if metadata['xesam:title'] else ''
    album = fix_string(metadata['xesam:album']) if metadata['xesam:album'] else ''

    if (quiet and status == 'Paused') or (not artist and not song and not album):
        print('')
    else:
        if font:
            artist = label_with_font.format(font=font, label=artist)
            song = label_with_font.format(font=font, label=song)
            album = label_with_font.format(font=font, label=album)

        # Add 4 to trunclen to account for status symbol, spaces, and other padding characters
        print(truncate(output.format(artist=artist, 
                                     song=song, 
                                     play_pause=play_pause, 
                                     album=album), trunclen + 4))

except Exception as e:
    if isinstance(e, dbus.exceptions.DBusException):
        print('')
    else:
        print(e)
