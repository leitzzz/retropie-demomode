#!/usr/bin/python3

from glob import glob
import random
import select
import os
import subprocess
import re
import signal
import threading
import time

# used to enable debug logging to file
DEBUG_MODE = False

if DEBUG_MODE:
    import logging
    logging.basicConfig(
        filename='/var/tmp/rungames_in_demomode.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# this variable holds the paths to search for games and the file extensions to include.
# you can modify this dictionary to add or remove systems and their corresponding file types.
GAMES_FOLDERS_PATHS = {'/home/pi/RetroPie/roms/snes': ['.zip', '.sfc', '.smc'],
                       '/home/pi/RetroPie/roms/nes': ['.nes', '.zip'],
                       '/home/pi/RetroPie/roms/megadrive': ['.md', '.bin', '.smd', '.zip'],
                       '/home/pi/RetroPie/roms/arcade': ['.zip'],
                       '/home/pi/RetroPie/roms/neogeo': ['.zip'], }

# this variable will hold the timeout value in seconds between each game execution in demo mode.
# settled to 5 minutes (300 seconds) by default. Adjust as needed.
INACTIVITY_TIMEOUT = 300

# list of games to choose from, filtered by inclusion rules.


def get_game_list(games_paths):
    """Returns a list of games that match the inclusion rules."""
    glist = []
    for path, extensions in games_paths.items():
        for ext in extensions:
            search_pattern = os.path.join(path, '*' + ext)
            found_games = glob(search_pattern)
            glist.extend(found_games)

    if DEBUG_MODE:
        logging.info(
            f'Total games in list: {len(glist)}')

    return glist

# pick a random game from the list


def getRandomGame(glist):
    """Returns a random game from the provided game list."""
    selected_game = glist[random.randint(0, len(glist) - 1)]
    if DEBUG_MODE:
        logging.info('Random game selected: ' + selected_game)

    return selected_game


def inputAvailable(fds, timeout, exitPipeFd):
    """Checks if there is input available on any of the provided file descriptors within the specified timeout."""
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
    """Kills the process with the given PID."""
    try:
        os.kill(pid, signal.SIGTERM)
    except:
        pass


def killgame(pid):
    """Kills the game process and all its child processes."""
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
    """Called when the game process exits."""
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
    """Clears any available input from the given file descriptor."""
    (rd, wr, sp) = select.select([fd], [], [], 0)

    while (rd != []):
        rd[0].read(1)
        (rd, wr, sp) = select.select([fd], [], [], 0)


def clearScreen():
    """Clears the terminal screen."""
    os.system('clear')


exitPipeRead, exitPipeWrite = os.pipe()
exitPipeRead, exitPipeWrite = os.fdopen(
    exitPipeRead, 'rb'), os.fdopen(exitPipeWrite, 'w')
fds.append(exitPipeRead)

if DEBUG_MODE:
    logging.info('exitPipeRead: ' + str(exitPipeRead))

# disable dialog command to avoid blocking the demo mode.
os.system('alias dialog=:')

# request the initial game list
game_list = get_game_list(GAMES_FOLDERS_PATHS)

while True:
    purgueFd(exitPipeRead)
    clearScreen()

    # refresh game list if empty
    if len(game_list) == 0:
        game_list = get_game_list(GAMES_FOLDERS_PATHS)

    gamefile = getRandomGame(game_list)
    current_game = gamefile
    # remove selected game from list to avoid repetition
    game_list.remove(gamefile)

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

    clearScreen()

    time.sleep(2)
