#!/usr/bin/env python

import argparse
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import sys
import time

def fix_string(string):
    # corrects encoding for the python version used
    if sys.version_info.major == 3:
        return string
    else:
        return string.encode('utf-8')

# python parsing library
parser = argparse.ArgumentParser()
parser.add_argument(
    '-t',
    '--trunclen',
    type=int,
    metavar='<maximum number of characters displayed>',
    default=35,
    dest='trunclen'
)
parser.add_argument(
    '-f',
    '--format',
    type=str,
    metavar='<custom format>',
    dest='custom_format',
    default=fix_string(u'{artist}: {song}')
)
parser.add_argument(
    '-p',
    '--playpause',
    type=str,
    metavar='<play-pause indicator>',
    dest='play_pause',
    default=fix_string(u'\u25B6,\u23F8') # first character is play, second is paused
)
parser.add_argument(
    '--font',
    type=str,
    metavar="<main label font index>",
    dest='font'
)
parser.add_argument(
    '--playpause-font',
    type=str,
    metavar='<play-pause button font index>',
    dest='play_pause_font'
)
parser.add_argument(
    '-q',
    '--quiet',
    action='store_true',
    help="if set, don't show any output when the current song is paused",
    dest='quiet',
)
parser.add_argument(
    '-i',
    '--interval',
    type=int,
    metavar='<label updating frequency>',
    help='number of miliseconds between each update() call',
    dest='interval',
    default=1000
)
parser.add_argument(
    '-s',
    '--slide',
    action='store_true',
    help="if set, long label won't be truncated but be displayed in sliding mode",
    dest='slide',
)
parser.add_argument(
    '-a',
    '--append',
    type=str,
    help="this will be appended to the displayed string for sliding mode",
    dest='append',
    default='        ',
    metavar='<appended string>'
)
args = parser.parse_args()

# argument parsing
font = args.font
play_pause_font = args.play_pause_font
trunclen = args.trunclen
output_format = args.custom_format
play_pause = args.play_pause
quiet = args.quiet
interval = args.interval
slide = args.slide
append = args.append

# formating template
label_with_font = '%{{T{font}}}{label}%{{T-}}'
label_with_button = '{button} {label}'

# Handle play/pause label
play_pause = play_pause.split(',')
if play_pause_font is not None:
    play_pause[0] = label_with_font.format(font=play_pause_font, label=play_pause[0])
    play_pause[1] = label_with_font.format(font=play_pause_font, label=play_pause[1])

try:
    ##########################################
    ### DBus properties changed signal handler
    ##########################################

    # Setting for asynchronous method calls
    DBusGMainLoop(set_as_default=True)

    # Connect to the bus
    session_bus = dbus.SessionBus()
    spotify_bus = session_bus.get_object(
        'org.mpris.MediaPlayer2.spotify',
        '/org/mpris/MediaPlayer2'
    )

    spotify_properties = dbus.Interface(
        spotify_bus,
        'org.freedesktop.DBus.Properties'
    )
    # Spotify metadata from d-bus
    artist = None
    song = None
    album = None
    play_pause_status = None

    # Variable for sliding window label
    displayStringStartPos = 0

    def getProperties():
        global spotify_properties, artist, song, album, play_pause_status
        metadata = spotify_properties.Get('org.mpris.MediaPlayer2.Player', 'Metadata')
        play_pause_status = fix_string( spotify_properties.Get('org.mpris.MediaPlayer2.Player', 'PlaybackStatus') )
        artist = fix_string(metadata['xesam:artist'][0]) if metadata['xesam:artist'] else ''
        song = fix_string(metadata['xesam:title']) if metadata['xesam:title'] else ''
        album = fix_string(metadata['xesam:album']) if metadata['xesam:album'] else ''

    #signal updateProperties(interface_name, changed_properties, invalidated_properties):
    def updateProperties(*args, **kwargs):
        (iface, changed_props, invalidated_prop) = args
        assert (iface == "org.mpris.MediaPlayer2.Player")
        global artist, song, album, play_pause_status, displayStringStartPos
        for property, value in changed_props.items():
            match property:
                case "PlaybackStatus":
                    play_pause_status = fix_string(value)
                case "Metadata":
                    artist = fix_string(value['xesam:artist'][0]) if value['xesam:artist'] else ''
                    song = fix_string(value['xesam:title']) if value['xesam:title'] else ''
                    album = fix_string(value['xesam:album']) if value['xesam:album'] else ''
                    displayStringStartPos = 0
        updateLabel(callFromGLib=False)

    ##########################################
    ### Label updater
    ##########################################
    def updateLabel(*args, **kwargs):
        # argument reader
        func_args = {
            "callFromGLib": True
        }
        for key, value in kwargs.items():
            assert (key in func_args)
            func_args[key] = value

        # final argument
        callFromGLib = func_args["callFromGLib"]

        if (quiet and status == 'Paused') or (not artist and not song and not album):
            print('')
        else:
            label = output_format.format(artist=artist, 
                                         song=song,
                                         album=album)
            label_len = len(label)
            display = label
            if trunclen < label_len:
                if slide:
                    label += append
                    label_len += len(append)

                    global displayStringStartPos
                    display = label[displayStringStartPos:displayStringStartPos + trunclen]
                    if displayStringStartPos + trunclen > label_len:
                        display += label[:displayStringStartPos + trunclen - label_len]

                    if callFromGLib:
                        displayStringStartPos += 1
                        if displayStringStartPos == label_len:
                            displayStringStartPos = 0

                else:
                    display = label[:trunclen] + '...'

            if font is not None:
                display = label_with_font.format(label=display,
                                                 font=font)
            print(label_with_button.format(button=play_pause[0] if play_pause_status=="Playing"
                                                                else play_pause[1],
                                           label=display))

        # never stop update label
        return True

    ##########################################
    ### Program main loop
    ##########################################

    # Declare two loops
    spotify_properties.connect_to_signal("PropertiesChanged", updateProperties)
    if slide:
        GLib.timeout_add(interval, updateLabel)

    # First output (no initial delay)
    getProperties()
    updateLabel()

    # Loop forever
    loop = GLib.MainLoop()
    loop.run()

except Exception as e:
    if isinstance(e, dbus.exceptions.DBusException):
        print('')
    else:
        print(e)
