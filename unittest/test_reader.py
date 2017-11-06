from unittest import TestCase
from pyDewesoft.DataReader import Reader
from os.path import dirname, abspath
from os import listdir
from dill import dump


class TestReader(TestCase):
    def test_read(self):
        reader = Reader()
        reader.read(dirname(__file__) + r'\..\resources\testdata\fieldtest_2017_09_21_092526.d7d')
        print(reader.data.Agregaat_weight)
        reader.save('data.dwp')
        del reader

        # def test_sequence_read(self):
        #     f_names = [dirname(__file__) + '\\..\\resources\\testdata\\' + x for x in listdir(dirname(__file__) + '\\..\\resources\\testdata\\') if x.endswith('.d7d')]
        #     reader = Reader()
        #     reader.sequence_read(filenames=f_names, fill_gaps=False)
        #     del reader
