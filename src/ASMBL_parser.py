import sys
import subprocess
import os
import re
from math import (
    inf,
    ceil,
    floor,
)
from . import utils
from .additive_gcode import AdditiveGcodeLayer
from .cam_gcode import (
    CamGcodeLine,
    CamGcodeSegment,
    CamGcodeLayer,
)


class Parser:
    """ Main parsing class. """

    def __init__(self, config, progress=None):
        self.config = config
        self.progress = progress    # progress bar for Fusion add-in
        self.offset = (config['Printer']['bed_centre_x'],
                       config['Printer']['bed_centre_y'],
                       config['PrintSettings']['raft_height'] - config['CamSettings']['layer_dropdown']
                       )
        #<JLC>
        self.flag_append_AddSubGcode = config['Flags']['append_AddSubGcode']
        #</JLC>
        
        self.last_additive_tool = None
        self.last_subtractive_tool = None 

        self.main()

    def main(self):
        progress = self.progress

        print('Opening files...')
        if progress:
            progress.message = 'Opening files'
            progress.progressValue += 1
        self.open_files(self.config)

        # Fusion 360 currently only exports absolute extrusion gcode, this needs to be converted
        # This method will not convert gcode if it is already relative
        print('Converting additive gcode to relative positioning...')
        if progress:
            progress.message = 'Converting additive gcode to relative positioning'
            progress.progressValue += 1
        self.gcode_add = utils.convert_relative(self.gcode_add)

        #<JLC>
        if self.flag_append_AddSubGcode:
            if progress:
                progress.message = 'Appending substractive to additive Gcode'
                progress.progressValue += 1
                
            self.merged_gcode_script = '; N-Fab gcode created by NAMMA\n'
            self.merged_gcode_script += self.appendSub2AddGcode()
            
            return
        #</JLC>
        
        print('Spliting additive gcode layers...')
        if progress:
            progress.message = 'Spliting additive gcode layers'
            progress.progressValue += 1
            
        #<JLC8>
        ORCA = False
        if 'OrcaSlicer' in self.gcode_add:
            ORCA = True
            
            #<JLC7>
            # OrcaSlicer adds an info bloc at the end of the gcode file after the line '; EXECUTABLE_BLOCK_END'
            # that contains many lines ' ; layer ....' causing an error in method get_layer_height() of class 
            # AdditiveGcodeLayer.
            # so we skip all the gcode after the line ; EXECUTABLE_BLOCK_END' if any.
            if '; EXECUTABLE_BLOCK_END' in self.gcode_add:
                self.gcode_add = self.gcode_add.split('; EXECUTABLE_BLOCK_END')[0] + '; EXECUTABLE_BLOCK_END\n'
            #</JLC7>
        #</JLC8>
        
        self.gcode_add_layers = self.split_additive_layers(self.gcode_add, ORCA)
        
        #<JLC4>
        print('Pre-processing substractive gcode file...')
        if progress:
            progress.message = 'Preprocessing subtractive gcode file'
            progress.progressValue += 1
        self.gcode_sub = self.preprocess_sub_gcode_file()
        #</JLC4>

        print('Spliting substractive gcode layers...')
        if progress:
            progress.message = 'Spliting subtractive gcode layers'
            progress.progressValue += 1
        operations = self.split_cam_operations(self.gcode_sub)

        print('Ordering subtractive gcode layers...')
        if progress:
            progress.message = 'Ordering subtractive gcode layers'
            progress.progressValue += 1
        self.cam_layers = self.order_cam_operations_by_layer(operations)

        print('Merging gcode layers...')
        if progress:
            progress.message = 'Merging gcode layers'
            progress.progressValue += 1
        self.merged_gcode = self.merge_gcode_layers(self.gcode_add_layers, self.cam_layers)

        print('Creating gcode script...')
        if progress:
            progress.message = 'Creating gcode script'
            progress.progressValue += 1
        self.create_gcode_script(self.merged_gcode)

    def open_files(self, config):
        """ Open the additive and subtractive gcode files in `config` """
        with open(config['InputFiles']['additive_gcode'], 'r') as gcode_add_file:
            self.gcode_add = gcode_add_file.read()

        with open(config['InputFiles']['subtractive_gcode'], 'r') as gcode_sub_file:
            if self.flag_append_AddSubGcode:
                self.gcode_sub = gcode_sub_file.read()
            #<JLC4>: rwind the file to get all the lines:
            gcode_sub_file.seek(0)
            self.gcode_sub_lines = gcode_sub_file.readlines()
            #</JLC4>
            
    #<JLC>
    def appendSub2AddGcode(self):
        """ Just append the substractive Gcode to the additive Gcode..."""
        if self.gcode_add[-1] != '\n': self.gcode_add += '\n'
        return self.gcode_add + self.gcode_sub.replace('(', ';(')
    #</JLC>

    #<JLC4>
    def preprocess_sub_gcode_file(self):
        '''
        To split CAM operations with a large Z range into smaller overlapping CAM 
        operations each covering a small Z range.
        '''
        
        # write debug info in a log file:
        if sys.platform == 'linux':
            outputFolder = './output'
        else:
            outputFolder = os.path.expanduser('~/N-Fab/output/')
            
        fileName = self.config['OutputSettings']['filename'] + '.log'
        log_file_name = os.path.join(outputFolder, fileName)
        if os.path.exists(log_file_name):
            os.remove(log_file_name)

        blocs_to_split = self.split_gcode_file_stage1(log_file_name)
        
        if len(blocs_to_split) == 0:
            # nothing to do...
            splitted_gcode = ''.join(self.gcode_sub_lines)
        else:
            splitted_gcode = self.split_gcode_file_stage2(blocs_to_split, log_file_name)
        
        # write the new substractive gcode file with '_split' added to its name:
        name = self.config['InputFiles']['subtractive_gcode']
        new_sub_gcode_file_name = name.replace('.gcode','') + '_split.gcode'
        
        if os.path.exists(new_sub_gcode_file_name):
            os.remove(new_sub_gcode_file_name)
            
        with open(new_sub_gcode_file_name, 'w') as F:
            F.write(splitted_gcode)
        F.close()

        # <JLC5> bug 5.2 presence of '(type: ramp)' in sub gcode ???
        # splitted_gcode = splitted_gcode.replace('(type: ramp)', '(type: cutting)')     
        # JLC: from ASMBL-1.3, the 'ramp' tag is fully processed 
        #       => no more need to replace 'ramp' by 'cutting'
        # </JLC5>
        
        # Now returns all the lines:
        return splitted_gcode
        
        # That's all...
                    
    def log_message(self, message, log_file_path):
        
        with open(log_file_path, 'a') as Log:
            Log.write(message)
            if message[-1] != '\n':
                Log.write('\n')
            Log.flush()
        Log.close()
        
    def split_gcode_file_stage1(self, log_file_path):
        '''
        This method:
        - reads the whole substractive GCode file to get all the lines
        - looks for lines beginning with the TAG :
            "(strategy: parallel_new)" or 
            "(strategy: ramp)"
            "(strategy: contour2D)
        For each bloc beginning with TAG and ending with a blank line ('\n'), the gcode  
        lines are grouped by sub-blocs with a z range <= zRangeMax3Dsurfacing_mm, 
        overlapping each other with zOverlap3Dsurfacing_mm.
        '''
        bloc_to_split= {}
        num_bloc = 0
        bloc_found = False

        STRATEGIES = ('(strategy: parallel_new)', 
                      '(strategy: ramp)',
                      '(strategy: contour2d)')

        # scan the GCode lines to catch the target:
        for i, line in enumerate(self.gcode_sub_lines, 1):
            if line.strip() in STRATEGIES:
                STRATEGY = line.strip()
                start_bloc = i-2
                name = self.gcode_sub_lines[start_bloc]
                bloc_to_split[num_bloc] = {'strategy': f'{STRATEGY}\n',
                                           'type': '',
                                           'name': name, 
                                           'header': '',
                                           'start_bloc': start_bloc, 
                                           'needs_header': False}
                bloc_found, cutting, first_cutting_line = True, False, None
                Zmin = None
                header = ''
                num_sub_bloc = 0
                continue
           
            if i == len(self.gcode_sub_lines) or line == '\n':
                # This is the end of a "(strategy: ...)"" CAM bloc, save the bloc data
                if bloc_found:
                    bloc_to_split[num_bloc]['header']   = header
                    bloc_to_split[num_bloc]['ZMinMax']  = (Zmin, Zmax)
                    bloc_to_split[num_bloc]['end_bloc'] = i
                    
                    num_bloc += 1
                    bloc_found, cutting, first_cutting_line = False, False, None
                continue
           
            if bloc_found:
                if line.startswith('T') or line.startswith('M'):
                    # add lines like "T1" and "M3 S14000" to header:
                    header += line
                    
                elif not cutting and (line.startswith('(type: cutting)') or line.startswith('(type: ramp)')):
                    cutting = True
                    if first_cutting_line is None:
                        first_cutting_line = i-1
                        bloc_to_split[num_bloc]['first_cutting_line'] = first_cutting_line
                        bloc_to_split[num_bloc]['type'] = line.strip()
                       
                elif line[:2] == 'G0':
                    prev_line = self.gcode_sub_lines[i-2]
                    if i <  len(self.gcode_sub_lines) :
                        next_line = self.gcode_sub_lines[i]
                    else:
                        next_line = '\n'
                    if prev_line.startswith('(type:') and next_line != '\n':
                        # A new surfacing phase takes place: we wil create a new sub-bloc
                        # with "(strategy: ...)"
                        # 1/ Save the data of the current bloc
                        bloc_to_split[num_bloc]['header']   = header
                        bloc_to_split[num_bloc]['ZMinMax']  = (Zmin, Zmax)
                        bloc_to_split[num_bloc]['end_bloc'] = i-3
                        # 2/ Prepare the new bloc
                        num_bloc += 1
                        num_sub_bloc +=1
                        start_bloc = i-2
                        new_name = name.strip()[:-1] + f'- split {num_sub_bloc})\n'
                        
                        bloc_to_split[num_bloc] = {'strategy': f'{STRATEGY}\n', 
                                                   'type': prev_line.strip,
                                                   'name': new_name, 
                                                   'header': header,
                                                   'start_bloc': start_bloc, 
                                                   'needs_header': True}
                        bloc_found, cutting = True, False
                        first_cutting_line, Zmin = None, None
                                         
                elif cutting and line[:2] == 'G1':
                    # Extract Z from a line in a 'cutting' zone like: 
                    # "G1 X100.202 Y108.725 Z2.083 F924"
                    Z = float(line.strip().split()[3][1:])
                    if Zmin is None: 
                        Zmin, Zmax = Z, Z
                    if Z < Zmin:
                        Zmin = Z
                    elif Z > Zmax:
                        Zmax = Z
                else:
                    cutting = False
                        
        return bloc_to_split
        
    def split_gcode_file_stage2(self, blocs_to_split, log_file_path):
        '''
        In this method we split each surfacing CAM operation with a large Z range
        into overlapping smaller surfacing operations.
        '''
        
        zRangeMax3Dsurfacing_mm = self.config['CamSettings']['zRangeMax_3Dsurfacing_mm']
        zOverlap3Dsurfacing_mm  = self.config['CamSettings']['zOverlap_3Dsurfacing_mm']

        mess = f"zRangeMax3Dsurfacing_mm: {zRangeMax3Dsurfacing_mm}, zOverlap3Dsurfacing_mm: {zOverlap3Dsurfacing_mm}"
        self.log_message(mess, log_file_path)

        splitted_gcode = ""
        start_line_number = 0

        for key in blocs_to_split:
            
            bloc = blocs_to_split[key]         
            mess = "\n" + "="*30 + \
                f"\nProcessing bloc {key}\n" + \
                f"\t(start, end):{(bloc['start_bloc'], bloc['end_bloc'])}\n" + \
                f"\tname        :{repr(bloc['name'])}, needs_header:{bloc['needs_header']}\n" + \
                f"\tstrategy    :{repr(bloc['strategy'])}\n" + \
                f"\ttype        :{repr(bloc['type'])}\n" + \
                f"\theader      :{repr(bloc['header'])}\n" + \
                f"\t(Zmin, Zmax):{(bloc['ZMinMax'])}\n"
            self.log_message(mess, log_file_path); print(mess)
            
            first_line_bloc, end_line_bloc = bloc['first_cutting_line'], bloc['end_bloc']
            Zmin, Zmax = bloc['ZMinMax']
           
            # Fill splitted_gcode with the Gcode lines until the firts line of the bloc:
            if bloc['needs_header']:
                splitted_gcode += bloc['name']
                splitted_gcode += bloc['strategy']
                splitted_gcode += bloc['header']
              
            splitted_gcode += ''.join(self.gcode_sub_lines[start_line_number:first_line_bloc])

            # TODO
            if abs(Zmax - Zmin) <= zRangeMax3Dsurfacing_mm: 
                # no need to split the CAM operation
                splitted_gcode += ''.join(self.gcode_sub_lines[first_line_bloc:end_line_bloc])
                if splitted_gcode[-2:] != '\n\n': splitted_gcode += '\n'
                start_line_number = end_line_bloc
                continue
            
            # The first split and following splits need some different processing:
            first_split = True
            
            while(True):
                Z, prevZ, Z1, Z2, L1, L2, next_L1 = None, None, None, None, None, None, None
                cutting, Z_increase = False, None
            
                if bloc['strategy'].strip() in ('(strategy: ramp)', '(strategy: contour2d)') and first_split == False:
                    # When surfacing a 'ramp', we are splitting a large numver of 'G1 ....' 
                    # # lines with just one '(cutting)' line in the preamble : we must keep
                    # the cutting state for all the 'G1 ...' lines:
                    cutting = True
                    
                # Every loop turn allows to build one of the overlapping smaller bloc:
                for i, line in enumerate(self.gcode_sub_lines[first_line_bloc:end_line_bloc], first_line_bloc):
                 
                    if not cutting and (line.startswith('(type: cutting)') or line.startswith('(type: ramp)')) :
                        # start the cutting state:
                        cutting = True
                        continue   
                                  
                    elif cutting and line.startswith('('):
                        # exit from the cutting state
                        print("line.startswith('('):", line)
                        cutting = False
                        continue
                 
                    if cutting: 
                        # When in cutting state we must find out the start and end of each small cutting bloc:
                        if line[:2] == 'G1': 
                            Z = float(line.strip().split()[3][1:])
                            if prevZ is None:
                                 prevZ = Z
                            else:
                                # JLC : Fusion BUG : sometime we find 2 consecutive G1 lines with a difference
                                #       between the 2 Z  of about 0.001 mm...
                                if 0 < abs(Z - prevZ) <= 0.001: 
                                    continue                              
                                if Z > prevZ: 
                                    Z_increase = True
                                elif Z < prevZ:
                                    Z_increase = False
                                #<JLC6>
                                elif Z == prevZ:
                                    Z_increase = None
                                #</JLC6>                               

                            if Z1 == None :
                                # this is the beginning of a small cutting bloc
                                Z1, L1 = Z, i
                            else:
                                if next_L1 == None:
                                    if abs(Z1 - Z) >= (zRangeMax3Dsurfacing_mm - zOverlap3Dsurfacing_mm):
                                        # this is the beginning of the next small overlapping cutting bloc
                                        next_L1 = i
                                        
                                if (abs(Z1 - Z) >= zRangeMax3Dsurfacing_mm) or \
                                   (Z_increase == True and Z == Zmax) or \
                                   (Z_increase == False and Z == Zmin):
                                    # this is the end of a small cutting bloc: the bloc is added to the 
                                    # object splitted_gcode:
                                    Z2, L2 = Z, i
                                    mess = f"(Z1,Z2):({Z1:.3f},{Z2:.3f}), (L1,L2)={(L1,L2)}" 
                                    self.log_message(mess, log_file_path); print(mess)
                                    
                                    if first_split == False:
                                        splitted_gcode += bloc['name']
                                        splitted_gcode += bloc['strategy']
                                        splitted_gcode += bloc['header']
                                        
                                        if bloc['strategy'].strip() in ('(strategy: ramp)', '(strategy: contour2d)'):
                                            # when splitting the many lines of a 'ramp', we must add
                                            # the '(type: cutting)\n' line in each small splitted bloc:
                                            splitted_gcode += f"{bloc['type']}\n"

                                    splitted_gcode += ''.join(self.gcode_sub_lines[first_line_bloc:L2+1])
                                    
                                    if splitted_gcode[-2:] != '\n\n': 
                                        splitted_gcode += '\n'
                
                                    if first_split: 
                                        first_split = False
                                 
                                    # Ready to build the surfacing bloc.
                                    # Normally the next bloc to process overlaps the current bloc
                                    if next_L1 is not None: 
                                        first_line_bloc = next_L1 + 1
                                    #<JLC6>
                                    else:
                                        first_line_bloc = i
                                    #</JLC6>
                                    
                                    # break the 'for loop' to come back to the 'while loop':
                                    break      
                                
                if Z_increase is not None:     
                    if (Z_increase == True and Z == Zmax) or (Z_increase == False and Z == Zmin): 
                        if bloc['strategy'].strip() in ('(strategy: ramp)', '(strategy: contour2d)'):
                            # add the rest of the lines of the bloc:
                            # 1/ remove the trailing '\n':
                            if splitted_gcode[-2:] == '\n\n': splitted_gcode = splitted_gcode[:-1]
                            # 2/ add the lines:
                            splitted_gcode += ''.join(self.gcode_sub_lines[i+1:end_line_bloc])
                            if splitted_gcode[-2:] != '\n\n': splitted_gcode += '\n'
                            
                            break  #<JLC6> break was outside the if bock
                        else:
                            pass
                #<JLC6>
                if i >= end_line_bloc - 1:
                    break
                #</JLC6>
            # Go on with the next bloc:
            start_line_number = end_line_bloc
            
        splitted_gcode += ''.join(self.gcode_sub_lines[end_line_bloc:])
        return splitted_gcode
    #</JLC4>
    
    def split_additive_layers(self, gcode_add, ORCA):
        """ JLC: Takes additive gcode and splits in by layer.
            the 'tmp_list' list consists in :
            - a header,
            - pairs of (layer_separator_tag str, gcode str of the layer)
            For fusion360 tah layer separator tag is '; layer', 
            for Orca it is ';LAYER_CHANGE'.
        """
        #<JLC8>
        tag = '(; layer)'                         # for Fusion360 additive GCode
        if ORCA : tag = '(;LAYER_CHANGE)'     # for OrcaSlicer additive GCode
        tmp_list = re.split(tag, gcode_add)
        #</JLC8>
        
        gcode_add_layers = []
        initialise_layer = AdditiveGcodeLayer(
            tmp_list.pop(0),
            name="initialise",
            layer_height=0,
        )    # slicer settings & initialise
        self.set_last_additive_tool(initialise_layer)
        # initialise_layer.comment_all_gcode()
        gcode_add_layers.append(initialise_layer)

        for i in range(ceil(len(tmp_list)/2)):

            layer = tmp_list[2*i] + tmp_list[2*i+1]
            if ORCA:
                name = ''.join(layer.split(';')[:3]).replace('\n',' ').strip()
            else:
                # Fusion360
                name = layer.split(',')[0][2:]

            if 2*i + 1 == len(tmp_list) - 1:
                #<JLC10>: was  gcode_add_layers.append(AdditiveGcodeLayer(layer, 'end', inf))
                gcode_add_layers.append(AdditiveGcodeLayer(layer, 'end', ORCA=ORCA))
                continue

            gcode_add_layers.append(AdditiveGcodeLayer(layer, name, ORCA=ORCA))

        return gcode_add_layers

    def assign_cam_line_type(self, unlabelled_lines):
        """ extract type information from string, returns a list of CamGcodeLine's """
        lines = []
        line_type = None
        for line in unlabelled_lines:
            if line.startswith('(type: '):
                line_type = line[7:].strip(')')
            elif line.startswith('(') or line.startswith('M'):
                continue
            else:
                lines.append(CamGcodeLine(line, self.offset, line_type))

        return lines

    def group_cam_lines(self, lines):
        """
        Group consecutive lines of the same type into CamGcodeSegment segments
        Returns a list of segments
        """
        segments = []
        segment_lines = [lines[0]]
        for i, line in enumerate(lines[1:]):
            if line.type != lines[i].type:
                segment_index = len(segments)
                segments.append(CamGcodeSegment(segment_index, segment_lines, lines[i].type))
                segment_lines = [line]
            else:
                segment_lines.append(line)

        segment_index = len(segments)
        segments.append(CamGcodeSegment(segment_index, segment_lines, lines[-1].type))

        return segments

    def add_lead_in_out(self, segments, cutting_group):
        """
        Add lead in to start of group of cutting segments, and lead out to end if they exist.
        This is required to ensure the cutter does not miss any stock for certain toolpaths
        """
        start_index = cutting_group[0].index
        pre_index = start_index - 1 if start_index - 1 >= 0 else start_index
        # <JLC-4> Add 'transition'
        if segments[pre_index].type in ('lead in', 'plunge', 'transition'):
            start_index = pre_index

        # warn user if a bad linking setting are detected
        if segments[pre_index].type in ('helix_ramp', 'profile_ramp', 'ramp'):
            print('CAM Linking may be set incorrectly')

        end_index = cutting_group[-1].index
        post_index = end_index + 1 if end_index + 1 <= len(segments) - 1 else end_index
        # <JLC-4> Add 'transition'
        if segments[post_index].type in ('lead out', 'transition'):
            end_index = post_index

        return segments[start_index:end_index+1]
    
    def group_cam_segments(self, segments, name, strategy, tool, start_tool):
        """
        Group all cutting segments with a continuous and equal cutting height, including all intermediary segments.
        Lead-ins and lead-outs will be added to the start and end respectively if they exist.
        Consecutive non planar segments are also grouped together.

        Returns a list of layers, each to be merged as a whole unit.
        """
        cutting_segments = [segment for segment in segments if segment.type in ('cutting', 'ramp') ]
        cam_layers = []
        cutting_group = [cutting_segments[0]]
        cutting_height = cutting_segments[0].height
        for cutting_segment in cutting_segments[1:]:
            # TODO logic needs fixing to deal with non planar and planar segments in same operation
            #<JLC>
            # was: if cutting_segment.height == cutting_height or cutting_segment.planar is False or len(cutting_segment.lines) == 1:
            # was: if cutting_segment.height == cutting_height or cutting_segment.planar is False:
            # Finally return to original test...
            #<JLC4> : ajout de <or strategy in ('parallel_new',)>
            #<JLC5> : modif -> strategy in ('parallel_new', 'ramp')>
            if cutting_segment.height == cutting_height or \
               cutting_segment.planar is False or \
               strategy in ('parallel_new', 'ramp'):
            #</JLC>
                cutting_group.append(cutting_segment)
                cutting_height = cutting_segment.height
            else:
                cutting_height = cutting_segment.height

                layer_group = self.add_lead_in_out(segments, cutting_group)
                cam_layers.append(CamGcodeLayer(layer_group, name, strategy, tool, start_tool))
                cutting_group = [cutting_segment]

        layer_group = self.add_lead_in_out(segments, cutting_group)
        cam_layers.append(CamGcodeLayer(layer_group, name, strategy, tool, start_tool))

        return cam_layers

    def split_cam_operations(self, gcode_sub):
        """ Takes fusion360 CAM gcode and splits the operations by execution height """
        tmp_operation_list = gcode_sub.split('\n\n')

        operations = []

        for i, operation in enumerate(tmp_operation_list):
            if operation == '': break
            unlabelled_lines = operation.split('\n')
            name = unlabelled_lines.pop(0)
            strategy = unlabelled_lines.pop(0)[11:].strip(')')
            tool = unlabelled_lines.pop(0)
            #<JLC>
            start_tool = unlabelled_lines.pop(0) if unlabelled_lines[0][0] == 'M' else None
            #</JLC>
            unlabelled_lines = [line for line in unlabelled_lines if line != '']

            # 'lines' is the list of CamGcodeLine objects:
            lines = self.assign_cam_line_type(unlabelled_lines)
            
            # 'segments' is the list of CamGcodeSegment objects (each grouping consecutive 
            # lines of 'lines' of the same type):
            segments = self.group_cam_lines(lines)
            
            # 'operation_layers' is the list of CamGcodeLayer objects (each grouping the 
            # cutting segments of equal cutting height or the non-planer cutting segments
            # that make the current operation):
            operation_layers = self.group_cam_segments(segments, name, strategy, tool, start_tool)
            
            operations.append(operation_layers)

        return operations

    def assign_cam_layer_height(self, cam_layer, later_cam_layers, layer_overlap):
        """ Calculate the additive layer height that should be printed to before the CAM layer happens """
        later_planar_layers = [layer for layer in later_cam_layers if layer.planar]

        if (not cam_layer.planar) or (len(later_planar_layers) == 0):
            cutting_height = cam_layer.cutting_height
        else:
            #<JLC>
            # was:  cutting_height = min([layer.cutting_height for layer in later_planar_layers])
            min_cutting_height_later_planar_layers = min([layer.cutting_height for layer in later_planar_layers])
            if min_cutting_height_later_planar_layers - cam_layer.cutting_height > 1:
                cutting_height = cam_layer.cutting_height
            else:
                cutting_height = min_cutting_height_later_planar_layers
            #</JLC>

        later_additive = [layer for layer in self.gcode_add_layers[:-1]
                          if layer.layer_height > cutting_height]

        if (layer_overlap == 0) or (len(later_additive) == 0):
            cam_layer_height = cutting_height

        elif len(later_additive) >= layer_overlap:
            cam_layer_height = later_additive[layer_overlap - 1].layer_height

        else:
            cam_layer_height = later_additive[-1].layer_height

        if cam_layer_height == inf:
            raise ValueError("CAM op height can't be 'inf'")

        cam_layer.layer_height = cam_layer_height
        return

    def order_cam_operations_by_layer(self, operations):
        """ Takes a list of cam operations and calculates the layer that they should be executed """
        unordered_cam_layers = []

        for operation in operations:
            for cam_layer in operation:
                unordered_cam_layers.append(cam_layer)

        ordered_cam_layers = sorted(unordered_cam_layers, key=lambda x: x.cutting_height)

        layer_overlap = self.config['CamSettings']['layer_overlap']

        # TODO assign layer height per layer in each operation independently.
        # There is an issue if you have sparse CAM currently
        for i, cam_layer in enumerate(ordered_cam_layers):
            later_cam_layers = [
                layer for layer in ordered_cam_layers if layer.cutting_height > cam_layer.cutting_height]
            self.assign_cam_layer_height(cam_layer, later_cam_layers, layer_overlap)

        return ordered_cam_layers

    def add_retracts(self, cam_layer, clearance_height=5):
        """
        Adds redamentary retracts between cam layers.
        Required since some of the retracts are removed by `group_cam_segments`
        """
        first_line = cam_layer.segments[0].lines[0]
        last_line = cam_layer.segments[-1].lines[-1]

        offset = (0, 0, clearance_height)
        pre_retract = utils.offset_gcode(first_line.gcode, offset)
        post_retract = utils.offset_gcode(last_line.gcode, offset)

        cam_layer.gcode = '; retract\n' + pre_retract + '\n' + cam_layer.gcode + '; retract\n' + post_retract + '\n'

    def merge_gcode_layers(self, gcode_add, cam_layers):
        """ Takes the individual CAM instructions and merges them into the additive file from Simplify3D """
        for cam_layer in cam_layers:
            #<JLC4> : don't add retracts if srategy is 'parallel_new':
            #<JLC5> : clearance is set to 15mm':
            #if cam_layer.strategy in ('parallel_new'):
            #    pass
            #else:
            self.add_retracts(cam_layer, 15)  # second argument was by default
            #</JLC>

        merged_gcode = gcode_add + cam_layers
        merged_gcode.sort(key=lambda x: x.layer_height)

        return merged_gcode

    def create_gcode_script(self, gcode):
        """ Converts list of layers into a single string with appropriate tool changes """
        self.merged_gcode_script = '; N-Fab gcode created by https://github.com/cjlux/ASMBL\n'
        prev_layer = gcode[0]
        for layer in gcode:
            self.set_last_additive_tool(prev_layer)
            self.tool_change(layer, prev_layer)
            prev_layer = layer
            self.merged_gcode_script += layer.gcode

    def set_last_additive_tool(self, layer):
        """ Finds the last used tool in a layer and saves it in memory """
        if isinstance(layer, AdditiveGcodeLayer):
            process_list = layer.gcode.split('\nT')
            if len(process_list) > 1:
                self.last_additive_tool = 'T' + process_list[-1].split('\n')[0]

    def tool_change(self, layer, prev_layer):
        """ Adds any required tool changes between 2 layers """
        if type(layer) == AdditiveGcodeLayer:
            if layer.name == 'initialise' or prev_layer.name == 'initialise':
                return  # no need to add a tool change
            first_gcode = layer.gcode.split('\n')[1]
            if first_gcode[0] != 'T':
                self.merged_gcode_script += self.last_additive_tool + '\n'
        elif type(layer) == CamGcodeLayer:
            self.merged_gcode_script += layer.tool + '\n'
            #<JLC>
            if layer.start_tool != None: self.merged_gcode_script += layer.start_tool + '\n'
            #</JLC>

    def create_output_file(self, gcode, folder_path="output/", relative_path=True):
        """ Saves the file to the output folder """
        file_path = folder_path + self.config['OutputSettings']['filename'] + ".gcode"

        file_path = os.path.expanduser(file_path)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w") as f:
            f.write(gcode)

        f.close()

        try:
            utils.open_file(file_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    gcode_add_file = open("gcode/cyclodial_gear/additive.gcode", "r")
    gcode_add = gcode_add_file.read()

    gcode_sub_file = open("gcode/cyclodial_gear/cam.nc", "r")
    gcode_sub = gcode_sub_file.read()

    parser = Parser(gcode_add, gcode_sub)
    parser.create_output_file(parser.merged_gcode_script)
