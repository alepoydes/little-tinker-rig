# Adapted from Pybricks Projects (MIT); see LICENSE.txt and catalog.json.
from inventor_51515_gelo import Gelo

gelo = Gelo()

# Normally, we don't call methods with
# double-underscores directly, but this
# is an exceptional case!
gelo.__enter__()

# A KeyboardInterrupt will stop the
# program and start the interactive
# prompt. You can also trigger this
# in any running program by pressing
# CTRL+C in the terminal.
raise KeyboardInterrupt
