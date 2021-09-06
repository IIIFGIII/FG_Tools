bl_info = {
	"name": "SOT",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 1),
	"blender": (2, 83, 0),
	"location": "Viev3D > N panel > FGT > SOT",
	"description": "SOT or Set Origin Transform tool. Limitation",
	"warning": "",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}


import bpy, bmesh, math, bgl, gpu, time
import mathutils as mu
from gpu_extras.batch import batch_for_shader

bpr = bpy.props

def do_once():
	return 

def combine_matrix_v3(v1,v2,v3):
	mt = mu.Matrix.Identity(3)
	mt.col[0] = v1
	mt.col[1] = v2
	mt.col[2] = v3
	return mt

def tov3(x,y,z):
	return mu.Vector((x,y,z))

def tov4(xyz,w):
	return mu.Vector((xyz[0],xyz[1],xyz[2],w))

def vector_fix(obm,vector):
	return (obm.inverted_safe().transposed().to_3x3() @ vector).normalized()

def distance(va,vb):
	return math.sqrt((vb[0]-va[0])**2+(vb[1]-va[1])**2+(vb[2]-va[2])**2)

def remap(va,vb,ra,rb,rv):
	if va == vb or ra == rb: return va
	else:
		if ra<rb and rv<=ra or ra>rb and rv>=ra: return va
		elif ra<rb and rv>=rb or ra>rb and rv<=rb: return vb
		else: return (va+(((rv-ra)/(rb-ra))*(vb-va)))

def vectors_remap(vx,vy,vz,sot):

	xr,yr,zr = vx,vy,vz
	zax = sot.z_axis

	if zax == 'z+': 
		rem = sot.rem_zp 
		vz = zr
		if   rem == '1': vx,vy = xr,yr
		elif rem == '2': vx,vy = yr,xr*-1
		elif rem == '3': vx,vy = xr*-1,yr*-1
		elif rem == '4': vx,vy = yr*-1,xr

	elif zax == 'z-': 
		rem = sot.rem_zn 
		vz = zr*-1
		if   rem == '1': vx,vy = xr,yr*-1
		elif rem == '2': vx,vy = yr,xr
		elif rem == '3': vx,vy = xr*-1,yr
		elif rem == '4': vx,vy = yr*-1,xr*-1

	elif zax == 'y+': 
		rem = sot.rem_yp
		vz = yr
		if   rem == '1': vx,vy = xr,zr*-1
		elif rem == '2': vx,vy = zr,xr
		elif rem == '3': vx,vy = xr*-1,zr
		elif rem == '4': vx,vy = zr*-1,xr*-1

	elif zax == 'y-': 
		rem = sot.rem_yn
		vz = yr*-1
		if   rem == '1': vx,vy = xr,zr
		elif rem == '2': vx,vy = zr,xr*-1
		elif rem == '3': vx,vy = xr*-1,zr*-1
		elif rem == '4': vx,vy = zr*-1,xr

	elif zax == 'x+': 
		rem = sot.rem_xp
		vz = xr
		if   rem == '1': vx,vy = zr*-1,yr
		elif rem == '2': vx,vy = yr,zr
		elif rem == '3': vx,vy = zr,yr*-1
		elif rem == '4': vx,vy = yr*-1,zr*-1

	elif zax == 'x-': 
		rem = sot.rem_xn
		vz = xr*-1
		if   rem == '1':  	vx = zr
		elif rem == '2': vx,vy = yr,zr*-1
		elif rem == '3': vx,vy = zr*-1,yr*-1
		elif rem == '4': vx,vy = yr*-1,zr

	return vx,vy,vz

def get_cursor_loc_rot(bco,sot,loc):
	mt = bco.scene.cursor.matrix
	if loc:
		return mu.Vector(mt.col[3][:3])
	else:
		mt = mt.to_3x3()
		vx,vy,vz = mu.Vector(mt.col[0]),mu.Vector(mt.col[1]),mu.Vector(mt.col[2])
		vx,vy,vz = vectors_remap(vx,vy,vz,sot)
		return combine_matrix_v3(vx,vy,vz)

def get_element_loc(rep,bco,aob):

	bmd = bmesh.from_edit_mesh(bco.edit_object.data)
	bma = bmd.select_history.active
	
	if bma == None:
		rep({'ERROR'}, 'No active element in selection!!!')
		return {'CANCELLED'}
		
	else:
		obm = aob.matrix_world
		if str(bma).find('BMVert') == 1:
			co = bma.co
		else:
			co = mu.Vector((0,0,0))
			verts = bma.verts
			for v in verts:
				co += v.co
			co = co/len(verts)
		if obm.to_scale() != (1.0,1.0,1.0):
			co = obm @ co
		return co

def get_element_vectors(rep,bco,sot,aob):

	bmd = bmesh.from_edit_mesh(bco.edit_object.data)
	bma = bmd.select_history.active
	vzw = mu.Vector((0,0,1))
	obm = aob.matrix_world

	if bma == None:
		rep({'ERROR'}, 'No active element in selection!!!')
		return{'CANCELLED'}

	else:
		if str(bma).find('BMVert') == 1:

			if len(bma.link_faces) == 0:
				vz = vector_fix(obm, (bma.co - mu.Vector(obm.col[3][:3])))
				if vz[2]>0:
					m = -1
				else:
					vzw = vzw*-1
					m = 1
				
				if vzw.dot(vz) > 0.5:
					vy = (vzw - (vzw.dot(vz)*vz)).normalized() * m
				else:
					m = m*-1
					vm = (vz * mu.Vector((1,1,0))).normalized()
					vy = (vm - (vm.dot(vz)*vz)).normalized() * m
				
				if (abs(sum(vy[:]))) == 0:
					if abs(vz[2]) == 1:
						vy = mu.Vector((0,1,0))
					elif vz[2] == 0:
						vy = mu.Vector((0,0,-1))
				vx = (vz.cross(vy))*-1

			else:
				vz = vector_fix(obm, bma.normal)
				if vz[2]>0:
					m = -1
				else:
					vzw = vzw*-1
					m = 1
				
				if vzw.dot(vz) > 0.5:
					vy = (vzw - (vzw.dot(vz)*vz)).normalized() * m
				else:
					m = m*-1
					vm = (vz * mu.Vector((1,1,0))).normalized()
					vy = (vm - (vm.dot(vz)*vz)).normalized() * m
				
				if (abs(sum(vy[:]))) == 0:
					if abs(vz[2]) == 1:
						vy = mu.Vector((0,1,0))
					elif vz[2] == 0:
						vy = mu.Vector((0,0,-1))

				vx = (vz.cross(vy))*-1

		elif str(bma).find('BMEdge') == 1:

			vy = vector_fix(obm, (bma.verts[0].co - bma.verts[1].co).normalized())

			if len(bma.link_faces) == 0:
				if vy[2]>0:
					m = -1
				else:
					vzw = vzw*-1
					m = 1

				if vzw.dot(vy) > 0.5:
					vz = (vzw - (vzw.dot(vy)*vy)).normalized() * m
				else:
					m = m*-1
					vm = (vy * mu.Vector((1,1,0))).normalized()
					vz = (vm - (vm.dot(vy)*vy)).normalized() * m
			elif len(bma.link_faces) == 1:
				vz = vector_fix(obm, bma.link_faces[0].normal) 
			else:
				vz = ((vector_fix(obm, bma.link_faces[0].normal) + vector_fix(obm, bma.link_faces[1].normal))/2).normalized()

			vx = (vz.cross(vy))*-1
		
		else:
			vz = vector_fix(obm, bma.normal)
			if len(bma.verts)	== 3:
				vy = vector_fix(obm, (bma.calc_tangent_edge())*-1)
			elif len(bma.verts) == 4:
				vy = vector_fix(obm, ((bma.calc_tangent_edge_pair()).normalized())*-1)
			else:
				le,ei = 0,-1
				c = 0
				for i,e in enumerate(bma.edges):
					if e.calc_length() > le:
						le = e.calc_length()
						ei = i
				vy = ector_fix(obm, (bma.edges[ei].verts[0].co - bma.edges[ei].verts[1].co).normalized())
				vy = vy-(vy.dot(vz)*vz)

			vx = (vz.cross(vy))*-1


		vx,vy,vz = vectors_remap(vx,vy,vz,sot)

		return combine_matrix_v3(vx,vy,vz)

def get_object_loc_rot(rep,bco,sot,loc):

	bcv = bco.view_layer
	aob = bcv.objects.active

	if aob == None:
		rep({'ERROR'}, 'No active object in selection!!!!')
		return{'CANCELLED'}
	else:
		if loc:
			return mu.Vector(aob.matrix_world.col[3][:3])
		else:
			mt = aob.matrix_world.to_3x3().normalized()
			vx,vy,vz = mu.Vector(mt.col[0]),mu.Vector(mt.col[1]),mu.Vector(mt.col[2])
			vx,vy,vz = vectors_remap(vx,vy,vz,sot)
			return combine_matrix_v3(vx,vy,vz)

def set_manual_values(sot,value,loc):
	if loc:
		sot.loc_x,sot.loc_y,sot.loc_z = value
	else:
		if abs(value[0]) < 0.0001: value[0] = 0
		if abs(value[1]) < 0.0001: value[1] = 0
		if abs(value[2]) < 0.0001: value[2] = 0
		sot.rot_x,sot.rot_y,sot.rot_z = value
	return

def screen_size(bco,loc):
	s3d = bco.space_data.region_3d
	a3d = bco.area.spaces.active.region_3d

	if s3d.view_perspective == 'ORTHO':
		scl = a3d.view_distance/10
	elif s3d.view_perspective == 'PERSP':
		vmt = a3d.view_matrix
		scl = abs(distance(vmt @ loc,mu.Vector((0,0,0))))/10
	else:
		zo = a3d.view_camera_zoom   
		vmt = a3d.view_matrix
		if zo>0:
			v = 3.14**(((30+((zo)+30))/30)*remap(1,0.26,0,1,math.sqrt((zo/600)**0.7)))
		else:
			v = 3.14**((30+((zo)+30))/30)
		scl = abs(distance(vmt @ loc,mu.Vector((0,0,0))))/v

	return scl

def draw_axis_main(self,context):
	bco = bpy.context
	sot = context.scene.sot_props

	vc = [(-0.3, 0.0, 0.0), (-0.1, 0.0, 0.0),
		(0.0, -0.3, 0.0), (0.0, -0.1, 0.0),
		(0.0, 0.0, -0.3), (0.0, 0.0, -0.1),
		(0.1, 0.0, 0.0), (1.0, 0.0, 0.0),
		(0.0, 0.1, 0.0), (0.0, 1.0, 0.0),
		(0.0, 0.0, 0.1), (0.0, 0.0, 1.0)]
	vcm = []

	loc = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
	euler = mu.Euler((sot.rot_x,sot.rot_y,sot.rot_z),'XYZ')
	rot = euler.to_matrix()

	scl = screen_size(bco,loc)

	for v in vc:
		v = (rot @ (mu.Vector(v) * scl)) + loc
		vcm.append(v)

	shader = gpu.shader.from_builtin('3D_SMOOTH_COLOR')
	col = [(1.0, 1.0, 1.0, 0.8), (1.0, 1.0, 1.0, 0.8),
		(1.0, 1.0, 1.0, 0.8), (1.0, 1.0, 1.0, 0.8),
		(1.0, 1.0, 1.0, 0.8), (1.0, 1.0, 1.0, 0.8),
		(1.0, 0.0, 0.0, 1.0), (1.0, 0.0, 0.0, 1.0),
		(0.0, 1.0, 0.0, 1.0), (0.0, 1.0, 0.0, 1.0),
		(0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0)]
	batch = batch_for_shader(shader, 'LINES', {"pos": vcm, "color": col})
	bgl.glLineWidth(5)
	shader.bind()
	batch.draw(shader)
	bgl.glLineWidth(1)
	return

def draw_axis_update(self, context):
	if context.scene.sot_props.draw_axis:
		bpy.ops.fgt.sot_draw_axis('INVOKE_DEFAULT')
	return

def draw_spots_update(self, context):
	sot =  context.scene.sot_props
	if sot.draw_spots:
		if sot.spots_auto == '2' and sot.spots_calc == False:
			 sot.spots_calc == True
		bpy.ops.fgt.sot_draw_spots('INVOKE_DEFAULT')
	return

class SOT_PT_Panel(bpy.types.Panel):
	bl_label = 'SOT'
	bl_idname = 'SOT_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'

	def draw(self, context):
		layout = self.layout

class SOT_PT_Location_Orientation(bpy.types.Panel):
	bl_label = 'Location & Orientation'
	bl_idname = 'SOT_PT_Location_Orientation'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Panel'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		bco = bpy.context
		sot = context.scene.sot_props

		layout = self.layout
		col = layout.column(align=True)

		col.label(text= 'Set Origin:')
		row = col.row(align=True)
		row.operator('fgt.sot_set_origin_location', icon='TRANSFORM_ORIGINS', text='Location')
		row.operator('fgt.sot_set_origin_orientation', icon='ORIENTATION_GIMBAL', text='Orientation')
		col.separator(factor=1)

		row = col.row(align=True)
		row.prop_enum(sot, 'active_batch', icon= 'DOT', value= '1')
		row.prop_enum(sot, 'active_batch', icon= 'LIGHTPROBE_GRID', value= '2')
		row = col.row(align=True)
		row.prop(sot, 'draw_axis', text= 'Hide Helper Axis' if sot.draw_axis else 'Show Helper Axis', icon='EMPTY_AXIS', toggle= True)

class SOT_PT_Location(bpy.types.Panel):
	bl_label = 'Location'
	bl_idname = 'SOT_PT_Location'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Location_Orientation'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		sot = context.scene.sot_props
		clear = 'fgt.sot_clear_value'
		get = 'fgt.sot_get_transform'

		layout = self.layout
		col = layout.column(align=True)


		col.label(text= 'Location Values')
		row = col.row(align=True)
		row.prop(sot, 'loc_x', text= 'X') 	
		row.operator(clear, icon='X' if sot.loc_x != 0 else 'DOT', text='').cop = 'loc_x'
		row = col.row(align=True)
		row.prop(sot, 'loc_y', text= 'Y')
		row.operator(clear, icon='X' if sot.loc_y != 0 else 'DOT', text='').cop = 'loc_y'
		row = col.row(align=True)			
		row.prop(sot, 'loc_z', text= 'Z')
		row.operator(clear, icon='X' if sot.loc_z != 0 else 'DOT', text='').cop = 'loc_z'
		col.separator(factor=1)

		row = col.row(align=True)
		row.operator('fgt.sot_set_origin_location', icon='TRANSFORM_ORIGINS', text='Set Origin Location')
		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Get Cursor').gop = 'l_c'
		row.operator(get, icon='PIVOT_ACTIVE', text='Get Active').gop = 'l_a'

class SOT_PT_Orientation(bpy.types.Panel):
	bl_label = 'Orientation'
	bl_idname = 'SOT_PT_Orientation'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Location_Orientation'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		bco = bpy.context
		sot = context.scene.sot_props
		rotate = 'fgt.sot_rotate_ninety'
		clear = 'fgt.sot_clear_value'
		get = 'fgt.sot_get_transform'

		zax_dic = {'z+':'rem_zp','z-':'rem_zn','y+':'rem_yp','y-':'rem_yn','x+':'rem_xp','x-':'rem_xn'}
		rem_dic = {'z+':sot.rem_zp,'z-':sot.rem_zn,'y+':sot.rem_yp,'y-':sot.rem_yn,'x+':sot.rem_xp,'x-':sot.rem_xn}

		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		row.label(text= 'Rotation Values')
		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='').rop = '-rot_x'
		row.operator(rotate, icon='LOOP_BACK',     text='').rop = '+rot_x'
		row.prop(sot, 'rot_x', text= 'X')
		row.operator(clear, icon='X' if sot.rot_x != 0 else 'DOT', text='').cop = 'rot_x'
		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='').rop = '-rot_y'
		row.operator(rotate, icon='LOOP_BACK',     text='').rop = '+rot_y'
		row.prop(sot, 'rot_y', text= 'Y')
		row.operator(clear, icon='X' if sot.rot_y != 0 else 'DOT', text='').cop = 'rot_y'
		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='').rop = '-rot_z'
		row.operator(rotate, icon='LOOP_BACK',     text='').rop = '+rot_z'
		row.prop(sot, 'rot_z', text= 'Z')
		row.operator(clear, icon='X' if sot.rot_z != 0 else 'DOT', text='').cop = 'rot_z'
		col.separator(factor=1)
		
		row = col.row(align=True)
		row.operator('fgt.sot_set_origin_orientation', icon='ORIENTATION_GIMBAL', text='Set Origin Orientation')
		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Get Cursor').gop = 'r_c'
		row.operator(get, icon='PIVOT_ACTIVE', text='Get Active').gop = 'r_a'

		row = col.row(align=True)
		row.label(text= 'Z Axis Remap')
		row.prop(sot, 'z_axis', text= '')
		row.operator(clear, icon='X' if sot.z_axis != 'z+' else 'DOT', text='').cop = 'z_axis'
		row = col.row(align=True)			
		row.prop(sot, zax_dic.get(sot.z_axis), text= '')
		row.operator(clear, icon='X' if rem_dic.get(sot.z_axis) != '1' else 'DOT', text='').cop = zax_dic.get(sot.z_axis)

class SOT_PT_Fixed_Snap(bpy.types.Panel):
	bl_label = 'Fixed Spots Snap'
	bl_idname = 'SOT_PT_Fixed_Snap'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Panel'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		bco = bpy.context
		sot = context.scene.sot_props
		clear = 'fgt.sot_clear_value'

		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		row.prop_enum(sot, 'set_pick', icon='TRANSFORM_ORIGINS', value= '1')
		row.prop_enum(sot, 'set_pick', icon='EXPORT', value= '2')
		if sot.set_pick == '1':
			row = col.row(align=True)
			row.prop_enum(sot, 'active_batch_spot', icon='DOT', value= '1')
			row.prop_enum(sot, 'active_batch_spot', icon='LIGHTPROBE_GRID', value= '2')
		if sot.active_batch_spot == '2' and sot.set_pick == '1':
			row = col.row(align=True)
			row.prop_enum(sot, 'batch_spot_mode', icon='PARTICLE_DATA', value= '1')
			row.prop_enum(sot, 'batch_spot_mode', icon='PRESET', value= '2')	
		col.separator(factor=1)

		row = col.row(align=True)
		row.prop_enum(sot, 'drop_p', value= '1')
		row.prop_enum(sot, 'drop_p', value= '2')
		row.prop_enum(sot, 'drop_p', value= '3')
		row = col.row(align=True)
		row.prop_enum(sot, 'drop_d', icon='ADD', value= '1')
		row.prop_enum(sot, 'drop_d', icon='REMOVE', value= '2')
		row = col.row(align=True)
		row.prop_enum(sot, 'drop_s', icon='FULLSCREEN_ENTER', value= '1')
		row.prop_enum(sot, 'drop_s', icon='FULLSCREEN_EXIT', value= '2')
		col.separator(factor=1)

		row = col.row(align=True)
		row.operator('fgt.sot_fixed_snap', icon='TRIA_UP', text='')				.dop = 'np'
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_FREE_VEC', text='')					.dop = 'cp'
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_FREE_VEC', text='')					.dop = 'pp'
		row.operator('fgt.sot_fixed_snap', icon='KEYTYPE_BREAKDOWN_VEC', text='Border Mesh')	.dop = 'bom'
		row = col.row(align=True)
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_VECTOR_VEC', text='')				.dop = 'nc'
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_FREE_VEC', text='')					.dop = 'cc'
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_FREE_VEC', text='')					.dop = 'pc'
		row.operator('fgt.sot_fixed_snap', icon='KEYTYPE_EXTREME_VEC', text='Bound Center')		.dop = 'boc'
		row = col.row(align=True)
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_VECTOR_VEC', text='')				.dop = 'nn'
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_VECTOR_VEC', text='')				.dop = 'cn'
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_VECTOR_VEC', text='')				.dop = 'pn'
		row.operator('fgt.sot_fixed_snap', icon='KEYTYPE_KEYFRAME_VEC', text='Center Of Mass')	.dop = 'com'
		col.separator(factor=1)

		row = col.row(align=True)	
		if sot.drop_s == '2':
			row.operator('fgt.sot_fixed_snap', icon='TRIA_DOWN_BAR', text='Drop To Bound')		.dop = 'dtp'
		else:
			row.operator('fgt.sot_fixed_snap', icon='TRIA_DOWN_BAR', text='Drop To')			.dop = 'dtp'
			row = col.row(align=True)		
			row.prop_enum(sot, 'ground_bound', icon='SNAP_PERPENDICULAR', value= '1')
			row.prop_enum(sot, 'ground_bound', icon='SNAP_FACE_CENTER', value= '2')	
		row = col.row(align=True)
		row.prop(sot, 'offset', text= 'Ground Offset' if sot.ground_bound == '1' and sot.drop_s == '1' else 'Bound Offset')
		row.operator(clear, icon='X' if sot.offset != 0 else 'DOT', text='').cop = 'offset'
		col.separator(factor=1)

		row = col.row(align=True)
		row.prop(sot, 'draw_spots', text= 'Hide Spots' if sot.draw_spots else 'Show Spots', icon='AXIS_FRONT', toggle= True)
		if sot.spots_auto == '2':
			row.prop(sot, 'spots_calc', text= 'Refresh', icon='FILE_REFRESH', toggle= True)
		row = col.row(align=True)
		row.prop_enum(sot, 'spots_auto', icon='AUTO', value= '1')
		row.prop_enum(sot, 'spots_auto', icon='SORTTIME', value= '2')
		row = col.row(align=True)
		row.prop(sot, 'spots_scale', text= 'Spots Scale')
		row.operator(clear, icon='X' if sot.spots_scale != 1 else 'DOT', text='').cop = 'spots_scale'


def object_in_edit(sob_r):
	eob = []
	for ob in sob_r:
		if ob.mode == 'EDIT': 
			print('Edit Object')
			eob.append(ob)
		elif ob.mode == 'OBJECT':
			print('Simple Object') 
			ob.select_set(False)
	if eob != []:
		bpy.ops.object.editmode_toggle()
	return eob

def recover_edit(eob,sob_r):
	if eob != []:
		for ob in eob: ob.select_set(True)
		bpy.ops.object.editmode_toggle()
	for ob in sob_r: ob.select_set(True)
	return

def set_origin_location(x,y,z,tob):
	loc = tob.matrix_world.col[3]
	pos = mu.Vector((x,y,z,1))
	dif = mu.Vector((loc - pos)[:3])
	tob.matrix_world.col[3] = pos
	obm = tob.matrix_world
	tmt = mu.Matrix.Identity(4)
	tmt.col[3] = tov4(obm.to_3x3().inverted() @ dif,1)		
	tob.data.transform(tmt)
	return

#((1.0000, 0.0000, 0.0000, 0.0000),(0.0000, 1.0000, 0.0000, 5.0139),(0.0000, 0.0000, 1.0000, 0.0000),(0.0000, 0.0000, 0.0000, 1.0000))
#M = mu.Matrix(((1, 0, 0, 0),(0, 0.707, 0.707, 0),(0, -0.707, 0.707, 0), (1, 0, 0, 1)))
#tmt = mu.Matrix(((1, 0, 0, 1),(0, 1, 0, 0),(0, 0, 1, 0), (0, 0, 0, 1)))

class SOT_OT_Set_Location(bpy.types.Operator):
	bl_idname = 'fgt.sot_set_origin_location'
	bl_label = 'Set Origin Location'
	bl_description = 'Set ACTIVE object origin location'

	def execute(self,context):
		sot = context.scene.sot_props
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active
		sob = bco.selected_objects
		sob_r = sob

		eob = object_in_edit(sob_r)

		if sot.active_batch == '1':
			if aob == None:
				self.report({'ERROR'}, 'No ACTIVE object in selection!!!!')
				return{'CANCELLED'}
			set_origin_location(sot.loc_x,sot.loc_y,sot.loc_z,aob)
			bpy.ops.ed.undo_push(message = 'Set Origin Location A' )
		else:
			if sob == []:
				self.report({'ERROR'}, 'No SELECTED objects!!!!')
				return{'CANCELLED'}
			for tob in sob:
				set_origin_location(sot.loc_x,sot.loc_y,sot.loc_z,tob)
			bpy.ops.ed.undo_push(message = 'Set Origin Location B' )

		recover_edit(eob,sob_r)

		return {'FINISHED'}

def set_origin_orientation(x,y,z,tob,bob,app_scl):
	bob.select_all(action='DESELECT')
	tob.select_set(True)
	rmt = (mu.Euler((x,y,z),'XYZ')).to_matrix()
	loc = tob.matrix_world.col[3]
	scl = tob.matrix_world.to_scale()
	rmt_m = rmt.to_4x4()
	rmt_m.col[0] = rmt_m.col[0]*scl[0]
	rmt_m.col[1] = rmt_m.col[1]*scl[1]
	rmt_m.col[2] = rmt_m.col[2]*scl[2] 	
	rmt_m.col[3] = loc
	rmt = (tob.matrix_world.to_3x3().inverted() @ rmt).to_4x4()
	rmt.col[0] = rmt.col[0]*scl[0]
	rmt.col[1] = rmt.col[1]*scl[1]
	rmt.col[2] = rmt.col[2]*scl[2]
	tob.data.transform(rmt.inverted())
	tob.matrix_world = rmt_m
	if app_scl:
		bob.transform_apply(location = False, rotation= False, scale= True,  properties=False)
	return


class SOT_OT_Set_Orientation(bpy.types.Operator):
	bl_idname = 'fgt.sot_set_origin_orientation'
	bl_label = 'Set Origin Orientation'
	bl_description = 'Set ACTIVE object origin orientation'

	def execute(self,context):
		bob = bpy.ops.object
		sot = context.scene.sot_props
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active
		sob = bco.selected_objects
		sob_r = sob

		eob = object_in_edit(sob_r)

		if sot.active_batch == '1':
			if aob == None:
				self.report({'ERROR'}, 'No ACTIVE object in selection!!!!')
				return{'CANCELLED'}
			set_origin_orientation(sot.rot_x,sot.rot_y,sot.rot_z,aob,bob,sot.apply_scale)
			bpy.ops.ed.undo_push(message = 'Set Origin Orientation A' )
		else:
			if sob == []:
				self.report({'ERROR'}, 'No SELECTED objects!!!!')
				return{'CANCELLED'}
			for tob in sob:
				set_origin_orientation(sot.rot_x,sot.rot_y,sot.rot_z,tob,bob,sot.apply_scale)
			bpy.ops.ed.undo_push(message = 'Set Origin Orientation B' )

		recover_edit(eob,sob_r)

		return {'FINISHED'}

class SOT_OT_Get_Transform(bpy.types.Operator):
	bl_idname = 'fgt.sot_get_transform'
	bl_label = 'SOT_OT_Get_Transform'
	bl_description = 'Get transform values from...'

	gop: bpr.StringProperty(name = '', default = '')

	def execute(self,context):
		sot = context.scene.sot_props
		gop = self.gop
		rep = self.report
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active

		if gop == 'l_c':		#Get location from Cursor
			set_manual_values(sot,get_cursor_loc_rot(bco,sot,True),True)

		elif gop == 'l_a':		#Get location from Active Object/Element
			if bco.mode == 'OBJECT':
				value = get_object_loc_rot(rep,bco,sot,True)
				if type(value) is not set: set_manual_values(sot,value,True)
			elif bco.mode == 'EDIT_MESH':
				value = get_element_loc(rep,bco,aob)
				if type(value) is not set: set_manual_values(sot, value,True)

		elif gop == 'r_c':		#Get rotation from Cursor
			set_manual_values(sot, get_cursor_loc_rot(bco,sot,False).to_euler(), False)

		elif gop == 'r_a':		#Get rotation from Active Object/Element
			if bco.mode == 'OBJECT':
				value = get_object_loc_rot(rep,bco,sot,False)
				if type(value) is not set: set_manual_values(sot, value.to_euler(), False)
			elif bco.mode == 'EDIT_MESH':
				value = get_element_vectors(rep,bco,sot,aob)
				if type(value) is not set: set_manual_values(sot, value.to_euler(), False)

		return {'FINISHED'}


class SOT_OT_Rotate_Ninety(bpy.types.Operator):
	bl_idname = 'fgt.sot_rotate_ninety'
	bl_label = 'SOT_OT_Rotate_Ninety'
	bl_description = 'Rotate orientation around this axis by 90 degrees'	

	rop: bpr.StringProperty(name = '', default = '')

	def execute(self,context):

		sot = context.scene.sot_props

		euler = mu.Euler((sot.rot_x,sot.rot_y,sot.rot_z),'XYZ')
		rmt = euler.to_matrix()
		rop_dic = {'x':rmt.col[0],'y':rmt.col[1],'z':rmt.col[2],'-':-90, '+':90}
		rmt.rotate(mu.Quaternion(rop_dic.get(self.rop[-1]), math.radians(rop_dic.get(self.rop[0]))))
		sot.rot_x,sot.rot_y,sot.rot_z = rmt.to_euler()

		if abs(math.degrees(sot.rot_x)) < 0.0001:
			sot.rot_x = 0
		if abs(math.degrees(sot.rot_y)) < 0.0001:
			sot.rot_y = 0
		if abs(math.degrees(sot.rot_z)) < 0.0001:
			sot.rot_z = 0

		return {'FINISHED'}

def vco(coord,v,b,number,vector,count):
	if b:
		if round(coord[v],5) >= number:
			number = round(coord[v],5)
			if round(coord[v],5) == round(vector[v]/count,5):
				vector = vector + coord
				count += 1
			else:
				vector = coord
				count = 1
	else:
		if round(coord[v],5) <= number:
			number = round(coord[v],5)
			if round(coord[v],5) == round(vector[v]/count,5):
				vector = vector + coord
				count += 1
			else:
				vector = coord
				count = 1
	return number,vector,count

def spots(sot,obm,vdata):
	fv = obm @ vdata[0].co if sot.drop_s == '1' else vdata[0].co
	xn,xp,yn,yp,zn,zp = round(fv[0],5),round(fv[0],5),round(fv[1],5),round(fv[1],5),round(fv[2],5),round(fv[2],5)
	xnv = xpv = ynv = ypv = znv = zpv = fv
	xnc = xpc = ync = ypc = znc = zpc = 1
	csm = fv

	for v in vdata[1:]:
		co = obm @ v.co if sot.drop_s == '1' else v.co
		xn,xnv,xnc = vco(co,0,False,xn,xnv,xnc)
		xp,xpv,xpc = vco(co,0,True,xp,xpv,xpc)
		yn,ynv,ync = vco(co,1,False,yn,ynv,ync)
		yp,ypv,ypc = vco(co,1,True,yp,ypv,ypc)
		zn,znv,znc = vco(co,2,False,zn,znv,znc)
		zp,zpv,zpc = vco(co,2,True,zp,zpv,zpc)
		csm = csm + co

	boc = mu.Vector((((xn+xp)/2),((yn+yp)/2),((zn+zp)/2)))
	com = csm/len(vdata)

	if xnc != 1: xnv = xnv/xnc
	if xpc != 1: xpv = xpv/xpc
	if ync != 1: ynv = ynv/ync
	if ypc != 1: ypv = ypv/ypc
	if znc != 1: znv = znv/znc
	if zpc != 1: zpv = zpv/zpc

	sps = {'xn':xn,'xp':xp,'yn':yn,'yp':yp,'zn':zn,'zp':zp,'boc':boc,'com':com,
			'xnv':xnv,'xpv':xpv,'ynv':ynv,'ypv':ypv,'znv':znv,'zpv':zpv,}
	return sps

def projection(sot,obm,sps):

	xn,xp,yn,yp,zn,zp,boc = sps.get('xn'),sps.get('xp'),sps.get('yn'),sps.get('yp'),sps.get('zn'),sps.get('zp'),sps.get('boc')
	xc,yc,zc = boc[0],boc[1],boc[2]
	dtp_a = mu.Vector((obm.to_translation()[:3])) if sot.drop_s == '1' else mu.Vector((0,0,0))

	if sot.drop_d == '1': x,y,z = xp,yp,zp
	else: x,y,z = xn,yn,zn

	dps = sot.drop_s
	gtb = sot.ground_bound
	off = sot.offset

	if sot.drop_p == '1':
		dtp_b = mu.Vector((x+off,dtp_a[1],dtp_a[2])) if gtb == '2' or dps == '2' else mu.Vector((off,dtp_a[1],dtp_a[2]))
		psp =  {'np':mu.Vector((x,yn,zp)),'cp':mu.Vector((x,yc,zp)),'pp':mu.Vector((x,yp,zp)),
						'nc':mu.Vector((x,yn,zc)),'cc':mu.Vector((x,yc,zc)),'pc':mu.Vector((x,yp,zc)),
						'nn':mu.Vector((x,yn,zn)),'cn':mu.Vector((x,yc,zn)),'pn':mu.Vector((x,yp,zn))}
	elif sot.drop_p == '2':
		dtp_b = mu.Vector((dtp_a[0],y+off,dtp_a[2])) if gtb == '2' or dps == '2' else mu.Vector((dtp_a[0],off,dtp_a[2]))
		psp =  {'np':mu.Vector((xn,y,zp)),'cp':mu.Vector((xc,y,zp)),'pp':mu.Vector((xp,y,zp)),
						'nc':mu.Vector((xn,y,zc)),'cc':mu.Vector((xc,y,zc)),'pc':mu.Vector((xp,y,zc)),
						'nn':mu.Vector((xn,y,zn)),'cn':mu.Vector((xc,y,zn)),'pn':mu.Vector((xp,y,zn))}
	else:
		dtp_b = mu.Vector((dtp_a[0],dtp_a[1],z+off)) if gtb == '2' or dps == '2' else mu.Vector((dtp_a[0],dtp_a[1],off))
		psp =  {'np':mu.Vector((xn,yp,z)),'cp':mu.Vector((xc,yp,z)),'pp':mu.Vector((xp,yp,z)),
						'nc':mu.Vector((xn,yc,z)),'cc':mu.Vector((xc,yc,z)),'pc':mu.Vector((xp,yc,z)),
						'nn':mu.Vector((xn,yn,z)),'cn':mu.Vector((xc,yn,z)),'pn':mu.Vector((xp,yn,z))}

	if sot.drop_p == '1':
		bom = sps.get('xpv') if sot.drop_d == '1' else sps.get('xnv')
	elif sot.drop_p == '2':
		bom = sps.get('ypv') if sot.drop_d == '1' else sps.get('ynv')
	else:
		bom = sps.get('zpv') if sot.drop_d == '1' else sps.get('znv')

	psp['bom'] = bom
	psp['boc'] = sps.get('boc')
	psp['com'] = sps.get('com')

	cage = [mu.Vector((xn,yn,zn)),mu.Vector((xn,yn,zp)),
			mu.Vector((xn,yn,zp)),mu.Vector((xn,yp,zp)),
			mu.Vector((xn,yp,zp)),mu.Vector((xn,yp,zn)),
			mu.Vector((xn,yp,zn)),mu.Vector((xn,yn,zn)),
			mu.Vector((xp,yn,zn)),mu.Vector((xp,yn,zp)),
			mu.Vector((xp,yn,zp)),mu.Vector((xp,yp,zp)),
			mu.Vector((xp,yp,zp)),mu.Vector((xp,yp,zn)),
			mu.Vector((xp,yp,zn)),mu.Vector((xp,yn,zn)),
			mu.Vector((xn,yn,zn)),mu.Vector((xp,yn,zn)),
			mu.Vector((xn,yn,zp)),mu.Vector((xp,yn,zp)),
			mu.Vector((xn,yp,zp)),mu.Vector((xp,yp,zp)),
			mu.Vector((xn,yp,zn)),mu.Vector((xp,yp,zn))]

	dtp = [dtp_a,dtp_b]

	if sot.drop_s == '2':
		for k,v in psp.items():
			psp[k] = obm @ v
		for i,v in enumerate(cage):
			cage[i] = obm @ v
		for i,v in enumerate(dtp):
			dtp[i] = obm @ v

	return psp,cage,dtp


def aob_check(aob,ob_type,rep):
	if aob == None:
		rep({'ERROR'}, 'No ACTIVE object in selection!!!!')
		return{'CANCELLED'}
	if aob.type != ob_type:
		rep({'ERROR'}, 'ACTIVE object not '+ ob_type +' type!!!!')
		return{'CANCELLED'}
	return

def get_snap_spot_active(bco,sot,aob):
	if bco.mode == 'EDIT_MESH':
		bmd = bmesh.from_edit_mesh(bco.edit_object.data)
		vdt = bmd.verts
	else:
		vdt = aob.data.vertices
	obm = aob.matrix_world
	sps = spots(sot,obm,vdt)
	psp = projection(sot,obm,sps)[0]
	psp['dtp'] = projection(sot,obm,sps)[2][1]
	return psp

#-----------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------


class SOT_OT_Fixed_Snap(bpy.types.Operator):
	bl_idname = 'fgt.sot_fixed_snap'
	bl_label = 'SOT_OT_Fixed_Snap'
	bl_description = 'Snap origin position to fixed bounding box point'	

	dop: bpr.StringProperty(name = '', default = '')


	def execute(self,context):
		
		dop = self.dop
		rep = self.report
		sot = context.scene.sot_props
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active
		sob = bco.selected_objects
		sob_r = sob
		


		if sot.set_pick == '2':
			aob_check(aob,'MESH',rep)
			psp = get_snap_spot_active(bco,sot,aob)
			sot.loc_x,sot.loc_y,sot.loc_z = psp.get(self.dop)
			bpy.ops.ed.undo_push(message = 'Pick Spot Location' )

		else:

			if sot.active_batch_spot == '1' or sot.batch_spot_mode == '1':

				aob_check(aob,'MESH',rep)
				psp = get_snap_spot_active(bco,sot,aob)
				x,y,z = psp.get(self.dop)

				eob = object_in_edit(sob_r)
				if sot.active_batch_spot == '1':
					set_origin_location(x,y,z,aob)
					bpy.ops.ed.undo_push(message = 'SOT Fixed Snap A' )
				elif sot.active_batch_spot == '2':
					for tob in sob:
						set_origin_location(x,y,z,tob)
					bpy.ops.ed.undo_push(message = 'SOT Fixed Snap BTA' )
				recover_edit(eob,sob_r)

			if sot.active_batch_spot == '2' and sot.batch_spot_mode == '2':

				eob = object_in_edit(sob_r)
				for tob in sob:
					vdt = tob.data.vertices
					obm = tob.matrix_world
					sps = spots(sot,obm,vdt)
					psp = projection(sot,obm,sps)[0]
					psp['dtp'] = projection(sot,obm,sps)[2][1]
					x,y,z = psp.get(self.dop)
					set_origin_location(x,y,z,tob)
				bpy.ops.ed.undo_push(message = 'SOT Fixed Snap BPO' )

				recover_edit(eob,sob_r)

		return{'FINISHED'}

#{'np': Vector((1.0, -1.0, 1.0)), 'cp': Vector((1.0, 0.0, 1.0)), 'pp': Vector((1.0, 1.0, 1.0)), 
# 'nc': Vector((1.0, -1.0, 0.0)), 'cc': Vector((1.0, 0.0, 0.0)), 'pc': Vector((1.0, 1.0, 0.0)), 
# 'nn': Vector((1.0, -1.0, -1.0)), 'cn': Vector((1.0, 0.0, -1.0)), 'pn': Vector((1.0, 1.0, -1.0)), 
# 'bom': Vector((1.0, 0.0, 0.0)), 'boc': Vector((0.0, 0.0, 0.0)), 'com': Vector((0.0, 0.0, 0.0))}

class SOT_OT_Clear_Value(bpy.types.Operator):
	bl_idname = 'fgt.sot_clear_value'
	bl_label = 'SOT_OT_Clear_Value'

	cop: bpr.StringProperty(name = '', default = '')
	cln_dic = {'loc':'= 0','rot':'= 0','z_a':"= 'z+'",'rem':"= '1'",'off':'= 0','spo':'= 1'}

	def execute(self,context):
		sot = context.scene.sot_props
		exec('sot.'+ self.cop + self.cln_dic.get(self.cop[0:3]))
		bpy.ops.ed.undo_push(message = 'SOT Clear Value' )
		return {'FINISHED'}

class SOT_OT_Draw_Axis(bpy.types.Operator):
	bl_idname = 'fgt.sot_draw_axis'
	bl_label = 'SOT_OT_Draw_Axis'

	def modal(self,context,event):

		sot = context.scene.sot_props
	
		if not sot.draw_axis:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			return {'CANCELLED'}		

		try:
			context.area.tag_redraw()
		except:
			stop_it = True
			for area in bpy.context.window.screen.areas:
				if area.type == 'VIEW_3D':
					stop_it = False			
			if stop_it:
				bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
				sot.draw_axis = False
				return {'CANCELLED'}
			else:
				return {'PASS_THROUGH'}
		else:
			context.area.tag_redraw()
			return {'PASS_THROUGH'}

	def invoke(self,context,event):
		for area in bpy.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				args = (self,context)
				self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_axis_main, args, 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				return {'RUNNING_MODAL'}

def same_object_check(bco,sot,obm,vdata):
	go = False
	data = False
	smt = sot.same_matrix
	vcheck = bco.scene.vector_check

	if smt != obm:
		sot.same_matrix[0] = obm[0]
		sot.same_matrix[1] = obm[1]
		sot.same_matrix[2] = obm[2]
		sot.same_matrix[3] = obm[3]
		go = True

	if not go:
		cv,sv = [],[]
		for v in vdata:
			cv.append(v.co)
		for i in vcheck:
			sv.append(i.saved_vectors)

		if cv != sv:
			vcheck.clear()
			for v in cv:
				add = vcheck.add()
				add.saved_vectors = v
			for i in vcheck:
				sv.append(i.saved_vectors)
			go = True

	return go

def Vector(vec):
	return mu.Vector(vec)

def draw_spots_main(self,context):

	bco = bpy.context
	sot = context.scene.sot_props
	bcv = bco.view_layer
	aob = bcv.objects.active

	if aob != None and aob.type == 'MESH':

		obm = aob.matrix_world

		if sot.spots_auto == '1':
			check_mesh = True
		else:
			check_mesh = True if sot.spots_calc else False


		if check_mesh:
			sot.spots_calc = False

			if bco.mode == 'EDIT_MESH':
				bmd = bmesh.from_edit_mesh(bco.edit_object.data)
				vdata = bmd.verts
			else:
				vdata = aob.data.vertices

			if sot.same_space != sot.drop_s:
				spots_recalc = True
				sot.same_space = sot.drop_s
			else:
				spots_recalc = same_object_check(bco,sot,obm,vdata)			

			if spots_recalc:
				sps = spots(sot,obm,vdata)
				sot.same_spots = str(sps)
			else:
				sps = eval(sot.same_spots)


		else:
			sps = eval(sot.same_spots)

		psp,cage,dtp = projection(sot,obm,sps)
		vmt = bco.area.spaces.active.region_3d.view_matrix
		vmtr = vmt.to_3x3().inverted()

		shader = gpu.shader.from_builtin('3D_SMOOTH_COLOR')
		 
		sva =  [(-0.2,0,0),(-0.05,0,0),
				(0.05,0,0),(0.2,0,0),
				(0,0,0),(-0.1,0.1,0),
				(-0.1,0.1,0),(0.1,0.1,0),
				(0.1,0.1,0),(0,0,0)] 
		svb =  [(-0.1,0,0),(0,0.1,0),
				(0,0.1,0),(0.1,0,0),
				(0.1,0,0),(0,-0.1,0),
				(0,-0.1,0),(-0.1,0,0)]
		svc =  [(-0.1,-0.1,0),(-0.1,0.1,0),
				(-0.1,0.1,0),(0.1,0.1,0),
				(0.1,0.1,0),(0.1,-0.1,0),
				(0.1,-0.1,0),(-0.1,-0.1,0)]
		svd =  [(-0.1,-0.1,0),(0,0,0),
				(0,0,0),(0.1,-0.1,0),
				(0.1,-0.1,0),(-0.1,-0.1,0)]
		
		c = [(1.0, 1.0, 1.0, 1.0),(0, 0.9, 1.0, 1.0),(0.1, 0.5, 0.05, 1.0),(0.9, 0.2, 0.2, 1.0),(1.0, 0.5, 0.05, 1.0),
			(1.0, 0.2, 0.2, 1.0),(0.4, 1, 0.0, 1.0),(0.0 , 0.5, 1.0, 1.0)]
		
		if sot.drop_p == '1': ca = [c[5],c[6],c[7]]
		elif sot.drop_p == '2': ca = [c[6],c[5],c[7]]
		else: ca = [c[7],c[5],c[6]]

		csd = {'np':(ca[2],2.2,svd),'cp':(c[0],1,svb),'pp':(c[0],1,svb),
			   'nc':(ca[2],2.2,svc),'cc':(c[0],1,svb),'pc':(c[0],1,svb),
			   'nn':(ca[0],2.2,svc),'cn':(ca[1],2.2,svc),'pn':(ca[1],2.2,svc),
			   'bom':(c[1],2,svb),'boc':(c[3],3.5,svb),'com':(c[4],2.7,svb)}
		cc = (1.0, 1.0, 1.0, 1.0)

	
		for key,vec in psp.items():
			vcm = []
			col = []

			scl = screen_size(bco,vec) * csd.get(key)[1] * sot.spots_scale
			for v in csd.get(key)[2]:
				v = (vmtr @ (mu.Vector(v)*scl)) + vec	
				vcm.append(v)
				col.append(csd.get(key)[0])

			batch = batch_for_shader(shader, 'LINES', {"pos": vcm, "color": col})
			bgl.glLineWidth(4)
			shader.bind()
			batch.draw(shader)
			bgl.glLineWidth(1)


		vcm = []
		col = []
		for v in cage:
			vcm.append(v)
			col.append((1,1,0,1))

		batch = batch_for_shader(shader, 'LINES', {"pos": vcm, "color": col})
		bgl.glLineWidth(1)
		shader.bind()
		batch.draw(shader)
		bgl.glLineWidth(1)


		vcm = []
		col = []
		for i,v in enumerate(dtp):
			vcm.append(v)
			col.append((1,1,1,1))

			if i == 1:
				for c in sva:
					c = (vmtr @ (mu.Vector(c)*scl)) + v
					vcm.append(c)
					col.append((1, 0.2, 1.0, 1.0))

		batch = batch_for_shader(shader, 'LINES', {"pos": vcm, "color": col})
		bgl.glLineWidth(3)
		shader.bind()
		batch.draw(shader)
		bgl.glLineWidth(1)


	return


class SOT_OT_Draw_Spots(bpy.types.Operator):
	bl_idname = 'fgt.sot_draw_spots'
	bl_label = 'SOT_OT_Draw_Spots'

	def modal(self,context,event):

		sot = context.scene.sot_props
	
		if not sot.draw_spots:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.spots_calc == False			
			return {'CANCELLED'}		

		try:
			context.area.tag_redraw()
		except:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.spots_calc == False			
			sot.draw_spots = False
			return {'CANCELLED'}


		else:
			context.area.tag_redraw()
			return {'PASS_THROUGH'}

	def invoke(self,context,event):
		for area in bpy.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				args = (self,context)
				self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_spots_main, args, 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				return {'RUNNING_MODAL'}

class SOT_Settings_Props(bpy.types.PropertyGroup):

	loc_x: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	loc_y: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	loc_z: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)

	rot_x: bpr.FloatProperty(subtype = 'ANGLE', unit= 'ROTATION', min= -6.28319, max= 6.28319)#, precision= 2
	rot_y: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319)
	rot_z: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319)

	z_axis: bpr.EnumProperty(name='',
		items= [('z+','Z+ Same','Z+ axis untached as it is.',1),
				('z-','Z- Axis','Z+ use Z- vector',2),
				('y+','Y+ Axis','Z+ use Y+ vector',3),
				('y-','Y- Axis','Z+ use Y+ vector',4),
				('x+','X+ Axis','Z+ use X+ vector',5),
				('x-','X- Axis','Z+ use X+ vector',6)], default= 'z+')

	rem_zp: bpr.EnumProperty(
		items= [('1','X+ same  | Y+ same ','',1),('2','X+ to Y+ | Y+ to X-','',2),
				('3','X+ to X- | Y+ to Y-','',3),('4','X+ to Y- | Y+ to X+','',4)], default= '1')

	rem_zn: bpr.EnumProperty(
		items= [('1','X+ same  | Y+ to Y-','',1),('2','X+ to Y+ | Y+ to X+','',2),
				('3','X+ to X- | Y+ same ','',3),('4','X+ to Y- | Y+ to X-','',4)], default= '1')

	rem_yp: bpr.EnumProperty(
		items= [('1','X+ same  | Y+ to Z-','',1),('2','X+ to Z+ | Y+ to X+','',2),
				('3','X+ to X- | Y+ to Z+','',3),('4','X+ to Z- | Y+ to X-','',4)], default= '1')

	rem_yn: bpr.EnumProperty(
		items= [('1','X+ same  | Y+ to Z+','',1),('2','X+ to Z+ | Y+ to X-','',2),
				('3','X+ to X- | Y+ to Z-','',3),('4','X+ to Z- | Y+ to X+','',4)], default= '1')

	rem_xp: bpr.EnumProperty(
		items= [('1','X+ to Z- | Y+ same ','',1),('2','X+ to Y+ | Y+ to Z+','',2),
				('3','X+ to Z+ | Y+ to Y-','',3),('4','X+ to Y- | Y+ to Z-','',4)], default= '1')

	rem_xn: bpr.EnumProperty(
		items= [('1','X+ to Z+ | Y+ same ','',1),('2','X+ to Y+ | Y+ to Z-','',2),
				('3','X+ to Z- | Y+ to Y-','',3),('4','X+ to Y- | Y+ to Z+','',4)], default= '1')


	drop_p: bpr.EnumProperty(items= [('1','X','',1),('2','Y','',2),('3','Z','',3)], default= '1')
	drop_d: bpr.EnumProperty(items= [('1','Positive','',1),('2','Negative','',2)], default= '1')
	drop_s: bpr.EnumProperty(items= [('1','World','',1),('2','Local','',2)], default= '1')	

	draw_axis: bpr.BoolProperty(name = '', default = False, update= draw_axis_update)
	draw_spots: bpr.BoolProperty(name = '', default = False, update= draw_spots_update)


	active_batch: bpr.EnumProperty(
		items= [('1','Active','Set ORIGIN for ACTIVE object only',1),
				('2','Batch','Set ORIGIN for EACH object in selection',2)], default= '1')
	apply_scale: bpr.BoolProperty(
		name = '',description = 'Apply OBJECT SCALE after changing ORIGIN orientaion', default = False)


	spots_auto: bpr.EnumProperty(
		items= [('1','Auto','Auto bound spots recalculation (may cause low performance on highpoly mesh!!!)',1),
				('2','Manual','Manual bound spots recalculation',2)], default= '1')
	spots_calc: bpr.BoolProperty(
		name = '',description = 'Recalculate current mesh bound spots manually', default = True)

	set_pick: bpr.EnumProperty(
		items= [('1','Set Origin','Set ORIGIN location to FIXED spot',1),
				('2','Pick Spot','Pick ACTIVE object spot location values',2)], default= '1')
	active_batch_spot: bpr.EnumProperty(
		items= [('1','Active','Set ORIGIN for ACTIVE object only',1),
				('2','Batch','Set ORIGIN for EACH object in selection',2)], default= '1')
	batch_spot_mode: bpr.EnumProperty(
		items= [('1','To Active','Set ORIGIN for ACTIVE object only',1),
				('2','Per Object','Set ORIGIN for EACH object in selection',2)], default= '1')

	ground_bound: bpr.EnumProperty(
		items= [('1','Ground','Drop ORIGIN to GROUND leve along selected axis',1),
				('2','Bound','Drop ORIGIN to object BOUND side',2)], default= '1')

	ground: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)

	offset: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)

	spots_scale: bpr.FloatProperty(default= 1,precision= 2,min= 0.1, max= 2)	

	same_space: bpr.StringProperty(name = '', default = 'World')
	same_matrix: bpr.FloatVectorProperty(size= 16, subtype= 'MATRIX')
	same_spots: bpr.StringProperty(name = '', default = '')#{"a":1}

class SOT_Vectors_Check(bpy.types.PropertyGroup):

	saved_vectors: bpr.FloatVectorProperty(name = '', subtype= 'COORDINATES', default= (0,0,0))

ctr = [
	SOT_PT_Panel,
	SOT_PT_Location_Orientation,
	SOT_PT_Location,
	SOT_PT_Orientation,
	SOT_PT_Fixed_Snap,
	SOT_OT_Set_Location,
	SOT_OT_Set_Orientation,
	SOT_OT_Get_Transform,
	SOT_OT_Rotate_Ninety,
	SOT_OT_Fixed_Snap,
	SOT_OT_Clear_Value,
	SOT_OT_Draw_Axis,
	SOT_OT_Draw_Spots,
	SOT_Settings_Props,
	SOT_Vectors_Check
]


def register():
	for cls in ctr:
		bpy.utils.register_class(cls)
	bpy.types.Scene.sot_props = bpy.props.PointerProperty(type=SOT_Settings_Props)
	bpy.types.Scene.vector_check = bpy.props.CollectionProperty(type=SOT_Vectors_Check)	


def unregister():
	for cls in reversed(ctr):
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.sot_props
	del bpy.types.Scene.vector_check
