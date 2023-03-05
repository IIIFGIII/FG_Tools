bl_info = {
	"name": "BMT",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 0),
	"blender": (2, 83, 0),
	"location": "Viev3D > N panel > FG Tools > BMT",
	"description": "Simple tools for UV Box Mapping.",
	"warning": "Work in probres version!!! Blablabla",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}

import bpy, bmesh, time
import mathutils as mu

def set_uv_coord(fcs,uvs,ma,mb,a,b,am,bm,sa,sb):
	if fcs != []:
		for fc in fcs:
			for vt,lp in zip(fc.verts,fc.loops):
				vtc = ma @ ( mb @ vt.co )
				lp[uvs].uv = ((((vtc[a]*(1/sa))*am)+0.5),(((vtc[b]*(1/sb))*bm)+0.5))
	return

class BMT_PT_Panel(bpy.types.Panel):
	bl_label = 'BMT'
	bl_idname = 'BMT_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FG_Tools'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		bco = bpy.context
		if bco.mode == 'EDIT_MESH' or bco.mode == 'OBJECT':
			layout = self.layout
			col = layout.column(align=True)
			bmt = context.scene.bmt_props
			col.prop(bmt, 'siz_x', text= 'UV Box X')
			col.prop(bmt, 'siz_y', text= 'UV Box Y')
			col.prop(bmt, 'siz_z', text= 'UV Box Z')
			col.prop(bmt, 'adv_z', text= 'Advanced Z')
			col.prop(bmt, 'opb_xy', text= 'Opposite XY back')
			col.prop(bmt, 'debug', text= 'Visual debug')
			col.prop(bmt, 'dot_v', text= '')		
			col.operator('fgt.bmt_test', icon='MESH_CUBE', text='Box Map It')

class BMT_OT_Test(bpy.types.Operator):
	bl_idname = "fgt.bmt_test"
	bl_label = "Test_Button"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Click it!!!'

	def execute(self,context):

		#time_s = time.time()

		bmt = context.scene.bmt_props
		bop = bpy.ops
		bpm = bop.mesh
		bda = bpy.data
		bco = bpy.context
		cob = bco.object

		if bco.mode != 'OBJECT' and bco.mode != 'EDIT_MESH':
			self.report({'ERROR'}, 'Operator work in Object or Edit Mesh modes only!!!')
			return{'FINISHED'}
		
		aob_n = bco.view_layer.objects.active.name
		sob_n,mob_n,eob_n = ([],[],[])
		for ob in bco.selected_objects:
			sob_n.append(ob.name)
			if ob.mode == 'EDIT':
				eob_n.append(ob.name)
			if ob.type == 'MESH':
				mob_n.append(ob.name)

		if not mob_n:
			self.report({'ERROR'}, ' No Mesh objects in selection!')
			return{'FINISHED'}

		ed_mod = False if bco.mode != 'EDIT_MESH' else True

		if ed_mod: bop.object.editmode_toggle()
		bop.object.select_all(action='DESELECT')

		#Cursor matrix
		crm = bco.scene.cursor.matrix
		crm_i = crm.inverted()
		crm_ti = crm.to_3x3().inverted()

		zvc = mu.Vector((0.0, 0.0, 1.0))
		yvc = mu.Vector((0.0, 1.0, 0.0))
		xym = mu.Vector((1.0, 1.0, 0.0))

		#Per object works
		uob_n = eob_n if ed_mod else mob_n
		for ob_n in uob_n:


			bco.view_layer.objects.active = bda.objects[ob_n]
			bda.objects[ob_n].select_set(True)
			bop.object.editmode_toggle()

			#Object matrix
			obm = bda.objects[ob_n].matrix_world
			obm_s = obm.to_scale()
			obm_tn = obm.to_3x3().normalized()

			bmd = bmesh.from_edit_mesh(bco.edit_object.data)

			#Select all if BMT from object mode
			if not ed_mod: bpm.select_all(action='SELECT')

			if not ed_mod: bop.mesh.reveal()
			sfc = [fc for fc in bmd.faces if fc.select]
			xfc,xfc_b,yfc,yfc_b,zfc = ([],[],[],[],[])

			if bda.objects[ob_n].data.uv_layers.active == None: bpm.uv_texture_add()

			for fc in sfc:
				# Matrix adjustment
				fcn_m = crm_ti @ (obm_tn @ fc.normal)
				# Face normal check
				if bmt.adv_z and (abs(fcn_m.dot(zvc)) - (abs(abs(fcn_m[0]**2)-abs(fcn_m[1]**2))*0.255)) >= bmt.dot_v:
					zfc.append(fc)
				elif not bmt.adv_z and abs(fcn_m.dot(zvc)) >= bmt.dot_v:
					zfc.append(fc)
				elif abs(((fcn_m*xym).normalized()).dot(yvc)) >= 0.7071:
					if bmt.opb_xy and ((fcn_m*xym).normalized())[1] < 0:
						yfc_b.append(fc)
					else:
						yfc.append(fc)
				else:
					if bmt.opb_xy and ((fcn_m*xym).normalized())[0] < 0:
						xfc_b.append(fc)
					else:
						xfc.append(fc)

			#Set UV's
			uvl = bmd.loops.layers.uv.verify()
			set_uv_coord(xfc,uvl,crm_i,obm,1,2,1,1,bmt.siz_y,bmt.siz_z)
			set_uv_coord(xfc_b,uvl,crm_i,obm,1,2,-1,1,bmt.siz_y,bmt.siz_z)
			set_uv_coord(yfc,uvl,crm_i,obm,0,2,-1,1,bmt.siz_x,bmt.siz_z)
			set_uv_coord(yfc_b,uvl,crm_i,obm,0,2,1,1,bmt.siz_x,bmt.siz_z)
			set_uv_coord(zfc,uvl,crm_i,obm,0,1,1,1,bmt.siz_x,bmt.siz_y)

			#Visuzl debug ----------------------------------------
			if bmt.debug:
				bop.mesh.select_all(action='DESELECT')
				for fc in xfc:
					fc.select = True
				bco.active_object.active_material_index = 0
				bop.object.material_slot_assign()	
	
				bop.mesh.select_all(action='DESELECT')
				for fc in yfc:
					fc.select = True
				bco.active_object.active_material_index = 1
				bop.object.material_slot_assign()		
	
				bop.mesh.select_all(action='DESELECT')
				for fc in zfc:
					fc.select = True
				bco.active_object.active_material_index = 2
				bop.object.material_slot_assign()	
			# ------------------------------------------------------


			bop.mesh.select_all(action='DESELECT')
			if ed_mod:
				for fc in sfc:
					fc.select = True
			bop.object.editmode_toggle()
			bda.objects[ob_n].select_set(False)



		bco.view_layer.objects.active = bda.objects[aob_n]
		if ed_mod:
			for ob_n in eob_n:
				bda.objects[ob_n].select_set(True)
			bop.object.editmode_toggle()
		for ob_n in sob_n:
			bda.objects[ob_n].select_set(True)

		#time_e = time.time()
		#print('Total time = ' + str(time_e - time_s))

		return {'FINISHED'}

class BMT_Settings_Props(bpy.types.PropertyGroup): 

	prp = bpy.props

	dot_v: prp.FloatProperty(
		name= 'Dot value', 
		default= 0.4439,
		min= 0.01,
		max= 0.99, 
	)

	adv_z: prp.BoolProperty(
		name = 'Advanced Z projection.',
		default = False,
	)

	opb_xy: prp.BoolProperty(
		name = 'Oposit back side XY mapping.',
		default = False,
	)

	debug: prp.BoolProperty(
		name = 'Debug',
		default = False,
	)

	top_z: prp.BoolProperty(
		name = 'Z look up always.',
		default = False,
	)

	siz_x: prp.FloatProperty(
		name= 'UV Box X size.',
		subtype = 'DISTANCE', 
		default= 1.000,
		min= 0.0,
	)

	siz_y: prp.FloatProperty(
		name= 'UV Box Y size.',
		subtype = 'DISTANCE', 
		default= 1.000,
		min= 0.0, 
	)

	siz_z: prp.FloatProperty(
		name= 'UV Box Z size.',
		subtype = 'DISTANCE',
		default= 1.000,
		min= 0.0,
	)



# Register/Unregister

CTR = [
	BMT_PT_Panel,
	BMT_OT_Test,
	BMT_Settings_Props,
]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	# Register properties		
	bpy.types.Scene.bmt_props = bpy.props.PointerProperty(type=BMT_Settings_Props)


def unregister():
	for cls in reversed(CTR):
		bpy.utils.unregister_class(cls)
	# Delete properties
	del bpy.types.Scene.bmt_props
