from .DWDataReaderHeader import *
from ctypes import *
import _ctypes
import platform
from pint import UnitRegistry
from pint.errors import UndefinedUnitError
from numpy import zeros, append, where, diff
from os.path import dirname
import re
from dill import dump, load
import gzip

u = UnitRegistry(autoconvert_offset_to_baseunit=True)


class Data:
    r"""
    Data structure containing the exported channels. Each Data class contains atleast:

    * sample_rate
    * start_store_time
    * duration
    * time (all individual channel times are discarded and the first channel time is used through out)

    """

    def __init__(self):
        self.sample_rate = None
        self.start_store_time = None
        self.duration = None
        self.time = None

    @property
    def channel_names(self):
        return self.__dict__.keys()


class Reader:
    r"""
    The DWdataReader reads .d7d, .dxd, .d7z and .dxz files and exports them to a data structure as Reader.data. Each
    individual channel and/or variable in the Dewesoft file is extracted to an property in the Data object with the same
    name. All time channels linked to the individual channels are discarded and a single time property is set, which is taken
    from the first encountered channel. This could result in unexpected behavior if asynchronous capture was used in Dewesoft.
    If a unit for a channel/variable is specified in Dewesoft, The reader tries to exports that unit to a Pint unit.

    :param filename: The file name to import
    """

    def __init__(self, filename=None):
        self.filename = filename
        self.platform = platform.architecture()
        self.data = Data()

        if 'Win' not in self.platform[1]:
            raise NotImplementedError('Only the Windows operating system is supported at this stage!')
        if '64bit' in self.platform[0]:
            self._lib = cdll.LoadLibrary(dirname(__file__) + r'\resources\Lib\DWDataReaderLib64.dll')
        else:
            self._lib = cdll.LoadLibrary(dirname(__file__) + r'\resources\Lib\DWDataReaderLib.dll')

        if self._lib.DWInit() != DWStatus.DWSTAT_OK.value:
            if '64bit' in self.platform[0]:
                raise RuntimeError('Could not initialize DWDataReaderLib64.dll')
            else:
                raise RuntimeError('Could not initialize DWDataReaderLib.dll')
        if self.filename is not None:
            self.read(filename=filename)

    def sequence_read(self, filenames, correcttime=False):
        r"""
        Reads a sequence of Dewesoft files and stitches them together, the results are stored in the Reader.data object
        and can be saved using the Read.save() method.

        :param filenames: An iterable object containing the filenames
        :param correcttime: True if gaps in time be filled with NAN values at the same interval as the sampling rate and
        existing sample in the n+m file be discarded. In other words it creates an continiuous time vector.
        """
        for fname in filenames:
            self.read(fname)
        if correcttime:
            self._fill_gaps()

    def read(self, filename=None):
        r"""
        Reads a Dewesoft file, the results are stored in the Reader.data object and can be saved using the Read.save() method.

        :param filename: the file name
        """
        if filename is None:
            if self.filename is None:
                raise ValueError('Dewesoft filename not specified!')
            filename = self.filename
        fname = c_char_p(filename.encode())
        finfo = DWFileInfo(0, 0, 0)
        if self._lib.DWOpenDataFile(fname, addressof(finfo)) != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not open file: ' + filename)
        if self.data.sample_rate is None:
            self.data.sample_rate = finfo.sample_rate
        if self.data.start_store_time is None:
            self.data.start_store_time = finfo.start_store_time
        if self.data.duration is None:
            self.data.duration = finfo.duration
        else:
            self.data.duration += finfo.duration

        # get number of channels
        num = self._lib.DWGetChannelListCount()
        if num == -1:
            raise RuntimeError('Could not obtain number of channels!')

        # get channel list
        ch_list = (DWChannel * num)()
        if self._lib.DWGetChannelList(byref(ch_list)) != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not obtain the channels!')

        # get the data
        for i in range(0, num):
            attr = self._get_channel_name(ch_list, i)
            unit = self._get_unit(ch_list, i)
            data = self._get_data(ch_list, i, unit)
            if hasattr(self.data, attr):
                prev_data = getattr(self.data, attr)
                setattr(self.data, attr, append(prev_data, self.data))
            else:
                setattr(self.data, attr, data)

        # close the data file
        self._close_dewefile()

    def _close_dewefile(self):
        if self._lib.DWCloseDataFile() != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not close the Dewesoft file!')

    def _fill_gaps(self):
        diff_t = diff(self.time) - 1.5 / self.sample_rate
        time_gaps = where(diff_t > 0)
        for gap in time_gaps:
            # fill the gap with NAN in all data
            # fill the time with sample rate
            # add time difference to next time_gaps
            pass

    def _get_channel_name(self, ch_list, i):
        return str(ch_list[i].name)[2:-1]

    def _get_unit(self, ch_list, i):
        unitstr = str(ch_list[i].unit)[2:-1]
        unitstr = re.sub(r'\[|\]|\%', '', unitstr)
        try:
            unit = u.parse_units(unitstr)
        except UndefinedUnitError:
            unit = u['dimensionless']
        return unit

    def _get_channel_type(self, i):
        idx = c_int(i)
        max_len = c_int(INT_SIZE)
        buff = create_string_buffer(max_len.value)
        p_buff = cast(buff, POINTER(c_void_p))
        if self._lib.DWGetChannelProps(idx, c_int(DWChannelProps.DW_CH_TYPE.value), p_buff,
                                       byref(max_len)) != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not obtain channel properties!')
        return DWChannelType(cast(p_buff, POINTER(c_int)).contents.value)

    def _get_channel_data_type(self, i):
        idx = c_int(i)
        max_len = c_int(INT_SIZE)
        buff = create_string_buffer(max_len.value)
        p_buff = cast(buff, POINTER(c_void_p))
        if self._lib.DWGetChannelProps(idx, c_int(DWChannelProps.DW_DATA_TYPE.value), p_buff,
                                       byref(max_len)) != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not obtain channel data type!')
        return DWDataType(cast(p_buff, POINTER(c_int)).contents.value)

    def _get_no_samples(self, ch_list, i):
        dw_ch_index = self._get_channel_index(ch_list, i)
        sample_cnt = c_int()
        sample_cnt = self._lib.DWGetScaledSamplesCount(dw_ch_index)
        if sample_cnt < 0:
            raise RuntimeError('Could not obtain channel sample count!')
        return sample_cnt

    def _get_channel_index(self, ch_list, i):
        return c_int(ch_list[i].index)

    def _get_data(self, ch_list, i, unit):
        ch_type = self._get_channel_type(i)
        ch_data_type = self._get_channel_data_type(i)
        sample_cnt = self._get_no_samples(ch_list, i)
        dw_ch_index = self._get_channel_index(ch_list, i)
        data = create_string_buffer(DOUBLE_SIZE * sample_cnt * ch_list[i].array_size)
        time_stamp = create_string_buffer(DOUBLE_SIZE * sample_cnt)
        p_data = cast(data, POINTER(c_double))
        p_time_stamp = cast(time_stamp, POINTER(c_double))
        if self._lib.DWGetScaledSamples(dw_ch_index, c_int64(0), sample_cnt, p_data,
                                        p_time_stamp) != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not obtain channel data')
        data_array = zeros((sample_cnt, 1))
        if i != 0:
            for j in range(0, sample_cnt):
                data_array[j] = p_data[j]
            data_array *= unit
        else:
            time_array = zeros((sample_cnt, 1))
            for j in range(0, sample_cnt):
                time_array[j] = p_time_stamp[j]
                data_array[j] = p_data[j]
            if self.data.time is None:
                self.data.time = time_array * u['s']
            else:
                self.data.time = append(self.data.time, time_array)
            data_array *= unit
        return data_array

    def __del__(self):
        if self._lib.DWDeInit() != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not deconstruct the DWDataReaderLib!')

    def save(self, filename):
        r"""
        Saves the Reader.data object to a file, using a compression algorithm and dill serialization

        :param filename: the filename
        """
        with gzip.open(filename, 'wb') as handle:
            dump(self.data, handle, protocol=4)

    def load(self, filename):
        r"""
        Loads previous obtained data

        :param filename: the filename
        :return: a Data object
        """
        with gzip.open(filename, 'rb') as handle:
            data = load(filename)
        return data
