# Python 3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# MoviePy and pyaudio
try:
	from moviepy.video.io.VideoFileClip import VideoFileClip
	from moviepy.tools import cvsecs
	import pyaudio
except ImportError as e:
	print("""Error importing dependencies:
{0}

This module depends on the following packages

- MoviePy
- ImageIO
- PyAudio

Please make sure that they are installed.""".format(e))

# Other modules
import os
import time
import threading

# constants to indicate player status
UNINITIALIZED = 0	# No video file loaded
READY = 1
PAUSED = 2		# Playback is paused
PLAYING = 3		# Player is playing
EOS = 4			# End of stream has been reached

# constants to indicate clock status
PAUSED = 1
RUNNING = 2
STOPPED = 3

class Clock(object):
	""" Clock functions as a stopwatch to measure time from an arbitrary 
	starting point. It runs in a separate thread and can time can be polled
	by checking the property clock.time """
		
	def __init__(self):
		""" Constructor """
		self.starttime = time.time()
		self.elapsed_time = 0
		self.status = PAUSED
		
	def reset(self):
		""" Reset the clock to 0 """
		self.starttime = time.time()
		self.elapsed_time = 0
		
	def pause(self):
		if self.status == RUNNING:
			self.status = PAUSED
		elif self.status == PAUSED:
			self.status = RUNNING
			
	def start(self):
		self.thread = threading.Thread(target=self.__run)
		self.status = RUNNING
		self.reset()
		self.thread.start()
					
	def __run(self):
		while self.status != STOPPED:
			if self.status == RUNNING:
				self.elapsed_time = time.time() - self.starttime
			# One refresh per 5 milliseconds seems enough
			time.sleep(0.005)
				
	def stop(self):
		self.status = STOPPED
		self.reset()
		
	@property
	def time(self):
		return self.elapsed_time
		
	
class Player(object):

	def __init__(self, videofile=None, renderfunc=None, play_audio=True):
		"""
		Constructor
		
		Keyword arguments:
		videofile  --  The path to the videofile to be loaded (default: None)
		renderfunc --  callback function that takes care of the actual
					rendering of the frame (default: None)
					
					The specified renderfunc should be able to accept the following
					arguments:
						- frame (numpy array): the frame to be rendered
		play_audio --  Whether audio of the clip should be played (default: True)
		"""
		
		# Load a video file if specified, but allow users to do this later
		# by initializing all variables to None		
		if not self.load_video(videofile, play_audio):
			self.reset()
		
		# Check if renderfunc is indeed a function
		if hasattr(renderfunc, '__call__'):
			self.renderfunc = renderfunc
	
	def reset(self):
		self.clip = None
		self.loaded_file = None
		self.audiostream = None
		self.fps = None
		self.frame_interval = None
		self.duration = None
		self.current_playtime = None
		self.frame_no = None
		self.status = UNINITIALIZED
		
	def load_video(self, videofile, play_audio=True):
		if not videofile is None:
			if os.path.isfile(videofile):
				self.clip = VideoFileClip(videofile,audio=play_audio)
				
				if play_audio and self.clip.audio:
					# If clip has audio and it needs to be played,
					# create a pyaudio to pass the sound to later
					p = pyaudio.PyAudio()
					self.audio_out = p.open(
						format   = pyaudio.paInt16,
						channels = self.clip.audio.nchannels,
						rate     = self.clip.audio.fps,
						output   = True
					)
					
				self.duration = self.clip.duration
				self.loaded_file = os.path.split(videofile)[1]
				
				## Timing variables
				# Frames per second of clip
				self.fps = self.clip.fps
				# Duration in seconds of one frame
				self.frame_interval = 1.0/self.fps
				# Current position in video in seconds
				self.current_playtime = 0.0
				# Current frame
				self.frame_no = 0
					
				print("Loaded {0}".format(videofile))		
				self.status = PAUSED
				return True
			else:
				raise IOError("File not found: {0}".format(videofile))
		else:
			print("No videofile specified")
		return False
		
	def play(self):		
		### First do some status checks

		# Make sure a file is loaded		
		if self.status == UNINITIALIZED or self.clip is None:
			raise RuntimeError("Player uninitialized or no file loaded")
			
		# Check if playback has already finished (rewind needs to be called first)
		if self.status == EOS:
			print("End of stream has been reached")
			return
		
		# Check if playback hasn't already been started (and thus if play()
		# has not been called before from another thread for instance)
		if self.status in [PLAYING,PAUSED]:
			print("Video already started")
			return
		
		### If all is in order start the general playing loop		
		if self.status == READY:
			self.status = PLAYING
			
		# Play while end of stream has not been reached
		while not self.status == EOS:
			# Only render frames and run time if state is not paused 
			if self.status == PAUSED:
				continue
			
						
			
	def pause(self):
		""" Change playback status only if current status is PLAYING or
		PAUSED (and not READY) """
		if self.status == PAUSED:
			self.status = PLAYING
		if self.status == PLAYING:
			self.status = PAUSED
		
	# Object specific functions	
	def __repr__(self):
		""" Create a string representation for when
		
		print(player)
		
		is called """
		return "Player [file loaded: {0}]".format(self.loaded_file)
		
				
if __name__ == "__main__":
	def render(frame):
		print(frame)
		
	player = Player("/home/daniel/Videos/VANGOGH_2.mp4", renderfunc=render)
	
	