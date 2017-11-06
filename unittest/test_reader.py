from unittest import TestCase
from pyDewesoft.DataReader import Reader
from os.path import dirname, abspath
import numpy as np
from os import listdir
from dill import dump

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

        # def test_sequence_read(self):
        #     f_names = [dirname(__file__) + '\\..\\resources\\testdata\\' + x for x in listdir(dirname(__file__) + '\\..\\resources\\testdata\\') if x.endswith('.d7d')]
        #     reader = Reader()
        #     reader.sequence_read(filenames=f_names, fill_gaps=False)
        #     del reader
