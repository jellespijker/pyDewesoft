from .DWDataReaderHeader import *
from ctypes import *
import _ctypes
import platform
from pint import UnitRegistry
from pint.errors import UndefinedUnitError
from numpy import array, zeros, append
from os.path import dirname
import re

u = UnitRegistry(autoconvert_offset_to_baseunit=True)


class Reader:
    def __init__(self, filename=None):
        self.filename = filename
        self.sample_rate = None
        self.start_store_time = None
        self.duration = None
        self.time = None
        self.platform = platform.architecture()
        if 'Win' not in self.platform[1]:
            raise NotImplementedError('Only the Windows operating system is supported at this stage!')
        if '64bit' in self.platform[0]:
            self._lib = cdll.LoadLibrary(dirname(__file__) + r'\..\resources\Lib\DWDataReaderLib64.dll')
        else:
            self._lib = cdll.LoadLibrary(dirname(__file__) + 'DWDataReaderLib.dll')

        if self._lib.DWInit() != DWStatus.DWSTAT_OK.value:
            if '64bit' in self.platform[0]:
                raise RuntimeError('Could not initialize DWDataReaderLib64.dll')
            else:
                raise RuntimeError('Could not initialize DWDataReaderLib.dll')
        if self.filename is not None:
            self.read(filename=filename)

    def sequence_read(self, filenames, fill_gaps):
        for fname in filenames:
            self.read(fname)
        if fill_gaps:
            self._fill_gaps()

    def read(self, filename=None):
        if filename is None:
            if self.filename is None:
                raise ValueError('Dewesoft filename not specified!')
            filename = self.filename
        fname = c_char_p(filename.encode())
        finfo = DWFileInfo(0, 0, 0)
        if self._lib.DWOpenDataFile(fname, addressof(finfo)) != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not open file: ' + filename)
        if self.sample_rate is None:
            self.sample_rate = finfo.sample_rate
        if self.start_store_time is None:
            self.start_store_time = finfo.start_store_time
        if self.duration is None:
            self.duration = finfo.duration
        else:
            self.duration += finfo.duration

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
            if hasattr(self, attr):
                prev_data = getattr(self, attr)
                setattr(self, attr, append(prev_data, data))
            else:
                setattr(self, attr, data)

        # close the data file
        self._close_dewefile()

    def _close_dewefile(self):
        if self._lib.DWCloseDataFile() != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not close the Dewesoft file!')

    def _fill_gaps(self):
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
            if self.time is None:
                self.time = time_array * u['s']
            else:
                self.time = append(self.time, time_array)
            data_array *= unit
        return data_array

    def __del__(self):
        if self._lib.DWDeInit() != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not deconstruct the DWDataReaderLib!')
