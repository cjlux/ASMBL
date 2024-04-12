import os

'''
To split surfacing operations with a large Z range into overlapping blocs
'''

zRangeMax3Dsurfacing_mm = 2
zOverlap3Dsurfacing_mm = 1

os.chdir('/home/jlc/work/01-github.com_cjlux/NAMMA/ASMBL-NAMMA/ASMBL-jlc/ASMBL/gcode')
with open('tmpSubtractive4.gcode', 'r') as F:
   gcode_sub = F.read()
   F.seek(0)
   gcode_sub_lines = F.readlines()

num_line_cutting = []
num_line_otherType = []
cutting_infos = []

cutting = False
for i, line in enumerate(gcode_sub_lines, 1):
   if '(type: cutting)' in line:
      #print(f'cutting line at <{i:10d}>')
      num_line_cutting.append(i)
      cutting = True
   elif '(type: ' in line:
      type = line.strip().split('(type: ')[1].replace(')','')
      #print(f'\t{type:10s} line at <{i:10d}>')
      num_line_otherType.append(i)

      if cutting:
         cutting = False
         splited_blocs = {}
         
         L1 = num_line_cutting[-1]+1
         Z1 = float(gcode_sub_lines[L1-1].split()[3].replace('Z',''))
         L2 = num_line_otherType[-1]-1
         Z2 = float(gcode_sub_lines[L2-1].split()[3].replace('Z',''))
         print(f"Z1, Z2: {Z1:.3f}, {Z2:.3f}")
         #assert Z1 >= Z2
         if Z1-Z2 >= zRangeMax3Dsurfacing_mm:
            nb_lines = L2 - L1 +1
            print(f'Z1:{Z1} line {L1}, Z2: {Z2} line {L2}')
            print(f'{nb_lines} lines for {zRangeMax3Dsurfacing_mm} mm')
            nb_lines_bloc = int(nb_lines * zOverlap3Dsurfacing_mm / zRangeMax3Dsurfacing_mm)
            print(f' {nb_lines_bloc} per splited bloc')
            num_bloc =1
            l1, l2 = L1, L1 + nb_lines_bloc -1
            while True:
               z1 = float(gcode_sub_lines[l1-1].split()[3].replace('Z',''))               
               z2 = float(gcode_sub_lines[l2-1].split()[3].replace('Z',''))
               print(f'bloc: {num_bloc} -> z1:{z1:.3f} line {l1}, z2: {z2:.3f} line {l2}')
               splited_blocs[num_bloc] = ((l1, l2), (z1, z2))
               if l2 == L2: break
               # find line number l1 for the overlapping:
               l1 = l2 -1
               z1 = float(gcode_sub_lines[l1-1].split()[3].replace('Z',''))
               while (z1 - z2 < zOverlap3Dsurfacing_mm):
                  l1 -= 1
                  z1 = float(gcode_sub_lines[l1-1].split()[3].replace('Z',''))
               l2 = l1 + nb_lines_bloc
               if l2 > L2: l2 = L2
               
               num_bloc += 1
               
            cutting_infos.append(splited_blocs)
         
# re-arrange the Gcode with splitted blocs :

prev_first_line_cut_bloc = 0
prev_last_line_cut_bloc  = 0
splitted_gcode = ''

for splited_blocs in cutting_infos:
   # splitted_bloc is a dict, with keys: 1,2...n
   first_line_cut_bloc = list(splited_blocs.values())[0][0][0]
   last_line_cut_bloc  = list(splited_blocs.values())[-1][0][1]

   splitted_gcode += ''.join(gcode_sub_lines[prev_last_line_cut_bloc:
                                            first_line_cut_bloc-2])

   num_blocs = len(splited_blocs)
   for n in range(1, num_blocs+1):
      (L1, L2), _ = splited_blocs[n]
      splitted_gcode += '(type: cutting)' + '\n'
      splitted_gcode += ''.join(gcode_sub_lines[L1-1:L2])

   prev_first_line_cut_bloc = first_line_cut_bloc
   prev_last_line_cut_bloc  = last_line_cut_bloc

splitted_gcode += ''.join(gcode_sub_lines[prev_last_line_cut_bloc:])

with open('tmpSubtractive4_splitted.gcode', 'w') as F:
   F.write(splitted_gcode)

                          
