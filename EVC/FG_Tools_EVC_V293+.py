bl_info = {
	'name':'EVC',
	'author':'IIFGIII',
	'version':(1, 0, 0),
	'blender':(2, 93, 0),
	"location": 'Viev3D > N panel > FGT > EVC',
	'description':'Tool that allow to editing vertex color from edit mesh mode. Big thanks to Yuriy Bozhyk for helping me with development ))',
	'warning'    :'',
	'doc_url'    :'https://github.com/IIIFGIII/FG_Tools/wiki/EVC',
	'category'   :'FG_Tools'
}


import bpy, bmesh, math, random, bgl, blf, gpu
from copy import copy
from mathutils import Matrix, Vector
from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import region_2d_to_location_3d as convert_screen_to_global 
from bpy_extras.view3d_utils import region_2d_to_origin_3d as convert_screen_to_global_origin

bpr = bpy.props
shd_uc = gpu.shader.from_builtin('3D_UNIFORM_COLOR')

shading_preserve = ['SOLID','MATCAP','MATERIAL',False]
nums_for_random = {'A':1, 'a':1, 'B':2, 'b':2, 'C':3, 'c':3, 'D':4, 'd':4, 'E':5, 'e':5, 'G':6, 'g':6, 'I':7, 'i':7, 'J':8, 'j':8, 'K':9, 'k':9, 'L':10, 'l':10, 'M':11, 'm':11, 'N':12, 'n':12,
 'O':13, 'o':13, 'P':14, 'p':14, 'Q':15, 'q':15, 'R':16, 'r':16, 'S':17, 's':17, 'T':18, 't':18, 'U':19, 'u':19, 'V':20, 'v':20, 'W':21, 'w':21, 'X':22, 'x':22, 'Y':23, 'y':23, 'Z':24, 'z':24,
 '0':0, '1':10, '2':20, '3':30, '4':40, '5':50, '6':60, '7':70, '8':80, '9':90}

color_palette = list()

def v3_to_v3_distance(va,vb):
	return math.sqrt((vb[0]-va[0])**2+(vb[1]-va[1])**2+(vb[2]-va[2])**2)

def vector_convert_to_matrix_inverted(mtr, pt_co = Vector((0,0,0))):
	return mtr.inverted() @ pt_co

def matrix_to_vector_row(mtr, row=0):
	return mtr.row[row].to_3d()

def remap_range(r_in_a, r_in_b, r_out_a, r_out_b, r_val):
	if r_in_a == r_in_b or r_out_a == r_out_b: return r_out_a
	elif r_in_a < r_in_b and r_val <= r_in_a: return r_out_a
	elif r_in_a > r_in_b and r_val >= r_in_a: return r_out_a
	elif r_in_b < r_in_a and r_val <= r_in_b: return r_out_b
	elif r_in_b > r_in_a and r_val >= r_in_b: return r_out_b
	else:
		r_in = r_in_b - r_in_a
		val_in = r_val - r_in_a
		r_out = r_out_b - r_out_a
		val_out = r_out_a + (r_out * (val_in/r_in))

		return val_out

def cast_ray(context, cursor_xy, custom_start_point= Vector((0,0,0)), use_custom_start_point= False):
	evc = context.scene.evc_props
	evc_p = context.preferences.addons[__name__].preferences
	cor = context.region
	s3d = context.space_data.region_3d
	mtr_view = s3d.view_matrix
	depsgraph = context.evaluated_depsgraph_get()

	if s3d.view_perspective == 'PERSP' or s3d.view_perspective == 'CAMERA':
		ray_start_point = vector_convert_to_matrix_inverted(mtr_view)
		ray_target_point = convert_screen_to_global(cor, s3d, cursor_xy, ((matrix_to_vector_row(s3d.view_matrix, 2) * -1) - ray_start_point))
		ray_vector = (ray_target_point - ray_start_point).normalized()
	else:
		ray_start_point = convert_screen_to_global_origin(cor, s3d, cursor_xy)
		ray_vector = matrix_to_vector_row(s3d.view_matrix, 2) * -1

	if use_custom_start_point:
		ray_result = context.scene.ray_cast(depsgraph, custom_start_point + (ray_vector * 0.001), ray_vector)
	else:
		ray_result = context.scene.ray_cast(depsgraph, ray_start_point, ray_vector)

	return ray_result

def set_loop_vertex_color(vc_edit_mode, col_msk, lp, llc, lp_color):
	if col_msk != 'RGBA':
		if vc_edit_mode == 'SET':
			if 'R' in col_msk: lp[llc][0] = lp_color[0]
			if 'G' in col_msk: lp[llc][1] = lp_color[1]
			if 'B' in col_msk: lp[llc][2] = lp_color[2]
			if 'A' in col_msk: lp[llc][3] = lp_color[3]
		elif vc_edit_mode == 'ADD':
			if 'R' in col_msk: lp[llc][0] = lp[llc][0] + lp_color[0]
			if 'G' in col_msk: lp[llc][1] = lp[llc][1] + lp_color[1]
			if 'B' in col_msk: lp[llc][2] = lp[llc][2] + lp_color[2]
			if 'A' in col_msk: lp[llc][3] = lp[llc][3] + lp_color[3]
		elif vc_edit_mode == 'SUB':
			if 'R' in col_msk: lp[llc][0] = lp[llc][0] - lp_color[0]
			if 'G' in col_msk: lp[llc][1] = lp[llc][1] - lp_color[1]
			if 'B' in col_msk: lp[llc][2] = lp[llc][2] - lp_color[2]
			if 'A' in col_msk: lp[llc][3] = lp[llc][3] - lp_color[3]

	else:
		if vc_edit_mode == 'SET':	lp[llc] = lp_color
		elif vc_edit_mode == 'ADD':	lp[llc] = lp[llc] + lp_color
		elif vc_edit_mode == 'SUB':	lp[llc] = lp[llc] - lp_color
			

def object_seed_generator(base_seed, ob_name):
	global nums_for_random
	
	object_seed = 0

	for c in ob_name:
		if c in nums_for_random.keys():
			object_seed += nums_for_random.get(c)
		else:
			object_seed += 1

	object_seed += base_seed

	return object_seed

def randomization_factor(r_factor):
	r_num = random.random()

	if r_factor < 0:
		r_num = pow(r_num, remap_range(-1, 0, 20, 1, r_factor))
	elif r_factor > 0:
		r_num = pow(r_num, remap_range(0, 1, 1, 0.1, r_factor))
	return r_num

def color_randomizer(vl_id, col_in, r_factor, col_sub, col_add, r_seed, r_chn):
	col_out = col_in
	col_r,col_g,col_b,col_a = col_in[0],col_in[1],col_in[2],col_in[3]

	if 'R' in r_chn:
		c_add = 10 * r_seed
		random.seed(vl_id + r_seed + c_add)
		r_num = randomization_factor(r_factor)
		col_min = col_in[0] + col_sub/255 if (col_in[0] + col_sub/255) >= 0 else 0
		col_max = col_in[0] + col_add/255 if (col_in[0] + col_add/255) <= 1 else 1
		col_r = round(remap_range(0,1,col_min,col_max,r_num)*255)/255

	if 'G' in r_chn:
		c_add = 21 * r_seed
		random.seed(vl_id + r_seed + c_add)
		r_num = randomization_factor(r_factor)
		col_min = col_in[1] + col_sub/255 if (col_in[1] + col_sub/255) >= 0 else 0
		col_max = col_in[1] + col_add/255 if (col_in[1] + col_add/255) <= 1 else 1
		col_g = round(remap_range(0,1,col_min,col_max,r_num)*255)/255

	if 'B' in r_chn:
		c_add = 32 * r_seed
		random.seed(vl_id + r_seed + c_add)
		r_num = randomization_factor(r_factor)
		col_min = col_in[2] + col_sub/255 if (col_in[2] + col_sub/255) >= 0 else 0
		col_max = col_in[2] + col_add/255 if (col_in[2] + col_add/255) <= 1 else 1
		col_b = round(remap_range(0,1,col_min,col_max,r_num)*255)/255

	if 'A' in r_chn:
		c_add = 44 * r_seed
		random.seed(vl_id + r_seed + c_add)
		r_num = randomization_factor(r_factor)
		col_min = col_in[3] + col_sub/255 if (col_in[3] + col_sub/255) >= 0 else 0
		col_max = col_in[3] + col_add/255 if (col_in[3] + col_add/255) <= 1 else 1
		col_a = round(remap_range(0,1,col_min,col_max,r_num)*255)/255

	return Vector((col_r,col_g,col_b,col_a))

def ray_cast_check(self, context):
	sob_n = [ob.name for ob in bpy.context.view_layer.objects.selected]
	hit_vallid_object = False
	no_hit = False
	raycast_n = 0
	hit_loc = Vector((0,0,0))
	hit_pid = 0
	hit_obn = ''

	while not hit_vallid_object and not no_hit:
		ray_result = cast_ray(context, self.cursor_xy) if raycast_n == 0 else cast_ray(context, self.cursor_xy, hit_loc, True)
		ray_hit = ray_result[0]

		if ray_hit:
			hit_loc = ray_result[1]
			hit_pid = ray_result[3]
			hit_obn = ray_result[4].name

			if bpy.data.objects[hit_obn].mode == 'EDIT' and bpy.data.objects[hit_obn].type == 'MESH':
				bpy.context.view_layer.objects.active = bpy.data.objects[hit_obn]
				bmd = bmesh.from_edit_mesh(context.edit_object.data)
				if bmd.faces[hit_pid].hide:
					still_in_edit = True
					hit_hidden = True
					while ray_hit and still_in_edit and hit_hidden:
						ray_result = cast_ray(context, self.cursor_xy, hit_loc, True)
						ray_hit = ray_result[0]
						if ray_hit:
							hit_loc = ray_result[1]
							hit_pid = ray_result[3]
							hit_obn = ray_result[4].name
							still_in_edit = True if bpy.data.objects[hit_obn].mode == 'EDIT' and bpy.data.objects[hit_obn].type == 'MESH' else False
							if still_in_edit:
								bpy.context.view_layer.objects.active = bpy.data.objects[hit_obn]
								bmd = bmesh.from_edit_mesh(context.edit_object.data)
								hit_hidden = True if bmd.faces[hit_pid].hide else False

			if ray_hit:
				if bpy.data.objects[hit_obn].type == 'MESH':
					if self.get_selected_only:
						hit_vallid_object = True if hit_obn in sob_n else False
					else:
						hit_vallid_object = True
			else:
				no_hit = True

		else:
			no_hit = True

		raycast_n += 1

	return hit_vallid_object, no_hit, hit_loc, hit_pid, hit_obn

def get_hit_lines_color(hit_loc, hit_pid, hit_obn, color_only= False):
	obm = bpy.data.objects[hit_obn].matrix_world

	if bpy.data.objects[hit_obn].mode == 'EDIT':
		bmd = bmesh.from_edit_mesh(bpy.context.edit_object.data)
		vtcscoids = [(obm @ vtc.co, vtc.index) for vtc in bmd.faces[hit_pid].verts]
	else:
		obd = bpy.data.objects[hit_obn].data
		vtcscoids = [(obm @ obd.vertices[vtc].co, vtc) for vtc in obd.polygons[hit_pid].vertices]

	dist,closest,cvtcid = 0,Vector((0,0,0)),0

	for enm,vtc in enumerate(vtcscoids):
		dist_to_vtc = v3_to_v3_distance(vtc[0], hit_loc)
		if enm == 0:
			dist = dist_to_vtc
			closest = vtc[0][:]
			cvtcid = vtc[1]
		if dist_to_vtc <= dist:
			dist = dist_to_vtc
			closest = vtc[0][:]
			cvtcid = vtc[1]

	if not color_only:
		get_lines = list()
		for enm,vtc in enumerate(vtcscoids):
			get_lines.append(vtc[0][:])
			get_lines.append(vtcscoids[(enm+1)%len(vtcscoids)][0][:])
		get_lines.append(hit_loc[:])
		get_lines.append(closest)

	get_color = (0,0,0,-1)

	if len(bpy.data.objects[hit_obn].data.vertex_colors) != 0:
		active_vc = bpy.data.objects[hit_obn].data.vertex_colors.active_index

		if bpy.data.objects[hit_obn].mode == 'EDIT':
			for lp in bmd.faces[hit_pid].loops:
				if lp.vert.index == cvtcid:
					get_color = lp[bmd.loops.layers.color[active_vc]][:]
					break

		else:
			ob_vc_data = bpy.data.objects[hit_obn].data.vertex_colors[active_vc]
			for lp_n in range(obd.polygons[hit_pid].loop_total):
				lp_id = obd.polygons[hit_pid].loop_indices[lp_n]
				if obd.loops[lp_id].vertex_index == cvtcid:
					get_color = ob_vc_data.data[lp_id].color[:]
					break

	if not color_only:
		return [get_lines,get_color]
	else:
		return get_color

def draw_points_uc(coordinates,color,point_size=1):
	batch = batch_for_shader(shd_uc, 'POINTS', {'pos': coordinates})
	bgl.glPointSize(point_size)
	shd_uc.bind()
	shd_uc.uniform_float("color", color)
	batch.draw(shd_uc)
	bgl.glPointSize(1)

def draw_lines_uc(coordinates,color,line_width=1):
	batch = batch_for_shader(shd_uc, 'LINES', {'pos': coordinates})
	bgl.glLineWidth(line_width)
	shd_uc.bind()
	shd_uc.uniform_float("color", color)
	batch.draw(shd_uc)
	bgl.glLineWidth(1)

def draw_rectangle_uc(coordinates,color,indices):
	batch = batch_for_shader(shd_uc, 'TRIS', {'pos': coordinates}, indices = indices)
	shd_uc.bind()
	shd_uc.uniform_float("color", color)
	batch.draw(shd_uc)

def draw_pick_color_lines(self,context):
	evc = context.scene.evc_props

	bgl.glDisable(bgl.GL_DEPTH_TEST)

	if evc.draw_hit:
		draw_lines_uc(self.draw_lines_color[0], (0,0,0,1), 6)		
		draw_lines_uc(self.draw_lines_color[0], (1,1,1,1), 2)

def draw_pick_color_info(self,context):
	evc = context.scene.evc_props

	if evc.draw_hit:
		dcl = self.draw_lines_color[1]
		scs_x = context.region.width
		csr_xyz = Vector((self.cursor_xy[0],self.cursor_xy[1],0))
		flip = True if self.cursor_xy[0] >= scs_x/2 else False

		if not flip:
			box_coord = [ (csr_xyz + Vector((30,6,0)))[:], (csr_xyz + Vector((435,6,0)))[:], (csr_xyz + Vector((435,-30,0)))[:], (csr_xyz + Vector((30,-30,0)))[:] ]
		else:
			box_coord = [ (csr_xyz + Vector((-30,6,0)))[:], (csr_xyz + Vector((-435,6,0)))[:], (csr_xyz + Vector((-435,-30,0)))[:], (csr_xyz + Vector((-30,-30,0)))[:] ]

		draw_rectangle_uc(box_coord,(0.1, 0.1, 0.1, 1), ((0, 1, 2), (0, 2, 3)))

		if dcl[3] != -1:
			draw_points_uc([(csr_xyz + Vector((48 if not flip else -416,-12,0)))[:]], (dcl[0],dcl[1],dcl[2],1),point_size=28)
			draw_points_uc([(csr_xyz + Vector((340 if not flip else -124,-12,0)))[:]], (dcl[3],dcl[3],dcl[3],1),point_size=28)

		fnt = 0
		blf.position(fnt, self.cursor_xy[0] + 70 if not flip else self.cursor_xy[0] - 394, self.cursor_xy[1] - 20, 0)
		blf.color(fnt, 1, 1, 1, 1)
		blf.size(fnt, 25, 70)

		if dcl[3] == -1:
			blf.draw(fnt, ' NO VERTEX COLOR DATA')
		else:
			clr	= round(dcl[0]*255)
			clg	= round(dcl[1]*255)
			clb	= round(dcl[2]*255)
			cla	= round(dcl[3]*255)
			txclr = str(clr) if len(str(clr)) == 3 else ' ' + str(clr) + ' ' if len(str(clr)) == 2 else '  ' + str(clr) + '  '
			txclg = str(clg) if len(str(clg)) == 3 else ' ' + str(clg) + ' ' if len(str(clg)) == 2 else '  ' + str(clg) + '  '
			txclb = str(clb) if len(str(clb)) == 3 else ' ' + str(clb) + ' ' if len(str(clb)) == 2 else '  ' + str(clb) + '  '
			txcla = str(cla) if len(str(cla)) == 3 else ' ' + str(cla) + ' ' if len(str(cla)) == 2 else '  ' + str(cla) + '  '
			blf.draw(fnt, 'R ' + txclr + ' | G ' + txclg + ' | B ' + txclb + '      A ' + txcla)

def loops_preparation(sob_em, freestyle_mask, face_mask, paint_hidden, create_vc_data= False):
	obn_loops = dict()

	for obn in sob_em:
		if len(bpy.data.objects[obn].data.vertex_colors) != 0 or create_vc_data: # Skip if no VC data
			bpy.context.view_layer.objects.active = bpy.data.objects[obn]

			if create_vc_data and len(bpy.data.objects[obn].data.vertex_colors) == 0:
				bpy.ops.geometry.attribute_add(name="Col",  domain='CORNER', data_type='BYTE_COLOR')
				if  len(bpy.data.objects[obn].data.vertex_colors) == 0: # Fix for 2.93 where vertex color is not in attributes
					bpy.ops.mesh.vertex_color_add()
				bpy.data.objects[obn].data.vertex_colors.active_index = 0

			bmd = bmesh.from_edit_mesh(bpy.context.edit_object.data)

			lps_selected = list()
			for vtc in bmd.verts:
				if vtc.select:
					vtc_id = vtc.index
					if not len(vtc.link_faces) == 0:
						for fc in vtc.link_faces:
							if face_mask:
								if fc.select:
									for lp in fc.loops:
										if lp.vert.index == vtc_id:
											lps_selected.append(lp.index)
							else:
								if paint_hidden:
									for lp in fc.loops:
										if lp.vert.index == vtc_id:
											lps_selected.append(lp.index)
								elif not fc.hide:
									for lp in fc.loops:
										if lp.vert.index == vtc_id:
											lps_selected.append(lp.index)

			if lps_selected == []: continue # Skip if no selected loops

			if freestyle_mask: # Check for freestyle masking
				bpy.data.objects[obn].update_from_editmode()
				ob_pl_data = bpy.data.objects[obn].data.id_data.polygons
				for pl in ob_pl_data:
					if not pl.use_freestyle_mark:
						for lnum in range(pl.loop_total):
							lp_id = pl.loop_indices[lnum]
							if lp_id in lps_selected:
								lps_selected.pop(lps_selected.index(lp_id))

			if lps_selected != []:
				obn_loops.update({obn:lps_selected})

	return obn_loops

def similar_color_check(main_col, col_to_check, sim_col_sub, sim_col_add, check_channels):
	check_r = True if (round(main_col[0]*255) + sim_col_sub <= round(col_to_check[0]*255) <= round(main_col[0]*255) + sim_col_add) or 'R' not in check_channels else False
	check_g = True if (round(main_col[1]*255) + sim_col_sub <= round(col_to_check[1]*255) <= round(main_col[1]*255) + sim_col_add) or 'G' not in check_channels else False
	check_b = True if (round(main_col[2]*255) + sim_col_sub <= round(col_to_check[2]*255) <= round(main_col[2]*255) + sim_col_add) or 'B' not in check_channels else False
	check_a = True if (round(main_col[3]*255) + sim_col_sub <= round(col_to_check[3]*255) <= round(main_col[3]*255) + sim_col_add) or 'A' not in check_channels else False

	return check_r and check_b and check_g and check_a


class EVC_PT_Panel(bpy.types.Panel):
	bl_label = 'EVC'
	bl_idname = 'EVC_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_options = {'DEFAULT_CLOSED'}


	def draw(self,context):
		global shading_preserve
		global color_palette

		evc = context.scene.evc_props

		layout = self.layout
		col = layout.column(align=True) # --------------------------------------------

		switch_row = col.row(align=True)
		switch_row.scale_y = 0.85
		overlay_switch = switch_row.row(align=True)
		overlay_switch.emboss = 'PULLDOWN_MENU'if not bpy.context.space_data.overlay.show_faces else 'NORMAL'
		overlay_text = 'Overlay OFF' if not bpy.context.space_data.overlay.show_faces else 'Overlay ON'
		overlay_switch.operator('fgt.evc_switch_faces_overlay', icon='MOD_UVPROJECT', text= overlay_text)

		shading = bpy.context.space_data.shading
		shading_switch =switch_row.row(align=True)
		if shading_preserve[3] == False and shading.type == 'SOLID' and shading.light == 'FLAT' and shading.color_type== 'VERTEX':
			shading_switch.emboss = 'PULLDOWN_MENU'
			shading_switch.operator('fgt.evc_switch_flat_color_view', icon='MOD_UVPROJECT', text= 'Solid Mode').switch_to_flat= 0

		elif shading_preserve[3] == True and shading.type == 'SOLID' and shading.light == 'FLAT' and shading.color_type== 'VERTEX':
			shading_switch.emboss = 'PULLDOWN_MENU'
			shading_switch.operator('fgt.evc_switch_flat_color_view', icon='MOD_UVPROJECT', text= 'Switch Back').switch_to_flat= 2 		

		elif shading_preserve[3] == False and (not shading.type == 'SOLID' or not shading.light == 'FLAT' or not shading.color_type== 'VERTEX'):
			shading_switch.emboss = 'NORMAL'
			shading_switch.operator('fgt.evc_switch_flat_color_view', icon='MOD_UVPROJECT', text= 'Flat Shading').switch_to_flat= 1

		elif shading_preserve[3] == True and (not shading.type == 'SOLID' or not shading.light == 'FLAT' or not shading.color_type== 'VERTEX'):
			shading_switch.emboss = 'NORMAL'
			shading_preserve = ['SOLID','MATCAP','MATERIAL',False]
			shading_switch.operator('fgt.evc_switch_flat_color_view', icon='MOD_UVPROJECT', text= 'Flat Shading').switch_to_flat= 1 

		col.separator(factor=0.3) # -----------------------------------------------

		row = col.row(align=True)
		row.scale_y = 0.9
		row.prop(evc,'paint_freestyle_mask_base', text= 'Freestyle Mask', toggle=True)
		srow = row.row(align=True)
		srow.scale_x = 0.712
		srow.operator('mesh.mark_freestyle_face',icon='SNAP_VOLUME', text= 'Mark').clear= False
		srow.operator('mesh.mark_freestyle_face',icon='META_CUBE', text= 'Clear').clear= True

		col.separator(factor=0.2)

		row = col.row(align=True)
		row.scale_y = 0.9
		row.prop(evc,'paint_face_mask_base', text= 'Face Mask', toggle=True)
		srow = row.row(align=True)
		srow.enabled = True if not evc.paint_face_mask_base else False
		srow.prop(evc,'paint_hidden_base', text= 'Paint Hidden', toggle=True)
		
		col.separator(factor=0.3) # -----------------------------------------------

		row = col.row(align=True)
		row.scale_y = 0.7
		row.prop(evc,'paint_color_mask_r', text= 'R', toggle= True)
		row.prop(evc,'paint_color_mask_g', text= 'G', toggle= True)
		row.prop(evc,'paint_color_mask_b', text= 'B', toggle= True)
		row.prop(evc,'paint_color_mask_a', text= 'A', toggle= True)

		row = col.row(align=True)
		row.scale_y = 0.9
		row.prop(evc,'vc_mode_set_base', text= 'Set', toggle= True)
		row.prop(evc,'vc_mode_add_base', text= 'Add', toggle= True)
		row.prop(evc,'vc_mode_sub_base', text= 'Sub', toggle= True)

		if   evc.vc_mode_set_base: edit_mode = 'Set'
		elif evc.vc_mode_add_base: edit_mode = 'Add'
		elif evc.vc_mode_sub_base: edit_mode = 'Subtract'

		row = col.row(align=True)
		row.scale_y = 0.9
		set_color = row.operator('fgt.evc_set_color',icon='BRUSH_DATA', text= edit_mode + ' VC')
		set_color.vc_edit_mode = 'SET' if evc.vc_mode_set_base else 'ADD' if evc.vc_mode_add_base else 'SUB'
		set_color.color_r = evc.paint_color_base_r
		set_color.color_g = evc.paint_color_base_g
		set_color.color_b = evc.paint_color_base_b
		set_color.color_a = evc.paint_color_base_a
		set_color.paint_freestyle_mask = evc.paint_freestyle_mask_base
		set_color.paint_face_mask = evc.paint_face_mask_base
		set_color.paint_hidden = evc.paint_hidden_base if not evc.paint_face_mask_base else False

		col_msk_chn = 'RGBA'
		if not evc.paint_color_mask_r or not evc.paint_color_mask_g or not evc.paint_color_mask_b or not evc.paint_color_mask_a:
			col_msk_chn = ''
			if evc.paint_color_mask_r: col_msk_chn += 'R'
			if evc.paint_color_mask_g: col_msk_chn += 'G'
			if evc.paint_color_mask_b: col_msk_chn += 'B'
			if evc.paint_color_mask_a: col_msk_chn += 'A'
		set_color.paint_col_msk_chn = col_msk_chn

		set_color.paint_rand = evc.paint_randomize
		set_color.paint_rand_static = evc.paint_randomize_static
		set_color.paint_rand_only = evc.paint_randomized_only
		set_color.paint_rand_seed = evc.paint_randomize_seed
		set_color.paint_rand_prc = evc.paint_randomize_percentage 
		set_color.paint_rand_fct = evc.paint_randomize_factor
		set_color.paint_rand_sub = evc.paint_randomize_sub
		set_color.paint_rand_add = evc.paint_randomize_add

		set_color.paint_rand_lvpe = 'L' if evc.paint_randomize_l else 'V' if evc.paint_randomize_v else 'P' if evc.paint_randomize_p else 'E'

		rand_chn = 'RGBA'
		if evc.paint_randomize_r or evc.paint_randomize_g or evc.paint_randomize_b or  evc.paint_randomize_a:
			rand_chn = ''
			if evc.paint_randomize_r: rand_chn += 'R'
			if evc.paint_randomize_g: rand_chn += 'G'
			if evc.paint_randomize_b: rand_chn += 'B'
			if evc.paint_randomize_a: rand_chn += 'A'
		set_color.paint_rand_chn = rand_chn

		row.prop(evc,'paint_color_base')

		col.separator(factor=0.3) # -----------------------------------------------

		row = col.row(align=True)
		row.scale_y = 0.85
		getvc = row.operator('fgt.evc_raycast_pick_color', icon='VIS_SEL_11', text= 'GET')
		getvc.get_selected_only = True if evc.get_vc_in_selected else False
		row.prop(evc, 'get_vc_in_selected', text= 'SOB', icon= 'BORDERMOVE')	
		srow = row.row(align=True)
		srow.scale_x = 1.421
		srow.enabled = True if evc.paint_color_mask_r else False
		srow.prop(evc,'paint_color_base_r', text= 'R')

		row = col.row(align=True)
		row.scale_y = 0.85
		row.operator('fgt.evc_update_paint_color', icon='PROPERTIES', text= 'BC').new_color = (0,0,0,1)
		row.operator('fgt.evc_update_paint_color', icon='PROPERTIES', text= 'RG').new_color = (1,1,0,1)
		srow = row.row(align=True)
		srow.scale_x = 1.421
		srow.enabled = True if evc.paint_color_mask_g else False
		srow.prop(evc,'paint_color_base_g', text= 'G')

		row = col.row(align=True)
		row.scale_y = 0.85
		row.operator('fgt.evc_update_paint_color', icon='PROPERTIES', text= 'GR').new_color = (0.5,0.5,0.5,1)
		row.operator('fgt.evc_update_paint_color', icon='PROPERTIES', text= 'RB').new_color = (1,0,1,1)  
		srow = row.row(align=True)
		srow.scale_x = 1.421
		srow.enabled = True if evc.paint_color_mask_b else False
		srow.prop(evc,'paint_color_base_b', text= 'B') 

		row = col.row(align=True)
		row.scale_y = 0.85
		row.operator('fgt.evc_update_paint_color', icon='PROPERTIES', text= 'WT').new_color = (1,1,1,1)
		row.operator('fgt.evc_update_paint_color', icon='PROPERTIES', text= 'GB').new_color = (0,1,1,1)
		srow = row.row(align=True)
		srow.scale_x = 1.421
		srow.enabled = True if evc.paint_color_mask_a else False
		srow.prop(evc,'paint_color_base_a', text= 'A') 

		col.separator(factor=0.4) # -----------------------------------------------

		row = col.row(align=True)
		row.scale_y = 0.7
		eblt = str(round(evc.eight_bit_line/255, 6)) + '  in 8-bit ='
		row.prop(evc, 'eight_bit_line', text= eblt)		

		col.separator(factor=0.4) # -----------------------------------------------

		rnd_text_mode = 'Randomize Per Loop' if evc.paint_randomize_l else 'Randomize Per Vertex' if evc.paint_randomize_v else 'Randomize Per Polygon' if evc.paint_randomize_p else 'Randomize Per Element'
		rnd_text_idle = 'Randomize Set Color ' if evc.vc_mode_set_base else 'Randomize Add Color' if evc.vc_mode_add_base else 'Randomize Subtract Color'
		rnd_text = rnd_text_mode if evc.paint_randomize else rnd_text_idle
		row = col.row(align=True)
		row.scale_y = 0.95
		row.prop(evc,'paint_randomize', icon= 'OPTIONS', text= rnd_text)
		if evc.paint_randomize:
			row = col.row(align=True)
			row.scale_y = 0.85
			row.prop(evc,'paint_randomize_l', text= 'Loop', toggle= True)
			row.prop(evc,'paint_randomize_v', text= 'Vertex', toggle= True)
			row.prop(evc,'paint_randomize_p', text= 'Polygon', toggle= True)
			row.prop(evc,'paint_randomize_e', text= 'Element', toggle= True)
			row = col.row(align=True)
			row.scale_y = 0.85
			row.prop(evc,'paint_randomize_seed', text= 'Seed')
			row.prop(evc,'paint_randomize_static', text= 'Static Seed?', toggle= True) 
			row = col.row(align=True)
			row.scale_y = 0.85
			row.prop(evc,'paint_randomized_only', text= 'Paint Randomized Elements Only', toggle= True)
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'paint_randomize_percentage', text= 'Randomize %')
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'paint_randomize_factor', text= 'Randomize Factor')
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'paint_randomize_sub', text= 'VC-')
			row.prop(evc,'paint_randomize_add',  text= 'VC+')
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'paint_randomize_r', text= 'R', toggle= True)
			row.prop(evc,'paint_randomize_g', text= 'G', toggle= True)
			row.prop(evc,'paint_randomize_b', text= 'B', toggle= True)
			row.prop(evc,'paint_randomize_a', text= 'A', toggle= True)

		col.separator(factor=0.4) # -----------------------------------------------

		adt_text = 'Collapse Additional Tools' if evc.additional_tools else 'Expand Additional Tools'
		row = col.row(align=True)
		row.scale_y = 0.95
		row.prop(evc,'additional_tools', icon= 'PRESET_NEW', text= adt_text)


		if evc.additional_tools:

			col.separator(factor=0.5) # -----------------------------------------------

			row = col.row(align=True)
			row.scale_y = 0.9
			ssvc = row.operator('fgt.evc_select_similar_vc', icon='ZOOM_SELECTED', text= 'Select Similar' )
			ssvc.sim_cl_r = evc.paint_color_base_r
			ssvc.sim_cl_g = evc.paint_color_base_g
			ssvc.sim_cl_b = evc.paint_color_base_b
			ssvc.sim_cl_a = evc.paint_color_base_a
			ssvc.sim_cl_mode = 'V' if evc.similar_vc_mode_v else 'F'
			sim_channels = 'RGBA'
			if evc.similar_vc_r or evc.similar_vc_g or evc.similar_vc_b or evc.similar_vc_a:
				sim_channels = ''
				if evc.similar_vc_r: sim_channels += 'R'
				if evc.similar_vc_g: sim_channels += 'G'
				if evc.similar_vc_b: sim_channels += 'B'
				if evc.similar_vc_a: sim_channels += 'A'
			ssvc.sim_cl_chn = sim_channels
			ssvc.sim_cl_in_sel = evc.similar_vc_in_sel
			ssvc.sim_cl_sub = evc.similar_vc_sub
			ssvc.sim_cl_add = evc.similar_vc_add
			row.prop(evc, 'similar_vc_in_sel', icon= 'BORDERMOVE', text= 'In Selection')
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'similar_vc_mode_v', text= 'Vertices', toggle= True)
			row.prop(evc,'similar_vc_mode_f', text= 'Faces', toggle= True)

			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'similar_vc_sub', text= 'VC-')
			row.prop(evc,'similar_vc_add',  text= 'VC+')
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'similar_vc_r', text= 'R', toggle= True)
			row.prop(evc,'similar_vc_g', text= 'G', toggle= True)
			row.prop(evc,'similar_vc_b', text= 'B', toggle= True)
			row.prop(evc,'similar_vc_a', text= 'A', toggle= True)

			col.separator(factor=0.5) # -----------------------------------------------

			mcs_a_ch = 'R' if evc.mcs_a_channel_r else 'G' if evc.mcs_a_channel_g else 'B' if evc.mcs_a_channel_b else 'A'
			mcs_b_ch = 'R' if evc.mcs_b_channel_r else 'G' if evc.mcs_b_channel_g else 'B' if evc.mcs_b_channel_b else 'A'
			if evc.mcs_move_mode: mcs_text = 'Move VC from ' + mcs_a_ch + ' to ' + mcs_b_ch
			elif evc.mcs_copy_mode: mcs_text = 'Copy VC from ' + mcs_a_ch + ' to ' + mcs_b_ch
			else:  mcs_text = 'Swap VC between ' + mcs_a_ch + ' and ' + mcs_b_ch

			row = col.row(align=True)
			row.scale_y = 0.9
			mcs = row.operator('fgt.evc_move_copy_swap', icon='SHADERFX', text= mcs_text )
			mcs.mcs_mode = 'MOV' if evc.mcs_move_mode else 'COP' if evc.mcs_copy_mode else 'SWP'
			mcs.mcs_a_channel = 'R' if evc.mcs_a_channel_r else 'G' if evc.mcs_a_channel_g else 'B' if evc.mcs_a_channel_b else 'A'
			mcs.mcs_b_channel = 'R' if evc.mcs_b_channel_r else 'G' if evc.mcs_b_channel_g else 'B' if evc.mcs_b_channel_b else 'A'
			mcs.mcs_freestyle_mask = evc.paint_freestyle_mask_base
			mcs.mcs_face_mask = evc.paint_face_mask_base
			mcs.mcs_hidden = evc.paint_hidden_base if not evc.paint_face_mask_base else False

			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'mcs_a_channel_r', text= 'R', toggle= True)
			row.prop(evc,'mcs_a_channel_g', text= 'G', toggle= True)
			row.prop(evc,'mcs_a_channel_b', text= 'B', toggle= True)
			row.prop(evc,'mcs_a_channel_a', text= 'A', toggle= True)
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'mcs_move_mode', text= 'Move', toggle= True)
			row.prop(evc,'mcs_copy_mode', text= 'Copy', toggle= True)
			row.prop(evc,'mcs_swap_mode', text= 'Swap', toggle= True)
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'mcs_b_channel_r', text= 'R', toggle= True)
			row.prop(evc,'mcs_b_channel_g', text= 'G', toggle= True)
			row.prop(evc,'mcs_b_channel_b', text= 'B', toggle= True)
			row.prop(evc,'mcs_b_channel_a', text= 'A', toggle= True)

			col.separator(factor=0.5) # -----------------------------------------------

			vmp_text = 'VC Mlt + Pow' if evc.vc_mp_mode_a else 'VC Pow + Mlt'
			row = col.row(align=True)
			row.scale_y = 0.9
			vmp = row.operator('fgt.evc_multiply_power', icon='SHADERFX', text= vmp_text )
			vmp.vc_mp_mode = 'MP' if evc.vc_mp_mode_a else 'PM'
			vmp.vc_mp_mlt = evc.vc_mp_multiplier
			vmp.vc_mp_exp = evc.vc_mp_exponent
			vc_mp_chn = 'RGBA'
			if evc.vc_mp_channel_r or evc.vc_mp_channel_g or evc.vc_mp_channel_b or evc.vc_mp_channel_a:
				vc_mp_chn = ''
				if evc.vc_mp_channel_r: vc_mp_chn +='R'
				if evc.vc_mp_channel_g: vc_mp_chn +='G'
				if evc.vc_mp_channel_b: vc_mp_chn +='B'
				if evc.vc_mp_channel_a: vc_mp_chn +='A'
			vmp.vc_mp_channel = vc_mp_chn
			vmp.vc_mp_freestyle_mask = evc.paint_freestyle_mask_base
			vmp.vc_mp_face_mask = evc.paint_face_mask_base
			vmp.vc_mp_hidden = evc.paint_hidden_base if not evc.paint_face_mask_base else False
			srow = row.row(align=True)
			srow.scale_x = 0.712
			srow.prop(evc,'vc_mp_mode_a', text= 'M+P', toggle=True)
			srow.prop(evc,'vc_mp_mode_b', text= 'P+M', toggle=True)

			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'vc_mp_multiplier', text= 'Multiplier')
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'vc_mp_exponent', text= 'Exponent')
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'vc_mp_channel_r', text= 'R', toggle= True)
			row.prop(evc,'vc_mp_channel_g', text= 'G', toggle= True)
			row.prop(evc,'vc_mp_channel_b', text= 'B', toggle= True)
			row.prop(evc,'vc_mp_channel_a', text= 'A', toggle= True)

			col.separator(factor=0.5) # -----------------------------------------------

			row = col.row(align=True)
			row.scale_y = 0.9
			vinv = row.operator('fgt.evc_invert_color', icon='CON_ACTION', text= 'INVERT' )
			vc_inv_chn = 'RGBA'
			if evc.vc_inv_channel_r or evc.vc_inv_channel_g or evc.vc_inv_channel_b or evc.vc_inv_channel_a:
				vc_inv_chn = ''
				if evc.vc_inv_channel_r: vc_inv_chn +='R'
				if evc.vc_inv_channel_g: vc_inv_chn +='G'
				if evc.vc_inv_channel_b: vc_inv_chn +='B'
				if evc.vc_inv_channel_a: vc_inv_chn +='A'
			vinv.vc_inv_channel = vc_inv_chn
			vinv.vc_inv_freestyle_mask = evc.paint_freestyle_mask_base
			vinv.vc_inv_face_mask = evc.paint_face_mask_base
			vinv.vc_inv_hidden = evc.paint_hidden_base if not evc.paint_face_mask_base else False
			row = col.row(align=True)
			row.scale_y = 0.7
			row.prop(evc,'vc_inv_channel_r', text= 'R', toggle= True)
			row.prop(evc,'vc_inv_channel_g', text= 'G', toggle= True)
			row.prop(evc,'vc_inv_channel_b', text= 'B', toggle= True)
			row.prop(evc,'vc_inv_channel_a', text= 'A', toggle= True)

		col.separator(factor=0.4) # -----------------------------------------------

		cpt_text = 'Collapse Color Palette' if evc.expand_palette else 'Expand Color Palette'
		row = col.row(align=True)
		row.scale_y = 0.9
		row.prop(evc,'expand_palette', icon= 'COLOR', text= cpt_text)

		if evc.expand_palette:

			if color_palette != []:
				for enm,clval in enumerate(color_palette):
					row = col.row(align=True)
					row.scale_y = 0.8
					ptclr = str(clval[0]) if len(str(clval[0])) == 3 else ' ' + str(clval[0]) + ' ' if len(str(clval[0])) == 2 else '  ' + str(clval[0]) + '  '
					ptclg = str(clval[1]) if len(str(clval[1])) == 3 else ' ' + str(clval[1]) + ' ' if len(str(clval[1])) == 2 else '  ' + str(clval[1]) + '  '
					ptclb = str(clval[2]) if len(str(clval[2])) == 3 else ' ' + str(clval[2]) + ' ' if len(str(clval[2])) == 2 else '  ' + str(clval[2]) + '  '
					ptcla = str(clval[3]) if len(str(clval[3])) == 3 else ' ' + str(clval[3]) + ' ' if len(str(clval[3])) == 2 else '  ' + str(clval[3]) + '  '
					ptclt = ptclr + ' | ' + ptclg + ' | ' + ptclb + ' | ' + ptcla
					palette_color = row.operator('fgt.evc_update_paint_color', text= ptclt)
					palette_color.new_color = Vector((clval[0]/255,clval[1]/255,clval[2]/255,clval[3]/255))
					remove_color = row.operator('fgt.evc_remove_palette_color', icon= 'X', text='')
					remove_color.remove_id = enm

			row = col.row(align=True)
			row.scale_y = 0.8
			addptc = row.operator('fgt.evc_add_palette_color', icon='ADD', text= 'Add New Color')
			addptc.add_color_r = evc.paint_color_base_r
			addptc.add_color_g = evc.paint_color_base_g
			addptc.add_color_b = evc.paint_color_base_b
			addptc.add_color_a = evc.paint_color_base_a

class EVC_OT_Panel_Popup(bpy.types.Operator):
	bl_label ='EVC_OT_Panel_Popup'
	bl_idname='fgt.evc_panel_popup'
	bl_description='EVC panel popup call operator'

	@classmethod
	def poll(cls, context):
		return context.space_data.type == 'VIEW_3D'

	def execute(self, context):
		bpy.ops.wm.call_panel(name='EVC_PT_Panel', keep_open= True)
		return {'FINISHED'}

class EVC_OT_Add_Palette_Color(bpy.types.Operator):
	bl_label ='New Palette Color'
	bl_idname='fgt.evc_add_palette_color'
	bl_description='Add new item to color palette'

	add_color_r:	bpr.IntProperty(name= 'R value', default= 255,  min= 0, max= 255, subtype= 'FACTOR')
	add_color_g:	bpr.IntProperty(name= 'G value', default= 255,  min= 0, max= 255, subtype= 'FACTOR')
	add_color_b:	bpr.IntProperty(name= 'B value', default= 255,  min= 0, max= 255, subtype= 'FACTOR')
	add_color_a:	bpr.IntProperty(name= 'A value', default= 255,  min= 0, max= 255, subtype= 'FACTOR')

	def execute(self, context):
		global color_palette
		color_palette.append((self.add_color_r,self.add_color_g,self.add_color_b,self.add_color_a))
		return {'FINISHED'}

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=130)	

class EVC_OT_Remove_Palette_Color(bpy.types.Operator):
	bl_label ='EVC_OT_Remove_Palette_Color'
	bl_idname='fgt.evc_remove_palette_color'
	bl_description='Remove item from color palette'

	remove_id: bpr.IntProperty(name= 'Remove Color ID', default= 0)

	def execute(self, context):
		global color_palette
		color_palette.pop(self.remove_id)
		return {'FINISHED'}

class EVC_OT_Swithc_Face_Overlay(bpy.types.Operator):
	bl_label ='EVC_OT_Swithc_Face_Overlay'
	bl_idname='fgt.evc_switch_faces_overlay'
	bl_description='Switch ON/OFF faces overlay'

	def execute(self,context):
		if bpy.context.space_data.overlay.show_faces:
			bpy.context.space_data.overlay.show_faces = False
		else:
			bpy.context.space_data.overlay.show_faces = True
		return {'FINISHED'}

class EVC_OT_Swithc_Flat_Color_View(bpy.types.Operator):
	bl_label ='EVC_OT_Swithc_Flat_Color_View'
	bl_idname='fgt.evc_switch_flat_color_view'
	bl_description='Switch shading to Solid, Flat, Vertex Color and back'

	switch_to_flat: bpr.IntProperty(name= '', default= 0)

	def execute(self,context):
		global shading_preserve
		shading = bpy.context.space_data.shading

		if self.switch_to_flat == 0:
			shading.type = 'SOLID'
			shading.light = 'MATCAP'
			shading.color_type = 'MATERIAL'

		elif self.switch_to_flat == 1 and (not shading.type == 'SOLID' or not shading.light == 'FLAT' or not shading.color_type== 'VERTEX' ):
			shading_preserve = list()
			shading_preserve.append(shading.type)
			shading_preserve.append(shading.light)
			if shading.type != 'WIREFRAME':
				shading_preserve.append(shading.color_type)
			else:
				shading_preserve.append('WIRE')
			shading_preserve.append(True)

			shading.type = 'SOLID'
			if shading_preserve[0] != 'SOLID':
				shading_preserve.append(shading.light)				
				shading_preserve.append(shading.color_type)

			shading.light = 'FLAT'
			shading.color_type = 'VERTEX'

		elif self.switch_to_flat == 2:
			if shading_preserve[0] != 'SOLID':
				shading.light = shading_preserve[4]
				shading.color_type = shading_preserve[5]

			shading.type = shading_preserve[0]
			shading.light = shading_preserve[1]
			if shading_preserve[2] != 'WIRE':
				shading.color_type = shading_preserve[2]

			shading_preserve = ['SOLID','MATCAP','MATERIAL',False]

		return {'FINISHED'}

class EVC_OT_Update_Paint_Color(bpy.types.Operator):
	bl_label ='EVC_OT_Update_Paint_Color'
	bl_idname='fgt.evc_update_paint_color'
	bl_description='Update paint color by picked in palette'
	bl_options={'REGISTER', 'UNDO'}

	new_color:	bpr.FloatVectorProperty(name= 'New Color',			
		default=(0, 0, 0, 1.0),
		min=0.0,max=1.0,step=1,precision=3,
		subtype='COLOR_GAMMA',size=4)

	def execute(self,context):
		evc = context.scene.evc_props
		ncl = self.new_color
		evc.paint_color_base_r = round(ncl[0]*255)
		evc.paint_color_base_g = round(ncl[1]*255)
		evc.paint_color_base_b = round(ncl[2]*255)
		evc.paint_color_base_a = round(ncl[3]*255)

		return {'FINISHED'}


class EVC_OT_Raycast_Pick_Color(bpy.types.Operator):
	bl_label ='EVC_OT_Raycast_Pick_Color'
	bl_idname='fgt.evc_raycast_pick_color'
	bl_description='Get VC values from mesh. Ray cast on mesh will trace polygon, then it check which one of polygon vertices are closest to hit location and get VC from loop (face corner) belonging to this polygon/vertex'

	get_selected_only: bpr.BoolProperty(name= 'Selected Only', default= False, description= 'Get VC only from selected mesh objects')

	@classmethod
	def poll(cls, context):
		return context.space_data.type == 'VIEW_3D'

	def __init__(self):
		self.draw_lines_color = [[], (0,0,0,0)]
		self.cursor_xy = Vector((0,0))

	def invoke(self, context, event):
		if context.space_data.type == 'VIEW_3D':
			args = (self,context)
			self.draw_handler_3d = bpy.types.SpaceView3D.draw_handler_add(draw_pick_color_lines, args, 'WINDOW', 'POST_VIEW')
			self.draw_handler_2d = bpy.types.SpaceView3D.draw_handler_add(draw_pick_color_info, args, 'WINDOW', 'POST_PIXEL')
			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}

		else:
			self.report({'WARNING'}, "Active space must be a View3d")
			return {'CANCELLED'}

	def modal(self,context,event):
		evc = context.scene.evc_props

		def remove_draw_handlers(self):
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler_3d, 'WINDOW')
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler_2d, 'WINDOW')

		if context.space_data.type != 'VIEW_3D':
			evc.draw_hit = False
			context.area.tag_redraw()
			remove_draw_handlers(self)
			return {'CANCELLED'}

		if (event.type == 'RIGHTMOUSE' or event.type == 'ESC') and event.value == 'PRESS':
			evc.draw_hit = False
			context.area.tag_redraw()
			remove_draw_handlers(self)
			return {'CANCELLED'}

		self.cursor_xy = Vector((event.mouse_region_x, event.mouse_region_y))

		hit_vallid_object, no_hit, hit_loc, hit_pid, hit_obn = ray_cast_check(self, context)

		if no_hit or not hit_vallid_object:
			evc.draw_hit = False
			context.area.tag_redraw()

		elif hit_vallid_object:
			self.draw_lines_color = get_hit_lines_color(hit_loc, hit_pid, hit_obn)
			evc.draw_hit = True
			context.area.tag_redraw()

		if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
			evc.draw_hit = False
			context.area.tag_redraw()

			hit_vallid_object, no_hit, hit_loc, hit_pid, hit_obn = ray_cast_check(self, context)

			if no_hit or not hit_vallid_object:
				self.report({'WARNING'}, 'No object to get vertex color!!!')
				remove_draw_handlers(self)
				return {'CANCELLED'}

			elif hit_vallid_object:

				get_color = get_hit_lines_color(hit_loc, hit_pid, hit_obn, True)

				if get_color == (0,0,0,-1):
					self.report({'WARNING'}, 'No vertex color on this object!!!')
					remove_draw_handlers(self)
					return {'CANCELLED'}
				else:
					evc.paint_color_base_r = round(get_color[0]*255)
					evc.paint_color_base_g = round(get_color[1]*255)
					evc.paint_color_base_b = round(get_color[2]*255)
					evc.paint_color_base_a = round(get_color[3]*255)

			remove_draw_handlers(self)
			return {'FINISHED'}

		return {'RUNNING_MODAL'}


class EVC_OT_Set_Color(bpy.types.Operator):
	bl_label ='EVC_OT_Set_Color'
	bl_idname='fgt.evc_set_color'
	bl_description='Set/Add/Subtract vertex color in Mesh Edit mode'
	bl_options={'REGISTER', 'UNDO'}


	paint_col_msk_chn:		bpr.EnumProperty(name= 'VC Edit Channels',
									items=  [('RGB','RGB Channels','',0), ('RG','RG Channels','',1), ('RB','RB Channels','',2), ('GB','GB Channels','',3),('R','R Channel','',4),('G','G Channel','',5),('B','B Channel','',6),('A','A Channel','',7),
											('RGBA','RGBA Channels','',8), ('RGA','RGA Channels','',9), ('RBA','RBA Channels','',10), ('GBA','GBA Channels','',11),('RA','RA Channels','',12),('GA','GA Channels','',13),('BA','BA Channels','',14)],
											 default= 'RGBA')

	vc_edit_mode:			bpr.EnumProperty(name= 'VC Edit Mode', 
									items=  [('SET','Set','Paint Color will override existing VC',0),
											('ADD','Add','Paint Color values will be added to existing VC values',1),
											('SUB','Subtract', 'Paint Color values will be subtracted from existing VC values', 2)],
											default= 'SET')

	color_r:				bpr.IntProperty(name= 'R Channel Value', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of main color R channel. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	color_g:				bpr.IntProperty(name= 'G Channel Value', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of main color G channel. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	color_b:				bpr.IntProperty(name= 'B Channel Value', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of main color B channel. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	color_a:				bpr.IntProperty(name= 'A Channel Value', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of main color A channel. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')

	paint_freestyle_mask:	bpr.BoolProperty(name= 'Freestyle Masking', default= False, description= 'Freestyle Mask will be used for masking Set/Add/Subtract')
	paint_face_mask:		bpr.BoolProperty(name= 'Face Masking', default= False, description= 'Only fully selected faces (in any selection mode) will be edited by Set/Add/Subtract')
	paint_hidden: 			bpr.BoolProperty(name= 'Paint Hidden Mesh', default= False, description= 'When enabled Set/Add/Subtract operators will also edit currently hidden mesh (DISABLED IF FACE MASKING ENABLED !!!)')


	paint_rand:				bpr.BoolProperty(name= 'Randomize Paint Color', default= False,
									description= 'Paint Color will be randomized in threshold range for selected percentage of loops(face corners)/vertices/faces/elements (depend on selected mode)')
	paint_rand_static:		bpr.BoolProperty(name= 'Randomizer Static Seed',  default= False,
									description= 'When true randomization will use specific seed value instead of random')
	paint_rand_only:		bpr.BoolProperty(name= 'Paint Randomized Only', default= False,
									description= 'Set/Add/Subtract will affect only randomized loops(face corners)/vertices/faces/elements')
	paint_rand_seed:		bpr.IntProperty(name='RND Seed', min= 0, max= 1000, subtype= 'FACTOR',
									description= 'Seed used for generating random values, work as intended only if Static Seed enabled, else you can move slider to refresh/regenerate random values')
	paint_rand_prc:			bpr.IntProperty(name='RND Percentage', min= 0, max= 100, default= 100, subtype= 'FACTOR',
									description= 'Percentage of loops(face corners)/vertices/faces/elements in selection to be randomized (percentage calculated per object in multi object editing cases)')
	paint_rand_fct:			bpr.FloatProperty(name='RND Factor', min= -1, max= 1, default= 0, precision=3, subtype= 'FACTOR', 
									description= 'Below 0 you will get more values closer to possible minimum, above 0 more closer to possible maximum')
	paint_rand_sub:			bpr.IntProperty(name='RND Color Minus', default= 0, min= -255, max= 0, subtype= 'FACTOR', 
									description= 'Value of range BELOW Paint Color channel(s) value to generate randomized value')
	paint_rand_add:			bpr.IntProperty(name='RND Color Plus', default= 0, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of range ABOVE Paint Color channel(s) value to generate randomized value')
	paint_rand_lvpe:			bpr.EnumProperty(name= 'RND Mode',
									items=  [('L','Per Loop','Randomize will work per Loop (face corner)',0),
											('V','Per Vertex','Randomize will work per Vertex',1),
											('P','Per Polygon','Randomize Paint Color per Polygon',2),
											('E','Per Element','Randomize will work per Element (linked mesh piece)',3)],
											default= 'L')

	paint_rand_chn:			bpr.EnumProperty(name= 'RND Channels',
									items=  [('RGB','RGB Channels','',0), ('RG','RG Channels','',1), ('RB','RB Channels','',2), ('GB','GB Channels','',3),('R','R Channel','',4),('G','G Channel','',5),('B','B Channel','',6),('A','A Channel','',7),
											('RGBA','RGBA Channels','',8), ('RGA','RGA Channels','',9), ('RBA','RBA Channels','',10), ('GBA','GBA Channels','',11),('RA','RA Channels','',12),('GA','GA Channels','',13),('BA','BA Channels','',14)],
											 default= 'RGBA')

	@classmethod
	def poll(cls, context):
		return context.space_data.type == 'VIEW_3D' and context.mode == 'EDIT_MESH'

	def execute(self,context):
		evc = context.scene.evc_props
		sob_em = [ob.name for ob in bpy.context.view_layer.objects.selected if (ob.mode == 'EDIT' and ob.type == 'MESH')]
		aob_r = bpy.context.view_layer.objects.active.name

		clr = self.color_r/255
		clg = self.color_g/255
		clb = self.color_b/255
		cla = self.color_a/255
		paint_color = Vector((clr,clg,clb,cla))
		use_r_colors = False

		if self.paint_face_mask:
			self.paint_hidden = False

		obn_loops = loops_preparation(sob_em, self.paint_freestyle_mask, self.paint_face_mask, self.paint_hidden, True)

		if self.paint_rand and (self.paint_rand_sub != 0 or self.paint_rand_add != 0 or self.paint_rand_only):
			use_r_colors = True
			# Set or generate seed
			if self.paint_rand_static:
				r_seed = self.paint_rand_seed
			else:
				r_num = random.random()
				r_seed = int(r_num*1000)
				evc.paint_randomize_seed = r_seed

		if use_r_colors and self.paint_rand_lvpe == 'E': # If mode is Element - prepare randomizer to randomize per element
			obn_vtc_selected = dict()
			obn_edg_selected = dict()
			obn_fac_selected = dict()
			obn_elements = dict()
			obn_edges_h = dict()

			sel_r = bpy.context.scene.tool_settings.mesh_select_mode[:]

			for obn in obn_loops.keys(): # Preserve selection to recover later
				bpy.context.view_layer.objects.active = bpy.data.objects[obn]
				bmd = bmesh.from_edit_mesh(context.edit_object.data)

				vtc_selected = list()
				edg_selected = list()
				fac_selected = list()
				if sel_r[0]:
					for vtc in bmd.verts:
						if vtc.select:
							vtc_selected.append(vtc.index)
					obn_vtc_selected.update({obn:vtc_selected})

				elif sel_r[1]:
					for vtc in bmd.verts:
						if vtc.select:
							vtc_selected.append(vtc.index)
					for edg in bmd.edges:
						if edg.select:
							edg_selected.append(edg.index)

					obn_vtc_selected.update({obn:vtc_selected})
					obn_edg_selected.update({obn:edg_selected})
					
				elif sel_r[2]: 
					for vtc in bmd.verts:
						if vtc.select:
							vtc_selected.append(vtc.index)
					for fac in bmd.faces:
						if fac.select:
							fac_selected.append(fac.index)

					obn_vtc_selected.update({obn:vtc_selected})
					obn_fac_selected.update({obn:fac_selected})

			for obn in obn_loops.keys(): # preserve mesh visibility to recover laetr
				bpy.context.view_layer.objects.active = bpy.data.objects[obn]
				bmd = bmesh.from_edit_mesh(context.edit_object.data)

				edges_h = list()
				for edg in bmd.edges:
					if edg.hide:
						edges_h.append(edg.index)
						edg.hide_set(False)
				
				obn_edges_h.update({obn:edges_h})

			bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

			for obn in obn_loops.keys():
				bpy.context.view_layer.objects.active = bpy.data.objects[obn]
				bmd = bmesh.from_edit_mesh(context.edit_object.data)

				lp_to_check = copy(obn_loops.get(obn))
				vtc_to_check = copy(obn_vtc_selected.get(obn))
				elements = list()

				bmd.verts.ensure_lookup_table()
				bpy.ops.mesh.select_all(action= 'DESELECT')

				while len(vtc_to_check) != 0:
					lp_element = list()
					bmd.verts[vtc_to_check[0]].select_set(True)
					bpy.ops.mesh.select_linked(delimit=set())

					vtc_to_pop = list()
					for vtc_id in vtc_to_check:
						if bmd.verts[vtc_id].select:
							vtc_to_pop.append(vtc_id)
							for lp in bmd.verts[vtc_id].link_loops:
								lp_id = lp.index
								if lp_id not in lp_element and lp_id in lp_to_check:
									lp_element.append(lp_id)
									lp_to_check.pop(lp_to_check.index(lp_id))

					for vtc_id in vtc_to_pop:
						vtc_to_check.pop(vtc_to_check.index(vtc_id))

					elements.append(lp_element)
					bpy.ops.mesh.select_all(action= 'DESELECT')

				obn_elements.update({obn:elements})

			if sel_r[0]: # Recover selection mode
				if sel_r[1]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='EDGE')
				if sel_r[2]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='FACE')
			elif sel_r[1]:
				bpy.ops.mesh.select_mode(type= 'EDGE')
				if sel_r[2]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='FACE')
			elif sel_r[2]:
				bpy.ops.mesh.select_mode(type= 'FACE')

			for obn in obn_loops.keys(): # Recover selection and visibility
				bpy.context.view_layer.objects.active = bpy.data.objects[obn]
				bmd = bmesh.from_edit_mesh(context.edit_object.data)

				bmd.edges.ensure_lookup_table()

				if sel_r[0]:
					for vtc_id in obn_vtc_selected.get(obn):
						bmd.verts[vtc_id].select_set(True)
				elif sel_r[1]:
					for edg_id in obn_edg_selected.get(obn):
						bmd.edges[edg_id].select_set(True)
				elif sel_r[2]:
					bmd.faces.ensure_lookup_table()
					for fac_id in obn_fac_selected.get(obn):
						bmd.faces[fac_id].select_set(True)

				for edg_id in obn_edges_h.get(obn):
					bmd.edges[edg_id].hide_set(True)

			bpy.ops.mesh.select_all(action= 'INVERT')
			bpy.ops.mesh.select_all(action= 'INVERT')



		for obn in obn_loops.keys():
			active_vc = bpy.data.objects[obn].data.vertex_colors.active_index
			bpy.context.view_layer.objects.active = bpy.data.objects[obn]
			bmd = bmesh.from_edit_mesh(context.edit_object.data)
			llc = bmd.loops.layers.color[active_vc]
			loops_ids = obn_loops.get(obn)

			if use_r_colors:
				ob_r_seed = object_seed_generator(r_seed, obn)
				random.seed(ob_r_seed)
				random.shuffle(loops_ids)
				r_colors = list()
				r_element = list()

				if self.paint_rand_lvpe == 'L': # randomizer mode Loops
					rand_prc = len(loops_ids) * (self.paint_rand_prc/100)

					for enm,lp_id in enumerate(loops_ids):
						if enm + 1 <= rand_prc:
							r_colors.append(color_randomizer(lp_id, paint_color, self.paint_rand_fct, self.paint_rand_sub, self.paint_rand_add, ob_r_seed, self.paint_rand_chn))
							r_element.append(True)
						else:
							r_colors.append(paint_color)
							r_element.append(False)

				elif self.paint_rand_lvpe == 'V': # randomizer mode Vertex
					vtc_lp_ids = copy(loops_ids)
					vtc_ids = list()
					vtc_cls = list()
					vtc_rnd = list()

					for vtc in bmd.verts:
						if len(vtc.link_loops) != 0:
							vtc_id = vtc.index
							for lp in vtc.link_loops:
								lp_id = lp.index
								if lp_id in loops_ids:
									vtc_lp_ids[loops_ids.index(lp_id)] = vtc_id
									if not vtc_id in vtc_ids:
										vtc_ids.append(vtc_id)

					random.shuffle(vtc_ids)
					rand_prc = len(vtc_ids) * (self.paint_rand_prc/100)

					for enm,vtc_id in enumerate(vtc_ids):
						if enm + 1 <= rand_prc:
							vtc_cls.append(color_randomizer(vtc_id, paint_color, self.paint_rand_fct, self.paint_rand_sub, self.paint_rand_add, ob_r_seed, self.paint_rand_chn))
							vtc_rnd.append(True)
						else:
							vtc_cls.append(paint_color)
							vtc_rnd.append(False)

					for vtc_id in vtc_lp_ids:
						elm_id = vtc_ids.index(vtc_id)
						r_colors.append(vtc_cls[elm_id])
						r_element.append(vtc_rnd[elm_id])

				elif self.paint_rand_lvpe == 'P': # randomizer mode Poly
					fac_lp_ids = copy(loops_ids)
					fac_ids = list()
					fac_cls = list()
					fac_rnd = list()

					for fac in bmd.faces:
						for lp in fac.loops:
							lp_id = lp.index
							if lp_id in loops_ids:
								fac_id = fac.index
								fac_lp_ids[loops_ids.index(lp_id)] = fac_id
								if not fac_id in fac_ids:
									fac_ids.append(fac_id)
				
					random.shuffle(fac_ids)
					rand_prc = len(fac_ids) * (self.paint_rand_prc/100)
				
					for enm,fac_id in enumerate(fac_ids):
						if enm + 1 <= rand_prc:
							fac_cls.append(color_randomizer(fac_id, paint_color, self.paint_rand_fct, self.paint_rand_sub, self.paint_rand_add, ob_r_seed, self.paint_rand_chn))
							fac_rnd.append(True)
						else:
							fac_cls.append(paint_color)
							fac_rnd.append(False)

					for fac_id in fac_lp_ids:
						elm_id = fac_ids.index(fac_id)
						r_colors.append(fac_cls[elm_id])
						r_element.append(fac_rnd[elm_id])

				elif self.paint_rand_lvpe == 'E':
					ob_elms = obn_elements.get(obn)
					random.shuffle(ob_elms)
					elm_cls = list()
					elm_rnd = list()
					
					for enm,elm in enumerate(ob_elms):
						if enm + 1 <= len(ob_elms) * (self.paint_rand_prc/100):
							elm_cls.append(color_randomizer(enm, paint_color, self.paint_rand_fct, self.paint_rand_sub, self.paint_rand_add, ob_r_seed, self.paint_rand_chn))
							elm_rnd.append(True)
						else:
							elm_cls.append(paint_color)
							elm_rnd.append(False)

					r_colors = [paint_color for n in range(len(loops_ids))]
					r_element = [False for n in range(len(loops_ids))]

					for elm, elm_cl, rnd_b in zip(ob_elms, elm_cls, elm_rnd):
						for lp_id in elm:
							if lp_id in loops_ids:
								elm_id = loops_ids.index(lp_id)
								r_colors[elm_id] = elm_cl
								r_element[elm_id] = rnd_b

			for edg in bmd.edges:
				if len(edg.link_loops) != 0:
					for lp in edg.link_loops:
						lp_id = lp.index
						if lp_id in loops_ids:
							lp_pos = loops_ids.index(lp_id)

							if use_r_colors:
								if self.paint_rand_only:
									if r_element[lp_pos]:
										lp_color = r_colors[lp_pos]
										set_loop_vertex_color(self.vc_edit_mode, self.paint_col_msk_chn, lp, llc, lp_color)
								else:
									lp_color = r_colors[lp_pos]
									set_loop_vertex_color(self.vc_edit_mode, self.paint_col_msk_chn, lp, llc, lp_color)
								
								r_element.pop(lp_pos)
								r_colors.pop(lp_pos)

							else:
								set_loop_vertex_color(self.vc_edit_mode, self.paint_col_msk_chn, lp, llc, paint_color)

							loops_ids.pop(lp_pos)
							

			bpy.data.objects[obn].data.update()

		bpy.context.view_layer.objects.active = bpy.data.objects[aob_r]

		return {'FINISHED'}

class EVC_OT_Select_Similar_VC(bpy.types.Operator):
	bl_label ='EVC_OT_Select_Similar_VC'
	bl_idname='fgt.evc_select_similar_vc'
	bl_description='Operator let you select vertices with similar to input color +/- range for RGB channels'
	bl_options = {'REGISTER','UNDO'}

	sim_cl_r:		bpr.IntProperty(name= 'Similar R Value', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of main color R channel used to search for similar values. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	sim_cl_g:		bpr.IntProperty(name= 'Similar G Value', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of main color G channel used to search for similar values. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	sim_cl_b:		bpr.IntProperty(name= 'Similar B Value', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of main color B channel used to search for similar values. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	sim_cl_a:		bpr.IntProperty(name= 'Similar A Value', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of main color A channel used to search for similar values. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')

	sim_cl_mode:	bpr.EnumProperty(name= 'Selection Mode', 
								items=  [('V','Vertices Mode','Select vertices if vertex belong to loop with VC similar +/- threshold',0),
										('F','Faces Mode','Select faces if all face corners (loops) VC similar +/- threshold',1)],
										default= 'V')

	sim_cl_chn:			bpr.EnumProperty(name= 'Similar Channels',
									items=  [('RGB','RGB Channels','',0), ('RG','RG Channels','',1), ('RB','RB Channels','',2), ('GB','GB Channels','',3),('R','R Channel','',4),('G','G Channel','',5),('B','B Channel','',6),('A','A Channel','',7),
											('RGBA','RGBA Channels','',8), ('RGA','RGA Channels','',9), ('RBA','RBA Channels','',10), ('GBA','GBA Channels','',11),('RA','RA Channels','',12),('GA','GA Channels','',13),('BA','BA Channels','',14)],
											 default= 'RGBA')

	sim_cl_in_sel:	bpr.BoolProperty(name= 'Search Inside Selection', default= False, description= 'Check for similar VC only inside current selection')	
	sim_cl_sub:		bpr.IntProperty(name='Value Subtract', min= -255, max= 0, default= 0, subtype= 'FACTOR', 
						description= 'Value of threshold BELOW current Search Color to search for vertices with similar colors in range (VC actually stored in "loops"(face corners), more than one vertex color could belong to one Blender vertex!!!)')
	sim_cl_add:		bpr.IntProperty(name='Value Add', min= 0, max= 255, default= 0, subtype= 'FACTOR', 
						description= 'Value of threshold ABOVE current Search Color to search for vertices with similar colors in range (VC actually stored in "loops"(face corners), more than one vertex color could belong to one Blender vertex!!!)')

	@classmethod
	def poll(cls, context):
		return context.space_data.type == 'VIEW_3D' and context.mode == 'EDIT_MESH'

	def execute(self, context):
		evc = context.scene.evc_props

		clr = self.sim_cl_r/255
		clg = self.sim_cl_g/255
		clb = self.sim_cl_b/255
		cla = self.sim_cl_a/255
		sim_cl = Vector((clr,clg,clb,cla))

		sob_em = [ob.name for ob in bpy.context.view_layer.objects.selected if (ob.mode == 'EDIT' and ob.type == 'MESH')]
		aob_r = bpy.context.view_layer.objects.active.name
		sel_r = bpy.context.scene.tool_settings.mesh_select_mode[:]

		obn_elm_ids = dict()

		for obn in sob_em:
			if len(bpy.data.objects[obn].data.vertex_colors) != 0:
				bpy.context.view_layer.objects.active = bpy.data.objects[obn]
				bmd = bmesh.from_edit_mesh(context.edit_object.data)

				if self.sim_cl_mode == 'V': # Vertices mode
					vts_ids = list()
					for vtc in bmd.verts:
						if self.sim_cl_in_sel:
							if vtc.select and not vtc.hide and vtc.link_loops != []: vts_ids.append(vtc.index)
						else:
							if not vtc.hide and vtc.link_loops != []: vts_ids.append(vtc.index)
					obn_elm_ids.update({obn:vts_ids})

				else: # Faces mode
					fcs_ids = list()
					for fac in bmd.faces:
						if self.sim_cl_in_sel:
							if fac.select and not fac.hide: fcs_ids.append(fac.index)
						else:
							if not fac.hide: fcs_ids.append(fac.index)
					obn_elm_ids.update({obn:fcs_ids})

		if self.sim_cl_mode == 'V': 
			bpy.ops.mesh.select_mode(type= 'VERT')
		else:
			bpy.ops.mesh.select_mode(type= 'FACE')

		bpy.ops.mesh.select_all(action= 'DESELECT')

		for obn in obn_elm_ids.keys():
			active_vc = bpy.data.objects[obn].data.vertex_colors.active_index
			bpy.context.view_layer.objects.active = bpy.data.objects[obn]
			bmd = bmesh.from_edit_mesh(context.edit_object.data)
			llc = bmd.loops.layers.color[active_vc]

			if self.sim_cl_mode == 'V': # Vertices mode
				bmd.verts.ensure_lookup_table()
				for elm_id in obn_elm_ids.get(obn):
					vtc = bmd.verts[elm_id]
					for lp in vtc.link_loops:
						if similar_color_check(sim_cl, lp[llc][:], self.sim_cl_sub, self.sim_cl_add, self.sim_cl_chn):
							vtc.select_set(True)
							break
			else: # Faces mode
				bmd.faces.ensure_lookup_table()
				for elm_id in obn_elm_ids.get(obn):
					fac = bmd.faces[elm_id]
					fac_sel = True
					for lp in fac.loops:
						if not similar_color_check(sim_cl, lp[llc][:], self.sim_cl_sub, self.sim_cl_add, self.sim_cl_chn):
							fac_sel = False
							break
					if fac_sel:
						fac.select_set(True)

		bpy.ops.mesh.select_all(action= 'INVERT')
		bpy.ops.mesh.select_all(action= 'INVERT')

		if self.sim_cl_mode == 'V':
			if sel_r[0]:
				if sel_r[1]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='EDGE')
				if sel_r[2]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='FACE')
			elif sel_r[1]:
				bpy.ops.mesh.select_mode(type= 'EDGE')
				if sel_r[2]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='FACE')
			elif sel_r[2]:
				bpy.ops.mesh.select_mode(type= 'FACE')
		else:
			if sel_r[2]:
				if sel_r[1]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='EDGE')
				if sel_r[0]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='VERT')
			elif sel_r[1]:
				bpy.ops.mesh.select_mode(type= 'EDGE')
				if sel_r[0]: bpy.ops.mesh.select_mode(use_extend=True, use_expand=False, type='VERT')
			elif sel_r[0]:
				bpy.ops.mesh.select_mode(type= 'VERT')

		bpy.context.view_layer.objects.active = bpy.data.objects[aob_r]

		return {'FINISHED'}


class EVC_OT_Move_Copy_Swap(bpy.types.Operator):
	bl_label ='EVC_OT_Move_Copy_Swap'
	bl_idname='fgt.evc_move_copy_swap'
	bl_description='Move/Copy/Swapvertex color from one channel to another (!!! affected by Freestyle Mask/Face Mask/Paint Hidden masking features !!!)'
	bl_options={'REGISTER', 'UNDO'}

	mcs_mode:				bpr.EnumProperty(name= 'MCS Mode', 
									items=  [('MOV','Move','Mode selection for Color Move/Copy/Swap feature',0),
											('COP','Copy','Paint Color values will be added to existing VC values',1),
											('SWP','Swap', 'Paint Color values will be subtracted from existing VC values', 2)],
											default= 'MOV')

	mcs_a_channel:			bpr.EnumProperty(name= 'MCS A Channel', items=  [('R','R Channel','',0),('G','G Channel','',1),('B','B Channel','',2),('A','A Channel','',3)], default= 'R')
	mcs_b_channel:			bpr.EnumProperty(name= 'MCS B Channel', items=  [('R','R Channel','',0),('G','G Channel','',1),('B','B Channel','',2),('A','A Channel','',3)], default= 'R')

	mcs_freestyle_mask:		bpr.BoolProperty(name= 'Freestyle Masking', default= False, description= 'Freestyle Mask will be used for masking Move/Copy/Swap')
	mcs_face_mask:			bpr.BoolProperty(name= 'Face Masking', default= False, description= 'Only fully selected faces (in any selection mode) will be edited by Move/Copy/Swap')
	mcs_hidden: 			bpr.BoolProperty(name= 'Edit Hidden Mesh', default= False, description= 'When enabled Move/Copy/Swap operators will also edit currently hidden mesh (DISABLED IF FACE MASKING ENABLED !!!)')


	@classmethod
	def poll(cls, context):
		return context.space_data.type == 'VIEW_3D' and context.mode == 'EDIT_MESH'

	def execute(self,context):
		evc = context.scene.evc_props
		sob_em = [ob.name for ob in bpy.context.view_layer.objects.selected if (ob.mode == 'EDIT' and ob.type == 'MESH')]
		aob_r = bpy.context.view_layer.objects.active.name

		if self.mcs_face_mask:
			self.mcs_hidden = False

		obn_loops = loops_preparation(sob_em, self.mcs_freestyle_mask, self.mcs_face_mask, self.mcs_hidden, False)
		ch_a,ch_b = 'RGBA'.index(self.mcs_a_channel), 'RGBA'.index(self.mcs_b_channel)

		for obn in obn_loops.keys():
			active_vc = bpy.data.objects[obn].data.vertex_colors.active_index
			bpy.context.view_layer.objects.active = bpy.data.objects[obn]
			bmd = bmesh.from_edit_mesh(context.edit_object.data)
			llc = bmd.loops.layers.color[active_vc]
			loops_ids = obn_loops.get(obn)

			for edg in bmd.edges:
				if len(edg.link_loops) != 0:
					for lp in edg.link_loops:
						lp_id = lp.index
						if lp_id in loops_ids:
							if self.mcs_mode == 'MOV':
								lp[llc][ch_b] = lp[llc][ch_a]
								lp[llc][ch_a] = 0
							elif self.mcs_mode == 'COP':
								lp[llc][ch_b] = lp[llc][ch_a]
							elif self.mcs_mode == 'SWP':
								col_buffer = lp[llc][ch_a]
								lp[llc][ch_a] = lp[llc][ch_b]
								lp[llc][ch_b] = col_buffer

							loops_ids.pop(loops_ids.index(lp_id))

			bpy.data.objects[obn].data.update()

		bpy.context.view_layer.objects.active = bpy.data.objects[aob_r]

		return {'FINISHED'}

class EVC_OT_Multiply_Power(bpy.types.Operator):
	bl_label ='EVC_OT_Multiply_Power'
	bl_idname='fgt.evc_multiply_power'
	bl_description='Multiply/power selected VC channel(s) value by multiplier/exponent value (!!! affected by Freestyle Mask/Face Mask/Paint Hidden masking features !!!)'
	bl_options={'REGISTER', 'UNDO'}


	vc_mp_mode:				bpr.EnumProperty(name= 'Mult/Pow Mode', 
								items=  [('MP','Multiply + Power','First do multiplication then power (in some cases different order give a bit different result)',0),
										('PM','Power + Multiply','First do power then multiplication (in some cases different order give a bit different result)',1)],
										default= 'MP')
	vc_mp_mlt:				bpr.FloatProperty(name='Multiplier Value', default= 1.0, min=0.0, soft_max=10.0, step=1, precision=4, subtype='FACTOR',
								description= 'Mininum hardcap = 0, maximum softcap = 10 (you can set your value greater than 10)')
	vc_mp_exp:				bpr.FloatProperty(name='Exponent Value', default= 1.0, min=0.0001, soft_max=10.0, step=1, precision=4, subtype='FACTOR',
								description= 'Mininum hardcap = 0, maximum softcap = 10 (you can set your value greater than 10)')
	vc_mp_channel:			bpr.EnumProperty(name= 'Mult/Pow Channels',
								items=  [('RGB','RGB Channels','',0), ('RG','RG Channels','',1), ('RB','RB Channels','',2), ('GB','GB Channels','',3),('R','R Channel','',4),('G','G Channel','',5),('B','B Channel','',6),('A','A Channel','',7),
										('RGBA','RGBA Channels','',8), ('RGA','RGA Channels','',9), ('RBA','RBA Channels','',10), ('GBA','GBA Channels','',11),('RA','RA Channels','',12),('GA','GA Channels','',13),('BA','BA Channels','',14)],
										 default= 'RGBA')

	vc_mp_freestyle_mask:	bpr.BoolProperty(name= 'Freestyle Masking', default= False, description= 'Freestyle Mask will be used for masking Multiply+Power')
	vc_mp_face_mask:		bpr.BoolProperty(name= 'Face Masking', default= False, description= 'Only fully selected faces (in any selection mode) will be edited by Multiply+Power')
	vc_mp_hidden: 			bpr.BoolProperty(name= 'Edit Hidden Mesh', default= False, description= 'When enabled Multiply+Power operators will also edit currently hidden mesh (DISABLED IF FACE MASKING ENABLED !!!)')

	@classmethod
	def poll(cls, context):
		return context.space_data.type == 'VIEW_3D' and context.mode == 'EDIT_MESH'

	def execute(self,context):
		evc = context.scene.evc_props
		sob_em = [ob.name for ob in bpy.context.view_layer.objects.selected if (ob.mode == 'EDIT' and ob.type == 'MESH')]
		aob_r = bpy.context.view_layer.objects.active.name

		if self.vc_mp_face_mask:
			self.vc_mp_hidden = False

		obn_loops = loops_preparation(sob_em, self.vc_mp_freestyle_mask, self.vc_mp_face_mask, self.vc_mp_hidden, False)

		for obn in obn_loops.keys():
			active_vc = bpy.data.objects[obn].data.vertex_colors.active_index
			bpy.context.view_layer.objects.active = bpy.data.objects[obn]
			bmd = bmesh.from_edit_mesh(context.edit_object.data)
			llc = bmd.loops.layers.color[active_vc]
			loops_ids = obn_loops.get(obn)

			for edg in bmd.edges:
				if len(edg.link_loops) != 0:
					for lp in edg.link_loops:
						lp_id = lp.index
						if lp_id in loops_ids:
							if self.vc_mp_exp != 1 and self.vc_mp_mode == 'PM':
								if 'R' in self.vc_mp_channel: lp[llc][0] = round(pow(lp[llc][0], self.vc_mp_exp)*255)/255
								if 'G' in self.vc_mp_channel: lp[llc][1] = round(pow(lp[llc][1], self.vc_mp_exp)*255)/255
								if 'B' in self.vc_mp_channel: lp[llc][2] = round(pow(lp[llc][2], self.vc_mp_exp)*255)/255
								if 'A' in self.vc_mp_channel: lp[llc][3] = round(pow(lp[llc][3], self.vc_mp_exp)*255)/255
							if self.vc_mp_mlt != 1:
								col_mlt =  lp[llc] * self.vc_mp_mlt
								if 'R' in self.vc_mp_channel: lp[llc][0] = round(col_mlt[0]*255)/255 if round(col_mlt[0]*255)/255 <= 1 else 1
								if 'G' in self.vc_mp_channel: lp[llc][1] = round(col_mlt[1]*255)/255 if round(col_mlt[1]*255)/255 <= 1 else 1
								if 'B' in self.vc_mp_channel: lp[llc][2] = round(col_mlt[2]*255)/255 if round(col_mlt[2]*255)/255 <= 1 else 1
								if 'A' in self.vc_mp_channel: lp[llc][3] = round(col_mlt[3]*255)/255 if round(col_mlt[3]*255)/255 <= 1 else 1
							if self.vc_mp_exp != 1 and self.vc_mp_mode == 'MP':
								if 'R' in self.vc_mp_channel: lp[llc][0] = round(pow(lp[llc][0], self.vc_mp_exp)*255)/255
								if 'G' in self.vc_mp_channel: lp[llc][1] = round(pow(lp[llc][1], self.vc_mp_exp)*255)/255
								if 'B' in self.vc_mp_channel: lp[llc][2] = round(pow(lp[llc][2], self.vc_mp_exp)*255)/255
								if 'A' in self.vc_mp_channel: lp[llc][3] = round(pow(lp[llc][3], self.vc_mp_exp)*255)/255
							
							loops_ids.pop(loops_ids.index(lp_id))

			bpy.data.objects[obn].data.update()

		bpy.context.view_layer.objects.active = bpy.data.objects[aob_r]

		return {'FINISHED'}

class EVC_OT_Invert_Color(bpy.types.Operator):
	bl_label ='EVC_OT_Invert_Color'
	bl_idname='fgt.evc_invert_color'
	bl_description='Invert vertex color values for selected channels (!!! affected by Freestyle Mask/Face Mask/Paint Hidden masking features !!!)'
	bl_options={'REGISTER', 'UNDO'}

	vc_inv_channel:			bpr.EnumProperty(name= 'Invert Channels',
								items=  [('RGB','RGB Channels','',0), ('RG','RG Channels','',1), ('RB','RB Channels','',2), ('GB','GB Channels','',3),('R','R Channel','',4),('G','G Channel','',5),('B','B Channel','',6),('A','A Channel','',7),
										('RGBA','RGBA Channels','',8), ('RGA','RGA Channels','',9), ('RBA','RBA Channels','',10), ('GBA','GBA Channels','',11),('RA','RA Channels','',12),('GA','GA Channels','',13),('BA','BA Channels','',14)],
										 default= 'RGBA')

	vc_inv_freestyle_mask:	bpr.BoolProperty(name= 'Freestyle Masking', default= False, description= 'Freestyle Mask will be used for masking Multiply+Power')
	vc_inv_face_mask:		bpr.BoolProperty(name= 'Face Masking', default= False, description= 'Only fully selected faces (in any selection mode) will be edited by Multiply+Power')
	vc_inv_hidden: 			bpr.BoolProperty(name= 'Edit Hidden Mesh', default= False, description= 'When enabled Multiply+Power operators will also edit currently hidden mesh (DISABLED IF FACE MASKING ENABLED !!!)')


	@classmethod
	def poll(cls, context):
		return context.space_data.type == 'VIEW_3D' and context.mode == 'EDIT_MESH'

	def execute(self,context):
		evc = context.scene.evc_props
		sob_em = [ob.name for ob in bpy.context.view_layer.objects.selected if (ob.mode == 'EDIT' and ob.type == 'MESH')]
		aob_r = bpy.context.view_layer.objects.active.name

		if self.vc_inv_face_mask:
			self.vc_inv_hidden = False

		obn_loops = loops_preparation(sob_em, self.vc_inv_freestyle_mask, self.vc_inv_face_mask, self.vc_inv_hidden, False)

		for obn in obn_loops.keys():
			active_vc = bpy.data.objects[obn].data.vertex_colors.active_index
			bpy.context.view_layer.objects.active = bpy.data.objects[obn]
			bmd = bmesh.from_edit_mesh(context.edit_object.data)
			llc = bmd.loops.layers.color[active_vc]
			loops_ids = obn_loops.get(obn)

			for edg in bmd.edges:
				if len(edg.link_loops) != 0:
					for lp in edg.link_loops:
						lp_id = lp.index
						if lp_id in loops_ids:
							if 'R' in self.vc_inv_channel: lp[llc][0] = 1 - lp[llc][0]
							if 'G' in self.vc_inv_channel: lp[llc][1] = 1 - lp[llc][1]
							if 'B' in self.vc_inv_channel: lp[llc][2] = 1 - lp[llc][2]
							if 'A' in self.vc_inv_channel: lp[llc][3] = 1 - lp[llc][3]
							loops_ids.pop(loops_ids.index(lp_id))

			bpy.data.objects[obn].data.update()

		bpy.context.view_layer.objects.active = bpy.data.objects[aob_r]

		return {'FINISHED'}




def prop_update_vc_mode_set_base(self, context):
	evc = context.scene.evc_props
	if evc.vc_mode_set_base and (evc.vc_mode_add_base or evc.vc_mode_sub_base): evc.vc_mode_add_base, evc.vc_mode_sub_base = False, False
	elif not evc.vc_mode_set_base:
		if not (evc.vc_mode_add_base or evc.vc_mode_sub_base): evc.vc_mode_add_base = True

def prop_update_vc_mode_add_base(self, context):
	evc = context.scene.evc_props
	if evc.vc_mode_add_base and (evc.vc_mode_set_base or evc.vc_mode_sub_base): evc.vc_mode_set_base, evc.vc_mode_sub_base = False, False
	elif not evc.vc_mode_add_base:
		if not (evc.vc_mode_set_base or evc.vc_mode_sub_base): evc.vc_mode_set_base = True

def prop_update_vc_mode_sub_base(self, context):
	evc = context.scene.evc_props
	if evc.vc_mode_sub_base and (evc.vc_mode_set_base or evc.vc_mode_add_base): evc.vc_mode_set_base, evc.vc_mode_add_base = False, False
	elif not evc.vc_mode_sub_base:
		if not (evc.vc_mode_set_base or evc.vc_mode_add_base): evc.vc_mode_set_base = True

def prop_update_paint_color_base(self, context):
	evc = context.scene.evc_props
	pcb = evc.paint_color_base
	if evc.paint_color_base_r != round(pcb[0]*255): evc.paint_color_base_r = round(pcb[0]*255)
	if evc.paint_color_base_g != round(pcb[1]*255): evc.paint_color_base_g = round(pcb[1]*255)
	if evc.paint_color_base_b != round(pcb[2]*255): evc.paint_color_base_b = round(pcb[2]*255)
	if evc.paint_color_base_a != round(pcb[3]*255): evc.paint_color_base_a = round(pcb[3]*255)

def prop_update_paint_color_base_r(self, context):
	evc = context.scene.evc_props
	if evc.paint_color_base_r/255 != evc.paint_color_base[0]: evc.paint_color_base[0] = evc.paint_color_base_r/255

def prop_update_paint_color_base_g(self, context):
	evc = context.scene.evc_props
	if evc.paint_color_base_g/255 != evc.paint_color_base[1]: evc.paint_color_base[1] = evc.paint_color_base_g/255

def prop_update_paint_color_base_b(self, context):
	evc = context.scene.evc_props
	if evc.paint_color_base_b/255 != evc.paint_color_base[2]: evc.paint_color_base[2] = evc.paint_color_base_b/255

def prop_update_paint_color_base_a(self, context):
	evc = context.scene.evc_props
	if evc.paint_color_base_a/255 != evc.paint_color_base[3]: evc.paint_color_base[3] = evc.paint_color_base_a/255


def prop_update_paint_color_mask_r(self, context):
	evc = context.scene.evc_props
	if not evc.paint_color_mask_r and not (evc.paint_color_mask_g or evc.paint_color_mask_b or evc.paint_color_mask_a): evc.paint_color_mask_g = True
		
def prop_update_paint_color_mask_g(self, context):
	evc = context.scene.evc_props
	if not evc.paint_color_mask_g and not (evc.paint_color_mask_r or evc.paint_color_mask_b or evc.paint_color_mask_a): evc.paint_color_mask_b = True

def prop_update_paint_color_mask_b(self, context):
	evc = context.scene.evc_props
	if not evc.paint_color_mask_b and not (evc.paint_color_mask_r or evc.paint_color_mask_g or evc.paint_color_mask_a): evc.paint_color_mask_a = True

def prop_update_paint_color_mask_a(self, context):
	evc = context.scene.evc_props
	if not evc.paint_color_mask_a and not (evc.paint_color_mask_r or evc.paint_color_mask_g or evc.paint_color_mask_b): evc.paint_color_mask_r = True


def prop_update_paint_randomize_r(self, context):
	evc = context.scene.evc_props
	if not evc.paint_randomize_r and not (evc.paint_randomize_g or evc.paint_randomize_b or evc.paint_randomize_a): evc.paint_randomize_g = True
		
def prop_update_paint_randomize_g(self, context):
	evc = context.scene.evc_props
	if not evc.paint_randomize_g and not (evc.paint_randomize_r or evc.paint_randomize_b or evc.paint_randomize_a): evc.paint_randomize_b = True

def prop_update_paint_randomize_b(self, context):
	evc = context.scene.evc_props
	if not evc.paint_randomize_b and not (evc.paint_randomize_r or evc.paint_randomize_g or evc.paint_randomize_a): evc.paint_randomize_a = True

def prop_update_paint_randomize_a(self, context):
	evc = context.scene.evc_props
	if not evc.paint_randomize_a and not (evc.paint_randomize_r or evc.paint_randomize_g or evc.paint_randomize_b): evc.paint_randomize_r = True


def prop_update_similar_vc_r(self, context):
	evc = context.scene.evc_props
	if not evc.similar_vc_r and not (evc.similar_vc_g or evc.similar_vc_b or evc.similar_vc_a): evc.similar_vc_g = True
		
def prop_update_similar_vc_g(self, context):
	evc = context.scene.evc_props
	if not evc.similar_vc_g and not (evc.similar_vc_r or evc.similar_vc_b or evc.similar_vc_a): evc.similar_vc_b = True

def prop_update_similar_vc_b(self, context):
	evc = context.scene.evc_props
	if not evc.similar_vc_b and not (evc.similar_vc_r or evc.similar_vc_g or evc.similar_vc_a): evc.similar_vc_a = True

def prop_update_similar_vc_a(self, context):
	evc = context.scene.evc_props
	if not evc.similar_vc_a and not (evc.similar_vc_r or evc.similar_vc_g or evc.similar_vc_b): evc.similar_vc_r = True


def prop_update_paint_randomize_l(self, context):
	evc = context.scene.evc_props
	if evc.paint_randomize_l and (evc.paint_randomize_v or evc.paint_randomize_p or evc.paint_randomize_e): evc.paint_randomize_v, evc.paint_randomize_p, evc.paint_randomize_e = False, False, False
	if not evc.paint_randomize_l and not (evc.paint_randomize_v or evc.paint_randomize_p or evc.paint_randomize_e): evc.paint_randomize_v = True

def prop_update_paint_randomize_v(self, context):
	evc = context.scene.evc_props
	if evc.paint_randomize_v and (evc.paint_randomize_l or evc.paint_randomize_p or evc.paint_randomize_e): evc.paint_randomize_l, evc.paint_randomize_p, evc.paint_randomize_e = False, False, False
	if not evc.paint_randomize_v and not (evc.paint_randomize_l or evc.paint_randomize_p or evc.paint_randomize_e): evc.paint_randomize_p = True

def prop_update_paint_randomize_p(self, context):
	evc = context.scene.evc_props
	if evc.paint_randomize_p and (evc.paint_randomize_l or evc.paint_randomize_v or evc.paint_randomize_e): evc.paint_randomize_l, evc.paint_randomize_v, evc.paint_randomize_e = False, False, False
	if not evc.paint_randomize_p and not (evc.paint_randomize_l or evc.paint_randomize_v or evc.paint_randomize_e): evc.paint_randomize_e = True

def prop_update_paint_randomize_e(self, context):
	evc = context.scene.evc_props
	if evc.paint_randomize_e and (evc.paint_randomize_l or evc.paint_randomize_v or evc.paint_randomize_p): evc.paint_randomize_l, evc.paint_randomize_v, evc.paint_randomize_p = False, False, False
	if not evc.paint_randomize_e and not (evc.paint_randomize_l or evc.paint_randomize_v or evc.paint_randomize_p): evc.paint_randomize_l = True


def prop_update_similar_vc_mode_v(self, context):
	evc = context.scene.evc_props
	if evc.similar_vc_mode_v and evc.similar_vc_mode_f: evc.similar_vc_mode_f = False
	if not evc.similar_vc_mode_v and not evc.similar_vc_mode_f: evc.similar_vc_mode_f = True

def prop_update_similar_vc_mode_f(self, context):
	evc = context.scene.evc_props
	if evc.similar_vc_mode_f and evc.similar_vc_mode_v: evc.similar_vc_mode_v = False
	if not evc.similar_vc_mode_f and not evc.similar_vc_mode_v: evc.similar_vc_mode_v = True


def prop_update_mcs_move_mode(self, context):
	evc = context.scene.evc_props
	if evc.mcs_move_mode and (evc.mcs_copy_mode or evc.mcs_swap_mode): evc.mcs_copy_mode, evc.mcs_swap_mode = False, False
	if not evc.mcs_move_mode and not (evc.mcs_copy_mode or evc.mcs_swap_mode): evc.mcs_copy_mode = True

def prop_update_mcs_copy_mode(self, context):
	evc = context.scene.evc_props
	if evc.mcs_copy_mode and (evc.mcs_move_mode or evc.mcs_swap_mode): evc.mcs_move_mode, evc.mcs_swap_mode = False, False
	if not evc.mcs_copy_mode and not (evc.mcs_move_mode or evc.mcs_swap_mode): evc.mcs_swap_mode = True

def prop_update_mcs_swap_mode(self, context):
	evc = context.scene.evc_props
	if evc.mcs_swap_mode and (evc.mcs_move_mode or evc.mcs_copy_mode): evc.mcs_move_mode, evc.mcs_copy_mode = False, False
	if not evc.mcs_swap_mode and not (evc.mcs_move_mode or evc.mcs_copy_mode): evc.mcs_move_mode = True


def prop_update_mcs_a_channel_r(self, context):
	evc = context.scene.evc_props
	if evc.mcs_a_channel_r and (evc.mcs_a_channel_g or evc.mcs_a_channel_b or evc.mcs_a_channel_a): evc.mcs_a_channel_g, evc.mcs_a_channel_b, evc.mcs_a_channel_a = False, False, False
	if not evc.mcs_a_channel_r and not (evc.mcs_a_channel_g or evc.mcs_a_channel_b or evc.mcs_a_channel_a): evc.mcs_a_channel_g = True
	if evc.mcs_a_channel_r and evc.mcs_b_channel_r: evc.mcs_b_channel_r, evc.mcs_b_channel_g = False, True

def prop_update_mcs_a_channel_g(self, context):
	evc = context.scene.evc_props
	if evc.mcs_a_channel_g and (evc.mcs_a_channel_r or evc.mcs_a_channel_b or evc.mcs_a_channel_a): evc.mcs_a_channel_r, evc.mcs_a_channel_b, evc.mcs_a_channel_a = False, False, False
	if not evc.mcs_a_channel_g and not (evc.mcs_a_channel_r or evc.mcs_a_channel_b or evc.mcs_a_channel_a): evc.mcs_a_channel_b = True
	if evc.mcs_a_channel_g and evc.mcs_b_channel_g: evc.mcs_b_channel_g, evc.mcs_b_channel_b = False, True

def prop_update_mcs_a_channel_b(self, context):
	evc = context.scene.evc_props
	if evc.mcs_a_channel_b and (evc.mcs_a_channel_r or evc.mcs_a_channel_g or evc.mcs_a_channel_a): evc.mcs_a_channel_r, evc.mcs_a_channel_g, evc.mcs_a_channel_a = False, False, False
	if not evc.mcs_a_channel_b and not (evc.mcs_a_channel_r or evc.mcs_a_channel_g or evc.mcs_a_channel_a): evc.mcs_a_channel_a = True
	if evc.mcs_a_channel_b and evc.mcs_b_channel_b: evc.mcs_b_channel_b, evc.mcs_b_channel_a = False, True

def prop_update_mcs_a_channel_a(self, context):
	evc = context.scene.evc_props
	if evc.mcs_a_channel_a and (evc.mcs_a_channel_r or evc.mcs_a_channel_g or evc.mcs_a_channel_b): evc.mcs_a_channel_r, evc.mcs_a_channel_g, evc.mcs_a_channel_b = False, False, False
	if not evc.mcs_a_channel_a and not (evc.mcs_a_channel_r or evc.mcs_a_channel_g or evc.mcs_a_channel_b): evc.mcs_a_channel_r = True
	if evc.mcs_a_channel_a and evc.mcs_b_channel_a: evc.mcs_b_channel_a, evc.mcs_b_channel_r = False, True


def prop_update_mcs_b_channel_r(self, context):
	evc = context.scene.evc_props
	if evc.mcs_b_channel_r and (evc.mcs_b_channel_g or evc.mcs_b_channel_b or evc.mcs_b_channel_a): evc.mcs_b_channel_g, evc.mcs_b_channel_b, evc.mcs_b_channel_a = False, False, False
	if not evc.mcs_b_channel_r and not (evc.mcs_b_channel_g or evc.mcs_b_channel_b or evc.mcs_b_channel_a): evc.mcs_b_channel_g = True
	if evc.mcs_b_channel_r and evc.mcs_a_channel_r: evc.mcs_a_channel_r, evc.mcs_a_channel_g = False, True

def prop_update_mcs_b_channel_g(self, context):
	evc = context.scene.evc_props
	if evc.mcs_b_channel_g and (evc.mcs_b_channel_r or evc.mcs_b_channel_b or evc.mcs_b_channel_a): evc.mcs_b_channel_r, evc.mcs_b_channel_b, evc.mcs_b_channel_a = False, False, False
	if not evc.mcs_b_channel_g and not (evc.mcs_b_channel_r or evc.mcs_b_channel_b or evc.mcs_b_channel_a): evc.mcs_b_channel_b = True
	if evc.mcs_b_channel_g and evc.mcs_a_channel_g: evc.mcs_a_channel_g, evc.mcs_a_channel_b = False, True

def prop_update_mcs_b_channel_b(self, context):
	evc = context.scene.evc_props
	if evc.mcs_b_channel_b and (evc.mcs_b_channel_r or evc.mcs_b_channel_g or evc.mcs_b_channel_a): evc.mcs_b_channel_r, evc.mcs_b_channel_g, evc.mcs_b_channel_a = False, False, False
	if not evc.mcs_b_channel_b and not (evc.mcs_b_channel_r or evc.mcs_b_channel_g or evc.mcs_b_channel_a): evc.mcs_b_channel_a = True
	if evc.mcs_b_channel_b and evc.mcs_a_channel_b: evc.mcs_a_channel_b, evc.mcs_a_channel_a = False, True

def prop_update_mcs_b_channel_a(self, context):
	evc = context.scene.evc_props
	if evc.mcs_b_channel_a and (evc.mcs_b_channel_r or evc.mcs_b_channel_g or evc.mcs_b_channel_b): evc.mcs_b_channel_r, evc.mcs_b_channel_g, evc.mcs_b_channel_b = False, False, False
	if not evc.mcs_b_channel_a and not (evc.mcs_b_channel_r or evc.mcs_b_channel_g or evc.mcs_b_channel_b): evc.mcs_b_channel_r = True
	if evc.mcs_b_channel_a and evc.mcs_a_channel_a: evc.mcs_a_channel_a, evc.mcs_a_channel_r = False, True


def prop_update_vc_mp_mode_a(self, context):
	evc = context.scene.evc_props
	if evc.vc_mp_mode_a and evc.vc_mp_mode_b: evc.vc_mp_mode_b = False
	if not evc.vc_mp_mode_a and not evc.vc_mp_mode_b: evc.vc_mp_mode_b = True

def prop_update_vc_mp_mode_b(self, context):
	evc = context.scene.evc_props
	if evc.vc_mp_mode_b and evc.vc_mp_mode_a: evc.vc_mp_mode_a = False
	if not evc.vc_mp_mode_b and not evc.vc_mp_mode_a: evc.vc_mp_mode_a = True


def prop_update_vc_mp_channel_r(self, context):
	evc = context.scene.evc_props
	if not evc.vc_mp_channel_r and not (evc.vc_mp_channel_g or evc.vc_mp_channel_b or evc.vc_mp_channel_a): evc.vc_mp_channel_g = True

def prop_update_vc_mp_channel_g(self, context):
	evc = context.scene.evc_props
	if not evc.vc_mp_channel_g and not (evc.vc_mp_channel_r or evc.vc_mp_channel_b or evc.vc_mp_channel_a): evc.vc_mp_channel_b = True

def prop_update_vc_mp_channel_b(self, context):
	evc = context.scene.evc_props
	if not evc.vc_mp_channel_b and not (evc.vc_mp_channel_r or evc.vc_mp_channel_g or evc.vc_mp_channel_a): evc.vc_mp_channel_a = True

def prop_update_vc_mp_channel_a(self, context):
	evc = context.scene.evc_props
	if not evc.vc_mp_channel_a and not (evc.vc_mp_channel_r or evc.vc_mp_channel_g or evc.vc_mp_channel_b): evc.vc_mp_channel_r = True


def prop_update_vc_inv_channel_r(self, context):
	evc = context.scene.evc_props
	if not evc.vc_inv_channel_r and not (evc.vc_inv_channel_g or evc.vc_inv_channel_b or evc.vc_inv_channel_a): evc.vc_inv_channel_g = True

def prop_update_vc_inv_channel_g(self, context):
	evc = context.scene.evc_props
	if not evc.vc_inv_channel_g and not (evc.vc_inv_channel_r or evc.vc_inv_channel_b or evc.vc_inv_channel_a): evc.vc_inv_channel_b = True

def prop_update_vc_inv_channel_b(self, context):
	evc = context.scene.evc_props
	if not evc.vc_inv_channel_b and not (evc.vc_inv_channel_r or evc.vc_inv_channel_g or evc.vc_inv_channel_a): evc.vc_inv_channel_a = True

def prop_update_vc_inv_channel_a(self, context):
	evc = context.scene.evc_props
	if not evc.vc_inv_channel_a and not (evc.vc_inv_channel_r or evc.vc_inv_channel_g or evc.vc_inv_channel_b): evc.vc_inv_channel_r = True



class EVC_Scene_Properties(bpy.types.PropertyGroup):

	vc_mode_set_base:			bpr.BoolProperty(name= 'Set mode', default= True  ,update= prop_update_vc_mode_set_base,  description= 'Paint Color will override existing VC')
	vc_mode_add_base:			bpr.BoolProperty(name= 'Add mode', default= False ,update= prop_update_vc_mode_add_base,  description= 'Paint Color values will be added to existing VC values')
	vc_mode_sub_base:			bpr.BoolProperty(name= 'Subtract mode', default= False ,update= prop_update_vc_mode_sub_base,  description= 'Paint Color values will be subtracted from existing VC values')

	paint_color_base: 			bpr.FloatVectorProperty(name='', default=(1, 1, 1, 1), min=0.0,max=1.0,step=1,precision=3,
									subtype='COLOR_GAMMA',size=4, update= prop_update_paint_color_base)

	paint_color_base_r:			bpr.IntProperty(name= 'R', default= 255, min= 0, max= 255, subtype= 'FACTOR', update= prop_update_paint_color_base_r,
									description= 'Value of main color R channel. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	paint_color_base_g:			bpr.IntProperty(name= 'G', default= 255, min= 0, max= 255, subtype= 'FACTOR', update= prop_update_paint_color_base_g,
									description= 'Value of main color G channel. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	paint_color_base_b:			bpr.IntProperty(name= 'B', default= 255, min= 0, max= 255, subtype= 'FACTOR', update= prop_update_paint_color_base_b,
									description= 'Value of main color B channel. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')
	paint_color_base_a:			bpr.IntProperty(name= 'A', default= 255, min= 0, max= 255, subtype= 'FACTOR', update= prop_update_paint_color_base_a,
									description= 'Value of main color A channel. Values presented as 0 - 255 (256 steps) because of 8 - bit nature of vertex color data in Bledner')

	eight_bit_line:				bpr.IntProperty(name= '0 - 255 to 0 - 1', default= 255, min= 0, max= 255, subtype= 'FACTOR',
									description= '0 - 255 converted to 0 - 1 format')

	paint_color_mask_r:			bpr.BoolProperty(name= 'Color Mask R', default= True, update= prop_update_paint_color_mask_r,
									description= 'Channels selection for Color Mask. Only selected channels will be painted with Set/Add/Subtract')
	paint_color_mask_g:			bpr.BoolProperty(name= 'Color Mask G', default= True, update= prop_update_paint_color_mask_g,
									description= 'Channels selection for Color Mask. Only selected channels will be painted with Set/Add/Subtract')
	paint_color_mask_b:			bpr.BoolProperty(name= 'Color Mask B', default= True, update= prop_update_paint_color_mask_b,
									description= 'Channels selection for Color Mask. Only selected channels will be painted with Set/Add/Subtract')
	paint_color_mask_a:			bpr.BoolProperty(name= 'Color Mask A', default= True, update= prop_update_paint_color_mask_a,
									description= 'Channels selection for Color Mask. Only selected channels will be painted with Set/Add/Subtract')

	paint_freestyle_mask_base: 	bpr.BoolProperty(name= 'Paint Feestyle Mask', default= False, description= 'Freestyle Mask will be used for masking Set/Add/Subtract, Move/Copy/Swap, Multiply+Power and Invert operators')

	paint_face_mask_base: 		bpr.BoolProperty(name= 'Paint Face Mask', default= False, description= 'Only fully selected faces (in any selection mode) will be edited by Set/Add/Subtract, Move/Copy/Swap, Multiply+Power and Invert operators')

	paint_hidden_base: 			bpr.BoolProperty(name= 'Paint Hidden', default= False, description= 'When enabled Set/Add/Subtract, Move/Copy/Swap, Multiply+Power and Invert operators will also edit currently hidden mesh (DISABLED IF FACE MASKING IS ENABLED !!!)')

	get_vc_in_selected:			bpr.BoolProperty(name= 'Only Selected Objects', default= False, description= 'Get VC only from currently selected mesh objects')

	paint_randomize:			bpr.BoolProperty(name= 'Randomize Paint Color for Set/Add/Subtrach operator', default= False,
									description= 'Paint Color will be randomized in threshold range for loops(face corners)/vertices/faces/elements (depend on selected mode) in selection')
	paint_randomize_l:			bpr.BoolProperty(name= 'Randomize Paint Color per loop',  default= False, update= prop_update_paint_randomize_l,
									description= 'Randomize will work per loop (face corner)')
	paint_randomize_v:			bpr.BoolProperty(name= 'Randomize Paint Color per vertex', default= True, update= prop_update_paint_randomize_v,
									description= 'Randomize will work per vertex')
	paint_randomize_p:			bpr.BoolProperty(name= 'Randomize Paint Color per polygon',  default= False, update= prop_update_paint_randomize_p,
									description= 'Randomize will work per polygon')
	paint_randomize_e:			bpr.BoolProperty(name= 'Randomize Paint Color per element',  default= False, update= prop_update_paint_randomize_e,
									description= 'Randomize will work per element (linked mesh pieces)')

	paint_randomize_static:		bpr.BoolProperty(name= 'Static Seed',  default= False,
									description= 'When enabled randomization will use specific seed value for randomization instead of random')
	paint_randomize_seed:		bpr.IntProperty(name='Randomize Seed', min= 0, max= 1000, subtype= 'FACTOR', 
									description= 'Seed used for generating random values ')
	paint_randomized_only:		bpr.BoolProperty(name= 'Paint Randomized Only',  default= False,
									description= 'Set/Add/Subtract will affect only randomized loops(face corners)/vertices/faces/elements')
	paint_randomize_percentage:	bpr.IntProperty(name='Randomize Percentage', min= 1, max= 100, default= 100, subtype= 'FACTOR', 
									description= 'Percentage of loops(face corners)/vertices/faces/elements (depend on selected mode) in selection for which color will be randomized')
	paint_randomize_factor:		bpr.FloatProperty(name='Randomize Factor', min= -1, max= 1, default= 0, precision=3, subtype= 'FACTOR', 
									description= 'Below 0 you will get more values closer to possible minimum, above 0 more values closer to possible maximum')

	paint_randomize_sub:		bpr.IntProperty(name= 'Randomize Color Subtract', default= 0, min= -255, max= 0, subtype= 'FACTOR',
									description= 'Value of range BELOW Paint Color to generate randomized values')
	paint_randomize_add:		bpr.IntProperty(name='Randomize Color Add', default= 0, min= 0, max= 255, subtype= 'FACTOR',
									description= 'Value of range ABOVE Paint Color to generate randomized values')
	paint_randomize_r:			bpr.BoolProperty(name= 'Randomize Color R', default= True, update= prop_update_paint_randomize_r,
									description= 'Channels selection for randomization features,  only selected channels values will be randomized')
	paint_randomize_g:			bpr.BoolProperty(name= 'Randomize Color G', default= True, update= prop_update_paint_randomize_g,
									description= 'Channels selection for randomization features,  only selected channels values will be randomized')
	paint_randomize_b:			bpr.BoolProperty(name= 'Randomize Color B', default= True, update= prop_update_paint_randomize_b,
									description= 'Channels selection for randomization features,  only selected channels values will be randomized')
	paint_randomize_a:			bpr.BoolProperty(name= 'Randomize Color A', default= True, update= prop_update_paint_randomize_a,
									description= 'Channels selection for randomization features,  only selected channels values will be randomized')

	additional_tools:			bpr.BoolProperty(name= 'EVC Additional Tools', default= False,
									description= 'Expand EVC additional tools UI')

	similar_vc_in_sel:			bpr.BoolProperty(name= 'Similar inside selection', default= False,
									description= 'Check for similar VC only inside current selection')
	similar_vc_mode_v:			bpr.BoolProperty(name= 'Vertices Mode', default= True, update= prop_update_similar_vc_mode_v,
									description= 'Select vertices if vertex belong to loop with VC similar +/- threshold')
	similar_vc_mode_f:			bpr.BoolProperty(name= 'Faces Mode', default= False, update= prop_update_similar_vc_mode_f,
									description= 'Select faces if all face corners (loops) VC similar +/- threshold')
	similar_vc_sub:				bpr.IntProperty(name='Select Similar Subtract', min= -255, max= 0, default= 0, subtype= 'FACTOR', 
									description= 'Value of threshold BELOW current Paint Color to search for vertices with similar colors in range (VC actually stored in "loops"(face corners), more than one vertex color could belong to one Blender vertex!!!)')
	similar_vc_add:				bpr.IntProperty(name='Select Similar Add', min= 0,  max= 255, default= 0, subtype= 'FACTOR', 
									description= 'Value of threshold ABOVE current Paint Color to search for vertices with similar colors in range (VC actually stored in "loops"(face corners), more than one vertex color could belong to one Blender vertex!!!)')
	similar_vc_r:				bpr.BoolProperty(name= 'Select Similar R', default= True, update= prop_update_similar_vc_r,
									description= 'Channels selection for Color Mask/Randomize/Select Similar features. Only selected channels will be taken in to account')
	similar_vc_g:				bpr.BoolProperty(name= 'Select Similar G', default= True, update= prop_update_similar_vc_g,
									description= 'Channels selection for Color Mask/Randomize/Select Similar features. Only selected channels will be taken in to account')
	similar_vc_b:				bpr.BoolProperty(name= 'Select Similar B', default= True, update= prop_update_similar_vc_b,
									description= 'Channels selection for Color Mask/Randomize/Select Similar features. Only selected channels will be taken in to account')
	similar_vc_a:				bpr.BoolProperty(name= 'Select Similar A', default= True, update= prop_update_similar_vc_a,
									description= 'Channels selection for Color Mask/Randomize/Select Similar features. Only selected channels will be taken in to account')

	mcs_move_mode:				bpr.BoolProperty(name= 'MCS Move Mode', default= True, update= prop_update_mcs_move_mode,
									description= 'Move VC from channel A to channel B (channel A will become = 0)')
	mcs_copy_mode:				bpr.BoolProperty(name= 'MCS Copy Mode', default= False, update= prop_update_mcs_copy_mode,
									description= 'Copy VC from channel A to channel B')
	mcs_swap_mode:				bpr.BoolProperty(name= 'MCS Swap Mode', default= False, update= prop_update_mcs_swap_mode,
									description= 'Swap VC between channels A and B')

	mcs_a_channel_r:			bpr.BoolProperty(name= 'MCS A Channel R', default= True, update= prop_update_mcs_a_channel_r,
									description= 'A channel selection for Color Move/Copy/Swap feature')
	mcs_a_channel_g:			bpr.BoolProperty(name= 'MCS A Channel G', default= False, update= prop_update_mcs_a_channel_g,
									description= 'A channel selection for Color Move/Copy/Swap feature')
	mcs_a_channel_b:			bpr.BoolProperty(name= 'MCS A Channel B', default= False, update= prop_update_mcs_a_channel_b,
									description= 'A channel selection for Color Move/Copy/Swap feature')
	mcs_a_channel_a:			bpr.BoolProperty(name= 'MCS A Channel A', default= False, update= prop_update_mcs_a_channel_a,
									description= 'A channel selection for Color Move/Copy/Swap feature')

	mcs_b_channel_r:			bpr.BoolProperty(name= 'MCS B Channel R', default= False, update= prop_update_mcs_b_channel_r,
									description= 'B channel selection for Color Move/Copy/Swap feature')
	mcs_b_channel_g:			bpr.BoolProperty(name= 'MCS B Channel G', default= True, update= prop_update_mcs_b_channel_g,
									description= 'B channel selection for Color Move/Copy/Swap feature')
	mcs_b_channel_b:			bpr.BoolProperty(name= 'MCS B Channel B', default= False, update= prop_update_mcs_b_channel_b,
									description= 'B channel selection for Color Move/Copy/Swap feature')
	mcs_b_channel_a:			bpr.BoolProperty(name= 'MCS B Channel A', default= False, update= prop_update_mcs_b_channel_a,
									description= 'B channel selection for Color Move/Copy/Swap feature')

	vc_mp_mode_a:				bpr.BoolProperty(name= 'Multiply + Power', default= True, update= prop_update_vc_mp_mode_a,
									description= 'First do multiplication then power (in some cases different order give a bit different result)')
	vc_mp_mode_b:				bpr.BoolProperty(name= 'Power + multiply', default= False, update= prop_update_vc_mp_mode_b,
									description= 'First do power then multiplication (in some cases different order give a bit different result)')

	vc_mp_multiplier:			bpr.FloatProperty(name='Multiplier Value', default= 1.0, min=0.0, soft_max=2, step=1, precision=4, subtype='FACTOR')
	vc_mp_exponent:				bpr.FloatProperty(name='Exponent Value', default= 1.0, min=0.0001, soft_max=2, step=1, precision=4, subtype='FACTOR')

	vc_mp_channel_r:			bpr.BoolProperty(name= 'VC Multiply/Power R', default= True, update= prop_update_vc_mp_channel_r,
									description= 'Channels selection for Color Multiply/Power feature')
	vc_mp_channel_g:			bpr.BoolProperty(name= 'VC Multiply/Power G', default= True, update= prop_update_vc_mp_channel_g,
									description= 'Channels selection for Color Multiply/Power feature')
	vc_mp_channel_b:			bpr.BoolProperty(name= 'VC Multiply/Power B', default= True, update= prop_update_vc_mp_channel_b,
									description= 'Channels selection for Color Multiply/Power feature')
	vc_mp_channel_a:			bpr.BoolProperty(name= 'VC Multiply/Power A', default= True, update= prop_update_vc_mp_channel_a,
									description= 'Channels selection for Color Multiply/Power feature')

	vc_inv_channel_r:			bpr.BoolProperty(name= 'VC Invert R', default= True, update= prop_update_vc_inv_channel_r,
									description= 'Channels selection for Color Invert feature')
	vc_inv_channel_g:			bpr.BoolProperty(name= 'VC Invert G', default= True, update= prop_update_vc_inv_channel_g,
									description= 'Channels selection for Color Invert feature')
	vc_inv_channel_b:			bpr.BoolProperty(name= 'VC Invert B', default= True, update= prop_update_vc_inv_channel_b,
									description= 'Channels selection for Color Invert feature')
	vc_inv_channel_a:			bpr.BoolProperty(name= 'VC Invert A', default= True, update= prop_update_vc_inv_channel_a,
									description= 'Channels selection for Color Invert feature')	

	expand_palette:				bpr.BoolProperty(name= 'Color Palette', default= False, description= 'Expand/Collapse color palette panel')

	draw_hit: 					bpr.BoolProperty(name= 'Draw Hit', default= False)

CTR = [
	EVC_PT_Panel,
	EVC_OT_Panel_Popup,
	EVC_OT_Add_Palette_Color,
	EVC_OT_Remove_Palette_Color,
	EVC_OT_Swithc_Face_Overlay,
	EVC_OT_Swithc_Flat_Color_View,
	EVC_OT_Update_Paint_Color,
	EVC_OT_Raycast_Pick_Color,
	EVC_OT_Set_Color,
	EVC_OT_Select_Similar_VC,
	EVC_OT_Move_Copy_Swap,
	EVC_OT_Multiply_Power,
	EVC_OT_Invert_Color,
	EVC_Scene_Properties
	]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)

	bpy.types.Scene.evc_props = bpr.PointerProperty(type= EVC_Scene_Properties, name='EVC_Scene_Properties')

def unregister():
	for cls in CTR:
		bpy.utils.unregister_class(cls)

	del bpy.types.Scene.evc_props
