import sys
import time
import vlc

#p = vlc.MediaPlayer(sys.argv[1])
#p.play()
#time.sleep(2)
#p.stop()
p = vlc.MediaPlayer("songs/"+sys.argv[1]+".mp4")
p.play()

time.sleep(30)