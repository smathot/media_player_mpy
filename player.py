# Python 3 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# MoviePy
try:
	from moviepy.video.io.VideoFileClip import VideoFileClip
	from moviepy.tools import cvsecs
except ImportError as e:
	print("""Error importing dependencies:
{0}

This module depends on the following packages

- MoviePy
- ImageIO

Please make sure that they are installed.""".format(e))

# Other modules
import os
import time
import threading

# constants to indicate player status
UNINITIALIZED = 0	# No video file loaded
READY = 1			# Video file loaded and ready to start
PAUSED = 2		# Playback is paused
PLAYING = 3		# Player is playing
EOS = 4			# End of stream has been reached

# constants to indicate clock status
RUNNING = 1		# Clock is ticking
# Clock uses PAUSED status from player variables above
STOPPED = 3		# Clock has been stopped and is reset

class Timer(object):
	""" Timer serves as a stopwatch to measure time from an arbitrary 
	starting point. It runs in a separate thread and time can be polled
	by checking its property clock.time """
		
	def __init__(self, fps=None, max_duration=None):
		""" Constructor """		
		self.status = PAUSED
		self.max_duration = max_duration
		self.fps = fps
		self.reset()
		
	def reset(self):
		""" Reset the clock to 0 by emptying previous intervals"""		
		self.previous_intervals = []
		self.current_interval_duration = 0.0
		
	def pause(self):
		""" Pauses the clock to continue running later 
		Saves the duration of the current interval in the previous_intervals list."""
		if self.status == RUNNING:
			self.status = PAUSED
			self.previous_intervals.append(time.time() - self.interval_start)
			self.current_interval_duration = 0.0
		elif self.status == PAUSED:
			self.interval_start = time.time()
			self.status = RUNNING
			
	def start(self):
		""" Start the clock from 0. Uses a separate thread to handle the timing
		functionalities. """
		if not hasattr(self,"thread") or not self.thread.isAlive():		
			self.thread = threading.Thread(target=self.__run)
			self.status = RUNNING
			self.reset()
			self.thread.start()
		else:
			print("Clock already running!")
					
	def __run(self):
		""" Internal function that is run in a separate thread. Do not call directly. """
		self.interval_start = time.time()
		while self.status != STOPPED:
			if self.status == RUNNING:
				self.current_interval_duration = time.time() - self.interval_start
				
			# If max_duration is set, stop the clock if it is reached
			if self.max_duration and self.time > self.max_duration:
				self.status == STOPPED
				
			# One refresh per 5 milliseconds seems enough
			time.sleep(0.001)
	
	""" Stop the clock. Also resets the internal timers """
	def stop(self):
		self.status = STOPPED
		self.reset()
		
	@property
	def time(self):
		""" Returns the current logged time of the clock """
		return sum(self.previous_intervals) + self.current_interval_duration
		
	@property
	def current_frame(self):
		if not self.__fps:
			raise RuntimeError("fps not set so current frame number cannot be calculated")
		else:
			return int(self.__fps * self.time)
	
	@property
	def frame_interval(self):
		""" The duration of a frame in seconds """
		if not self.__fps:
			raise RuntimeError("fps not set so current frame interval cannot be calculated")
		else:
			return 1.0/self.__fps
			
	@property
	def fps(self):
		""" Return the frames per second that is set in clock """
		return self.__fps
	
	@fps.setter
	def fps(self,value):
		""" Sets the frames per second of the current movie the clock is used for. 
		
		Arguments:
		-- value (float), the value for fps
		"""
		if not value is None:
			if not type(value) == float:
				raise ValueError("fps needs to be specified as a float")
			if value<1.0:
				raise ValueError("fps needs to be greater than 1.0")
		self.__fps = value

	@property		
	def max_duration(self):
		""" Return the max duration the clock should run for. (Usually the
		duration of the videoclip) """
		return self.__max_duration
		
	@max_duration.setter
	def max_duration(self,value):
		""" Set the value of max duration
		
		Arguments:
		-- value (float), the value for fps
		"""
		if not value is None:
			if not type(value) == float:
				raise ValueError("max_duration needs to be specified as a float")
			if value<1.0:
				raise ValueError("max_duration needs to be greater than 1.0")
		self.__max_duration = value
					
	def __repr__(self):
		""" Create a string representation for the print function"""
		if self.__fps:
			return "Clock [current time: {0}, fps: {1}, current_frame: {2}]".format(self.time, self.__fps, self.current_frame)
		else:
			return "Clock [current time: {0}]".format(self.time)
		
	
class Player(object):
	""" This class loads a video file that can be played. It returns video and audioframes, but can also
	be passed a callback function that can take care of the rendering elsewhere. """

	def __init__(self, videofile=None, videorenderfunc=None, audiorenderfunc=None, play_audio=True):
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
		# Create an internal timer
		self.clock = Timer()		
		
		# Load a video file if specified, but allow users to do this later
		# by initializing all variables to None	
		if not self.load_video(videofile, play_audio):
			self.reset()
		
		## Set callback functions if set
		
		# Check if renderfunc is indeed a function
		if not videorenderfunc is None:
			if not hasattr(videorenderfunc, '__call__'):
				raise TypeError("The object passed for videorenderfunc is not function")
		self.videorenderfunc = videorenderfunc
			
		if not audiorenderfunc is None:
			if not hasattr(audiorenderfunc, '__call__'):
				raise TypeError("The object passed for audiorenderfunc is not function")
		self.audiorenderfunc = audiorenderfunc
		
		self.play_audio = play_audio

	@property			
	def frame_interval(self):
		""" Duration in seconds of a single frame """
		return self.clock.frame_interval
		
	@property
	def current_frame_no(self):
		""" Current frame_no of video """
		return self.clock.current_frame
		
	@property
	def current_videoframe(self):
		""" Representation of current video frame as a numpy array """
		return self.__current_videoframe
		
	@property
	def current_playtime(self):
		""" Clocks current runtime in seconds """
		return self.clock.time
			
	def reset(self):
		self.clip = None
		self.loaded_file = None
		self.audio = None
		
		self.fps = None
		self.duration = None
		
		self.status = UNINITIALIZED
		self.clock.reset()
		
	def load_video(self, videofile, play_audio=True):
		if not videofile is None:
			if os.path.isfile(videofile):
				self.clip = VideoFileClip(videofile,audio=play_audio)
				
				if play_audio and self.clip.audio:
					self.audio = {
						'bits':  		16,
						'channels': 	self.clip.audio.nchannels,
						'rate':	 	self.clip.audio.fps,
					}
				else:
					self.audio = None
					
				self.loaded_file = os.path.split(videofile)[1]
				
				## Timing variables
				# Clip duration
				self.duration = self.clip.duration
				self.clock.max_duration = self.clip.duration
				# Frames per second of clip
				self.fps = self.clip.fps
				self.clock.fps = self.clip.fps
					
				print("Loaded {0}".format(videofile))		
				self.status = READY
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
		self.last_frame_no = 0
		
		if not hasattr(self,"thread") or not self.thread.isAlive():	
			self.thread = threading.Thread(target=self.__render)
			self.thread.start()
			self.clock.start()
		else:
			print("Rendering thread already running!")
		
	def __render(self):
		""" Main rendering loop """
		while self.status in [PLAYING,PAUSED]:
			current_frame_no = self.clock.current_frame
			current_time = self.clock.time

			# Check if end of clip has been reached
			if current_time > self.duration:
				self.status = EOS
				break
			
			if self.last_frame_no != current_frame_no:
				new_videoframe = self.clip.get_frame(current_time)
				new_audioframe = None
				if self.videorenderfunc:
					self.videorenderfunc(new_videoframe)
				if self.play_audio and self.audiorenderfunc:
					self.audiorenderfunc(new_audioframe)
				
				self.__current_videoframe = new_videoframe
				self.__current_audioframe = new_audioframe
				
				
			self.last_frame_no = current_frame_no
			time.sleep(0.5*self.frame_interval)
		
		self.clock.stop()
		print("Rendering stopped!")
		
			
	def pause(self):
		""" Change playback status only if current status is PLAYING or
		PAUSED (and not READY) """
		if self.status == PAUSED:
			self.status = PLAYING
			self.clock.pause()
		if self.status == PLAYING:
			self.status = PAUSED
			self.clock.pause()
	
	def stop(self):
		self.clock.stop()
		self.status = READY
		
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
	
	