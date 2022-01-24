import os
import unittest
import sys

from nanome.util import Logs

chem_interactions_dir = f'{os.getcwd()}/chem_interactions/'
sys.path.append(chem_interactions_dir)

test_directory = 'tests'
suite = unittest.TestLoader().discover(test_directory)

output = unittest.TextTestRunner(verbosity=1).run(suite)

if output.wasSuccessful():
    sys.exit(0)
else:
    sys.exit(1)
