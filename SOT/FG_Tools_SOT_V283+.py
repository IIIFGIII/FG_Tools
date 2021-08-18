bl_info = {
	"name": "SOT",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 0),
	"blender": (2, 83, 0),
	"location": "Viev3D > N panel > FG Tools > SOT Panel",
	"description": "SOT or Set Origin Transform tool. Limitation",
	"warning": "",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}


import bpy, bmesh, math, bgl, gpu
import mathutils as mu
from gpu_extras.batch import batch_for_shader

bpr = bpy.props

def combine_matrix_v3(v1,v2,v3):
	mt = mu.Matrix.Identity(3)
	mt.col[0] = v1
	mt.col[1] = v2
	mt.col[2] = v3
	return mt

def vector_fix(obm,vector):
	return (obm.inverted_safe().transposed().to_3x3() @ vector).normalized()

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
		sot.rot_x,sot.rot_y,sot.rot_z = value
	return

def draw_axis_main(self,context):

	bco = bpy.context
	sot = context.scene.sot_props

	vc = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
		(0.0, 0.0, 0.0), (0.0, 1.0, 0.0),
		(0.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
	vcm = []


	loc = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
	euler = mu.Euler((sot.rot_x,sot.rot_y,sot.rot_z),'XYZ')
	rot = euler.to_matrix()

	for v in vc:
		v = (rot @ mu.Vector(v)) + loc
		vcm.append(v)

	shader = gpu.shader.from_builtin('3D_SMOOTH_COLOR')
	col = [(1.0, 0.0, 0.0, 1.0), (1.0, 0.0, 0.0, 1.0),
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



class SOT_PT_Panel(bpy.types.Panel):
	bl_label = 'SOT Panel'
	bl_idname = 'SOT_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FG_Tools'

	def draw(self, context):
		bco = bpy.context
		sot = context.scene.sot_props
		clear = 'fgt.sot_clear_value'
		rotate = 'fgt.sot_rotate_ninety'
		get = 'fgt.sot_get_transform'

		zax_dic = {'z+':'rem_zp','z-':'rem_zn','y+':'rem_yp','y-':'rem_yn','x+':'rem_xp','x-':'rem_xn'}
		rem_dic = {'z+':sot.rem_zp,'z-':sot.rem_zn,'y+':sot.rem_yp,'y-':sot.rem_yn,'x+':sot.rem_xp,'x-':sot.rem_xn}

		layout = self.layout
		col = layout.column(align=True)


		col.operator('fgt.sot_set_origin', icon='TRANSFORM_ORIGINS', text='Set Origin Location').rot = False
		col.operator('fgt.sot_set_origin', icon='ORIENTATION_GIMBAL', text='Set Origin Rotation').rot = True
		col.separator(factor=1)
		col.prop(sot, 'draw_axis', text= 'Hide Helper Axis' if sot.draw_axis else 'Show Helper Axis', icon='EMPTY_AXIS', toggle= True)


		row = col.row(align=True)
		row.label(text= 'Location Values')
		row = col.row(align=True)
		row.prop(sot, 'loc_x', text= 'X') 	
		row.operator(clear, icon='X' if sot.loc_x != 0 else 'DOT', text='').cop = 'loc_x'
		row = col.row(align=True)
		row.prop(sot, 'loc_y', text= 'Y')
		row.operator(clear, icon='X' if sot.loc_y != 0 else 'DOT', text='').cop = 'loc_y'
		row = col.row(align=True)			
		row.prop(sot, 'loc_z', text= 'Z')
		row.operator(clear, icon='X' if sot.loc_z != 0 else 'DOT', text='').cop = 'loc_z'

		row = col.row(align=True)
		row.label(text= 'Get Location From:')
		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Cursor').gop = 'l_c'
		row.operator(get, icon='PIVOT_ACTIVE', text='Active').gop = 'l_a'

		col.separator(factor=3)

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

		row = col.row(align=True)
		row.label(text= 'Get Rotation From:')
		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Cursor').gop = 'r_c'
		row.operator(get, icon='PIVOT_ACTIVE', text='Active').gop = 'r_a'

		row = col.row(align=True)
		row.label(text= 'Z Axis Remap')
		row.prop(sot, 'z_axis', text= '')
		row.operator(clear, icon='X' if sot.z_axis != 'z+' else 'DOT', text='').cop = 'z_axis'
		row = col.row(align=True)			
		row.prop(sot, zax_dic.get(sot.z_axis), text= '')
		row.operator(clear, icon='X' if rem_dic.get(sot.z_axis) != '1' else 'DOT', text='').cop = zax_dic.get(sot.z_axis)

class SOT_OT_Set_Origin(bpy.types.Operator):
	bl_idname = 'fgt.sot_set_origin'
	bl_label = 'SOT_OT_Set_Origin'
	bl_description = 'Set active object origin transforms'
	bl_options = {'REGISTER', 'UNDO'}

	rot: bpr.BoolProperty(default= False)

	def execute(self,context):
		sot = context.scene.sot_props
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active


		if aob == None:
			rep({'ERROR'}, 'No active object in selection!!!!')
			return{'FINISHED'}
		
		if self.rot:

			euler = mu.Euler((sot.rot_x,sot.rot_y,sot.rot_z),'XYZ')
			rmt = euler.to_matrix()

			loc = aob.matrix_world.col[3]
			scl = aob.matrix_world.to_scale()

			rmt_m = rmt.to_4x4()
			rmt_m.col[0] = rmt_m.col[0]*scl[0]
			rmt_m.col[1] = rmt_m.col[1]*scl[1]
			rmt_m.col[2] = rmt_m.col[2]*scl[2]
			rmt_m.col[3] = loc

			rmt = aob.matrix_world.to_3x3().inverted() @ rmt

			if bco.mode == 'OBJECT':
				for v in aob.data.vertices:
					v.co = rmt.inverted() @ v.co
				aob.data.update()
				aob.matrix_world = rmt_m
				for v in aob.data.vertices:
					v.co = mu.Vector((v.co[0]/scl[0],v.co[1]/scl[1],v.co[2]/scl[2]))
				aob.data.update()				

			elif bco.mode == 'EDIT_MESH':
				bmd = bmesh.from_edit_mesh(bco.edit_object.data)
				for v in bmd.verts:
					v.co = rmt.inverted() @ v.co
				aob.matrix_world = rmt_m
				for v in bmd.verts:
					v.co = mu.Vector((v.co[0]/scl[0],v.co[1]/scl[1],v.co[2]/scl[2]))
				bpy.ops.object.editmode_toggle()
				bpy.ops.object.editmode_toggle()

		else:
			loc = aob.matrix_world.col[3]
			pos = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z,1))
			dif = mu.Vector((pos - loc)[:3])

			tar = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))

			aob.matrix_world.col[3] = pos

			obm = aob.matrix_world

			if bco.mode == 'OBJECT':
				for v in aob.data.vertices:
					v.co = v.co - ( obm.to_3x3().inverted() @ dif)
				aob.data.update()
			elif bco.mode == 'EDIT_MESH':
				bmd = bmesh.from_edit_mesh(bco.edit_object.data)
				for v in bmd.verts:
					v.co = v.co - ( obm.to_3x3().inverted() @ dif)	
				bpy.ops.object.editmode_toggle()
				bpy.ops.object.editmode_toggle()

		return {'FINISHED'}

class SOT_OT_Get_Transform(bpy.types.Operator):
	bl_idname = 'fgt.sot_get_transform'
	bl_label = 'SOT_OT_Get_Transform'
	bl_description = 'Get transform values from...'
	bl_options = {'REGISTER', 'UNDO'}

	gop: bpr.StringProperty(name = '', default = '')

	def execute(self,context):
		sot = context.scene.sot_props
		gop = self.gop
		rep = self.report
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active
		sob = bco.selected_objects

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
	bl_label = 'sot_OT_Rotate_Ninety'

	rop: bpr.StringProperty(name = '', default = '')

	def execute(self,context):
		sot = context.scene.sot_props
		exec('sot.'+ self.rop[1:] + '=' + 'sot.' + self.rop[1:] + self.rop[0] + str(math.radians(90)))
		return {'FINISHED'}

class SOT_OT_Clear_Value(bpy.types.Operator):
	bl_idname = 'fgt.sot_clear_value'
	bl_label = 'SOT_OT_Clear_Value'

	cop: bpr.StringProperty(name = '', default = '')
	cln_dic = {'loc':'= 0','rot':'= 0','z_a':"= 'z+'",'rem':"= '1'"}

	def execute(self,context):
		sot = context.scene.sot_props
		exec('sot.'+ self.cop + self.cln_dic.get(self.cop[0:3]))
		return {'FINISHED'}

class SOT_OT_Draw_Axis(bpy.types.Operator):
	bl_idname = 'fgt.sot_draw_axis'
	bl_label = 'SOT_OT_Draw_Axis'

	def modal(self,context,event):

		sot = context.scene.sot_props

		stop_it = True
		for area in bpy.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				stop_it = False

		if stop_it:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.draw_axis = False
			return {'CANCELLED'}	


		context.area.tag_redraw()
		if not sot.draw_axis:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			return {'CANCELLED'}

		return {'PASS_THROUGH'}

	def invoke(self,context,event):
		for area in bpy.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				args = (self,context)
				self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_axis_main, args, 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				return {'RUNNING_MODAL'}

class SOT_Settings_Props(bpy.types.PropertyGroup):

	loc_x: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	loc_y: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	loc_z: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)

	rot_x: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319, precision= 6)
	rot_y: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319, precision= 6)
	rot_z: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319, precision= 6)

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

	draw_axis: bpr.BoolProperty(name = '', default = False, update= draw_axis_update)


# Register/Unregister

CTR = [
	SOT_PT_Panel,
	SOT_OT_Set_Origin,
	SOT_OT_Get_Transform,
	SOT_OT_Rotate_Ninety,
	SOT_OT_Clear_Value,
	SOT_OT_Draw_Axis,
	SOT_Settings_Props,
]


def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	# Register properties		
	bpy.types.Scene.sot_props = bpy.props.PointerProperty(type=SOT_Settings_Props)


def unregister():
	for cls in reversed(CTR):
		bpy.utils.unregister_class(cls)
	# Delete properties
	del bpy.types.Scene.sot_props
