bl_info = {
	"name": "FRP",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 0),
	"blender": (2, 83, 0),
	"location": "Viev3D > N panel > FG Tools > FRP",
	"description": "Handy PIE menu for ratating object to fixed angles.",
	"warning": "Work in progress",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}

import bpy,math

bop = bpy.ops
bco = bpy.context
bda = bpy.data
bpr = bpy.props

angles = [10.0, 30.0, 45.0]

class FRP_PT_Panel(bpy.types.Panel):
	bl_label = 'FRP'
	bl_idname = 'FRP_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FG_Tools'

	def draw(self,context):
		layout = self.layout
		split = layout.split(factor=0.5)
		col = layout.column()
		row = layout.row(align=True)

		sc_frp = context.scene.frp_props

		row_a = layout.row(align=True)
		row_a.prop(sc_frp, 'frp_angle_a', text = '')
		row_a.operator('fgt.frp_angle_a_add', text='', icon='ADD')
		row_a.operator('fgt.frp_angle_a_rem', text='', icon='REMOVE').ang_b = False


		row_b = layout.row(align=True)
		row_b.prop(sc_frp, 'frp_angle_b', text = '')
		row_b.operator('fgt.frp_angle_a_add', text='', icon='ADD')
		row_b.operator('fgt.frp_angle_a_rem', text='', icon='REMOVE').ang_b = True

class FRP_MT_PIE_Menu(bpy.types.Menu):
	bl_idname = 'FRP_MT_PIE_Menu'
	bl_label = ''


	def draw(self, context):
		layout = self.layout
		pie = layout.menu_pie()

		frp = context.scene.frp_props

		if frp.frp_angle_a == '' or frp.frp_angle_b == '':
			an_a = 0.0
			an_b = 0.0
		else:
			an_a = round(angles[int(frp.frp_angle_a)],3)
			an_b = round(angles[int(frp.frp_angle_b)],3)

		to = frp.frp_transform

		#LT
		pie.operator("fgt.frp_rotator", text="- 90", icon='LOOP_FORWARDS').r_angle = -90.0
		#RT
		pie.operator("fgt.frp_rotator", text="90", icon='LOOP_BACK').r_angle = 90.0
		#BO
		pie.operator("fgt.frp_rotator", text="180", icon='FILE_REFRESH').r_angle = 180.0
		#TO
		pie.operator("wm.call_menu_pie", text="TO - " + to, icon='NONE').name = 'FRP_MT_PIE_SMenu_TO'
		#LTTO
		pie.operator("fgt.frp_rotator", text='- ' + str(an_a), icon='LOOP_FORWARDS').r_angle = -1.0 * an_a
		#RTTO
		pie.operator("fgt.frp_rotator", text= str(an_a), icon='LOOP_BACK').r_angle = an_a
		#LTBO
		pie.operator("fgt.frp_rotator", text='- ' + str(an_b), icon='LOOP_FORWARDS').r_angle = -1.0 * an_b
		#RTBO
		pie.operator("fgt.frp_rotator", text= str(an_b), icon='LOOP_BACK').r_angle = an_b

class FRP_MT_PIE_SMenu_TO(bpy.types.Menu):
	bl_idname = 'FRP_MT_PIE_SMenu_TO'
	bl_label = 'FRP_MT_PIE_SMenu_TO'

	def draw(self, context):
		layout = self.layout
		pie = layout.menu_pie()

		#LT
		pie.operator("fgt.frp_transform", text= 'CURSOR', icon='ORIENTATION_CURSOR').set_to = 'CURSOR'
		#RT
		pie.operator("fgt.frp_transform", text= 'LOCAL', icon='ORIENTATION_LOCAL').set_to = 'LOCAL'
		#BO
		pie.operator("fgt.frp_transform", text= 'TO', icon='NONE').set_to = 'CURRENT'
		#TO
		pie.operator("fgt.frp_transform", text= 'CURRENT', icon='OBJECT_ORIGIN').set_to = 'CURRENT'
		#LTTO
		pie.operator("fgt.frp_transform", text= 'GLOBAL', icon='ORIENTATION_GLOBAL').set_to = 'GLOBAL'
		#RTTO
		pie.operator("fgt.frp_transform", text= 'NORMAL', icon='ORIENTATION_NORMAL').set_to = 'NORMAL'
		#LTBO
		pie.operator("fgt.frp_transform", text= 'VIEW', icon='ORIENTATION_VIEW').set_to = 'VIEW'
		#RTBO
		pie.operator("fgt.frp_transform", text= 'GIMBAL', icon='ORIENTATION_GIMBAL').set_to = 'GIMBAL'


class FRP_OT_Transform(bpy.types.Operator):
	bl_idname = 'fgt.frp_transform'
	bl_label = 'Set transform orientation.'


	set_to = bpr.StringProperty(name = '', default = 'GLOBAL')

	def execute(self, context):

		frp = context.scene.frp_props
		if self.set_to == 'CURRENT':
			frp.frp_transform = context.scene.transform_orientation_slots[0].type
		else:
			frp.frp_transform = self.set_to
		print(frp.frp_transform)

		return{'FINISHED'}

class FRP_OT_Rotator(bpy.types.Operator):
	bl_idname = 'fgt.frp_rotator'
	bl_label = 'FRP_OT_Rotator'
	bl_option = {'REGISTER','UNDO'}
	bl_description = 'Rotator.'


	r_angle = bpr.FloatProperty(name = '', default = 0.0)

	def execute(self, context):

		frp = context.scene.frp_props
		tor = frp.frp_transform 

		bpy.ops.transform.rotate(value=math.radians(self.r_angle), orient_axis= 'Z', orient_type= tor,)
		print(self.r_angle)
		
		return{'FINISHED'}

class FRP_OT_Angle_Add(bpy.types.Operator):
	bl_idname = 'fgt.frp_angle_a_add'
	bl_label = 'Add custom angle.'

	angle = bpr.FloatProperty(name = 'Angel', default = 0.0, min= 0.0, max= 360.0, precision = 3)

	def execute(self, context):
		for a in angles:
			if a == self.angle:
				self.report({'ERROR'}, 'This angle already in list.')
				return{'FINISHED'}
		angles.append(self.angle)

		return{'FINISHED'}

	def invoke(self, context, event):

		return context.window_manager.invoke_props_dialog(self)

class FRP_OT_Angle_Rem(bpy.types.Operator):
	bl_idname = 'fgt.frp_angle_a_rem'
	bl_label = 'Remove custom angle.'

	ang_b = bpr.BoolProperty(name = '', default = False)


	def execute(self, context):
		
		frp = context.scene.frp_props
		ang_l = len(angles)
		
		if not self.ang_b:
			# A angle enum
			if ang_l != 0:

				enm_a = int(frp.frp_angle_a)
				enm_b = int(frp.frp_angle_b)
				print('A =' + frp.frp_angle_a + '| B =' + frp.frp_angle_b)
				angles.pop(enm_a)

				if ang_l > 1 and frp.frp_angle_a != '0':
					frp.frp_angle_a = str(enm_a-1)
					
				if ang_l > 1 and frp.frp_angle_b != '0':
					if frp.frp_angle_b == '':
						print('B = nothing')
						frp.frp_angle_b = str(enm_b-1)
					elif enm_b >= enm_a:
						print('B > A | B = B - 1')
						frp.frp_angle_b = str(enm_b-1)
			else:
				self.report({'ERROR'}, 'No more items to remove :(')
				return{'FINISHED'}	
		else:
			# B angle enum
			if ang_l != 0:
				enm_i = int(frp.frp_angle_b)
				angles.pop(enm_i)
				if ang_l > 1 and frp.frp_angle_b != '0':
					frp.frp_angle_b = str(enm_i-1)
					if frp.frp_angle_a == '':
						frp.frp_angle_a = str(enm_i-1)
			else:
				self.report({'ERROR'}, 'No more items to remove :(')
				return{'FINISHED'}

		return{'FINISHED'}


def upd_angles(self, context):

	enum_items = []
	ang_num = len(angles)
	for a in angles:
		n = len(enum_items)
		new_angle = (str(n), str(round(a,3)), '', n)
		enum_items.append(new_angle)

	return enum_items

class FRP_Settings_Props(bpy.types.PropertyGroup):

	frp_transform: bpr.StringProperty(
		name = 'Transform Orientation',
		default = 'GLOBAL'
		) 

	frp_angle_a: bpr.EnumProperty(
		name = 'Angle_A',
		description= 'Something here',
		items = upd_angles
		)

	frp_angle_b: bpr.EnumProperty(
		name = 'Angle_B',
		description= 'Something here',
		items = upd_angles
		)

# Register/Unregister

CTR = [
	FRP_PT_Panel,
	FRP_MT_PIE_Menu,
	FRP_MT_PIE_SMenu_TO,
	FRP_OT_Transform,
	FRP_OT_Rotator,
	FRP_OT_Angle_Add,
	FRP_OT_Angle_Rem,
	FRP_Settings_Props,
	]

FRP_Keymap = []

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	# Register properties
	bpy.types.Scene.frp_props = bpr.PointerProperty(type=FRP_Settings_Props)

	wm = bpy.context.window_manager
	kc = wm.keyconfigs.addon
	if kc:
		km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
		kmi = km.keymap_items.new('wm.call_menu_pie', 'R', 'PRESS', alt=True)
		kmi.properties.name = 'FRP_MT_PIE_Menu'
		FRP_Keymap.append((km, kmi))



def unregister():
	for cls in CTR:
		bpy.utils.unregister_class(cls)

	# Delete properties
	del bpy.types.Scene.frp_props

	wm = bpy.context.window_manager
	kc = wm.keyconfigs.addon
	if kc:
		for km,kmi in FRP_Keymap:
			km.keymap_items.remove(kmi)
	addon_keymaps.clear()


#	frp = context.scene.frp_props
#	if self.set_to == 'CURRENT':
#		frp.frp_transform = bco.scene.transform_orientation_slots[0].type
#	else:
#		frp.frp_transform = self.set_to
#	print(frp.frp_transform)
