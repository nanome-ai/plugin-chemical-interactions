import os
import unittest
import sys

from nanome.util import Logs

chem_interactions_dir = f'{os.getcwd()}/chem_interactions/'
sys.path.append(chem_interactions_dir)

test_directory = 'tests'
Logs._set_verbose(True)
suite = unittest.TestLoader().discover(test_directory)
unittest.TextTestRunner(verbosity=1).run(suite)
