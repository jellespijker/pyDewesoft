# pyDewesoft module

Python module to work with Dewesoft files. 

Current capabilities:
* Reading native Dewesoft files (.d7d, .dxd, .d7z and .dxz)
* Appending multiple Dewesoft files in a single Python data object.
* Filling time gaps between multiple Dewesoft files, to create a continues time vector (useful when Dewesoft has error due to data lost)
* Data is stored in a Python object, where each channel is an attribute
* Time vectors are stored effectively for each channel. If a time vector is used for multiple channels it is only stored once.
* Saving to disk of the Python object is done with the highest compression rate

[Window installer for the lattest release](http://mti-gitlab.ihc.eu/generic-software/pyDewesoft/uploads/bcadd446380121fde7e30a88e6227037/pyDewesoft-1.0rc0.win-amd64.exe)

[Releases with windows installer](http://mti-gitlab.ihc.eu/generic-software/pyDewesoft/tags?utf8=%E2%9C%93&search=v)