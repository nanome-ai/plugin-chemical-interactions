import os
import unittest
import sys

from nanome.util import Logs

sys.path.append(f'{os.getcwd()}/chem_interactions/')

test_directory = 'chem_interactions/tests'
Logs._set_verbose(True)
suite = unittest.TestLoader().discover(test_directory)
unittest.TextTestRunner(verbosity=1).run(suite)
