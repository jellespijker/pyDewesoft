from .DWDataReaderHeader import *
from ctypes import *
import _ctypes
import platform
from pint import UnitRegistry, set_application_registry
from pint.errors import UndefinedUnitError
from numpy import zeros, append, where, diff, ndarray, arange, insert, nan, empty, array, linspace, histogram, \
    max as np_max, where, in1d
from os.path import dirname
import re
from dill import dumps, loads, HIGHEST_PROTOCOL
import zlib
from .logger import logged

u = UnitRegistry(autoconvert_offset_to_baseunit=True)
set_application_registry(u)
if hasattr(u, 'setup_matplotlib'):
    u.setup_matplotlib()

__all__ = ['Data', 'Reader', 'dewe_reader']


@logged
class Time:
    r"""
    Class that stores the individual channel times. It stores only unique channel time arrays, mapping the channels.
    """

    def __init__(self):
        self._time_map = {}
        self._time = {}
        self._main_time = None
        self.sample_rate = None
        self._idx = 0

    def __contains__(self, item):
        return item in self._time_map.keys()

    def __iter__(self):
        for tm_key, tm_value in self._time_map.items():
            yield (tm_key, self._time[tm_value] * u.s)
        return

    def __len__(self):
        return len(self._time_map)

    def __getitem__(self, item):
        if item == 'main':
            if self.main_time is None:
                try:
                    self._get_main_time_idx()
                except RuntimeError:
                    self.main_time = max(self._time, key=lambda k: len(set(self._time[k])))
            return self._time[self.main_time] * u.s
        else:
            return self._time[self._time_map[item]] * u.s

    def __setitem__(self, key, value):
        if key == 'main':
            if self.main_time is None:
                try:
                    self._get_main_time_idx()
                except RuntimeError:
                    self.main_time = max(self._time, key=lambda k: len(set(self._time[k])))
            self._time[self.main_time] = value
            return
        idx, contains = self._contains_time(value)
        if contains:
            self._time_map[key] = idx
        else:
            self._append_new_time(key, value)

    def __delitem__(self, key):
        time_key = self._time_map[key]
        cnt = list(self._time.values()).count(time_key)
        del self._time_map[key]
        if cnt == 1:
            del self._time[time_key]

    def append(self, channel_name, time):
        r"""
        Add new time data for a channel, if the time vector exists, it maps the channel to the time line

        :param channel_name: The channel name
        :param time: The time vector to append
        """
        if channel_name == 'main':
            if self.main_time is None:
                try:
                    self._get_main_time_idx()
                except RuntimeError:
                    self.main_time = max(self._time, key=lambda k: len(set(self._time[k])))
            self._time[self.main_time] = time
            return
        idx, contains = self._contains_time(time)
        if contains:
            self._time_map[channel_name] = idx
        else:
            self._append_new_time(channel_name, time)

    def filter_existing(self, channel_name, time):
        return where(in1d(time, self[channel_name]) == False)[0]

    def clean(self):
        r"""
        Cleans unused timelines
        """
        removed_cnt = []
        self.main_time = None
        for k in self._time.keys():
            if k not in self._time_map.values():
                removed_cnt.append(k)
        for k in removed_cnt:
            del self._time[k]

    @property
    def main_time(self):
        r"""
        The index of the main time line. end user stay away
        """
        return self._main_time

    @main_time.setter
    def main_time(self, value):
        self._main_time = value

    @property
    def dt(self):
        r"""
        The DT time step or the inverse of the sample rate
        """
        return 1 / self.sample_rate * u.s

    def _append_new_time(self, key, value):
        self._time_map[key] = self._idx
        self._time[self._time_map[key]] = value
        self.main_time = None
        self._idx += 1

    def _get_main_time_idx(self):
        if self.sample_rate is None:
            error_msg = 'Sample rate not set!'
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        for k, t in self._time.items():
            if len(t) < 2:
                continue
            diff_t = diff(t)
            hist = histogram(diff_t)
            dt = round(hist[1][where(hist[0] == np_max(hist[0]))][0], 4) * u.s
            if dt == self.dt:
                self._main_time = k
                self.logger.info(r'Main time index is: {}'.format(k))
                return
        error_msg = r'No main time index found!'
        self.logger.error(error_msg)
        raise RuntimeError(error_msg)

    def _contains_time(self, item):
        contains = True
        for k, t in self._time.items():
            if len(t) == len(item):
                if len(t) > 10:
                    check_idx = linspace(start=0, stop=int(len(t) / 2), num=5, dtype=int)
                    check_idx = append(check_idx, -check_idx)
                    check_idx[6] = -1
                elif len(t) > 0:
                    if (t == item)[0]:
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


@logged
class Data:
    r"""
    Data structure containing the exported channels. Each Data class contains at least:

    * sample_rate
    * start_store_time
    * duration
    * time for each channel
    * Individually exported channels attributes with documentation and units if these are specified in Dewesoft

    """

    def __init__(self):
        self.time = Time()
        self.sample_rate = None
        self.start_store_time = None
        self.duration = None
        self.offset_channel_idx = len(self.channel_names)
        self.version = '1.0'

    def __contains__(self, item):
        return item in self.channel_names

    def __iter__(self):
        for chan in self.channel_names:
            yield (chan, self[chan])
        return

    def __len__(self):
        return len(self.channel_names)

    def __getitem__(self, item):
        if item in self.time:
            return self.time[item], getattr(self, item)
        else:
            return None, array(getattr(self, item))

    def __setitem__(self, key, value):
        raise NotImplementedError

    def __delitem__(self, key):
        raise NotImplementedError

    @property
    def sample_rate(self):
        r"""
        The Dewesoft specified sample rate
        :return:
        """
        return self.time.sample_rate

    @sample_rate.setter
    def sample_rate(self, value):
        self.time.sample_rate = value

    @property
    def channel_names(self):
        r"""
        A list of imported channels
        :return:
        """
        channels = list(self.__dict__.keys())
        if 'offset_channel_idx' in channels:
            channels.remove('offset_channel_idx')
            channels.remove('time')
        return channels


@logged
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
        self.logger.info('Reader initialized')
        self.filename = filename
        self.platform = platform.architecture()
        self.logger.info('{} platform used'.format(self.platform))
        self.data = Data()
        self.compression_rate = 5

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
        finfo = self._open_file(filename)
        self._get_file_info(finfo)
        num = self._get_nof_channels()
        ch_list = self._get_channel_list(num)
        # get the data

        for i in range(0, num):
            attr = self._get_channel_name(ch_list, i)
            unit = self._get_unit(ch_list, i)
            time, data = self._get_data(ch_list, i, unit)
            desc = self._get_channel_desc(ch_list, i, attr, data)
            if hasattr(self.data, attr):
                prev_data = getattr(self.data, attr)
                setattr(self.data, attr, append(prev_data, data))
                prev_time = self.data.time[attr]
                self.data.time.append(attr, append(prev_time, time))
                self.logger.info('Imported and appended {}'.format(attr))
            else:
                setattr(self.data, attr, data)
                setattr(getattr(self.data, attr), '__doc__', desc)
                self.data.time[attr] = time
                self.logger.info('Imported {}'.format(attr))

        self.data.time.clean()
        # close the data file
        self._close_dewefile()

    def _open_file(self, filename):
        if filename is None:
            if self.filename is None:
                raise ValueError('Dewesoft filename not specified!')
            filename = self.filename
        self.logger.info('Reading file: {}'.format(filename))
        fname = c_char_p(filename.encode())
        finfo = DWFileInfo(0, 0, 0)
        if self._lib.DWOpenDataFile(fname, addressof(finfo)) != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not open file: ' + filename)
        return finfo

    def _get_file_info(self, finfo):
        if self.data.sample_rate is None:
            self.data.sample_rate = finfo.sample_rate
        if self.data.start_store_time is None:
            self.data.start_store_time = finfo.start_store_time
        if self.data.duration is None:
            self.data.duration = finfo.duration
        else:
            self.data.duration += finfo.duration

    def _get_nof_channels(self):
        num = self._lib.DWGetChannelListCount()
        if num == -1:
            raise RuntimeError('Could not obtain number of channels!')

        return num

    def _get_channel_list(self, num):
        ch_list = (DWChannel * num)()
        if self._lib.DWGetChannelList(byref(ch_list)) != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not obtain the channels!')

        return ch_list

    def _close_dewefile(self):
        if self._lib.DWCloseDataFile() != DWStatus.DWSTAT_OK.value:
            raise RuntimeError('Could not close the Dewesoft file!')
        self.logger.info('Closing Dewefile')

    def _fill_gaps(self):
        diff_t = diff(self.data.time['main']) - 1.5 / self.data.sample_rate
        idx = where(diff_t > 0)[0]
        self.logger.debug(r'The following indexes found {}'.format(idx))
        for gap in idx:
            start_time = self.data.time['main'][gap]
            end_time = self.data.time['main'][gap + 1]
            fill_time = arange(start_time.m, end_time.m, self.data.time.dt.m) * u.s
            self.logger.debug(r'Filling time: {}'.format(fill_time))
            for chan_name in self.data.channel_names[self.data.offset_channel_idx:]:
                chan = getattr(self.data, chan_name)
                if isinstance(chan, ndarray) and len(chan) == len(self.data.time['main']):
                    try:
                        shape = (len(fill_time), chan.shape[1])
                    except IndexError:
                        shape = fill_time.shape

                    nan_data = empty(shape)
                    nan_data[:] = nan
                    setattr(self.data, chan_name, insert(chan, gap + 1, nan_data))
            self.data.time['main'] = insert(self.data.time['main'].m, gap + 1, fill_time.m)

    def _get_channel_name(self, ch_list, i):
        attr = str(ch_list[i].name)[2:-1]
        valid_attr = re.sub(r'[^a-zA-Z0-9_][^a-zA-Z0-9_]*', '_', attr)
        return 'ch_' + valid_attr

    def _get_channel_desc(self, ch_list, i, attr, data):
        dw_desc = 'states: \"{}\"'.format(str(ch_list[i].description)[2:-1])
        if len(dw_desc[10:]) == 0:
            dw_desc = 'is empty'
        desc = ('{} is an imported Dewesoft channel consisting of an {} with a {} unit. The channel description {}'
                ).format(attr[3:], type(data.magnitude), str(data.units), dw_desc)
        return desc

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
        data_array = zeros((sample_cnt,))
        time_array = zeros((sample_cnt,))
        for j in range(0, sample_cnt):
            time_array[j] = p_time_stamp[j]
            data_array[j] = p_data[j]
        data_array *= unit
        return time_array, data_array

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
        self.logger.info('Saving file {}'.format(filename))
        with open(filename, 'wb') as handle:
            handle.write(zlib.compress(dumps(self.data, protocol=HIGHEST_PROTOCOL), level=self.compression_rate))
        self.logger.info('Saved file {}'.format(filename))

    def load(self, filename):
        r"""
        Loads previous obtained data

        :param filename: the filename, if no extension is given .pyDW is used.
        :return: a Data object
        """
        if '.' not in filename:
            filename += '.pyDW'
        self.logger.info('Loading file {}'.format(filename))
        with open(filename, 'rb') as handle:
            data: Data = loads(zlib.decompress(handle.read()))
        self.logger.info('File {} loaded'.format(filename))
        self.logger.info('The following channels are available: {}'.format(data.channel_names))
        return data

    @property
    def compression_rate(self):
        r"""
        Compression rate used when storing the data object to disk. A value between 1...9. Standard value is 5
        :return:
        """
        return self._compression_rate

    @compression_rate.setter
    def compression_rate(self, value):
        if isinstance(value, int) and value >= 1 and value <= 9:
            self._compression_rate = value
            self.logger.info(r'Compression is set to : {}'.format(value))
        else:
            raise ValueError


def dewe_reader(filename):
    reader = Reader(filename)
    return reader.data
