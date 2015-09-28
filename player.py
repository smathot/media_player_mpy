from moviepy.video.io.VideoFileClip import VideoFileClip
import os

class Player(object):

	def __init__(self, videofile=None):
		self.load_video(videofile)
		
		
	def load_video(self, videofile):
		if not videofile is None:
			if os.path.exists(videofile):
				self.clip = VideoFileClip(videofile)
			else:
				raise IOError("File not found: {0}".format(videofile))