from .DWDataReaderHeader import *
from ctypes import *
import _ctypes
import platform
from pint import UnitRegistry
from pint.errors import UndefinedUnitError
from numpy import zeros, append, where, diff, ndarray, arange, insert, nan, empty, array, linspace, ones
from os.path import dirname
import re
from dill import dumps, loads, HIGHEST_PROTOCOL
import zlib
import logging

u = UnitRegistry(autoconvert_offset_to_baseunit=True)


class Time:
    r"""
    Class that stores the individual channel times. It stores only unique channel time arrays, mapping the channels.
    """

    def __init__(self):
        self._time_map = {}
        self._time = {}

    def __contains__(self, item):
        return item in self._time_map.keys()

    def __iter__(self):
        for tm_key, tm_value in self._time_map.items():
            yield (tm_key, self._time[tm_value] * u.s)
        return

    def __len__(self):
        return len(self._time_map)

    def __getitem__(self, item):
        return self._time[self._time_map[item]] * u.s

    def __setitem__(self, key, value):
        if key not in self._time_map.keys():
            self.append(key, value)
        else:
            idx, contains = self._contains_time(value)
            if contains:
                self._time_map[key] = idx
            else:
                self._time_map[key] = len(self._time)
                self._time[self._time_map[key]] = value

    def __delitem__(self, key):
        time_key = self._time_map[key]
        cnt = list(self._time.values()).count(time_key)
        del self._time_map[key]
        if cnt == 1:
            del self._time[time_key]

    def append(self, channel_name, time):
        idx, contains = self._contains_time(time)
        if contains:
            self._time_map[channel_name] = idx
        else:
            self._time_map[channel_name] = len(self._time)
            self._time[self._time_map[channel_name]] = time

    def _contains_time(self, item):
        contains = True
        for k, t in self._time.items():
            if len(t) == len(item):
                if len(t) > 10:
                    check_idx = linspace(start=0, stop=int(len(t) / 2), num=5, dtype=int)
                    check_idx = append(check_idx, -check_idx)
                elif len(t) > 0:
                    if (t == item)[0, 0]:
                        return k, True
                    else:
                        contains = False
                        continue
                else:
                    return k, True

                for idx in check_idx:
                    if t[idx] != item[idx]:
                        contains = False
                        break
                if contains:
                    return k, True
        return '', False


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
        self.time = Time()
        self.offset_channel_idx = len(self.channel_names)

    @property
    def channel_names(self):
        channels = list(self.__dict__.keys())
        if 'offset_channel_idx' in channels:
            channels.remove('offset_channel_idx')
            channels.remove('time')
        return channels


class Reader:
    r"""
    The DWdataReader reads .d7d, .dxd, .d7z and .dxz files and exports them to a data structure as Reader.data. Each
    individual channel and/or variable in the Dewesoft file is extracted to an property in the Data object with the same
    name. All time channels linked to the individual channels are discarded and a single time property is set, which is
    taken from the first encountered channel. This could result in unexpected behavior if asynchronous capture was used
    in Dewesoft. If a unit for a channel/variable is specified in Dewesoft, The reader tries to exports that unit to a
    Pint unit.

    :param filename: The file name to import
    """

    def __init__(self, filename=None):
        logging.info('Reader initialized')
        self.filename = filename
        self.platform = platform.architecture()
        logging.info('{} platform used'.format(self.platform))
        self.data = Data()

        if 'Win' not in self.platform[1]:
            raise NotImplementedError('Only the Windows operating system is supported at this stage!')
        if '64bit' in self.platform[0]:
            self._lib = cdll.LoadLibrary(dirname(__file__) + r'\resources\DWDataReaderLib64.dll')
        else:
            self._lib = cdll.LoadLibrary(dirname(__file__) + r'\resources\DWDataReaderLib.dll')

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
        Reads a Dewesoft file, the results are stored in the Reader.data object and can be saved using the Read.save()
        method.

        :param filename: the file name
        """
        if filename is None:
            if self.filename is None:
                raise ValueError('Dewesoft filename not specified!')
            filename = self.filename
        logging.info('Reading file: {}'.format(filename))
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
            attr = self._generate_valid_attr_name(attr)
            unit = self._get_unit(ch_list, i)
            time, data = self._get_data(ch_list, i, unit)
            if hasattr(self.data, attr):
                prev_data = getattr(self.data, attr)
                setattr(self.data, attr, append(prev_data, data))
                prev_time = self.data.time[attr]
                self.data.time[attr] = append(prev_time, time)
                logging.info('Imported and appended {}'.format(attr))
            else:
                setattr(self.data, attr, data)
                self.data.time[attr] = time
                logging.info('Imported {}'.format(attr))

        # close the data file
        self._close_dewefile()

    def _close_dewefile(self):
        if self._lib.DWCloseDataFile() != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not close the Dewesoft file!')
        logging.info('Closing Dewefile')

    def _fill_gaps(self):
        diff_t = diff(self.data.time) - 1.5 / self.data.sample_rate
        time_gaps = where(diff_t > 0)
        for gap in time_gaps[0]:
            start_time = self.data.time[gap]
            end_time = self.data.time[gap + 1]
            dt = 1 / self.data.sample_rate
            fill_time = arange(start_time, end_time, dt)
            for chan_name in self.data.channel_names[self.data.offset_channel_idx:]:
                chan = getattr(self.data, chan_name)
                if isinstance(chan, ndarray) and len(chan) == len(self.data.time):
                    try:
                        shape = (len(fill_time), chan.shape[1])
                    except IndexError:
                        shape = fill_time.shape

                    nan_data = empty(shape)
                    nan_data[:] = nan
                    setattr(self.data, chan_name, insert(chan, gap + 1, nan_data))
            self.data.time = insert(self.data.time, gap + 1, fill_time)

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
        time_array = zeros((sample_cnt, 1))
        for j in range(0, sample_cnt):
            time_array[j] = p_time_stamp[j]
            data_array[j] = p_data[j]
        data_array *= unit
        return time_array, data_array

    def _generate_valid_attr_name(self, attr):
        valid_attr = re.sub(r'[^a-zA-Z0-9_][^a-zA-Z0-9_]*', '_', attr)
        return 'ch_' + valid_attr

    def __del__(self):
        if self._lib.DWDeInit() != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not deconstruct the DWDataReaderLib!')

    def save(self, filename: str):
        r"""
        Saves the Reader.data object to a file, using a compression algorithm and dill serialization

        :param filename: the filename, if no extension is given .pyDW is used.
        """
        if '.' not in filename:
            filename += '.pyDW'
        with open(filename, 'wb') as handle:
            handle.write(zlib.compress(dumps(self.data, protocol=HIGHEST_PROTOCOL), level=9))

    def load(self, filename):
        r"""
        Loads previous obtained data

        :param filename: the filename, if no extension is given .pyDW is used.
        :return: a Data object
        """
        if '.' not in filename:
            filename += '.pyDW'
        with open(filename, 'rb') as handle:
            data = loads(zlib.decompress(handle.read()))
        return data
