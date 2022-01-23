import time
import vlc


vlc_instance = vlc.Instance('--input-repeat=99999', '--mouse-hide-timeout=99999999')
player = vlc_instance.media_player_new()

media = vlc.Media('video/cat.mp4')

player.set_media(media)
player.play()

time.sleep(30)