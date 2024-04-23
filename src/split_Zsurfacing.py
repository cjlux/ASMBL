import os, sys
import numpy as np

'''
To split surfacing operations with a large Z range into smaller overlapping surfacing 
operations each covering a small Z range.

First step is to process the tag: (strategy: parallel_new), or the presence of lines 
'G0 ...'
'''

zRangeMax3Dsurfacing_mm = 5
zOverlap3Dsurfacing_mm  = 0.75

os.chdir('/home/jlc/work/01-github.com_cjlux/NAMMA/ASMBL-NAMMA/ASMBL-jlc/ASMBL/gcode')
with open('tmpSubtractive4.gcode', 'r') as F:
   gcode_sub = F.read()
   F.seek(0)
   gcode_sub_lines = F.readlines()

bloc_to_split= {}
num_bloc = 0
bloc_found = False

STRATEGY = '(strategy: parallel_new)'

# scan the GCode lines to catch the target:
for i, line in enumerate(gcode_sub_lines, 1):
   if STRATEGY in line:
      start_bloc = i-2
      name = gcode_sub_lines[start_bloc]
      bloc_to_split[num_bloc] = {'strategy': f'{STRATEGY}\n', 
                                 'name': name, 
                                 'header': '',
                                 'start_bloc': start_bloc,
                                 'needs_header': False}
      bloc_found, cutting, first_cutting_line = True, False, None
      Zmin = None
      header = ''
      num_sub_bloc = 0
      continue
   
   if line == '\n':
      # This is the end of a "(strategy: ...)"" CAM bloc
      if bloc_found:
         # If a blac was found, save the bloc data:
         bloc_to_split[num_bloc]['header'] = header
         bloc_to_split[num_bloc]['ZMinMax'] = (Zmin, Zmax)
         bloc_to_split[num_bloc]['end_bloc'] = i
         
         num_bloc += 1
         bloc_found, cutting, first_cutting_line = False, False, None
      continue
   
   if bloc_found:
      if line.startswith('T') or line.startswith('M'):
         header += line
         
      elif line.startswith('(type: cutting)'):
         cutting = True
         if first_cutting_line is None:
            first_cutting_line = i-1
            bloc_to_split[num_bloc]['first_cutting_line'] = first_cutting_line
         
            
      elif line[:2] == 'G0':
         if gcode_sub_lines[i-2].startswith('(type:') and gcode_sub_lines[i] != '\n':
            #
            # A new surfacing phase takes place: we wil create a new sub-bloc
            # with "(strategy: ...)"
            #
            
            #
            # 1/ Save the data of the current bloc
            #
            bloc_to_split[num_bloc]['header'] = header
            bloc_to_split[num_bloc]['ZMinMax'] = (Zmin, Zmax)
            bloc_to_split[num_bloc]['end_bloc']  = i-3
            
            #
            # 2/ Prepare the new bloc
            #
            num_bloc += 1
            num_sub_bloc +=1
            start_bloc = i-2
            new_name = name.strip()[:-1] + f'-{num_sub_bloc})\n'
            
            bloc_to_split[num_bloc] = {'strategy': f'{STRATEGY}\n', 
                                       'name': new_name, 
                                       'header': header,
                                       'start_bloc': start_bloc,
                                       'needs_header': True}
            bloc_found, cutting = True, False
            first_cutting_line  = None
            Zmin = None
         
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
         
del name, new_name, cutting, first_cutting_line, bloc_found, Z, Zmin, Zmax, 
del line, i, F, start_bloc, num_bloc, header, gcode_sub
         
# Now process each surfacing CAM operation to plit it into overlapping smaller 
# surfacing operations.

splitted_gcode = ""
start_line_number = 0

with open('tmpSubtractive4_split.gcode', 'w') as F:
   F.write("")

for key in bloc_to_split:
   bloc = bloc_to_split[key]
   print(f"Processing bloc {key}\n"
         f"\t(start, end):{(bloc['start_bloc'], bloc['end_bloc'])}\n"
         f"\tname:{repr(bloc['name'])}, needs_header:{bloc['needs_header']}\n"
         f"\theader:{repr(bloc['header'])}\n"
         f"\tstrategy:{repr(bloc['strategy'])}\n",
         f"\t(Zmin, Zmax):{bloc['ZMinMax']}\n")
   
   first_line_bloc, end_line_bloc = bloc['first_cutting_line'], bloc['end_bloc']
   Zmin, Zmax = bloc['ZMinMax']
   
   # Fill splitted_gcode with the Gcode lines until the firts line of the bloc:
   if bloc['needs_header']:
      splitted_gcode = bloc['name']
      splitted_gcode += bloc['strategy']
      splitted_gcode += bloc['header']
   else:
      splitted_gcode = ''
      
   splitted_gcode += ''.join(gcode_sub_lines[start_line_number:first_line_bloc])

   if abs(Zmax - Zmin) <= zRangeMax3Dsurfacing_mm: break
   
   first_split = True
   while(True):
   
      Z, prevZ, Z1, Z2 = None, None, None, None
      L1, L2, next_L1 = None, None, None
      cutting = False
      Z_increase = None
      
      # Every loop turn allows to build one of the overlapping bloc:
      
      for i, line in enumerate(gcode_sub_lines[first_line_bloc:end_line_bloc], first_line_bloc):
         
         if not cutting and line.startswith('(type: cutting)'):
            cutting = True
            continue
         
         elif cutting and line.startswith('('):
            cutting = False
            continue
         
         if cutting: 
            if line[:2] == 'G1': 
               Z = float(line.strip().split()[3][1:])
               if prevZ is not None:
                  
                  # JLC : Fusion BUG : sometime we find 2 consecive G1 lines with a differnce
                  #       between the 2 Z  of about 0.001 mm...
                  if abs(Z - prevZ) <= 0.001: continue
                  
                  if Z > prevZ: 
                     Z_increase = True
                  elif Z < prevZ:
                     Z_increase = False
               else:
                  prevZ = Z

               if Z1 == None :
                  Z1, L1 = Z, i
               else:
                  if next_L1 == None:
                     if abs(Z1 - Z) >= (zRangeMax3Dsurfacing_mm - zOverlap3Dsurfacing_mm):
                        next_L1 = i
                  if (abs(Z1 - Z) >= zRangeMax3Dsurfacing_mm) or (Z_increase and Z == Zmax) or (not Z_increase and Z == Zmin):
                     Z2 = Z
                     L2 = i
                     print(f"(Z1,Z2):({Z1:.3f},{Z2:.3f}), (L1,L2)={(L1,L2)}")
                     if first_split == False:
                        splitted_gcode += bloc['name']
                        splitted_gcode += bloc['strategy']
                        splitted_gcode += bloc['header']
                     splitted_gcode += ''.join(gcode_sub_lines[first_line_bloc:L2+1])
                     splitted_gcode += '\n'
   
                     with open('tmpSubtractive4_split.gcode', 'a') as F:
                        F.write(splitted_gcode)
                  
                     splitted_gcode = ""
                     if first_split: first_split = False
                     
                     # Ready to build the surfacing bloc.
                     # Normally the new bloc to process overlaps the current bloc
                     if next_L1 is not None: first_line_bloc = next_L1 + 1
                       
                     # come back to the while loop:
                     break      
                               
      if Z_increase is not None:     
         if (Z_increase and Z == Zmax) or (not Z_increase and Z == Zmin): 
            break
         
   start_line_number = end_line_bloc

   
splitted_gcode += ''.join(gcode_sub_lines[end_line_bloc:])

with open('tmpSubtractive4_split.gcode', 'a') as F:
   F.write(splitted_gcode)

