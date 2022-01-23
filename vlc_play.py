import sys
import time
import vlc
from time import sleep
from PIL import Image


instance = vlc.Instance()
media_list = instance.media_list_new()
media_list.add_media(instance.media_new('video/cat.mp4'))

list_player = instance.media_list_player_new()
list_player.set_playback_mode(vlc.PlaybackMode.loop)
list_player.set_media_list(media_list)

list_player.play()


time.sleep(30)