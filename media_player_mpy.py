"""
This file is part of OpenSesame.

OpenSesame is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

OpenSesame is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with OpenSesame.  If not, see <http://www.gnu.org/licenses/>.

This module interfaces with the GStreamer framework through the 
Python bindings supplied with it. The module enables media playback functionality 
in the OpenSesame Experiment buider. In this module's current version, the 
GStreamer SDK (from http://www.gstreamer.com) is expected to be 
installed at its default location (in windows this is c:\gstreamer-sdk). 
If this is not the case in your situation, please change the GSTREAMER_PATH 
variable so that it points to the location at which you installed the 
GStreamer framework. This plugin should then automatically find all required
libraries and Python modules.
"""

__author__ = "Daniel Schreij"
__license__ = "GPLv3"

# Import Python 3 compatibility functions
from libopensesame.py3compat import *
# Import the required modules.
from libopensesame import debug
from libopensesame.item import item
from libqtopensesame.items.qtautoplugin import qtautoplugin

import os
import sys

# Rendering components
import pygame
import psychopy
import pyaudio

from OpenGL.GL import *
import numpy as np

# The player itself
import player

#---------------------------------------------------------------------
# Sound renderer objects
#---------------------------------------------------------------------

class SoundrendererPygame(object):
	""" Uses pygame.mixer to play sound """
	def __init__(self, audioformat):
		fps 		= audioformat["fps"]
		nchannels 	= audioformat["nchannels"]
		nbytes   	= audioformat["nbytes"]
		
		pygame.mixer.quit()
		print "Using pygame mixer with {0}".format(audioformat)
		pygame.mixer.init(fps, -8 * nbytes, nchannels, 1024)
		
	def write(self, frame):
		""" write frame to output channel """
		chunk = pygame.sndarray.make_sound(frame)
		if not hasattr(self,"channel"):
			self.channel = chunk.play()
		else:
			self.channel.queue(chunk)
			
	def close(self):
		""" Cleanup (done by pygame.quit() in main loop) """
		pass
	
class SoundrendererPyAudio(object):
	""" Uses pyaudio to play sound """
	def __init__(self, audioformat):
		fps 		= audioformat["fps"]
		nchannels = audioformat["nchannels"]
		nbytes    = audioformat["nbytes"]
		
		p = pyaudio.PyAudio()
		self.stream = p.open(
			channels  	= nchannels,
			rate 		= fps,
			format 	= pyaudio.get_format_from_width(nbytes),
			output 	= True
		)
		
	def write(self, frame):
		""" write frame to output channel """
		self.stream.write(frame.data)
		
	def close(self):
		""" cleanup """
		self.stream.stop_stream()
		self.stream.close()


#---------------------------------------------------------------------
# Base classes (should be subclassed by backend-specific classes)
#---------------------------------------------------------------------

class pygame_handler(object):
	"""
	Superclass for both the legacy and expyriment hanlders. Both these backends are based on pygame, so have 
	the same event handling methods, which they can both inherit from this class.
	"""
	
	def __init__(self, main_player, screen, custom_event_code = None):
		"""
		Constructor. Set variables to be used in rest of class.

		Arguments:
		main_player -- reference to the main_player_gst object (which instantiates this class or its sublass)
		screen -- reference to the pygame display surface		

		Keyword arguments:
		custom_event_code -- (Compiled) code that is to be called after every frame
		"""		
		self.main_player = main_player
		self.screen = screen
		self.custom_event_code = custom_event_code	
	
	def handle_videoframe(self, frame):
		"""
		Callback method for handling a video frame

		Arguments:
		frame - the video frame supplied as a str/bytes object
		frame_on_time - (True|False) indicates if renderer is lagging behind
			internal frame counter of the player (False) or is still in sync (True)
		"""	
		self.frame = frame	
		
	def swap_buffers(self):
		"""
		Flips back and front buffers
		"""
		pygame.display.flip()
	
	def prepare_for_playback(self):
		"""
		Dummy function (to be implemented in OpenGL based subclasses like expyriment)
		This function should prepare the context of OpenGL based backends for playback
		"""
		pass
	
	def playback_finished(self):
		"""
		Dummy function (to be implemented in OpenGL based subclasses like expyriment)
		This function should restore OpenGL context to as it was before playback
		"""
		pass
			
	def process_user_input(self):
		"""
		Process events from input devices
		
		Returns:
		True -- if no key/mouse button has been pressed or if custom event code returns True
		False -- if a keypress or mouse click was detected (an OS indicates playback should be stopped then
			or custom event code has returned False
		"""

		for event in pygame.event.get():
			if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
				# Catch escape presses
				if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
					self.main_player.playing = False
					raise osexception(u"The escape key was pressed")				
				
				if self.custom_event_code != None:
					if event.type == pygame.KEYDOWN:
						return self.process_user_input_customized(("key", pygame.key.name(event.key)))
					elif event.type == pygame.MOUSEBUTTONDOWN:
						return self.process_user_input_customized(("mouse", event.button))	
				# Stop experiment on keypress (if indicated as stopping method)
				elif event.type == pygame.KEYDOWN and self.main_player.duration == u"keypress":					
					self.main_player.experiment.response = pygame.key.name(event.key)
					self.main_player.experiment.end_response_interval = pygame.time.get_ticks()
					return False
				# Stop experiment on mouse click (if indicated as stopping method)
				elif event.type == pygame.MOUSEBUTTONDOWN and self.main_player.duration == u"mouseclick":					
					self.main_player.experiment.response = event.button
					self.main_player.experiment.end_response_interval = pygame.time.get_ticks()
					return False	
		
		pygame.event.pump()
		return True

	def process_user_input_customized(self, event=None):
		"""
		Allows the user to insert custom code. Code is stored in the event_handler variable.

		Arguments:
		event -- a tuple containing the type of event (key or mouse button press)
			   and the value of the key or mouse button pressed (which character or mouse button)
		"""

		# Listen for escape presses and collect keyboard and mouse presses if no event has been passed to the function
		# If only one button press or mouse press is in the event que, the resulting event variable will just be a tuple
		# Otherwise the collected event tuples will be put in a list, which the user can iterate through with his custom code
		# This way the user will have either
		#  1. a single tuple with the data of the event (either collected here from the event que or passed from process_user_input)
		#  2. a list of tuples containing all key and mouse presses that have been pulled from the event queue		
				
		if event is None:
			events = pygame.event.get()
			event = []  # List to contain collected info on key and mouse presses			
			for ev in events:
				if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
					self.main_player.playing = False
					raise osexception(u"The escape key was pressed")								
				elif ev.type == pygame.KEYDOWN or ev.type == pygame.MOUSEBUTTONDOWN:
					# Exit on ESC press					
					if ev.type == pygame.KEYDOWN:
						event.append(("key", pygame.key.name(ev.key)))
					elif ev.type == pygame.MOUSEBUTTONDOWN:
						event.append(("mouse", ev.button))
			# If there is only one tuple in the list of collected events, take it out of the list 
			if len(event) == 1:
				event = event[0]
																
		continue_playback = True

		# Variables for user to use in custom script
		exp = self.main_player.experiment
		frame = self.main_player.frame_no
		mov_width = self.main_player.destsize[0]
		mov_height = self.main_player.destsize[1]
		times_played = self.main_player.times_played
		
		# Easily callable pause function
		# Use can now simply say pause() und unpause()

		paused = self.main_player.paused # for checking if player is currently paused or not
		pause = self.main_player.pause

		# Add more convenience functions?

		try:
			exec(self.custom_event_code)
		except Exception as e:
			self.main_player.playing = False
			raise osexception(u"Error while executing event handling code: %s" % e)

		if type(continue_playback) != bool:
			continue_playback = False

		pygame.event.pump()
		return continue_playback


class OpenGL_renderer(object):
	"""
	Superclass for both the expyriment and psychopy handlers. Both these backends 
	are OpenGL based and basically have the same drawing routines. 
	By inheriting from this class, they only need to be defined once in here.
	"""
	
	def __init__(self):
		raise osexception("This class should only be subclassed on not be instantiated directly!")
	
	def prepare_for_playback(self):
		"""Prepares the OpenGL context for playback"""
		GL = self.GL
				
		# Prepare OpenGL for drawing
		GL.glPushMatrix()		# Save current OpenGL context
		GL.glLoadIdentity()				

		# Set screen coordinates to useful values for movie playback (per pixel coordinates)
		GL.glMatrixMode(GL.GL_PROJECTION)
		GL.glPushMatrix()
		GL.glLoadIdentity()
		GL.glOrtho(0.0,  self.main_player.experiment.width,  self.main_player.experiment.height, 0.0, 0.0, 1.0)		
		GL.glMatrixMode(GL.GL_MODELVIEW)
		
		# Create black empty texture to start with, to prevent artifacts
		img = np.zeros([self.main_player.vidsize[0], self.main_player.vidsize[1],3], dtype=np.uint8)
		img.fill(0) 
		
		GL.glEnable(GL.GL_TEXTURE_2D)
		GL.glBindTexture(GL.GL_TEXTURE_2D, self.texid)
		GL.glTexImage2D( GL.GL_TEXTURE_2D, 0, GL.GL_RGB, self.main_player.vidsize[0], self.main_player.vidsize[1], 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, img.tostring())
		GL.glTexParameterf(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
		GL.glTexParameterf(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)	
		
		GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT)	
		
	def playback_finished(self):
		""" Restore previous OpenGL context as before playback """
		GL = self.GL
		
		GL.glMatrixMode(GL.GL_PROJECTION)
		GL.glPopMatrix()
		GL.glMatrixMode(GL.GL_MODELVIEW)				
		GL.glPopMatrix()
		
	def draw_frame(self):		
		"""
		Does the actual rendering of the buffer to the screen
		"""	
		GL = self.GL

		# Get desired format from main player
		(w,h) = self.main_player.destsize
		(x,y) = self.main_player.vidPos						
					
		# Frame should blend with color white
		GL.glColor4f(1,1,1,1)
						
		# Only if a frame has been set, blit it to the texture
		if hasattr(self,"frame") and not self.frame is None:			    				
			GL.glLoadIdentity()
			GL.glTexSubImage2D( GL.GL_TEXTURE_2D, 0, 0, 0, self.main_player.vidsize[0], self.main_player.vidsize[1], GL.GL_RGB, GL.GL_UNSIGNED_BYTE, self.frame)
					
		# Drawing of the quad on which the frame texture is projected
		GL.glBegin(GL.GL_QUADS)
		GL.glTexCoord2f(0.0, 0.0); GL.glVertex3i(x, y, 0)
		GL.glTexCoord2f(1.0, 0.0); GL.glVertex3i(x+w, y, 0)
		GL.glTexCoord2f(1.0, 1.0); GL.glVertex3i(x+w, y+h, 0)
		GL.glTexCoord2f(0.0, 1.0); GL.glVertex3i(x, y+h, 0)				
		GL.glEnd()
		
		# Make sure there are no pending drawing operations and flip front and backbuffer
		GL.glFlush()

		
#---------------------------------------------------------------------
# Backend specific classes
#---------------------------------------------------------------------	

class legacy_handler(pygame_handler):
	"""
	Handles video frames and input supplied by media_player_gst for the legacy backend, which is based on pygame
	"""
	
	def __init__(self, main_player, screen, custom_event_code = None):
		"""
		Constructor. Set variables to be used in rest of class.

		Arguments:
		main_player -- reference to the main_player_gst object (which should instantiate this class)
		screen -- reference to the pygame display surface		

		Keyword arguments:
		custom_event_code -- (Compiled) code that is to be called after every frame
		"""	
		# Call constructor of super class
		super(legacy_handler, self).__init__(main_player, screen, custom_event_code )		
				
		# Already create surfaces so this does not need to be redone for every frame
		# The time to process a single frame should be much shorter this way.				
		self.img = pygame.Surface(self.main_player.vidsize, pygame.SWSURFACE, 24, (255, 65280, 16711680, 0))
		# Create pygame bufferproxy object for direct surface access
		# This saves us from using the time consuming pygame.image.fromstring() method as the frame will be
		# supplied in a format that can be written directly to the bufferproxy		
		self.imgBuffer = self.img.get_buffer()
		if self.main_player.fullscreen == u"yes":			
			self.dest_surface = pygame.Surface(self.main_player.destsize, pygame.SWSURFACE, 24, (255, 65280, 16711680, 0))		
		
	def prepare_for_playback(self):
		"""
		Setup screen for playback (Just fills the screen with the background color for this backend)
		"""
		# Fill surface with background color
		self.screen.fill(pygame.Color(str(self.main_player.experiment.background)))
		self.last_drawn_frame_no = 0
	
	def draw_frame(self):
		"""
		Does the actual rendering of the buffer to the screen
		"""	
		
		if hasattr(self,"frame") and not self.frame is None:					
			# Only draw each frame to screen once, to give the pygame (software-based) rendering engine
			# some breathing space
			if self.last_drawn_frame_no != self.main_player.frame_no:
				# Write the video frame to the bufferproxy
				self.imgBuffer.write(self.frame, 0)
				
				# If resize option is selected, resize frame to screen/window dimensions and blit
				if hasattr(self, "dest_surface"):
					pygame.transform.scale(self.img, self.main_player.destsize, self.dest_surface)
					self.screen.blit(self.dest_surface, self.main_player.vidPos)
				else:	
				# In case movie needs to be displayed 1-on-1 blit directly to screen
					self.screen.blit(self.img.copy(), self.main_player.vidPos)		
	
				self.last_drawn_frame_no = self.main_player.frame_no
	
		
class expyriment_handler(OpenGL_renderer, pygame_handler):
	"""
	Handles video frames and input supplied by media_player_gst for the expyriment backend, 
	which is based on pygame (with OpenGL in fullscreen mode)
	"""
	def __init__(self, main_player, screen, custom_event_code = None):
		import OpenGL.GL as GL
		
		# Initialize super c lass
		pygame_handler.__init__(self, main_player, screen, custom_event_code )
		
		# GL context to use by the OpenGL_renderer class
		self.GL = GL
		self.texid = GL.glGenTextures(1)	
		
		
class psychopy_handler(OpenGL_renderer):
	"""
	Handles video frames and input for the psychopy backend supplied by media_player_gst
	Based on OpenGL so inherits from the OpenGL_renderer superclass
	"""
	def __init__(self, main_player, screen, custom_event_code = None):
		"""
		Constructor. Set variables to be used in rest of class.

		Arguments:
		main_player -- reference to the main_player_gst object (which should instantiate this class)
		screen -- reference to the pygame display surface		

		Keyword arguments:
		custom_event_code -- (Compiled) code that is to be called after every frame
		"""		
		import ctypes
		import pyglet.gl		
		
		self.main_player = main_player
		self.win = screen
		self.frame = None
		self.custom_event_code = custom_event_code	

		# GL context to be used by the OpenGL_renderer class
		# Create texture to render frames to later
		GL = self.GL = pyglet.gl	
		self.texid = GL.GLuint()
		GL.glGenTextures(1, ctypes.byref(self.texid))
					
	def handle_videoframe(self, frame):
		"""
		Callback method for handling a video frame

		Arguments:
		frame - the video frame supplied as a str/bytes object
		"""		
		self.frame = frame
		
	def swap_buffers(self):
		"""Draw buffer to screen"""
		self.win.flip()
		
	def process_user_input(self):		
		"""
		Process events from input devices
		
		Returns:
		True -- if no key/mouse button has been pressed or if custom event code returns True
		False -- if a keypress or mouse click was detected (an OS indicates playback should be stopped then
			or custom event code has returned False
		"""		
		pressed_keys = psychopy.event.getKeys()				
		
		for key in pressed_keys:				
			# Catch escape presses
			if key == "escape":
				self.main_player.playing = False
				raise osexception("The escape key was pressed")	
	
			if self.custom_event_code != None:
				return self.process_user_input_customized(("key", key))				
			elif self.main_player.duration == u"keypress":
				self.main_player.experiment.response = key
				self.main_player.experiment.end_response_interval = time.time()	
				return False		
		return True
						
		
	def process_user_input_customized(self, event=None):
		"""
		Allows the user to insert custom code. Code is stored in the event_handler variable.

		Arguments:
		event -- a tuple containing the type of event (key or mouse button press)
			   and the value of the key or mouse button pressed (which character or mouse button)
		"""
	
		if event is None:
			events = psychopy.event.getKeys()
			event = []  # List to contain collected info on key and mouse presses			
			for key in events:
				if key == "escape":
					self.main_player.playing = False
					raise osexception(u"The escape key was pressed")								
				else:
					event.append(("key", key))

			# If there is only one tuple in the list of collected events, take it out of the list 
			if len(event) == 1:
				event = event[0]		
		
		
		continue_playback = True		
	
		# Variables for user to use in custom script
		exp = self.main_player.experiment		
		frame = self.main_player.frame_no
		mov_width = self.main_player.destsize[0]
		mov_height = self.main_player.destsize[1]
		times_played = self.main_player.times_played
		
		# Easily callable pause function
		# Use can now simply call pause() to pause and unpause()
		paused = self.main_player.paused
		pause = self.main_player.pause

		# Add more convenience functions?	
		
		# Execute custom code
		try:
			exec(self.custom_event_code)
		except Exception as e:
			self.main_player.playing = False
			raise osexception(u"Error while executing event handling code: %s" % e)

		# if continue_playback has been set to anything else than True or False, then stop playback
		if type(continue_playback) != bool:
			continue_playback = False	
		
		return continue_playback
		
#---------------------------------------------------------------------
# Main player class -- communicates with MoviePy
#---------------------------------------------------------------------

class media_player_mpy(item):
	description = u'Media player based on moviepy'	

	def reset(self):
		"""
		desc:
			Initialize/ reset the plug-in.
		"""
		# Set default experimental variables and values	
		self.var.video_src 			= u""
		self.var.duration 			= u"keypress"
		self.var.resizeVideo 			= u"yes"
		self.var.playaudio 			= u"yes"
		self.var.loop 				= u"no"
		self.var.event_handler_trigger 	= u"on keypress"
		self.var.event_handler 		= u""
		self.var.soundrenderer 		= "pygame"		
		
		# Set default internal variables
		self.texUpdated 				= False		
		
		# Debugging output is only visible when OpenSesame is started with the
		# --debug argument.
		debug.msg(u'media_player_mpy has been initialized!')

	def prepare(self):
		"""
		desc:
			Opens the video file for playback and compiles the event handler
			code.

		returns:
			desc:	True on success, False on failure.
			type:	bool
		"""
		# Call parent functions.
		item.prepare(self)
		# Prepare your plug-in here.
		
		# Set handler of frames and user input
		if type(self.var.canvas_backend) in [unicode,str]:
			if self.var.canvas_backend == u"legacy" or self.var.canvas_backend == u"droid":				
				self.handler = legacy_handler(self, self.experiment.surface, custom_event_handler)
			if self.var.canvas_backend == u"psycho":				
				self.handler = psychopy_handler(self, self.experiment.window, custom_event_handler)
			if self.var.canvas_backend == u"xpyriment":			
				# Expyriment uses OpenGL in fullscreen mode, but just pygame 
				# (legacy) display mode otherwise
				if self.experiment.fullscreen:				
					self.handler = expyriment_handler(self, self.experiment.window, custom_event_handler)
				else:
					self.handler = legacy_handler(self, self.experiment.window, custom_event_handler)
		else:
			# Give a sensible error message if the proper back-end has not been selected
			raise osexception(u"The media_player plug-in could not determine which backend was used!")		


		if self.var.playaudio == u"yes":
			playaudio = True
		else:
			playaudio = False
			
		self.player = player.Player(
			videorenderfunc=self.handler.handle_videoframe,
			audiorenderfunc=self.__render_audioframe,
			play_audio=playaudio
		)
		
		# Load video file to play
		if self.var.video_src == u"":
			raise osexception(u"No video file was set")
		elif not os.path.exists(self.var.video_src):
			raise osexception(u"Invalid path to video file (file not found)")
		# Load the video file. Returns false if this failed
		elif not self.player.load_video(self.var.video_src):
			raise osexception(u"Video file could not be loaded")
			
		# Set audiorenderer
		if self.var.playaudio == u"yes" and self.player.audioformat:
			if self.var.soundrenderer == u"pygame":
				self.audio_handler = SoundrendererPygame(self.player.audioformat)
			elif self.var.soundrenderer == u"pyaudio":
				self.audio_handler = SoundrendererPyAudio(self.player.audioformat)
		# Report success		
	
		return True

	def run(self):
		# Record the timestamp of the plug-in execution.
		self.set_item_onset()
		# Run your plug-in here.
		
		# Signal player to start video playback
		self.paused = False
		
		# Prepare frame renderer in handler for playback
		# (e.g. set up OpenGL context, thus only relevant for OpenGL based backends)
		self.handler.prepare_for_playback()

		### Main player loop. While True, the movie is playing
		start_time = time.time()
		self.player.play()

		# While video is playing, render frames
		while self.player.status in [player.PLAYING, player.PAUSED]:
			if self.__frame_updated:
				# Draw current frame to screen
				self.handler.draw_frame()
				
				# Swap buffers to show drawn stuff on screen
				self.handler.swap_buffers()
				# Reset updated flag
				self.__frame_updated = False
						
			# Handle input events								
			if self._event_handler_always:
				self.playing = self.handler.process_user_input_customized()
			elif not self._event_handler_always:				
				self.playing = self.handler.process_user_input()
							
			# Determine if playback should continue when a time limit is set
			if type(self.duration) == int:
				if time.time() - start_time > self.duration:
					self.stop()		

		# Restore OpenGL context as before playback
		self.handler.playback_finished()
		
		if self.player.audioformat:
			self.audio_out.close()
		
	def calculate_scaled_resolution(self, screen_res, image_res):
		"""Calculate image size so it fits the screen
		Arguments:
		screen_res  --  Tuple containing display window size/Resolution
		image_res   --  Tuple containing image width and height
			
		Returns:
		(width, height) tuple of image scaled to window/screen
		"""
		
		rs = screen_res[0]/float(screen_res[1])
		ri = image_res[0]/float(image_res[1])
	
		if rs > ri:
			return (int(image_res[0] * screen_res[1]/image_res[1]), screen_res[1])
		else:
			return (screen_res[0], int(image_res[1]*screen_res[0]/image_res[0]))

	def __render_audioframe(self, frame):
		self.audio_handler.write(frame)
		
	def __handle_videoframe(self, frame):
		self.__frame_updated = True
		self.handler.handle_videoframe(frame)
		
	def stop(self):
		self.player.stop()
		
	def pause(self):
		if self.player.status == player.PAUSED:
			self.player.pause()
			self.paused = False
		elif self.player.status == player.PLAYING:
			self.player.pause()
			self.paused = True
		else:
			print "Player not in pausable state"

class qtmy_plugin(media_player_mpy, qtautoplugin):

	def __init__(self, name, experiment, script=None):

		# Call parent constructors.
		media_player_mpy.__init__(self, name, experiment, script)
		qtautoplugin.__init__(self, __file__)

