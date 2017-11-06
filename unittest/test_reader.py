from unittest import TestCase
from pyDewesoft.DataReader import Reader
from os.path import dirname
import numpy as np
from os import listdir

base_test_dir = dirname(__file__) + r'/../pyDewesoft/resources/testdata/'

class TestReader(TestCase):
    def test_read(self):
        reader = Reader()
        reader.read(base_test_dir + 'data_01.dxd')
        expected_result = reader.load(base_test_dir + 'data_01.pyDW')
        self.assertEqual(reader.data.channel_names, expected_result.channel_names)
        for channel in expected_result.channel_names:
            np.testing.assert_array_equal(getattr(reader.data, channel), getattr(expected_result, channel))
        del reader

    def test_sequence_read_nocorrection(self):
        f_names = [base_test_dir + x for x in listdir(base_test_dir) if x.endswith('.dxd')]
        reader = Reader()
        reader.sequence_read(filenames=f_names, correcttime=False)
        expected_result = reader.load(base_test_dir + 'data_01_02_nocorrection.pyDW')
        self.assertEqual(reader.data.channel_names, expected_result.channel_names)
        for channel in expected_result.channel_names:
            np.testing.assert_array_equal(getattr(reader.data, channel), getattr(expected_result, channel))
        del reader
