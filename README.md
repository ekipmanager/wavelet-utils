# wavelet-utils
Communication tools for Wavelet devices

This utility is to get **raw** data from Wavelet devices using python.

## Set Up
Use `python setup develop` to install the Cython packages

## Dependencies
- [Pygattlib](https://bitbucket.org/OscarAcena/pygattlib)
- [PyPrind](https://github.com/rasbt/pyprind)

## Usage
### Show a list of bluetooth devices nearby
`sudo python wed_tool --list`
### Blink device(s)
`sudo python wed_tool --blink --devices [MAC ADDRESS(es)]`
### Download from device(s)
`sudo python wed_tool --download --devices [MAC ADDRESS(es)]`
### Actively look for devices in the list and download them 
`sudo python wed_tool --start [yaml config file]`

The current options in the yaml are:

 - `max_process`: maximum number of processes to run simultaneously 
 - `devices`: list of device mac addresses to connect to 
 - `raw`: if the data should be transferred in raw format or compressed format 
 - `log_dir`: directory to save the log files to 
 - `data_dir`: directory to save the  data files too  
 - `data_prefix`: file name prefix used for data files
 - `battery_warn`: Minimum battery level to warn in the log file 
 - `min_logs`: Minimum logs in a device before initiating a download

### Additional options
Please use `python wed_tools --help` for list of all commands.