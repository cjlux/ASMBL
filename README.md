<img src="resources/N-Fab/Asmbl_banner.jpg">

# Overview

This code is designed to create a gcode file suitable for Additive & Subtractive Manufacturing By Layer (N-Fab).

## What is N-Fab? 

N-Fab is a manufacturing technique which combines FDM 3D printing with traditional milling. 

The additive and subtractive tools are alternated throughout the print so that milling of otherwise impossible to reach features is now possible. 

### Useful Links

[E3D Toolchanger Milling Tool - Thingiverse](https://www.thingiverse.com/thing:4206827)

https://e3d-online.com/blogs/news/N-Fab

## What does the repo do? 

Historically, combining an additive and subtractive gcode file has needed to be done manually. This is an arduous process that is only realistically feasible for simple shapes. 

This repo automatically merges a milling gcode file into a FDM gcode file; so that each milling segment is merged only after the part has been printed to the required height. 
This merging is also compatible with non-planar milling operations that occur over a range of print layers (such as as chamfers or fillets), allowing the staircase effect typically found in FDM parts to be removed from your print. . 

## How it can be used? 

There are 2 main ways this repo can be used.

- As a standalone program that takes 2 input files
  - An additive`.gcode` file from Simplify3D using the `N-Fab.factory` file to get the appropriate settings.
  - A subtractive `.gcode` file from Fusion360.
  - These files require specific setup for this program to work
- As a **Fusion 360 add-in** where the **ENTIRE** workflow from designing the part to getting the merged gcode is in Fusion 360
  - This means no handling dirty STL files!!!

The Fusion 360 add-in is the recommended option however the slicer is new and not widely adopted yet. Therefore, support for Simplify3D is present. The 2 slicers create mostly compatible gcode files. Until further notice, support for both programs will exist.

![Fusion add-in demo](docs/images/asmbl_demo.gif)

For the standalone program, download the latest release for the `N-Fab.exe`, an example `config.json`, and the Simplify3D factory file.

<br>
<br>
<br>

# Contents

- [Overview](#overview)
- [Contents](#contents)
- [Installation](#installation)
  - [Fusion 360 Add-in](#fusion-360-add-in)
  - [Fusion360 Design Workspace](#fusion360-design-workspace)
  - [Setting up the code for standalone use (Simplify3D)](#setting-up-the-code-for-standalone-use-simplify3d)
- [Usage](#usage)
  - [Material Choice](#material-choice)
  - [Additive Setup](#additive-setup)
    - [Fusion360](#fusion360)
    - [Standalone (Simplify3D, Other Slicers)](#standalone-simplify3d-other-slicers)
  - [Subtractive Setup](#subtractive-setup)
    - [Stock setup](#stock-setup)
      - [Fusion360](#fusion360-1)
      - [External Slicer](#external-slicer)
    - [CAM setup](#cam-setup)
      - [Retraction & Non-Planar Understanding Point](#retraction--non-planar-understanding-point)
      - [Tool Config](#tool-config)
      - [Operation Setup](#operation-setup)
  - [Post Processing](#post-processing)
    - [Fusion Add-in](#fusion-add-in)
    - [Standalone](#standalone)
      - [Config](#config)
      - [Program](#program)
  - [Run Standalone](#run-standalone)
- [Updating](#updating)
- [Contributions](#contributions)
- [Authors and Acknowledgment](#authors-and-acknowledgment)
- [License](#license)

<br>
<br>
<br>

# Installation

## Fusion 360 Add-in

Unzip the repo in your desired folder location or clone the repo:

```bash
git clone https://github.com/AndyEveritt/N-Fab.git
```

- Open Fusion360
- Click the add-in tool
- Click the green plus to add an existing add-in

<img src="docs/installation/images/fusion_add_existing.png" width=480>

- Navigate to the N-Fab repo location and select the folder

<img src="docs/installation/images/fusion_select_location.png" width=480>

- Select the N-Fab add-in from the list, click `Run on Startup`, then `Run`

<img src="docs/installation/images/fusion_run.png" width=240>

## Fusion360 Design Workspace

To make orienting the coordinate axis between modeling, additive, and subtractive workspaces; it is highly recommended to change the `Default modeling orientation` in Fusion360.

This can be done by:

- Going to user preferences
- Changing the `Default modeling orientation` to `Z up`

<img src="docs/installation/images/fusion_z_up.png" width=480>

## Setting up the code for standalone use (Simplify3D)

Download the following files from the [releases](https://github.com/AndyEveritt/N-Fab/releases) page:

- `N-Fab.exe`
- `config.json`
- `N-Fab.factory`

Ensure the config and exe are in the same folder for the program to run.

To modify the source code follow the guide here: [Standalone Installation](docs/installation/standalone.md)

<br>
<br>
<br>

# Usage

## Material Choice

A details on materials that have been tested can be found [here](docs/usage/materials.md).

<br>

## Additive Setup

The additive gcode can be setup in various ways.

- Using Fusion360 for the complete workflow (recommended)
- Using Simplify3D (or PrusaSlicer if you want to make a profile) to generate the FFF gcode and Fusion to generate the CAM gcode.

> **<font color="red">DO NOT TURN OFF THE RAFT</font> UNLESS YOU KNOW WHAT YOU ARE DOING...IT IS VERY EASY TO CUT INTO THE BED AND BREAK THE TOOL**

> If you do remove the raft, make sure the part is placed flat on the bed.

### Fusion360

First you need to create an offset of your model, this will control how much cut-in you have.

- Open you Fusion 360 file, or `.step` in Fusion 360.
- Turn on `Capture Design History` if it is not already on.
  - This can be found in the `Design` workspace.

<img src="docs/usage/images/fusion_design_history.png" width=240>

- Make a duplicate of the model body(s).
  - Select the body from the Browser menu on the left and `Ctrl+C`, `Ctrl+V`
  - Make sure both bodies perfectly overlaid.
  - Both bodies should be outside a component if one exists. (Weird graphics happen otherwise).

<img src="docs/usage/images/fusion_component_body.png" width=240>

- Offset all the faces on the new body that you wish to machine.
  - Hide the original body to make selecting faces easier.
  - An offset amount of ~0.2-0.3 mm works well in my testing.
  - You do not want to offset any face you will not be able to machine, **ie the base**
  - For top surfacing to work properly, you need to offset a sufficient amount for the additive slicer to add an additional layer. This can normally be achieved by offsetting the same amount as your print layer height.
  - _You do not want to offset more than 1 print layer in the vertical direction or the cutting order will not work._
- Once you are done, hide the offset body and show the original body.

<img src="docs/usage/images/fusion_fff_offset.png" width=480>

- You should have 2 of each body in your part, the exactly modelled part, and the offset part.
- Enter the `Additive` Tab in the `Manufacturing` workspace in Fusion360.
- Create a new setup
  - Click `Select` Machine
  - Import the [`E3D - Tool Changer.machine`](https://github.com/AndyEveritt/N-Fab/blob/master/settings/E3D%20-%20Tool%20Changer.machine) profile from the [`settings`](https://github.com/AndyEveritt/N-Fab/tree/master/settings) folder of this repo
  - Click `Select` next to `Print Settings`
  - Import the [`N-Fab.printsetting`](https://github.com/AndyEveritt/N-Fab/blob/master/settings/N-Fab.printsetting) profile from the [`settings`](https://github.com/AndyEveritt/N-Fab/tree/master/settings) folder of this repo
  - Under `Model` select the offset body created earlier

Workspace:

<img src="docs/usage/images/fusion_fff_workspace.png" width=480>

Machine:

<img src="docs/usage/images/fusion_fff_machine.png" width=480>

Setup:

<img src="docs/usage/images/fusion_fff_setup.png" width=480>

- Optionally rename the setup to `Additive`

### Standalone (Simplify3D, Other Slicers)

Guide on how to create a properly configured gcode file can be generated can be found [here](docs/usage/standalone.md)

<br>

## Subtractive Setup

### Stock setup

- Create a new Setup by clicking `Setup` > `New Setup`
- Select `From solid` for the Stock mode
- Click on the part body to select it
  - Select the offset body if created earlier
- Under the `Model` option in the `Setup` tab, select the original part body.

The origin changes depending on if you are using Fusion360 or an external slicer for the additive gcode.

#### Fusion360

- Under `Work Coordinate System` select:
  - Orientation: `Model orientation`
  - Origin: `Model origin`
- The origin should now align with the previously configured FFF setup

<img src="docs/usage/images/fusion_cam_setup.png" width=480>

#### External Slicer

- Move the origin to the bottom middle of the part
- Orient the Z axis to be vertically upwards

<br>

### CAM setup

The CAMing proceedures for N-Fab can be configured with the following processes:

| Process             | Usage                                                                                                            |
| ------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 3D Contour          | Used for vertical & close to vertical side walls (including chamfers & filets).                                  |
| 2D Adaptive         | Used for top surfacing                                                                                           |
| 2D Contour          | Used for vertical side walls of parts                                                                            |
| Other 3D operations | Can be used for non planar operations **if you know what you are doing** (it is easy to break stuff, be careful) |

See [Operation Setup](#operation-setup) for more details.

#### Retraction & Non-Planar Understanding Point

> **This is key to understanding how to CAM a model effectively. Below are guidelines but they may not work for every situation.
> Use this overview to understand what to look for when setting up the CAM operations.**

This program separates each of the CAM operations into segments separated by motion type (cutting, lead-in, plunge, etc.).

Each of the `cutting` segments are then classified as either planar or non-planar.

- Planar segments are where the cutting happens on the XY plane.
- Non-planar segments also cut in the Z axis.

The height of each segment is determined:

- For planar segments, it is the minimum height the cutter is active.
- For non-planar segments, it is the maximum height the cutter is active.

Consequetive cutting segments are then grouped if they have the same height as the previous segment. Consequetive segments are also grouped if they are non planar.

For each group, any prior `lead-in` or `plunge` segments and post `lead-out` segments are found and added to the group start or end respectively. A `CamGcodeLayer` is created containing every segment between the first and last segment in the group for all motion types.

Retracts are automatically added between each `CamGcodeLayer` to ensure the tool does not collide with the part.
Therefore, if there are multiple consequetive cutting segments at the same height (top surfacing etc.), the Fusion retracts will be used;
otherwise, this program will automatically replace any retracts/transitions Fusion creates.

> **Always inspect the gcode with travel moves turned on after it has been generated. This program reorders a significant proportion of the gcode, and replaces Fusion360's default retracts & travel moves.**
>
> It can happen that a single missing/wrong line in the toolpath causes the tool to pass through the model, this is unlikely if sticking with planar operations but a possibility when using non-planar

#### Tool Config

You can import our tool config by opening the `Tool Library` then right clicking on either the Document, `Cloud`, or `Local` then `Import Tool Library`. The library to import is located in this repo in [`settings`/`N-Fab.tools`](https://github.com/AndyEveritt/N-Fab/blob/master/settings/N-Fab.tools)

<img src="docs/usage/images/fusion_cam_tool_import.png" width=480>

When selecting the tool you must renumber the tool to match the tool number on your printer.

A `Cutting Feedrate` of 500 mm/min works well.

<img src="docs/usage/images/fusion_cam_tool.png" width=480>

#### Operation Setup

The CAM operations can be created using these buttons in the `Milling` Toolbar

<img src="docs/usage/images/fusion_cam_operations.png" width=480>

Full setup details for operations can be found here: [CAM Operation Setup](docs/usage/cam_operations.md)

## Post Processing

### Fusion Add-in

- Regenerate the additive setup
- Regenerate the subtractive setup
  - This offsets the CAM operation Z height equal to the raft height.
- Click on the `N-Fab` tab along the top navigation bar
- Click `Post Process`
  - If all the toolpaths have not been previously generated or are out of date, you can tick the box to re generate all toolpaths
    - This currently has a bug if the additive toolpath isn't the last to generate where the progress bar will not complete. If this happens just close the progress bar are rerun the post process command
  - The default settings are auto filled.
    - Layer overlap is an important setting
      - An overlap > 0 will use the side of the cutter instead of the tip, this can give a better finish to walls. If there are no overhangs, recommended to use `2`.
      - However this can cause issues if machining overhangs, in which case set the overlap to 0
    - Layer Dropdown can also affect finish
      - This will lower the z height of all the CAM operations by this value, it can be used to make the cutter tip locate in the middle of a layer instead of between 2 layers which can give a better finish; but if you want Z accuracy, leave it at 0.
  - Click `OK`
- The output gcode will be saved in `~/N-Fab/output/`
  - If the file name already exists, it will be overwritten without warning.
  - The generated file will automatically open in your default `.gcode` editor.
  - **Always preview the gcode fully to check it for mistakes** This is Beta software, there will be bugs.

### Standalone

- Generate and Simulate the full Setup to ensure in looks sensible
- In the `Manufacturing` workspace, `N-Fab` tab; click `Actions` > `Post Process Cam`
- Click `Ok`

>A new temporary file is created for each unsuppressed milling setup, rename or change the folder location of any generated file
you want to keep else it may be deleted/overwritten.

Fusion will try to open the generated gcode file in VSCode by default, if you don't have it installed it will prompt you to download it. This is entirely up to you.

#### Config

The `config.json` contains the parameters that control how the N-Fab parser merges the 2 input files if running the program standalone.

Update the `config.json` so that the following settings are correct for your project:

```json
{
    "InputFiles": {
        "additive_gcode": "path to Simplify3D additive .gcode file",
        "subtractive_gcode": "path to Fusion360 CAM .gcode file"
    },
    "Printer": {
        "bed_centre_x": "mm from origin to bed centre in x axis (150)",
        "bed_centre_y": "mm from origin to bed centre in y axis (100)"
    },
    "PrintSettings": {
        "raft_height": "Height of the top layer of the raft (2.133)"
    },
    "CamSettings": {
        "layer_overlap": "How many layers the tip of the cutter should be lower than the layers being cut",
        "layer_dropdown": "What number of mm the tip of the cutter should be lowered by"
    },
    "OutputSettings": {
        "filename": "Name of the output file containing the merged gcode script
    }
}
```

#### Program

The program takes the following arguments:

| Arg (long) | Arg (short) | Default       | Usage                               |
| ---------- | ----------- | ------------- | ----------------------------------- |
| `--config` | `-C`        | `config.json` | Path to the configuration JSON file |

By default the program expects the `config.json` to be in the same directory as the main file.

## Run Standalone

To run the program, ensure the `config.json` is configured correctly, then run the `N-Fab.exe`

The latest `.exe` can be found here https://github.com/AndyEveritt/N-Fab/releases

The program will output the file with a name according the the config settings in the `output` folder. (An output folder will be created in the same directory as the `.exe` if one does not exist)

> **Always preview the generated gcode in Simplify3D before attempting to print it**

Set the coloring to `Active Toolhead` and enable `Travel moves` to ensure the part is using the correct tools at the correct times.

The subtractive processes are displayed as travel moves, scroll through the layers to check the subtractive processes have been added at the correct point in the print (defined in `config.json`)

<img src="docs/images/simplify3d_preview.png" width="480">

# Updating

Close Fusion 360 and overwrite the contents of the N-Fab repo folder with the latest version from releases (or use `git pull` if you previously cloned the repo).

If you want Fusion to automatically detect the update then make sure the folder names are the same, otherwise repeat this step with the new folder [Fusion 360 Add-in](#fusion-360-add-in).

# Authors and Acknowledgment

| Author        | Contribution |
| ------------- | ------------ |
| @AndyEveritt  | Code         |
| Greg Holloway | Printer      |

# License

LGPL-3.0
