# gds4all

Command line GDS parser for 2010 and prior Hyundai vehicles.

It parses and extracts information on vehicle modules. 

Information includes connection payloads and paremeters, DTCs the module can report, data that can be read, actuation tests, and additional functions a module supports.

Basic communication has been implemented for reading CAN module DTCs from Linux. Support for K-Line modules and Windows is anticipated in future.

This project is supported by [OpenGK.org](https://opengk.org)

## Installation

Clone the repository

`git clone https://github.com/OpenGK-org/gds4all.git`

Install Python 3.10 for your specific operating system
https://www.python.org/downloads/release/python-31020/

Install required packages

`python3 -m pip install requirements.txt`

Confirm that no errors occurred.

## Usage

### Parse GDS definitions
Run `python3 gds4all.py` and follow the interactive selection.

### Scan DTCs
Currently a Linux operating system is assumed. Connect a CANbus adapter to your computer and vehicle, then run `scan_dtcs.py`. 

Any DTCs will be output to the console, including manufacturer specific ones.

### Parameters
-i --interactive-select Prefill selections with indices
-k --kia Use KIA vehicles
--interface CAN interface name (default: can0)