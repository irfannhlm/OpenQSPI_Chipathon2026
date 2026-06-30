/*
 * COPYRIGHT (c) 2017 MACRONIX INTERNATIONAL CO., LTD
 * MX25-series verilog behavioral model
 *
 * This README file introduces the verilog of MX25-series behavioral model.
 *
 * Filename: README.txt
 * Issued Date: February 23, 2017
 *
 * Any questions or suggestions, please send emails to:
 *
 *     flash_model@mxic.com.tw
 */

 * Notice: All source files are saved as UNIX text format.

This README file describes MXIC MX25-series verilog behavioral
model. It consists of several sections as follows:

1. Overview
2. Files
3. Usage

1. Overview
---------------------------------
The MX25-series verilog behavioral model is able to assist you to integrate
MX25-series flash product at early simulation stage. There are helpful tips
and notes in this READEME file. Please read this file before applying this
behavioral model.

2. Files
---------------------------------
The following files will be available after extracting the zipped file
(or other compression format):

  MX25XXXX\
    |- README.txt
    |- MX25XXXX.v


The naming rule of MX25-series verilog behavioral model is as follows:

  MX25XXXX.v:
      ---- -
       |   |--> v. Verilog source code.
       |
       |------> Flash's part name. e.g., MX25L1605D.

3. Usage
---------------------------------
The MX25-series behavioral model can be applied directly at the simulation
stage. Please connect correct wires to top module of this model according to
flash datasheet. This is not a synthesizable verilog code but for functional
simulation only. Please be aware of the followings:

a. The model can load initial flash data from a file by parameter definition.
   Users can change File_Name, File_Name_Secu or File_Name_SFDP definition with
   initial data's file name.
   Default file name is "none" and initial flash data is "FF".

   for normal array, initial data:
   `define  File_Name = "xxx";

   for Security array, initial data:
   `define  File_Name_Secu = "xxx";

   for SFDP array, initial data:
   `define  File_Name_SFDP = "xxx";

   where xxx: initial flash data file name, default is "none".

   For example: `define File_Name_SFDP	"MX25R6435FM2IL0_V6.sfdp"
   to initial the SFDP data from file MX25R6435FM2IL0_V6.sfdp.

b. Note that the behavioral model needs to wait for power setup time, tVSL.
   After tVSL time, chip can be fully accessible. If tPUW has defined, read
   instruction and write instruction can be accepted by flash after tVSL and
   tPUW time. The tPUW is longer than tVSL.

   tPUW is not defined:

      |     |---------tVSL---------|
      |____________________________|
      |                            |
   Power on              Read/Write enable


   tPUW is defined:

      |  |----------tPUW------------|
      |     |--tVSL--|              |
      |_____________________________|
      |              |              |
   Power on     Read enable    Write enable

c. More than one value (min. typ. max. value) is defined for some AC parameters
   in the datasheet. But only one of them is selected in the behavioral model,
   e.g. program and erase cycle time is the typical value. For detailed
   information of the parameters, please refer to the datasheet and feel free
   to contact Macronix.

