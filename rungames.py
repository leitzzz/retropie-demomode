#!/usr/bin/python3

from glob import glob
import random
import select
import os
import subprocess
import re
import signal
import threading
# import sys
import time

# used to enable debug logging to file
DEBUG_MODE = False

if DEBUG_MODE:
    import logging
    logging.basicConfig(
        filename='/var/tmp/rungames_in_demomode.log', level=logging.INFO)

# Exclusion rules for games that should not be included in demo mode.
# These are regex patterns matched against the full path of each game.
GAME_EXCLUSIONS = ['.*/gamelist.xml', '.*/genesis/.*', '.*/apple2/.*', '.*/bbcmicro/.*', '.*/cdimono1/.*', '.*/mame-advmame/.*', '.*/nds/*.dsv',
                   '.*/pc/pcdata/.*', '.*/vectrex/overlays/.*', '.*/psx/.bin', '.*/*/*.srm*', '.*/*/*.state*', '.*/snes/*.state', '.*/videopac/.*', '.*/ti99/.*']

# this variable will hold the timeout value in seconds between each game execution in demo mode.
INACTIVITY_TIMEOUT = 60

# check every game in the folder path if it matches the exclusion rules
# if it does not match any rule it will be included in the game list


def filter_games(gamename):
    for rule in GAME_EXCLUSIONS:
        if re.match(rule, gamename) is not None:
            return False

    return True


# list of games to choose from, filtered by exclusion rules.
GAME_LIST = list(filter(filter_games, glob('/home/pi/RetroPie/roms/*/*')))

# pick a random game from the list


def getRandomGame():
    global GAME_LIST
    random.shuffle(GAME_LIST)
    if DEBUG_MODE:
        logging.info('Random game selected: ' + GAME_LIST[0])

    return GAME_LIST[0]


def inputAvailable(fds, timeout, exitPipeFd):
    global current_game
    # logging.info('Checking for input on: ' + str(fds) + ', exitFd= '+str(exitPipeFd))
    (rd, wr, sp) = select.select(fds, [], [], timeout)
    # logging.debug('Select reported read available on: ' + str(rd))
    result = rd != []
    while (rd != []):
        rd[0].read(1)
        if rd[0] == exitPipeFd:
            if DEBUG_MODE:
                logging.warning(
                    'Dead child received in main loop (inputAvailable)')
            result = False
        (rd, wr, sp) = select.select(fds, [], [], 0)
    # logging.info('inputAvailable = ' + str(result))
    return result


# to prepare and read inputs from all event devices (using the file descriptors - fds)
fds = [open(fn, 'rb') for fn in glob('/dev/input/event*')]


def killprocs(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except:
        pass


def killgame(pid):
    subp = subprocess.Popen(
        'pstree '+str(pid)+' -p -a -l | cut -d, -f2 | cut -d\' \' -f1', stdout=subprocess.PIPE, shell=True)
    result = subp.communicate()[0].decode('utf8').split('\n')
    list(map(lambda procid: killprocs(int(procid)),
         [v for v in result if v != '']))


proc = 0


def popenAndCall(onExit, *popenArgs, **popenKWArgs):
    """
    Runs a subprocess.Popen, and then calls the function onExit when the
    subprocess completes.

    Use it exactly the way you'd normally use subprocess.Popen, except include a
    callable to execute as the first argument. onExit is a callable object, and
    *popenArgs and **popenKWArgs are simply passed up to subprocess.Popen.
    """

    def runInThread(onExit, popenArgs, popenKWArgs):
        global proc
        proc = subprocess.Popen(*popenArgs, **popenKWArgs)
        onExit(proc.wait())
        return

    thread = threading.Thread(target=runInThread,
                              args=(onExit, popenArgs, popenKWArgs))
    thread.start()

    return thread


def on_exit(code):
    global game_start_time
    global exitPipeWrite
    if DEBUG_MODE:
        logging.info('onExit received at '+str(time.time()))
    if (code == 0):
        if (time.time() - game_start_time > 10):
            if DEBUG_MODE:
                logging.info('Game exited by user after 10sec. Exiting.')
            os._exit(0)
        else:
            if DEBUG_MODE:
                logging.info(
                    'Game exited before 10sec. Assumed dead. Signaling to main thread')
            exitPipeWrite.write('a')
            logging.info('Signaled')
    else:
        if DEBUG_MODE:
            logging.info(
                'Game exited with nonzero result. Assumed dead. Signaling to main thread')
        exitPipeWrite.write('b')
        if DEBUG_MODE:
            logging.info('Signaled')


def purgueFd(fd):
    (rd, wr, sp) = select.select([fd], [], [], 0)
    #  result = rd != []
    while (rd != []):
        rd[0].read(1)
        (rd, wr, sp) = select.select([fd], [], [], 0)


def clearScreen():
    os.system('clear')


exitPipeRead, exitPipeWrite = os.pipe()
exitPipeRead, exitPipeWrite = os.fdopen(
    exitPipeRead, 'rb'), os.fdopen(exitPipeWrite, 'w')
fds.append(exitPipeRead)

if DEBUG_MODE:
    logging.info('exitPipeRead: ' + str(exitPipeRead))

os.system('alias dialog=:')

while 1:
    purgueFd(exitPipeRead)
    clearScreen()
    gamefile = getRandomGame()
    current_game = gamefile
    emulator = re.search('.*/([^/]+)/[^/]+', gamefile).group(1)
    cmd = '/opt/retropie/supplementary/runcommand/runcommand.sh 0 _SYS_ "' + \
        emulator + '" "'+gamefile+'"'
    game_start_time = time.time()
    if DEBUG_MODE:
        logging.info('Starting game at ' +
                     str(game_start_time)+' with command: '+cmd)

    popenAndCall(on_exit, cmd, stdin=0, stdout=1, stderr=2,
                 shell=True)

    timeOutTime = INACTIVITY_TIMEOUT
    while inputAvailable(fds, timeOutTime, exitPipeRead):
        pass

    if DEBUG_MODE:
        logging.info('Killing game at '+str(time.time()))

    killgame(proc.pid)
    time.sleep(5)
