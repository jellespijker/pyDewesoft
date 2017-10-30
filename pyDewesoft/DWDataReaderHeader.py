
#----------------------------------------------------------------------------------------------------------------
# DWDataReader "header" for Python
#----------------------------------------------------------------------------------------------------------------
# Author: Dewesoft
# Notes:
#   - requires DWDataReaderLib.dll 4.0.0.0 or later
#   - tested with Python 3.4
#----------------------------------------------------------------------------------------------------------------

from ctypes import *
from enum import Enum
import sys

INT_SIZE = 4 # size of integer
DOUBLE_SIZE = 8 # size of double

class DWStatus(Enum):
    DWSTAT_OK = 0
    DWSTAT_ERROR = 1
    DWSTAT_ERROR_FILE_CANNOT_OPEN = 2
    DWSTAT_ERROR_FILE_ALREADY_IN_USE = 3
    DWSTAT_ERROR_FILE_CORRUPT = 4
    DWSTAT_ERROR_NO_MEMORY_ALLOC = 5
    DWSTAT_ERROR_CREATE_DEST_FILE = 6
    DWSTAT_ERROR_EXTRACTING_FILE = 7
    DWSTAT_ERROR_CANNOT_OPEN_EXTRACTED_FILE = 8

class DWChannelProps(Enum):
	DW_DATA_TYPE = 0
	DW_DATA_TYPE_LEN_BYTES = 1
	DW_CH_INDEX = 2
	DW_CH_INDEX_LEN = 3
	DW_CH_TYPE = 4
	DW_CH_SCALE = 5
	DW_CH_OFFSET = 6
	DW_CH_XML = 7
	DW_CH_XML_LEN = 8
	DW_CH_XMLPROPS = 9
	DW_CH_XMLPROPS_LEN = 10

class DWChannelType(Enum):
	DW_CH_TYPE_SYNC = 0 # sync
	DW_CH_TYPE_ASYNC = 1 # async
	DW_CH_TYPE_SV = 2 # single value
	
class DWFileInfo(Structure):
    _fields_ =\
    [
        ("sample_rate", c_double),
        ("start_store_time", c_double),
        ("duration", c_double)
    ]
	
class DWChannel(Structure):
    _fields_ =\
    [
        ("index", c_int),
        ("name", c_char * 100),
        ("unit", c_char * 20),
        ("description", c_char * 200),
        ("color", c_uint),
        ("array_size", c_int),
        ("data_type", c_int)
    ]

class DWEvent(Structure):
	_fields_ =\
	[
        ("event_type", c_int),
		("time_stamp", c_double),
        ("event_text", c_char * 200)
	]
	
class DWReducedValue(Structure):
	_fields_ =\
	[
		("time_stamp", c_double),
        ("ave", c_double),
        ("min", c_double),
        ("max", c_double),
        ("rms", c_double)
	]
	
class DWArrayInfo(Structure):
	_fields_ =\
	[
        ("index", c_int),
        ("name", c_char * 100),
        ("unit", c_char * 20),
        ("size", c_int)
	]
	
class DWCANPortData(Structure):
	_fields_ =\
	[
        ("arb_id", c_ulong),
        ("data", c_char * 8)
	]
	
class DWComplex(Structure):
	_fields_ =\
	[
        ("re", c_double),
        ("im", c_double)
	]
	
class DWEventType(Enum):
	etStart = 1
	etStop = 2
	etTrigger = 3
	etVStart = 11
	etVStop = 12
	etKeyboard = 20
	etNotice = 21
	etVoice = 22
	etModule = 24	
	
class DWStoreType(Enum):
	ST_ALWAYS_FAST = 0
	ST_ALWAYS_SLOW = 1
	ST_FAST_ON_TRIGGER = 2
	ST_FAST_ON_TRIGGER_SLOW_OTH = 3
	
class DWDataType(Enum):
	dtByte = 0
	dtShortInt = 1
	dtSmallInt = 2
	dtWord = 3
	dtInteger = 4
	dtSingle = 5
	dtInt64 = 6
	dtDouble = 7
	dtLongword = 8
	dtComplexSingle = 9
	dtComplexDouble = 10
	dtText = 11
	dtBinary = 12
	dtCANPortData = 13

def DWRaiseError(err_str):
    print(err_str)
    sys.exit(-1)
