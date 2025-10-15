In retropie v4.8: 

# Copy:

1. rungames.py to /usr/share/pyshared
2. demomode.sh to /home/pi/RetroPie/retropiemenu
3. demomode.png to /home/pi/RetroPie/retropiemenu/icons

4. and copy the content of the gamelist.xml to the existing gamelist.xml in /opt/retropie/configs/all/emulationstation/gamelists/retropie/gamelist.xml

# To run at startup before emulationstation starts:

edit /opt/retropie/configs/all/autostart.sh to have something like this:

bash /home/pi/RetroPie/retropiemenu/demomode.sh
emulationstation #auto

