import os
import pickle
from unittest import TestCase, mock

from nanome.api.structure import Complex

from chem_interactions.ChemicalInteractions import ChemicalInteractions

fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')


mocked_interactions_url = "https://fake-arpeggio-service.com"


class MockRequestResponse:
    def __init__(self, content_data, status_code):
        self.content = content_data
        self.status_code = status_code



@mock.patch.dict(os.environ, {"INTERACTIONS_URL": mocked_interactions_url})
class ChemInteractionsTestCase(TestCase):

    def setUp(self):
        with open(f'{fixtures_dir}/1a9l.pickle', 'rb') as f:
            self.complex1 = pickle.load(f)

        with open(f'{fixtures_dir}/1fsv.pickle', 'rb') as f:
            self.complex2 = pickle.load(f)

        self.plugin = ChemicalInteractions()
        self.plugin.start()

    def test_setup(self):
        self.assertTrue(self.complex1, Complex)
        self.assertTrue(self.plugin, ChemicalInteractions)

    @mock.patch('requests.post', return_value=MockRequestResponse(b"Doesn't really matter what data is returned", 200))
    def test_clean_complex(self, mock_post):
        self.plugin.start()
        cleaned_file = self.plugin.clean_complex(self.complex1)
        self.assertEqual(open(cleaned_file.name).read(), "Doesn't really matter what data is returned")
        pass
