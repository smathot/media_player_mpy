# Import Python 3 compatibility functions
from libopensesame.py3compat import *
# Import the required modules.
from libopensesame import debug
from libopensesame.item import item
from libqtopensesame.items.qtautoplugin import qtautoplugin

class media_player_mpy(item):

	description = u'Plug-in description'

	def reset(self):
		# Set default experimental variables and values
		self.var.my_line_edit_var = u'some default'
		self.var.my_checkbox_var = u'some default'
		# Debugging output is only visible when OpenSesame is started with the
		# --debug argument.
		debug.msg(u'media_player_mpy has been initialized!')

	def prepare(self):

		# Call parent functions.
		item.prepare(self)
		# Prepare your plug-in here.

	def run(self):

		# Record the timestamp of the plug-in execution.
		self.set_item_onset()
		# Run your plug-in here.

class qtmy_plugin(my_plugin, qtautoplugin):

	def __init__(self, name, experiment, script=None):

		# Call parent constructors.
		media_player_mpy.__init__(self, name, experiment, script)
		qtautoplugin.__init__(self, __file__)

