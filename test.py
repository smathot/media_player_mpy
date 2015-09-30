# -*- coding: utf-8 -*-
"""
Created on Wed Sep 30 15:46:24 2015

@author: daniel
"""

import os
import sys
import pygame
import time

from OpenGL.GL import *
import numpy as np


import player

class videoPlayer():
	def __init__(self, (windowWidth, windowHeight), fullscreen = False):
		pygame.init()
		flags = pygame.DOUBLEBUF|pygame.OPENGL|pygame.HWSURFACE
		self.fullscreen = fullscreen
		if fullscreen:
			flags = flags | pygame.FULLSCREEN
		pygame.display.set_mode((windowWidth,windowHeight), flags)
		self.windowSize = (windowWidth, windowHeight)
		self.printed = False
		self.texUpdated = False

		self.__initGL()

		self.player = player.Player(
			videorenderfunc=self.__texUpdate,
			#audiorenderfunc=self.__audiorenderer
		)


	def __initGL(self):
		glViewport(0, 0, self.windowSize[0], self.windowSize[1])

		glPushAttrib(GL_ENABLE_BIT)
		glDisable(GL_DEPTH_TEST)
		glDisable(GL_CULL_FACE)

		glDepthFunc(GL_ALWAYS)
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

		glMatrixMode(GL_PROJECTION)
		glPushMatrix()
		glLoadIdentity()
		glOrtho(0.0,  self.windowSize[0],  self.windowSize[1], 0.0, 0.0, 1.0)

		glMatrixMode(GL_MODELVIEW)
		glPushMatrix()

		glColor4f(1,1,1,1)
		glClearColor(0.0, 0.0, 0.0, 1.0)
		glClearDepth(1.0)



	def calcScaledRes(self, screen_res, image_res):
		"""Calculate image size so it fits on screen
		Args
			screen_res (tuple)   -  Display window size/Resolution
			image_res (tuple)    -  Image width and height

		Returns
			tuple - width and height of image scaled to window/screen
		"""
		rs = screen_res[0]/float(screen_res[1])
		ri = image_res[0]/float(image_res[1])

		if rs > ri:
			return (int(image_res[0] * screen_res[1]/image_res[1]), screen_res[1])
		else:
			return (screen_res[0], int(image_res[1]*screen_res[0]/image_res[0]))


	def load_video(self, vidSource):
		if not os.path.exists(vidSource):
			print >> sys.stderr, "File not found: " + vidSource
			sys.exit(1)

		self.player.load_video(vidSource)
		pygame.display.set_caption(os.path.split(vidSource)[1])
		self.vidsize = self.player.clip.size

		self.destsize = self.calcScaledRes(self.windowSize, self.vidsize)
		self.vidPos = ((self.windowSize[0] - self.destsize[0]) / 2, (self.windowSize[1] - self.destsize[1]) / 2)

		self.__textureSetup()

		if(self.player.audio):
			try:
				pygame.mixer.quit()
				fps 		= self.player.audioformat["fps"] ,
				nchannels = self.player.audioformat["nchannels"]
				nbytes    = self.player.audioformat["nbytes"]
				pygame.mixer.init(fps, -8 * nbytes, nchannels, 1024)
			except:
				Exception("Pygame mixer could not be initialized!")


	def __textureSetup(self):
		# Setup texture in OpenGL to render video to
		glEnable(GL_TEXTURE_2D)
		glMatrixMode(GL_MODELVIEW)
		self.textureNo = glGenTextures(1)
		glBindTexture(GL_TEXTURE_2D, self.textureNo)
		glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
		glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)

		# Fill texture with black to begin with.
		img = np.zeros([self.vidsize[0],self.vidsize[1],3],dtype=np.uint8)
		img.fill(0)
		glTexImage2D( GL_TEXTURE_2D, 0, GL_RGB, self.vidsize[0], self.vidsize[1], 0, GL_RGB, GL_UNSIGNED_BYTE, img)

		# Create display list which draws to the quad to which the texture is rendered
		(x,y) = self.vidPos
		(w,h) = self.destsize

		self.frameQuad = glGenLists(1);
		glNewList(self.frameQuad, GL_COMPILE)
		glBegin(GL_QUADS)
		glTexCoord2f(0.0, 0.0); glVertex3i(x, y, 0)
		glTexCoord2f(1.0, 0.0); glVertex3i(x+w, y, 0)
		glTexCoord2f(1.0, 1.0); glVertex3i(x+w, y+h, 0)
		glTexCoord2f(0.0, 1.0); glVertex3i(x, y+h, 0)
		glEnd()
		glEndList()

		# Clear The Screen And The Depth Buffer
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

	def __texUpdate(self, frame):
		# Retrieve buffer from videosink
		self.buffer = frame
		self.texUpdated = True

	def __audiorenderer(self, frame):
		chunk = pygame.sndarray.make_sound(frame)
		if not hasattr(self,"channel"):
			self.channel = chunk.play()
		else:
			self.channel.queue(chunk)


	def drawFrame(self):
		glCallList(self.frameQuad)
		# Flip the buffer to show frame to screen
		pygame.display.flip()


	def play(self):
		# Signal player to start video playback
		self.paused = False
		self.player.play()

		# While video is playing, render frames
		while self.player.status in [player.PLAYING, player.PAUSED]:
			if self.texUpdated:
				#t1 = time.time()
				# Update texture
				glTexSubImage2D( GL_TEXTURE_2D, 0, 0, 0, self.vidsize[0], self.vidsize[1], GL_RGB, GL_UNSIGNED_BYTE, self.buffer)
				#t2 = time.time()
				#print "Texture updated in {0} ms".format(int((t2-t1)*1000))
				self.drawFrame()
				#print "Frame drawn in {0} ms".format(round((time.time()-t2)*1000))

			for e in pygame.event.get():
				if e.type == pygame.QUIT:
					self.stop()
				if e.type == pygame.KEYDOWN:
					if e.key == pygame.K_ESCAPE:
						self.stop()
					if e.key == pygame.K_SPACE:
						self.pause()

			pygame.event.pump()   # Prevent freezing of screen while dragging window
		pygame.quit()

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


if __name__ == '__main__':
	print "Starting video player"
	try:
		vidSource = sys.argv[1]
	except:
		print sys.stderr, "Please supply a video file"
		sys.exit(0)
	#vidSource = "e:/Movies/bbb_sunflower_1080p_30fps_normal.mp4"
	windowRes = (800, 600)
	myVideoPlayer = videoPlayer(windowRes,fullscreen = False)
	myVideoPlayer.load_video(vidSource)
	myVideoPlayer.play()
