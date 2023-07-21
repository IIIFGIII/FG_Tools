bl_info = {
	"name": "ABT",
	"author": "IIIFGIII",
	"version": (0, 1),
	"blender": (2, 93, 0),
	"location": "Viev3D > N panel > FGT > ABT",
	"description": "!!! Work in progress !!!",
	"warning": "",
	"wiki_url": "",
	"category": "FG_Tools",
}

import bpy, bmesh, math, bgl, blf, gpu
import numpy as np
from copy import copy
from mathutils import Matrix, Vector, Euler
from mathutils.geometry import normal as mug_normal
from mathutils.geometry import intersect_line_line_2d, intersect_line_plane
from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import location_3d_to_region_2d as convert_global_to_screen
from bpy_extras.view3d_utils import region_2d_to_location_3d as convert_screen_to_global 
from bpy_extras.view3d_utils import region_2d_to_origin_3d as convert_screen_to_global_origin

bpr = bpy.props

shd_uc = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
shd_sc = gpu.shader.from_builtin('3D_SMOOTH_COLOR')

abt_cot_pr_val = {}


def is_view_transparent(context):
	shading = context.space_data.shading
	return shading.show_xray_wireframe if shading.type == 'WIREFRAME' else shading.show_xray

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

def vector_convert_to_matrix_inverted(mtr, pt_co = Vector((0,0,0))):
	return mtr.inverted() @ pt_co

def vector_fix_a(obm,vct):
	return (obm.inverted_safe().transposed().to_3x3() @ vct).normalized()

def vector_fix_b(obm,vct):
	return (obm.to_3x3() @ vct).normalized()

def vector_reprojection(vct_a, vct_b):
	return (vct_a - (vct_a.dot(vct_b)*vct_b)).normalized()

def vectors_dot_product(vct_a, vct_b):
	vct_a_lsq = vct_a.dot(vct_a)
	if vct_a_lsq != 0:
		return vct_b.dot(vct_a)/vct_a.dot(vct_a)
	else:
		return 0

def distance_between_vectors(va,vb):
	return math.sqrt((vb[0] - va[0])**2 + (vb[1] - va[1])**2 + (vb[2] - va[2])**2)

def vectors_to_matrix_col(v1,v2,v3): 
	mtr = Matrix.Identity(3)
	mtr.col[0] = v1
	mtr.col[1] = v2
	mtr.col[2] = v3
	return mtr

def vectors_to_matrix_row(v1,v2,v3): # Inverted version of   vectors_to_matrix_col()
	mtr = Matrix.Identity(3)
	mtr.row[0] = v1
	mtr.row[1] = v2
	mtr.row[2] = v3
	return mtr

def vector_to_cam_normalized(s3d, vct_point):
	mtr_view = s3d.view_matrix
	if s3d.view_perspective == 'PERSP' or s3d.view_perspective == 'CAMERA':	
		vct_to_cam = (vector_convert_to_matrix_inverted(mtr_view) - vct_point).normalized()
	else:
		vct_to_cam = matrix_to_vector_row(mtr_view,2)

	return vct_to_cam

def matrix_to_vector_row(mtr, row=0):
	return mtr.row[row].to_3d()

def matrix_to_vector_col(mtr, col=0):
	return mtr.col[col].to_3d()

def rotate_matrix_around_axis(mtr_to_rotate, angle_x, angle_y, angle_z):
	return Euler((angle_x,angle_y,angle_z), 'XYZ').to_matrix().to_4x4() @ mtr_to_rotate

def get_transform_orientaions_from_mode(context,mode,slice_pts):
	aob = context.view_layer.objects.active
	mtr_tro = Matrix.Identity(3)

	if mode == '0': # Global Orientation
		pass
	elif mode == '1': # Local Orientaion
		mtr_tro = aob.matrix_world.to_3x3().normalized()
	elif mode == '2': # Cursor
		mtr_tro = context.scene.cursor.matrix.to_3x3()
	elif mode == '3': # Active Element Orientation
		mtr_tro = get_active_element_vectors(context,aob) if get_active_element_vectors(context,aob) != None else aob.matrix_world.to_3x3().normalized()
	elif mode == '4': # Slice
		if   len(slice_pts) == 1:
			s3d = context.space_data.region_3d
			mtr_tro = s3d.view_matrix.to_3x3().inverted()
		elif len(slice_pts) == 2:
			s3d = context.space_data.region_3d
			vct_y = (Vector(slice_pts[1]) - Vector(slice_pts[0])).normalized()
			vct_to_cam = vector_to_cam_normalized(s3d, Vector(slice_pts[0]))
			if round(abs(vct_y.dot(vct_to_cam)),5) != 1:
				vct_z = -1 * vector_reprojection(-1 * vct_to_cam,vct_y)
				vct_x = vct_y.cross(vct_z)
			else:
				vct_z = matrix_to_vector_row(s3d.view_matrix.to_3x3().inverted(), 1)
				vct_x = vct_y.cross(vct_z)
			mtr_tro = vectors_to_matrix_col(vct_x,vct_y,vct_z)
		elif len(slice_pts) == 3:
			vct_y = (Vector(slice_pts[1]) - Vector(slice_pts[0])).normalized()
			vct_z = mug_normal(slice_pts[0], slice_pts[1], slice_pts[2])
			vct_z = -1 * vct_z if round(vct_z.z,6) < 0 else vct_z
			vct_x = vct_y.cross(vct_z)
			mtr_tro = vectors_to_matrix_col(vct_x,vct_y,vct_z)
		else:
			pass
	elif mode == '5': # Gravity
		if   len(slice_pts) == 1:
			s3d = context.space_data.region_3d
			vct_z = vector_to_cam_normalized(s3d,Vector(slice_pts[0]))
			if abs(round(vct_z.z,6)) == 1:
				vct_y = Vector((0,0,1))
				vct_z = -1 * matrix_to_vector_row(s3d.view_matrix,1)
				vct_x = vct_y.cross(vct_z)
			else:
				vct_y = Vector((0,0,1))
				vct_z = Vector((vct_z.x, vct_z.y, 0)).normalized()
				vct_x = vct_y.cross(vct_z)
			mtr_tro = vectors_to_matrix_col(vct_x,vct_y,vct_z)
		elif len(slice_pts) == 2:
			vct_y = (Vector(slice_pts[1]) - Vector(slice_pts[0])).normalized()
			if abs(round(vct_y.z,6)) == 1: # Check if Y axis look straight up
				vct_x = Vector((1,0,0))
				vct_z = vct_y.cross(vct_x)
			else:
				vct_z = vector_reprojection(Vector((0,0,1)),vct_y)
				vct_x = vct_y.cross(vct_z)
			mtr_tro = vectors_to_matrix_col(vct_x,vct_y,vct_z)
		elif len(slice_pts) == 3:
			vct_z = mug_normal(slice_pts[0], slice_pts[1], slice_pts[2])
			vct_z = -1 * vct_z if round(vct_z.z,6) < 0 else vct_z
			if abs(round(vct_z.z,6)) == 1: # Check if Y axis look straight up
				vct_x = Vector((1,0,0))
				vct_y = vct_z.cross(vct_x)
			else:
				vct_y = vector_reprojection(Vector((0,0,1)),vct_z)
				vct_x = vct_y.cross(vct_z)
			mtr_tro = vectors_to_matrix_col(vct_x,vct_y,vct_z)
		else:
			pass
	elif mode == '6': # Preset
		pass

	return mtr_tro

def rotated_align_orientation(mtr_align, align_mode, switch_align, slice_angle):
	if   align_mode == '1':
		mtr_modified = mtr_align.to_4x4() @ rotate_matrix_around_axis(Matrix.Identity(4), math.radians(90) + slice_angle if switch_align else slice_angle, 0, 0) # X axis
	elif align_mode == '2':
		mtr_modified = mtr_align.to_4x4() @ rotate_matrix_around_axis(Matrix.Identity(4), 0, math.radians(90) + slice_angle if switch_align else slice_angle, 0) # Y axis
	elif align_mode == '3':
		mtr_base = rotate_matrix_around_axis(Matrix.Identity(4), 0, math.radians(90), 0)
		mtr_modified = mtr_align.to_4x4() @ rotate_matrix_around_axis(mtr_base, 0, 0, (math.radians(90) + slice_angle) if switch_align else slice_angle, ) # Z axis
	elif align_mode == '4':
		mtr_modified = mtr_align.to_4x4() @ rotate_matrix_around_axis(Matrix.Identity(4), 0, math.radians(90), 0) # X plane
	elif align_mode == '5':
		mtr_modified = mtr_align.to_4x4() @ rotate_matrix_around_axis(Matrix.Identity(4), -1 *  math.radians(90), 0, 0) # Y plane
	elif align_mode == '6':
		mtr_modified = mtr_align # Z plane

	return mtr_modified


def slice_setup_single_point(context, zero_pt, mtr_view, mtr_align, align_mode = '0', switch_align = False, slice_angle = 0):
	s3d = context.space_data.region_3d
	slice_pts = [zero_pt]

	if align_mode !='0':
		slice_angle = -1 * slice_angle
		mtr_align = rotated_align_orientation(mtr_align, align_mode, switch_align, slice_angle)
		slice_pts.append(zero_pt + matrix_to_vector_col(mtr_align,0)) # +x
		slice_pts.append(zero_pt + matrix_to_vector_col(mtr_align,1)) # +y

	else:
		slice_angle = slice_angle + math.radians(90) if switch_align else slice_angle
		slice_angle = -1 * slice_angle
		if s3d.view_perspective == 'PERSP' or s3d.view_perspective == 'CAMERA':
			slice_pts.append(zero_pt + (zero_pt - vector_convert_to_matrix_inverted(mtr_view)).normalized())
		else:
			slice_pts.append(zero_pt + (-1 * matrix_to_vector_row(mtr_view,2)))
		slice_pts.append(zero_pt + matrix_to_vector_row(rotate_matrix_around_axis(mtr_view, 0, 0, -1 * slice_angle), 1))
	return slice_pts

def rotated_align_orientation_two_points(mtr_align, align_mode, switch_align, slice_angle, vct_slice):
	if align_mode in ['1','4']:
		vct_al_y = matrix_to_vector_col(mtr_align, 0)
		vct_al_x = -1 * matrix_to_vector_col(mtr_align, 1)
	elif align_mode in ['2','5']:
		vct_al_y = matrix_to_vector_col(mtr_align, 1)
		vct_al_x = matrix_to_vector_col(mtr_align, 0)
	else:
		vct_al_y = matrix_to_vector_col(mtr_align, 2)
		vct_al_x = matrix_to_vector_col(mtr_align, 0)

	if round(abs(vct_al_y.dot(vct_slice)),5) != 1:
		vct_al_z = vct_al_y.cross(vct_slice).normalized()
		vct_al_x = vct_al_y.cross(vct_al_z)
	else:
		vct_al_z = vct_al_x.cross(vct_al_y)

	mtr_modified = vectors_to_matrix_col(vct_al_x, vct_al_y, vct_al_z) # if not round(abs(vct_al_x.dot(vct_slice)),5) == 1 else mtr_align
	mtr_modified = mtr_modified.to_3x3() @ rotate_matrix_around_axis(Matrix.Identity(4), 0, math.radians(90) + slice_angle if switch_align else slice_angle,0).to_3x3()

	return mtr_modified

def slice_setup_two_points(context, slice_pts, mtr_view, mtr_align, align_mode = '0', switch_align = False, slice_angle = 0):

	if align_mode !='0':
		vct_slice = (slice_pts[1] - slice_pts[0]).normalized()
		mtr_align = rotated_align_orientation_two_points(mtr_align, align_mode, switch_align, -1 * slice_angle, vct_slice)
		slice_pts = [slice_pts[0]]
		slice_pts.append(slice_pts[0] + matrix_to_vector_col(mtr_align,0))
		slice_pts.append(slice_pts[0] + matrix_to_vector_col(mtr_align,1))
	else:
		s3d = context.space_data.region_3d
		if s3d.view_perspective == 'PERSP' or s3d.view_perspective == 'CAMERA':
			pt_c =  vector_convert_to_matrix_inverted(mtr_view)
		else:
			pt_c =  slice_pts[0] + matrix_to_vector_row(mtr_view,2)

		if slice_angle != 0 or switch_align:
			slice_angle = slice_angle + math.radians(90) if switch_align else slice_angle
			pt_a, pt_b = slice_pts[0], slice_pts[1]

			vct_z = (pt_a - pt_c).normalized()
			vct_x = (mug_normal(pt_a, pt_b, pt_c)).normalized()
			vct_y = vct_z.cross(vct_x)

			mtr_slice = vectors_to_matrix_col(vct_x, vct_y, vct_z).to_4x4()
			mtr_slice_rot = mtr_slice @ rotate_matrix_around_axis(Matrix.Identity(4), 0, 0, slice_angle)
			pt_b = pt_a + (mtr_slice_rot @ Vector((0,1,0)))
			slice_pts = [pt_a, pt_c, pt_b]

		else:
			slice_pts.append(pt_c)

	return slice_pts

def rotated_align_orientation_triple_point(mtr_align, align_mode, switch_align, slice_angle):
	rot_ang = math.radians(90) + slice_angle if switch_align else slice_angle
	rot_x, rot_y, rot_z = rot_ang if align_mode in ['1','4'] else 0, rot_ang if align_mode in ['2','5'] else 0,  rot_ang if align_mode in ['3','6'] else 0
	mtr_modified = mtr_align.to_3x3() @ rotate_matrix_around_axis(Matrix.Identity(4), rot_x, rot_y, rot_z).to_3x3()

	return mtr_modified

def slice_setup_triple_point(context, slice_pts, mtr_align, align_mode = '0', switch_align = False, slice_angle = 0):

	if align_mode !='0':
		pt_b, pt_c = mtr_align.inverted() @ (Vector(slice_pts[1]) - Vector(slice_pts[0])), mtr_align.inverted() @ (Vector(slice_pts[2]) - Vector(slice_pts[0]))
		mtr_align = rotated_align_orientation_triple_point(mtr_align, align_mode, switch_align, -1 * slice_angle)
		pt_b, pt_c = Vector(slice_pts[0]) + (mtr_align @ pt_b), Vector(slice_pts[0]) + (mtr_align @ pt_c)
		slice_pts = [slice_pts[0], pt_b[:] ,pt_c[:]]
	else:
		pass

	return slice_pts

def align_view_to_slice(self, context):
	abt = context.scene.abt_props
	s3d = context.space_data.region_3d

	mtr_view = s3d.view_matrix
	mtr_orientation = get_transform_orientaions_from_mode(context,self.orientation_mode,self.slice_pts)

	pt_a = Vector(self.slice_pts[0])

	if len(self.slice_pts) == 1:
		pts_align = slice_setup_single_point(context, Vector(self.slice_pts[0]), mtr_view, mtr_orientation, self.align_mode, self.switch_align, self.slice_angle)
		pt_b, pt_c = pts_align[1], pts_align[2]
		pt_d = pt_a + mug_normal(pt_a, pt_b, pt_c)
		if   self.align_mode == '1': vct_x, vct_y, vct_z = (pt_b - pt_a).normalized(), (pt_c - pt_a).normalized(), (pt_d - pt_a).normalized()
		elif self.align_mode == '2': vct_x, vct_y, vct_z = (pt_b - pt_a).normalized(), (pt_c - pt_a).normalized(), (pt_d - pt_a).normalized()
		elif self.align_mode == '3': vct_x, vct_y, vct_z = (pt_d - pt_a).normalized(), (pt_c - pt_a).normalized(), (pt_b - pt_a).normalized()
		elif self.align_mode == '4': vct_x, vct_y, vct_z = (pt_d - pt_a).normalized(), (pt_c - pt_a).normalized(), (pt_b - pt_a).normalized()
		elif self.align_mode == '5': vct_x, vct_y, vct_z = (pt_b - pt_a).normalized(), (pt_d - pt_a).normalized(), (pt_c - pt_a).normalized()
		elif self.align_mode == '6': vct_x, vct_y, vct_z = (pt_b - pt_a).normalized(), (pt_c - pt_a).normalized(), (pt_d - pt_a).normalized()

	elif len(self.slice_pts) == 2:
		pts_align = slice_setup_two_points(context, [Vector(self.slice_pts[0]),Vector(self.slice_pts[1])], mtr_view, mtr_orientation, self.align_mode, self.switch_align, self.slice_angle)
		pt_b, pt_c = pts_align[1], pts_align[2]
		pt_d = pt_a + mug_normal(pt_a, pt_b, pt_c)
		vct_x, vct_y, vct_z = (pt_c - pt_a).normalized(), (pt_b - pt_a).normalized(), (pt_d - pt_a).normalized()
		if   self.align_mode in ['1','4']: vct_x, vct_y, vct_z = (pt_c - pt_a).normalized(), (pt_b - pt_a).normalized(), (pt_d - pt_a).normalized()
		elif self.align_mode in ['2','5']: vct_x, vct_y, vct_z = (pt_b - pt_a).normalized(), (pt_c - pt_a).normalized(), (pt_d - pt_a).normalized()
		elif self.align_mode in ['3','6']: vct_x, vct_y, vct_z = (pt_d - pt_a).normalized(), (pt_b - pt_a).normalized(), (pt_c - pt_a).normalized()

	elif len(self.slice_pts) == 3:
		tp_pts = slice_setup_triple_point(context, self.slice_pts, mtr_orientation, self.align_mode, self.switch_align, self.slice_angle)
		mtr_orientation_tp = get_transform_orientaions_from_mode(context, '5', tp_pts).inverted()		
		pt_b, pt_c, pt_d = pt_a + matrix_to_vector_row(mtr_orientation_tp, 0), pt_a + matrix_to_vector_row(mtr_orientation_tp, 1), pt_a + matrix_to_vector_row(mtr_orientation_tp, 2)
		vct_x, vct_y, vct_z = (pt_b - pt_a).normalized(), (pt_c - pt_a).normalized(), (pt_d - pt_a).normalized()

	vct_vz = vct_x if abt.align_view_set_id in [0,1] else vct_y if abt.align_view_set_id in [2,3] else vct_z
	vct_vz = -1 * vct_vz if abt.align_view_set_id in [1,3,5] else vct_vz

	if abs(round(vct_vz.z,6)) == 1:
		vct_vx = Vector((1,0,0))
		vct_vy = vct_vz.cross(vct_vx)
	else:
		vct_vy = vector_reprojection(Vector((0,0,1)),vct_vz)
		vct_vx = vct_vy.cross(vct_vz)

	mtr_view_new = vectors_to_matrix_col(vct_vx, vct_vy, vct_vz)
	mtr_view_new = mtr_view_new.to_4x4()
	pt_a = pt_a + (distance_between_vectors(pt_a, vector_convert_to_matrix_inverted(mtr_view)) * vct_vz) if s3d.view_perspective == 'PERSP' else pt_a
	col_w = pt_a.resized(4)
	col_w.w = 1
	mtr_view_new.col[3] = col_w
	s3d.view_matrix = mtr_view_new.inverted()



def axis_vertex_one_edge(bma,obm,vzw,edg_l):
	vtc_a = bma.co
	vtc_b = edg_l.verts[0].co if edg_l.verts[1].co == vtc_a else edg_l.verts[1].co
	vtc_a, vtc_b = obm @ vtc_a, obm @ vtc_b

	vy = (vtc_a - vtc_b).normalized()
	
	if abs(round(vy.z,6)) == 1:
		vx = Vector((1,0,0))
		vz = vx.cross(vy)
	else:
		vz = vector_reprojection(vzw,vy)
		vx = vy.cross(vz)

	return vx,vy,vz

def axis_vertex_two_edges(bma,obm,vzw,edg_a,edg_b):
	vtc_a = bma.co
	vtc_b = edg_a.verts[0].co if edg_a.verts[1].co == vtc_a else edg_a.verts[1].co
	vtc_c = edg_b.verts[0].co if edg_b.verts[1].co == vtc_a else edg_b.verts[1].co
	vtc_a, vtc_b, vtc_c = obm @ vtc_a, obm @ vtc_b, obm @ vtc_c

	# Reproduced from Blender source
	if len(bma.link_edges[0].link_loops) != 0:
		flip = True if bma.link_edges[0].link_loops[0].vert.index == bma.index else False
	else:
		flip = False
	vy_a = (vtc_b - vtc_a).normalized() if flip else (vtc_a - vtc_b).normalized() 
	vy_b = (vtc_a - vtc_c).normalized() if flip else (vtc_c - vtc_a).normalized()

	if abs(round(vy_a.dot(vy_b),6)) == 1:
		vy = vy_a
		if abs(round(vy.z,6)) == 1:
			vx = Vector((1,0,0))
			vz = vx.cross(vy)
		else:
			vz = vector_reprojection(vzw,vy)
			vx = vy.cross(vz)
	else:
		vy = ((vy_a + vy_b)/2).normalized() 
		vz = mug_normal((vtc_a),(vtc_c),(vtc_b))
		vx = vy.cross(vz)

	if len(bma.link_faces) != 0: # If vertex has faces connected - use faces normal as Z
		vz = vector_fix_a(obm, bma.normal)
		vx = vy.cross(vz)

	return vx,vy,vz

def axis_vertex_three_plus_edges(bma,obm,eds):
	vtc_a = bma.co
	v_sum = Vector((0,0,0))
	vtcs, vtc_t, eds_lv = list(), list(), list()

	for edg in eds:
		vtc_b = edg.verts[0].co if edg.verts[1].co == vtc_a else edg.verts[1].co  # Calculate second vertex and find normalized edge vector
		vtcs.append(vtc_b)
		vtc_t.append(vtc_b)
		edg_v = ((obm @ vtc_a) - (obm @ vtc_b)).normalized() 
		edg_l =  round(edg.calc_length(),4)
		v_sum = v_sum + edg_v # Sum of linked edges vectors to calculate vertex normal
		eds_lv.append((edg_l,edg_v))

	if len(bma.link_faces) != 0: # If vertex has faces connected - use faces normal as Z
		vz = vector_fix_a(obm, bma.normal)
	else:
		if round(v_sum.length,4) > 0.1: # If all linked edges not in flat plane
			vz = (v_sum/(len(eds))).normalized()
		else: # Else Get Z from three vertices						
			vz = mug_normal(vtc_t[:3])

	eds_lv.sort(reverse=True ,key=lambda el:el[0]) # Sort linked edges by length
	
	if eds_lv[0][0] < (eds_lv[-1][0]*1.5): 
		eds_lv.reverse()

	edg_a, edg_b = eds_lv[0][1], eds_lv[-1][1]
	vy = vector_reprojection(edg_a,vz) if abs(round(edg_a.dot(vz),5)) != 1 else edg_b # Y oriented to one of the edges to follow topology
	vx = vz.cross(vy)
	
	return vx,vy,vz

def axis_edge_no_face(obm,vzw,vtc_a,vtc_b):
	vtc_aco, vtc_bco = obm @ vtc_a.co, obm @ vtc_b.co
	vy = (vtc_aco - vtc_bco).normalized()

	if abs(round(vy.z,6)) == 1: # Check if Y axis look straight up
		vx = Vector((1,0,0))
		vz = vy.cross(vx)
	else:
		vz = vector_reprojection(vzw,vy)
		vx = vy.cross(vz)

	return vx,vy,vz

def axis_edge_with_faces(bma,obm,edg_lf,vzw,vtc_a,vtc_b):
	flip = False
	# Reproduced from Blender source and yet sometimes Y axis loo in wrong direction, check later for solution
	if bma.link_loops[0].index == bma.link_loops[0].link_loop_radial_next.index:
		if bma.link_loops[0].vert.index != bma.verts[0].index:
			flip = True

	vtc_aco, vtc_bco = obm @ vtc_a.co, obm @ vtc_b.co
	vy = (vtc_aco - vtc_bco).normalized() if flip else (vtc_bco - vtc_aco).normalized()
	vts_n = vector_fix_b(obm, vtc_a.normal + vtc_b.normal) # sum of two linked vertices normals

	if vts_n.dot(vy) != 0:
		vz = vector_reprojection(vts_n,vy)
	elif vts_n.dot(vy) == 1:
		vz = vector_reprojection(vzw,vy)
	else:
		vz = vts_n

	vx = vy.cross(vz)

	return vx,vy,vz

def axis_face_triangle(bma,obm):
	vz = vector_fix_a(obm, bma.normal)
	vtcs = bma.verts
	unic = list() 
	
	for i in range(3):  # Reproduced Bleder way to check for "most unic" edge to get same Y vector
		vtc_p,vtc_c,vtc_n = vtcs[i-1].co,vtcs[i].co,vtcs[(i+1)%3].co
		mid_vec = (0.5*(vtc_p+vtc_n))-vtc_c
		proj_p = mid_vec*(vtc_p.dot(mid_vec)/mid_vec.dot(mid_vec))
		proj_n = mid_vec*(vtc_n.dot(mid_vec)/mid_vec.dot(mid_vec))
		proj_l = proj_n - proj_p
		unic.append((i, proj_l.dot(proj_l)))

	uid = sorted(unic, key= lambda l:l[1])[0][0]
	# Vector Fix for scaled objects, Bledner original code do it incorrect
	vy = vector_fix_b(obm, (vtcs[(uid+2)%3].co - vtcs[(uid+1)%3].co)).normalized()  
	vx = vy.cross(vz)

	return vx,vy,vz

def axis_face_quad(bma,obm):
	vz = vector_fix_a(obm, bma.normal)
	vy = vector_fix_a(obm, ((bma.calc_tangent_edge_pair()).normalized())*-1)
	vy = vector_reprojection(vy,vz)
	vx = vy.cross(vz)

	return vx,vy,vz

def axis_face_ngon(bma,obm):
	vz = vector_fix_a(obm, bma.normal)
	vtc_aco, vtc_bco = Vector((0,0,0)), Vector((0,0,0))
	vts = bma.verts
	dist_l = 0
	# reproduced Blender code, iterating through vertices and checking for longest distance
	for en,vtc in enumerate(vts): 
		vtc_a = vtc
		vtc_b = vts[(en+1)%len(vts)]
		dist = vtc_b.co - vtc_a.co
		dist_d = dist.dot(dist)
		if dist_d >= dist_l:
			dist_l = dist_d
			vtc_aco = vtc_a.co
			vtc_bco = vtc_b.co

	vy = vector_fix_a(obm, (vtc_bco - vtc_aco))
	vy = vector_reprojection(vy,vz)
	vx = vy.cross(vz)

	return vx,vy,vz


def get_active_element_vectors(context,aob):
	bmd = bmesh.from_edit_mesh(context.edit_object.data)
	bma = bmd.select_history.active
	obm = aob.matrix_world
	zero = Vector((0,0,0))
	vzw = Vector((0,0,1))

	if bma == None: return None
	else:

		# Vertex Normal Orientation
		if str(bma).find('BMVert') == 1:
			eds = [edg for edg in bma.link_edges if round(edg.calc_length(),6) != 0] # Check if linked edge/esged length > 0, if == 0 edge ignored

			if len(eds) == 0:  # Global Orientation if no linked edges or linked edge length = 0
				vx,vy,vz = Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))

			elif len(eds) == 1: # Single Edge mode if only one linked edge or only one edge length > 0
				vx,vy,vz = axis_vertex_one_edge(bma,obm,vzw,eds[0])

			elif len(eds) == 2: # Double Edge mode if only two linked edges or only two edges length > 0
				vx,vy,vz = axis_vertex_two_edges(bma,obm,vzw,eds[0],eds[1])

			else:
				vx, vy, vz = axis_vertex_three_plus_edges(bma,obm,eds)

		# Edges Normal Orientation
		elif str(bma).find('BMEdge') == 1:
			edg_lf = bma.link_faces
			vtc_a, vtc_b = bma.verts[0], bma.verts[1]

			if len(edg_lf) == 0: # If edge has no connected faces
				vx, vy, vz = axis_edge_no_face(obm,vzw,vtc_a,vtc_b)

			else:
				vx, vy, vz = axis_edge_with_faces(bma,obm,edg_lf,vzw,vtc_a,vtc_b)

		# Faces Normal Orientation
		else:

			if len(bma.verts) == 3: # Triangle Face

				if round(bma.calc_area(),5) == 0:     # In case if triangle == line (one of vertices on opposite edge), do something better later
					vx, vy, vz = Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))
				else:
					vx, vy, vz = axis_face_triangle(bma,obm)

			elif len(bma.verts) == 4: # Quad Face
				vx, vy, vz = axis_face_quad(bma,obm)

			else: # Ngon Face		
				vx, vy, vz = axis_face_ngon(bma,obm)

		return vectors_to_matrix_col(vx,vy,vz)


def screen_size(context, loc, pdc= False):
	s3d = context.space_data.region_3d
	a3d = context.area.spaces.active.region_3d

	if s3d.view_perspective  == 'ORTHO':
		scl = a3d.view_distance/10
	elif s3d.view_perspective == 'PERSP':
		vmt = a3d.view_matrix
		dis = distance_between_vectors(vmt @ loc, Vector((0,0,0)))
		if dis<30 and pdc:
			scl = abs(dis)/remap_range(1,10,0,30,dis)
		else:
			scl = abs(dis)/10

	else:
		zo = a3d.view_camera_zoom
		vmt = a3d.view_matrix
		if zo>0:
			v = 3.14**(((30+((zo)+30))/30)*remap_range(1,0.26,0,1,math.sqrt((zo/600)**0.7)))
		else:
			v = 3.14**((30+((zo)+30))/30)

		dis = distance_between_vectors(vmt @ loc, Vector((0,0,0)))
		if dis<30 and pdc:
			scl = abs(dis)/remap_range(1,v,0,30,dis)
		else:
			scl = abs(dis)/v

	return scl

def cast_ray(context, cursor_xy, custom_start_point= Vector((0,0,0)), use_custom_start_point= False):
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

def screen_aligned_vector_line_2d(context, pt_a, pt_b):
	s3d = context.space_data.region_3d

	pt_as = convert_global_to_screen(context.region, s3d, pt_a)
	pt_bs = convert_global_to_screen(context.region, s3d, pt_b)

	if pt_as == None or pt_bs == None:
		if pt_as == None and pt_bs == None:
			cam_pos = -1 * matrix_to_vector_col(mtr_view,3) @ s3d.view_matrix.to_3x3()
			pt_a = pt_a + (2 * (cam_pos - pt_a))
			pt_b = pt_b + (2 * (cam_pos - pt_b))
			pt_as = convert_global_to_screen(context.region, s3d, pt_a)
			pt_bs = convert_global_to_screen(context.region, s3d, pt_b)
		elif pt_as == None:
			pt_a = pt_a + (2 * (pt_b - pt_a))
			pt_as = convert_global_to_screen(context.region, s3d, pt_a)
		else:
			pt_b = pt_b + (2 * (pt_a - pt_b))
			pt_bs = convert_global_to_screen(context.region, s3d, pt_b)

	scv = pt_bs - pt_as
	scs_x, scs_y = context.region.width, context.region.height

	if scv.y == 0: # Straight Horizontal
		lco_a = Vector((0,    pt_as.y, 0))
		lco_b = Vector((scs_x, pt_as.y, 0))

	elif scv.x == 0: # Straight Vertical
		lco_a = Vector((pt_as.x, 0, 0))
		lco_b = Vector((pt_as.x, scs_y, 0))

	elif abs(scv.x) >= abs(scv.y): # Closer to horizontal
		if pt_as.x >= pt_bs.x:
			scv, pt_cs = pt_as - pt_bs, pt_as 
		else:
			scv, pt_cs = pt_bs - pt_as, pt_as 						

		lco_a = Vector(( 0, pt_cs.y + ((pt_cs.x / scv.x) * scv.y * -1), 0))
		lco_b = Vector(( scs_x, pt_cs.y + (((scs_x - pt_cs.x) / scv.x) * scv.y), 0))

	else: # # Closer to vertical
		if pt_as.y >= pt_bs.y:
			scv, pt_cs  = pt_as - pt_bs, pt_as
		else:
			scv, pt_cs = pt_bs - pt_as, pt_bs 

		lco_a = Vector(( pt_cs.x + ((pt_cs.y / scv.y) * scv.x * -1), 0, 0))
		lco_b = Vector(( pt_cs.x + (((scs_y - pt_cs.y) / scv.y) * scv.x), scs_y, 0))

	return lco_a, lco_b

def draw_points_uc(coordinates,color,point_size=1): # for list of points with single color
	batch = batch_for_shader(shd_uc, 'POINTS', {'pos': coordinates})
	bgl.glPointSize(point_size)
	shd_uc.bind()
	shd_uc.uniform_float("color", color)
	batch.draw(shd_uc)
	bgl.glPointSize(1)

def draw_lines_uc(coordinates,color,line_width=1): # for list of lines with single color
	batch = batch_for_shader(shd_uc, 'LINES', {'pos': coordinates})
	bgl.glLineWidth(line_width)
	shd_uc.bind()
	shd_uc.uniform_float("color", color)
	batch.draw(shd_uc)
	bgl.glLineWidth(1)


def draw_lines_sc(coordinates,color,line_width=1): # for list of lines with different colors 
	batch = batch_for_shader(shd_sc, 'LINES', {'pos': coordinates, 'color': color})
	bgl.glLineWidth(line_width)
	shd_sc.bind()
	batch.draw(shd_sc)
	bgl.glLineWidth(1)


def draw_orientation_axis(context, abt_p, mtr_orientation, first_point):
	axis_data = [[(-0.3, 0.0, 0.0), (-0.1, 0.0, 0.0), (1.0, 1.0, 1.0, 0.8), False],
				[(0.0, -0.3, 0.0), (0.0, -0.1, 0.0), (1.0, 1.0, 1.0, 0.8), False],
				[(0.0, 0.0, -0.3), (0.0, 0.0, -0.1), (1.0, 1.0, 1.0, 0.8), False],
				[(1.0, 0.0, 0.0), (0.1, 0.0, 0.0), abt_p.orientation_axis_col_x, True], 
				[(0.0, 1.0, 0.0), (0.0, 0.1, 0.0), abt_p.orientation_axis_col_y, True],
				[(0.0, 0.0, 1.0), (0.0, 0.0, 0.1), abt_p.orientation_axis_col_z, True]]

	scl = screen_size(context,first_point,False)

	axis_data_mod = []
	for dat in axis_data:
		dat_mod = [((mtr_orientation.to_3x3() @ Vector(crd)) * (abt_p.orientation_axis_size/10) * scl + first_point) for crd in dat[:2]]
		#print('DAT MOD >>> ', dat_mod)
		dat_mod.append(dat[2])
		#print('DAT MOD >>> ', dat_mod)
		dat_mod.append(dat[3])
		#print('DAT MOD >>> ', dat_mod)
		axis_data_mod.append(dat_mod)

	mtr_view = context.space_data.region_3d.view_matrix

	#print(mtr_view.inverted().to_3x3())
	#print('VECTOR (1,0,0) = ', mtr_view.to_3x3() @ Vector((1,0,0)))
	#print('VECTOR (-1,0,0) = ', mtr_view.to_3x3() @ Vector((-1,0,0)))

	axis_data_ordered = sorted(axis_data_mod, key= lambda x: (mtr_view @ x[0]).z)

	#print('DRAW >>>>>>>>>>>>>')



	for dat in axis_data_ordered:
		col = dat[2]
		draw_lines_sc(dat[:2], [col, col], abt_p.gizmo_lns_width)
		#print('DEPTH >>>', (mtr_view.inverted() @ dat[0]).z, 'DAT >>> ', dat)
		if dat[3]:
			
			draw_points_uc([dat[0][:]], col, 5 * abt_p.gizmo_lns_width)

def draw_slice_plane_grid(context, abt_p, mtr_orientation, align, first_point, points_num):
	grid_crd = [(-2.0, 2.25, 0.0), (-2.0, -2.25, 0.0),
				(-1.0, 2.25, 0.0), (-1.0, -2.25, 0.0),
				(0.0, 2.25, 0.0 ), (0.0, -2.25, 0.0),
				(1.0, 2.25, 0.0 ), (1.0, -2.25, 0.0),
				(2.0, 2.25, 0.0 ), (2.0, -2.25, 0.0),
				(2.25, -2.0, 0.0), (-2.25, -2.0, 0.0),
				(2.25, -1.0, 0.0), (-2.25, -1.0, 0.0),
				(2.25, 0.0, 0.0), (-2.25, 0.0, 0.0),
				(2.25, 1.0, 0.0), (-2.25, 1.0, 0.0),
				(2.25, 2.0, 0.0), (-2.25, 2.0, 0.0)]

	col_x, col_y, col_z = abt_p.orientation_axis_col_x, abt_p.orientation_axis_col_y, abt_p.orientation_axis_col_z
	col_a, col_b = abt_p.grid_lns_color, abt_p.grid_lns_color

	if points_num == 3:
		grid_col = [col_y, col_y,
					col_a, col_a,
					col_a, col_a,
					col_a, col_a,
					col_y, col_y,
					col_x, col_x,
					col_b, col_b,
					col_b, col_b,
					col_b, col_b,
					col_x, col_x]

	else:
		if align == '1': col_a, col_b = col_x, col_x # X axis
		elif align == '2': col_a, col_b = col_y, col_y # Y axis
		elif align == '3': col_a, col_b = col_z, col_z # Z axis
		elif align == '4': col_a, col_b = col_y if points_num == 1 else col_x, col_z if points_num == 1 else col_x # X plane
		elif align == '5': col_a, col_b = col_z if points_num == 1 else col_y, col_x if points_num == 1 else col_y # Y plane
		elif align == '6': col_a, col_b = col_y if points_num == 1 else col_z, col_x if points_num == 1 else col_z # Z plane

		grid_col = [col_a, col_a,
					col_a, col_a,
					col_a, col_a,
					col_a, col_a,
					col_a, col_a,
					col_b, col_b,
					col_b, col_b,
					col_b, col_b,
					col_b, col_b,
					col_b, col_b]

	scli = 0.025
	scl = screen_size(context,first_point,False)
	scl_steps = [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 25, 50, 100, 150, 250]

	for scl_stp in scl_steps:
		if scl >= scl_stp:
			scli = scl_stp

	if scli != 1:
		grid_crd_mod = [((mtr_orientation.to_3x3() @ (Vector(crd) * scli)) + first_point) for crd in grid_crd]
	else:
		grid_crd_mod = [((mtr_orientation.to_3x3() @ Vector(crd)) + first_point) for crd in grid_crd]

	draw_lines_sc(grid_crd_mod, grid_col, abt_p.grid_lns_width)

#    333333333   DDDDDDDDD
#         33333  DDD    DDD
#    333333333   DDD    DDDD   ----------------------------------------------------------------------------------------------------
#    333333333   DDD    DDDD   ----------------------------------------------------------------------------------------------------
#         33333  DDD    DDD
#    333333333   DDDDDDDDD

def draw_3d_stuff(self,context):
	abt_p = context.preferences.addons[__name__].preferences
	abt = context.scene.abt_props
	s3d = context.space_data.region_3d

	if not is_view_transparent(context):
		bgl.glEnable(bgl.GL_DEPTH_TEST)
	bgl.glDepthFunc(bgl.GL_LESS)

	if abt.hid_eds_enabled and self.hid_eds_draw.size != 0: # Draw hidden mesh edges
		draw_lines_uc(self.hid_eds_draw, abt_p.hid_eds_color, abt_p.hid_eds_width)

	if abt.vtc_pts_enabled: # Draw vertex points
		draw_points_uc(self.vtc_pts_draw, abt_p.vtc_pts_color[:], abt_p.vtc_pts_size) # draw vertices slice points

	if abt.mid_pts_enabled: # Draw midpoints
		draw_points_uc(self.mid_pts_draw, abt_p.mid_pts_color[:], abt_p.mid_pts_size) # draw median slice pints 

	bgl.glDisable(bgl.GL_DEPTH_TEST)

	if self.slice_pts != []:
		mtr_orientation = get_transform_orientaions_from_mode(context,self.orientation_mode,self.slice_pts)
		mtr_view = s3d.view_matrix

		if abt.orientation_axis_enabled or abt.slice_plane_grid_enabled: # draw orientation axis and slice grid/line --------------------------

			if  abt.orientation_axis_enabled: # Transform orientation axis gizmo
				draw_orientation_axis(context, abt_p, mtr_orientation, Vector(self.slice_pts[0]))

			if abt.slice_plane_grid_enabled: # Slice plane preview grid

				if len(self.slice_pts) >= 3 and self.align_mode == '0':
					pt_a, pt_b, pt_c = Vector(self.slice_pts[0]), Vector(self.slice_pts[1]), Vector(self.slice_pts[2])
					vz = mug_normal(pt_a, pt_b, pt_c)
					if abs(round(vz.z,6)) == 1:
						vx = Vector((1,0,0))
						vy = vx.cross(vz)
					else:
						vy = vector_reprojection(Vector((0,0,1)),vz)
						vx = vy.cross(vz)

					mtr_orientation_mod = vectors_to_matrix_col(vx,vy,vz)
					draw_slice_plane_grid(context, abt_p, mtr_orientation_mod, '0', Vector(self.slice_pts[0]), 3)

				elif self.align_mode != '0':
					if len(self.slice_pts) == 1: # One point XYZ aligned
						mtr_orientation_mod = rotated_align_orientation(mtr_orientation, self.align_mode, self.switch_align, -1 * self.slice_angle)
						draw_slice_plane_grid(context, abt_p, mtr_orientation_mod, self.align_mode, Vector(self.slice_pts[0]), 1)
					elif len(self.slice_pts) == 2: # Two points XYZ aligned
						vct_slice = (Vector(self.slice_pts[1]) - Vector(self.slice_pts[0])).normalized()
						mtr_orientation_mod = rotated_align_orientation_two_points(mtr_orientation, self.align_mode, self.switch_align, -1 * self.slice_angle, vct_slice)
						draw_slice_plane_grid(context, abt_p, mtr_orientation_mod, self.align_mode, Vector(self.slice_pts[0]), 2)
					else:
						align_mode = '1' if self.align_mode in ['1','4'] else '2' if self.align_mode in ['2','5'] else '3'
						mtr_orientation_mod = rotated_align_orientation(mtr_orientation, align_mode, self.switch_align, -1 * self.slice_angle)
						draw_slice_plane_grid(context, abt_p, mtr_orientation_mod, align_mode, Vector(self.slice_pts[0]), 1)						


		if not is_view_transparent(context):
			bgl.glEnable(bgl.GL_DEPTH_TEST)

		if self.draw_slice:
			if self.slc_lines_draw.size != 0:
				draw_lines_uc(self.slc_lines_draw,  abt_p.slc_lns_color[:], abt_p.slc_lns_width)
			if self.slc_points_draw.size != 0:
				draw_points_uc(self.slc_points_draw, abt_p.slc_pts_color[:], abt_p.slc_pts_size)

		bgl.glDisable(bgl.GL_DEPTH_TEST)

		if len(self.slice_pts) == 3: # Draw slice triangle in 3D for triple point mod
			slc_triangle = [self.slice_pts[0],self.slice_pts[1],self.slice_pts[1],self.slice_pts[2],self.slice_pts[2],self.slice_pts[0]]
			if self.bisect_offset != 0 or (self.align_mode != '0' and (self.slice_angle != 0 or self.switch_align)):
				draw_lines_uc(slc_triangle, abt_p.ui_txt_shadow_color, abt_p.axis_lns_width * 1.2)
				draw_lines_uc(slc_triangle, abt_p.grid_lns_color, abt_p.axis_lns_width)			
			
				if self.align_mode != '0' and (self.slice_angle != 0 or self.switch_align):	
					pts_slc = slice_setup_triple_point(context, copy(self.slice_pts), mtr_orientation, self.align_mode, self.switch_align, self.slice_angle)
				else:
					pts_slc = copy(self.slice_pts)

				if self.bisect_offset != 0:
					bisect_normal = mug_normal([Vector(pt) for pt in pts_slc]) * -1 if self.bisect_flip_normal else mug_normal([Vector(pt) for pt in pts_slc])
					pts_slc = [(Vector(pt) + (bisect_normal * self.bisect_offset))[:] for pt in pts_slc]

				slc_triangle = [pts_slc[0],pts_slc[1],pts_slc[1],pts_slc[2],pts_slc[2],pts_slc[0]]
				draw_lines_uc(slc_triangle,abt_p.mrk_pts_color[:],abt_p.axis_lns_width)
			else:
				draw_lines_uc(slc_triangle,abt_p.mrk_pts_color[:],abt_p.axis_lns_width)


		if self.slice_pts != []: # Draw actual slice points
			draw_points_uc(self.slice_pts, abt_p.mrk_pts_color[:], abt_p.mrk_pts_size) # draw marked points

#     222222222   DDDDDDDDD
#    222   22222  DDD    DDD
#         22222   DDD    DDDD   ----------------------------------------------------------------------------------------------------
#       22222     DDD    DDDD   ----------------------------------------------------------------------------------------------------
#    22222222222  DDD    DDD
#    22222222222  DDDDDDDDD


def draw_2d_stuff(self,context):
	abt_p = context.preferences.addons[__name__].preferences
	abt = context.scene.abt_props
	
	if self.slice_pts != []: # Slice helper lines
		s3d = context.space_data.region_3d

		mtr_orientation = get_transform_orientaions_from_mode(context,self.orientation_mode,self.slice_pts)
		mtr_view = s3d.view_matrix

		if len(self.slice_pts)==1: # Single point stuff -------------------------------------------------------------------
			if self.align_mode == '0':
				slice_line_col = abt_p.orientation_axis_col_x if self.switch_align else abt_p.orientation_axis_col_y
				pt_a = Vector(self.slice_pts[0])
				pts_slc = slice_setup_single_point(context, Vector(self.slice_pts[0]), mtr_view, mtr_orientation, '0', self.switch_align, self.slice_angle)
				pt_b, pt_c = pts_slc[2], pts_slc[1]

				# Gray line if angle is not zero
				if self.slice_angle != 0:
					pt_d = slice_setup_single_point(context, Vector(self.slice_pts[0]), mtr_view, mtr_orientation, '0', self.switch_align, 0)[2]
					slice_line_co = screen_aligned_vector_line_2d(context, pt_a, pt_d)
					slice_line = [slice_line_co[0][:],slice_line_co[1][:]]
					draw_lines_uc(slice_line, abt_p.ui_txt_shadow_color, abt_p.axis_lns_width * 1.2)
					draw_lines_uc(slice_line, abt_p.grid_lns_color, abt_p.axis_lns_width)
				# Grey line if offset is not zero
				if self.bisect_offset != 0:
					slice_line_co = screen_aligned_vector_line_2d(context, pt_a, pt_b)
					slice_line = [slice_line_co[0][:],slice_line_co[1][:]]
					draw_lines_uc(slice_line, abt_p.ui_txt_shadow_color, abt_p.axis_lns_width * 1.2)
					draw_lines_uc(slice_line, abt_p.grid_lns_color, abt_p.axis_lns_width)


				slice_side_vct = -1 * mug_normal(pts_slc) if  self.bisect_flip_normal else mug_normal(pts_slc)
				slice_line_co = screen_aligned_vector_line_2d(context,pt_a + (slice_side_vct * self.bisect_offset),pt_b + (slice_side_vct * self.bisect_offset))
				slice_line = [slice_line_co[0][:],slice_line_co[1][:]]
				draw_lines_uc(slice_line, slice_line_col, abt_p.axis_lns_width)

			else:
				pt_a = Vector(self.slice_pts[0])
				pts_align = slice_setup_single_point(context, Vector(self.slice_pts[0]), mtr_view, mtr_orientation, self.align_mode, self.switch_align, self.slice_angle)
				pt_b, pt_c = pts_align[1], pts_align[2]
				pt_d = pt_a + mug_normal(pt_a, pt_b, pt_c)
				if   self.align_mode == '1': pts_x, pts_y, pts_z = [pt_a,pt_b], [pt_a,pt_c], [pt_a,pt_d]
				elif self.align_mode == '2': pts_x, pts_y, pts_z = [pt_a,pt_b], [pt_a,pt_c], [pt_a,pt_d]
				elif self.align_mode == '3': pts_x, pts_y, pts_z = [pt_a,pt_d], [pt_a,pt_c], [pt_a,pt_b]  
				elif self.align_mode == '4': pts_x, pts_y, pts_z = [pt_a,pt_d], [pt_a,pt_c], [pt_a,pt_b]
				elif self.align_mode == '5': pts_x, pts_y, pts_z = [pt_a,pt_b], [pt_a,pt_d], [pt_a,pt_c]
				elif self.align_mode == '6': pts_x, pts_y, pts_z = [pt_a,pt_b], [pt_a,pt_c], [pt_a,pt_d]

				vct_to_cam = vector_to_cam_normalized(s3d, pt_a)

				if abs((pts_x[1] - pt_a).normalized().dot(vct_to_cam)) < 0.9999:
					line_x_co = screen_aligned_vector_line_2d(context, pts_x[0], pts_x[1])
					draw_lines_uc([line_x_co[0][:],line_x_co[1][:]], abt_p.orientation_axis_col_x, abt_p.axis_lns_width)

				if abs((pts_y[1] - pt_a).normalized().dot(vct_to_cam)) < 0.9999:
					line_y_co = screen_aligned_vector_line_2d(context, pts_y[0], pts_y[1])
					draw_lines_uc([line_y_co[0][:],line_y_co[1][:]], abt_p.orientation_axis_col_y, abt_p.axis_lns_width)

				if abs((pts_z[1] - pt_a).normalized().dot(vct_to_cam)) < 0.9999:
					line_z_co = screen_aligned_vector_line_2d(context, pts_z[0], pts_z[1])
					draw_lines_uc([line_z_co[0][:],line_z_co[1][:]], abt_p.orientation_axis_col_z, abt_p.axis_lns_width)				

				if self.bisect_offset != 0:
					if   self.align_mode == '1': pts_slc, vct_off = [pt_a,pt_c], -1 * (pt_d - pt_a).normalized() if self.bisect_flip_normal else (pt_d - pt_a).normalized()
					elif self.align_mode == '2': pts_slc, vct_off = [pt_a,pt_b], -1 * (pt_d - pt_a).normalized() if self.bisect_flip_normal else (pt_d - pt_a).normalized()
					elif self.align_mode == '3': pts_slc, vct_off = [pt_a,pt_b], -1 * (pt_d - pt_a).normalized() if self.bisect_flip_normal else (pt_d - pt_a).normalized()
					elif self.align_mode in ['4','5','6']: pts_slc, vct_off = [pt_a,pt_b,pt_a,pt_c], -1 * (pt_d - pt_a).normalized() if self.bisect_flip_normal else (pt_d - pt_a).normalized()

					pts_slc = [pt + (vct_off * self.bisect_offset) for pt in pts_slc]

					if abs((pts_slc[1] - pts_slc[0]).normalized().dot(vct_to_cam)) < 0.9999:
						line_slc_co = screen_aligned_vector_line_2d(context, pts_slc[0], pts_slc[1])
						draw_lines_uc([line_slc_co[0][:],line_slc_co[1][:]], abt_p.mrk_pts_color, abt_p.axis_lns_width)
					if self.align_mode in ['4','5','6']:

						if abs((pts_slc[3] - pts_slc[0]).normalized().dot(vct_to_cam)) < 0.9999:					
							line_slc_co = screen_aligned_vector_line_2d(context, pts_slc[2], pts_slc[3])
							draw_lines_uc([line_slc_co[0][:],line_slc_co[1][:]], abt_p.mrk_pts_color, abt_p.axis_lns_width)


		elif len(self.slice_pts)==2: # Two points stuff -------------------------------------------------------------------
			pt_a, pt_b = Vector(self.slice_pts[0]), Vector(self.slice_pts[1])
			vct_to_cam = vector_to_cam_normalized(s3d, pt_a)

			if self.align_mode == '0':
				#if self.slice_angle == 0:
				if abs((pt_b - pt_a).normalized().dot(vct_to_cam)) < 0.9999:
					slice_line_co = screen_aligned_vector_line_2d(context, pt_a, pt_b)
					slice_line = [slice_line_co[0][:],slice_line_co[1][:]]
					if self.bisect_offset != 0 or self.slice_angle != 0 or self.switch_align: # Grey line if offset or angle is not zero
						draw_lines_uc(slice_line, abt_p.ui_txt_shadow_color, abt_p.axis_lns_width * 1.2)
						draw_lines_uc(slice_line, abt_p.grid_lns_color, abt_p.axis_lns_width)
					else:
						draw_lines_uc(slice_line, abt_p.mrk_pts_color, abt_p.axis_lns_width)

					if self.bisect_offset != 0 or self.slice_angle != 0 or self.switch_align: # Offset line if offset is not zero
						pts_slc = slice_setup_two_points(context, [pt_a, pt_b], mtr_view, mtr_orientation, self.align_mode, self.switch_align, self.slice_angle)
						pt_c, pt_b = pts_slc[1], pts_slc[2]
						vct_slice_side = -1 * mug_normal(pt_a, pt_c, pt_b) if  self.bisect_flip_normal else mug_normal(pt_a, pt_c, pt_b)
						if self.slice_angle != 0 or self.switch_align:
							vct_to_cam = vector_to_cam_normalized(s3d, pt_a)
							if abs((pt_b - pt_a).normalized().dot(vct_to_cam)) < 0.9999:
								slice_line_co = screen_aligned_vector_line_2d(context, pt_a, pt_b)
								slice_line = [slice_line_co[0][:],slice_line_co[1][:]]
								if self.bisect_offset != 0:
									draw_lines_uc(slice_line, abt_p.ui_txt_shadow_color, abt_p.axis_lns_width * 1.2)
									draw_lines_uc(slice_line, abt_p.grid_lns_color, abt_p.axis_lns_width)
								else:
									draw_lines_uc(slice_line, abt_p.mrk_pts_color, abt_p.axis_lns_width)
						if self.bisect_offset != 0:
							pt_a_off = pt_a + (vct_slice_side * self.bisect_offset)
							slice_along_vct =  mug_normal(pt_a, pt_a_off, pt_c)
							pt_b_off = pt_a_off + slice_along_vct
							if abs((pt_b_off - pt_a_off).normalized().dot(vct_to_cam)) < 0.9999:
								slice_line_co = screen_aligned_vector_line_2d(context, pt_a_off, pt_b_off)
								slice_line = [slice_line_co[0][:],slice_line_co[1][:]]
								draw_lines_uc(slice_line, abt_p.mrk_pts_color, abt_p.axis_lns_width)

			else:
				if abs((pt_b - pt_a).normalized().dot(vct_to_cam)) < 0.9999: # Slice line on two points
					slice_line_co = screen_aligned_vector_line_2d(context, pt_a, pt_b)
					slice_line = [slice_line_co[0][:],slice_line_co[1][:]]

					if self.bisect_offset != 0: # Grey line if offset is not zero
						draw_lines_uc(slice_line, abt_p.ui_txt_shadow_color, abt_p.axis_lns_width * 1.2)
						draw_lines_uc(slice_line, abt_p.grid_lns_color, abt_p.axis_lns_width)
					else:
						draw_lines_uc(slice_line, abt_p.mrk_pts_color, abt_p.axis_lns_width)


				pts_align = slice_setup_two_points(context, [Vector(self.slice_pts[0]),Vector(self.slice_pts[1])], mtr_view, mtr_orientation, self.align_mode, self.switch_align, self.slice_angle)
				pt_b, pt_c = pts_align[1], pts_align[2]
				pt_d = pt_a + mug_normal(pt_a, pt_b, pt_c)
				if   self.align_mode in ['1','4']: pts_x, pts_y, pts_z = [pt_a,pt_c], [pt_a,pt_b], [pt_a,pt_d]
				elif self.align_mode in ['2','5']: pts_x, pts_y, pts_z = [pt_a,pt_b], [pt_a,pt_c], [pt_a,pt_d]
				elif self.align_mode in ['3','6']: pts_x, pts_y, pts_z = [pt_a,pt_d], [pt_a,pt_b], [pt_a,pt_c]

				vct_to_cam = vector_to_cam_normalized(s3d, pt_a)

				if abs((pts_x[1] - pt_a).normalized().dot(vct_to_cam)) < 0.999:
					line_x_co = screen_aligned_vector_line_2d(context, pts_x[0], pts_x[1])
					draw_lines_uc([line_x_co[0][:],line_x_co[1][:]], abt_p.orientation_axis_col_x, abt_p.axis_lns_width)

				if abs((pts_y[1] - pt_a).normalized().dot(vct_to_cam)) < 0.999:
					line_y_co = screen_aligned_vector_line_2d(context, pts_y[0], pts_y[1])
					draw_lines_uc([line_y_co[0][:],line_y_co[1][:]], abt_p.orientation_axis_col_y, abt_p.axis_lns_width)

				if abs((pts_z[1] - pt_a).normalized().dot(vct_to_cam)) < 0.999:
					line_z_co = screen_aligned_vector_line_2d(context, pts_z[0], pts_z[1])
					draw_lines_uc([line_z_co[0][:],line_z_co[1][:]], abt_p.orientation_axis_col_z, abt_p.axis_lns_width)	

				if self.bisect_offset != 0:
					if   self.align_mode in ['1','4']: pts_slc, vct_off = [pt_a,pt_b], -1 * (pt_d - pt_a).normalized() if self.bisect_flip_normal else (pt_d - pt_a).normalized()
					elif self.align_mode in ['2','5']: pts_slc, vct_off = [pt_a,pt_b], -1 * (pt_d - pt_a).normalized() if self.bisect_flip_normal else (pt_d - pt_a).normalized()
					elif self.align_mode in ['3','6']: pts_slc, vct_off = [pt_a,pt_b], -1 * (pt_d - pt_a).normalized() if self.bisect_flip_normal else (pt_d - pt_a).normalized()

					pts_slc = [pt + (vct_off * self.bisect_offset) for pt in pts_slc]

					vct_to_cam = vector_to_cam_normalized(s3d, pts_slc[0])
					if abs((pts_slc[1] - pts_slc[0]).normalized().dot(vct_to_cam)) < 0.999:
						line_slc_co = screen_aligned_vector_line_2d(context, pts_slc[0], pts_slc[1])
						draw_lines_uc([line_slc_co[0][:],line_slc_co[1][:]], abt_p.mrk_pts_color, abt_p.axis_lns_width)

		elif len(self.slice_pts)==3:
			tp_pts = slice_setup_triple_point(context, self.slice_pts, mtr_orientation, self.align_mode, self.switch_align, self.slice_angle)
			mtr_orientation_tp = get_transform_orientaions_from_mode(context, '5', tp_pts).inverted()
			#if self.align_mode != '0' and (self.slice_angle != 0 or self.switch_align):
			#	mtr_orientation_tp = rotated_align_orientation_triple_point(mtr_orientation_tp, self.align_mode, self.switch_align, self.slice_angle)
			pt_a = Vector(self.slice_pts[0])
			pt_b, pt_c, pt_d = pt_a + matrix_to_vector_row(mtr_orientation_tp, 0), pt_a + matrix_to_vector_row(mtr_orientation_tp, 1), pt_a + matrix_to_vector_row(mtr_orientation_tp, 2)
			pts_x, pts_y, pts_z = [pt_a,pt_b], [pt_a,pt_c], [pt_a,pt_d]
			vct_to_cam = vector_to_cam_normalized(s3d, pt_a)
			if abs((pts_x[1] - pt_a).normalized().dot(vct_to_cam)) < 0.999:
				line_x_co = screen_aligned_vector_line_2d(context, pts_x[0], pts_x[1])
				draw_lines_uc([line_x_co[0][:],line_x_co[1][:]], abt_p.orientation_axis_col_x, abt_p.axis_lns_width)
			if abs((pts_y[1] - pt_a).normalized().dot(vct_to_cam)) < 0.999:
				line_y_co = screen_aligned_vector_line_2d(context, pts_y[0], pts_y[1])
				draw_lines_uc([line_y_co[0][:],line_y_co[1][:]], abt_p.orientation_axis_col_y, abt_p.axis_lns_width)
			if abs((pts_z[1] - pt_a).normalized().dot(vct_to_cam)) < 0.999:
				line_z_co = screen_aligned_vector_line_2d(context, pts_z[0], pts_z[1])
				draw_lines_uc([line_z_co[0][:],line_z_co[1][:]], abt_p.orientation_axis_col_z, abt_p.axis_lns_width)				


#	TTTTTTTTTTTT   EEEEEEEEEEEE   XXXX    XXXX   TTTTTTTTTTTT
#	TTTTTTTTTTTT   EEEEE          XXXXXXXXXXXX   TTTTTTTTTTTT
#	    TTTT       EEEEEEEEEEEE     XXXXXXXX         TTTT    
#	    TTTT       EEEEEEEEEEEE     XXXXXXXX         TTTT    
#	    TTTT       EEEEE          XXXXXXXXXXXX       TTTT    
#	    TTTT       EEEEEEEEEEEE   XXXX    XXXX       TTTT    


	# Text UI  -------------------------------------------------------------------
	v3d_x = context.region.x
	v3d_y = context.region.y
	v3d_xs = context.region.width
	v3d_ys = context.region.height

#	Draw angles -----------------------------------

#	pt_cen = Vector((v3d_xs/2, v3d_ys/2))
#	draw_points_uc([pt_cen[:]], (1,1,0,1), 10)
#	pt_str = self.cursor_xy
#	rad = 5*(math.sqrt(abs((pt_str[0] - pt_cen[0]) + (pt_str[1] - pt_cen[1]))))
#	ang = 40
#	pts_num = 50
#
#	pts_circle = [Vector((rad,0))]
#	pt_sx, pt_sy = pts_circle[0][0], pts_circle[0][1]
#	for pt_n in range(ang):
#		pt_ang = (ang/pts_num)*pt_n
#		sang = math.sin(math.radians(pt_ang))
#		cang = math.cos(math.radians(pt_ang))
#		pts_circle.append(Vector((pt_sx * cang - pt_sy * sang, pt_sy * cang - pt_sx * sang)))
#
#	pts_circle_co = [(pt + pt_cen)[:] for pt in pts_circle]
#
#	draw_points_uc(pts_circle_co, (1,0,0,1), 10)



	spl = len(self.slice_pts)
	alm = self.align_mode
	txt_cb, txt_cs = abt_p.ui_txt_base_color, abt_p.ui_txt_shadow_color
	txt_cm, txt_cx, txt_cy, txt_cz = abt_p.mrk_pts_color, abt_p.orientation_axis_col_x, abt_p.orientation_axis_col_y, abt_p.orientation_axis_col_z
	shd_xy = (abt_p.ui_txt_shadow_x, abt_p.ui_txt_shadow_y)
	to_dict = {'0':'Global', '1':'Local', '2':'Cursor', '3':'Active', '4':'Slice', '5':'Gravity', '6':'Preset'}


	fnt = 0 # Create font here -------------------------------------------------------------------

	def draw_txt_row(fnt, txt, tps, tcb= txt_cb, tcs= txt_cs, shd_xy= shd_xy):
		blf.color(fnt, tcs[0], tcs[1], tcs[2], tcs[3])
		blf.position(fnt, tps[0] + shd_xy[0], tps[1] + shd_xy[1], 0)
		blf.draw(fnt, txt)
		blf.color(fnt, tcb[0], tcb[1], tcb[2], tcb[3])
		blf.position(fnt, tps[0], tps[1], 0)
		blf.draw(fnt, txt)		



	# Screen TextUI
	if abt_p.scr_ui_show: 
		scr_siz = abt_p.scr_ui_txt_size
		scr_px = math.floor(abt_p.scr_ui_txt_pos_x * (v3d_xs/100))
		scr_py = math.floor((100 - abt_p.scr_ui_txt_pos_y) * (v3d_ys/100))

		blf.size(fnt, int(25 * scr_siz), 70)

		draw_txt_row(fnt, 'Mode:', (scr_px, scr_py - (20 * scr_siz), 0))

		if spl == 0:
			draw_txt_row(fnt, '- x -', (scr_px + (75 * (pow(scr_siz,1.05))), scr_py - (20 * scr_siz), 0))

		if spl == 1:
			draw_txt_row(fnt, 'ONE PT', (scr_px + (75 * (pow(scr_siz,1.05))), scr_py - (20 * scr_siz), 0))
			if alm == '0':
				txt_opt_alm = 'SCREEN X' if self.switch_align else 'SCREEN Y'
				txt_opt_alm_col = txt_cx if self.switch_align else txt_cy
			elif alm in ['1','2','3']:
				txt_opt_alm = 'X AXIS' if alm == '1' else 'Y AXIS' if alm == '2' else 'Z AXIS'
				txt_opt_alm = txt_opt_alm + ' +90°' if self.switch_align else txt_opt_alm
				txt_opt_alm_col = txt_cx if alm == '1' else txt_cy if alm == '2' else txt_cz
			elif alm in ['4','5','6']:
				txt_opt_alm = 'X PLANE' if alm == '4' else 'Y PALNE' if alm == '5' else 'Z PLANE'
				txt_opt_alm_col = txt_cx if alm == '4' else txt_cy if alm == '5' else txt_cz
			draw_txt_row(fnt, txt_opt_alm, (scr_px + (170 * (pow(scr_siz,1.05))), scr_py - (20 * scr_siz), 0), txt_opt_alm_col)

		if spl == 2:
			draw_txt_row(fnt, 'TWO PTS', (scr_px + (75 * (pow(scr_siz,1.05))), scr_py - (20 * scr_siz), 0))
			if alm == '0':
				txt_tpt_alm = 'SCREEN'
				txt_tpt_alm_col = txt_cm
			else:
				txt_tpt_alm = 'X AXIS' if (alm in ['1','4']) else 'Y AXIS' if (alm in ['2','5']) else 'Z AXIS'
				txt_tpt_alm = txt_tpt_alm + ' +90°' if self.switch_align else txt_tpt_alm
				txt_tpt_alm_col = txt_cx if (alm in ['1','4']) else txt_cy if (alm in ['2','5']) else txt_cz
			draw_txt_row(fnt, txt_tpt_alm, (scr_px + (190 * (pow(scr_siz,1.05))), scr_py - (20 * scr_siz), 0), txt_tpt_alm_col)

		if spl == 3:
			draw_txt_row(fnt, 'THREE PTS', (scr_px + (75 * (pow(scr_siz,1.05))), scr_py - (20 * scr_siz), 0))
			if alm == '0':
				txt_tpt_alm = 'PLANE'
				txt_tpt_alm_col = txt_cm
			else:
				txt_tpt_alm = 'X AXIS' if (alm in ['1','4']) else 'Y AXIS' if (alm in ['2','5']) else 'Z AXIS'
				txt_tpt_alm = txt_tpt_alm + ' +90°' if self.switch_align else txt_tpt_alm
				txt_tpt_alm_col = txt_cx if (alm in ['1','4']) else txt_cy if (alm in ['2','5']) else txt_cz
			draw_txt_row(fnt, txt_tpt_alm, (scr_px + (210 * (pow(scr_siz,1.05))), scr_py - (20 * scr_siz), 0), txt_tpt_alm_col)


		draw_txt_row(fnt, 'Orientation: ' + to_dict.get(self.orientation_mode) , (scr_px, scr_py - (50 * scr_siz), 0))

		draw_txt_row(fnt, '->|', (scr_px - (40 * (pow(scr_siz,1.05))), scr_py - ((110 if self.switch_input else 80) * scr_siz), 0))

		draw_txt_row(fnt, 'Angle: ' +  self.am_angle + ('_' if not self.switch_input else '') + '°', (scr_px, scr_py - (80 * scr_siz), 0))

		draw_txt_row(fnt, 'Offset: ' + self.am_offset + ('_' if self.switch_input else '') + 'm', (scr_px, scr_py - (110 * scr_siz), 0))

		if abt_p.slc_obs_show:
			draw_txt_row(fnt, 'Objects to slice:', (scr_px, scr_py - (150*scr_siz), 0))
			for enm,obn in enumerate(self.obs_lst_slice):
				draw_txt_row(fnt, obn, (scr_px + 20, scr_py - ((180 + (30*enm))*scr_siz), 0))

		if abt_p.snp_obs_show:
			txt_pos = 200 + (30*len(self.obs_lst_slice))
			draw_txt_row(fnt, 'Objects to snap:', (scr_px, scr_py - (txt_pos * scr_siz), 0))
			for enm,obn in enumerate(self.obs_lst_main):
				txt_pos = txt_pos + 30
				draw_txt_row(fnt, obn, (scr_px + 20, scr_py - (txt_pos * scr_siz), 0))

			if self.obs_lst_add != []:
				txt_pos = txt_pos + 10
				for enm,obn in enumerate(self.obs_lst_add):
					txt_pos = txt_pos + 30
					draw_txt_row(fnt, obn, (scr_px + 20, scr_py - (txt_pos * scr_siz), 0))

	# Cursor Text UI
	if abt_p.crs_ui_show: 
		crs_siz = abt_p.crs_ui_txt_size
		blf.size(fnt, int(25 * crs_siz), 70)

		crs_px = self.cursor_xy[0] + remap_range(0, 1, 20, -150, self.cursor_xy[0]/v3d_xs)
		crs_py = self.cursor_xy[1] - 40

		if spl == 0:
			draw_txt_row(fnt, '-X-', (crs_px, crs_py, 0))		
		if spl == 1:
			draw_txt_row(fnt, '1P', (crs_px, crs_py, 0))
			if alm == '0':
				txt_opt_alm = 'SC-X' if self.switch_align else 'SC-Y'
				txt_opt_alm_col = txt_cx if self.switch_align else txt_cy
			elif alm in ['1','2','3']:
				txt_opt_alm = 'AX-X' if alm == '1' else 'AX-Y' if alm == '2' else 'AX-Z'
				txt_opt_alm = txt_opt_alm + ' +90°' if self.switch_align else txt_opt_alm
				txt_opt_alm_col = txt_cx if alm == '1' else txt_cy if alm == '2' else txt_cz
			elif alm in ['4','5','6']:
				txt_opt_alm = 'PL-X' if alm == '4' else 'PL-Y' if alm == '5' else 'PL-Z'
				txt_opt_alm_col = txt_cx if alm == '4' else txt_cy if alm == '5' else txt_cz
			draw_txt_row(fnt, txt_opt_alm, (crs_px + (40 * (pow(crs_siz,1.05))), crs_py, 0), txt_opt_alm_col)
		if spl == 2:
			draw_txt_row(fnt, '2P', (crs_px, crs_py, 0))
			if alm == '0':
				txt_tpt_alm = 'SC'
				txt_tpt_alm_col = txt_cm
			else:
				txt_tpt_alm = 'AX-X' if (alm in ['1','4']) else 'AX-Y' if (alm in ['2','5']) else 'AX-Z'
				txt_tpt_alm = txt_tpt_alm + ' +90°' if self.switch_align else txt_tpt_alm
				txt_tpt_alm_col = txt_cx if (alm in ['1','4']) else txt_cy if (alm in ['2','5']) else txt_cz
			draw_txt_row(fnt, txt_tpt_alm, (crs_px + (40 * (pow(crs_siz,1.05))), crs_py, 0), txt_tpt_alm_col)
		if spl == 3:
			draw_txt_row(fnt, '3P', (crs_px, crs_py, 0))
			if alm == '0':
				txt_tpt_alm = 'PL'
				txt_tpt_alm_col = txt_cm
			else:
				txt_tpt_alm = 'AX-X' if (alm in ['1','4']) else 'AX-Y' if (alm in ['2','5']) else 'AX-Z'
				txt_tpt_alm = txt_tpt_alm + ' +90°' if self.switch_align else txt_tpt_alm
				txt_tpt_alm_col = txt_cx if (alm in ['1','4']) else txt_cy if (alm in ['2','5']) else txt_cz
			draw_txt_row(fnt, txt_tpt_alm, (crs_px + (40 * (pow(crs_siz,1.05))), crs_py, 0), txt_tpt_alm_col)

		draw_txt_row(fnt, 'AO: ' +  to_dict.get(self.orientation_mode), (crs_px, crs_py - (25 * crs_siz), 0))

		draw_txt_row(fnt, '->|', (crs_px - (40 * (pow(crs_siz,1.05))), crs_py - ((75 if self.switch_input else 50) * crs_siz), 0))

		draw_txt_row(fnt, 'AN: ' +  self.am_angle + ('_' if not self.switch_input else '') + '°', (crs_px, crs_py - (50 * crs_siz), 0))

		draw_txt_row(fnt, 'OF: ' + self.am_offset + ('_' if self.switch_input else '') + 'm', (crs_px, crs_py - (75 * crs_siz), 0))




class ABT_PT_Panel(bpy.types.Panel):
	bl_label = 'ABT'
	bl_idname = 'ABT_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self,context):
		abt = context.scene.abt_props

		angle_rotate = 'fgt.abt_rotate_angle_ninety'
		angle_clear = 'fgt.sot_clear_angle_value'		

		layout = self.layout
		col = layout.column(align=True)

		col.operator('fgt.abt_bisect_tool', text= 'Start ABT', icon= 'EDITMODE_HLT')

		col.separator(factor=0.8) # -----------------------------------------------

		row = col.row(align=True)
		row.scale_y = 0.7 if abt.expand_opt else 1
		row.prop(abt, 'expand_opt', text= 'Collapse Options' if abt.expand_opt else 'Expand Options', icon= 'NONE' if abt.expand_opt else 'OPTIONS', toggle= True)

		if abt.expand_opt:
			col.separator(factor=0.3) # -----------------------------------------------
			row = col.row(align=True)
			row.scale_y = 0.6			
			row.label(text= 'Show toggles: ')
			row = col.row(align=True)
			row.scale_y = 0.9
			row.prop(abt, 'mid_pts_enabled', text= 'Midpoints', icon= 'SNAP_MIDPOINT', toggle= True)
			row.prop(abt, 'hid_eds_enabled', text= 'Hid Edges', icon= 'MOD_DECIM', toggle= True)
			row = col.row(align=True)
			row.scale_y = 0.9
			row.prop(abt, 'orientation_axis_enabled', text= 'Axis', icon= 'ORIENTATION_LOCAL', toggle= True)
			row.prop(abt, 'slice_plane_grid_enabled', text= 'Grid', icon= 'GRID', toggle= True)

			col.separator(factor=0.6) # -----------------------------------------------
			row = col.row(align=True)
			row.scale_y = 0.6	
			row.label(text= 'Initial state:')
			row = col.row(align=True)
			row.scale_y = 0.9
			row.prop(abt, 'slice_angle_reset', text= 'Reset Angle', toggle= True)
			row.prop(abt, 'slice_offset_reset', text= 'Reset Offset', toggle= True)			
			row = col.row(align=True)
			row.scale_y = 0.9
			row.label(text= 'Default TO: ')
			row.prop(abt, 'orientation_mode_default', text= '')

		col.separator(factor=0.2) # -----------------------------------------------

		row = col.row(align=True)
		row.scale_y = 0.7 if abt.expand_qas else 1
		row.prop(abt, 'expand_qas', text= 'Collapse Quick Angles' if abt.expand_qas else 'Expand Quick Angles', icon= 'NONE' if abt.expand_qas else 'GIZMO', toggle= True)

		if abt.expand_qas:
			col.separator(factor=0.3) # -----------------------------------------------

			qas = [('slice_qa_a', 'A', abt.slice_qa_a), ('slice_qa_b', 'B', abt.slice_qa_b), ('slice_qa_c', 'C', abt.slice_qa_c), ('slice_qa_d', 'D',abt.slice_qa_d),
					('slice_qa_e', 'E', abt.slice_qa_e), ('slice_qa_f', 'F', abt.slice_qa_f), ('slice_qa_g', 'G', abt.slice_qa_g), ('slice_qa_i', 'I', abt.slice_qa_i)]

			for qa in qas:
				row = col.row(align=True)
				row.scale_y = 0.8
				row.operator(angle_rotate, icon='LOOP_BACK', text='')						.ran = qa[1] + '-'
				row.operator(angle_rotate, icon='LOOP_FORWARDS',     text='')						.ran = qa[1] + '+'
				row.prop(abt, qa[0], text= qa[1] + ' ')
				row.operator(angle_clear, icon='X' if qa[2] != 0 else 'DOT', text='')			.can = qa[1]		

		col.separator(factor=0.2) # -----------------------------------------------

		row = col.row(align=True)
		row.scale_y = 0.7 if abt.expand_tos else 1
		row.prop(abt, 'expand_tos', text= 'Collapse Orientations' if abt.expand_tos else 'Expand Orientations', icon= 'NONE' if abt.expand_tos else 'MOD_NORMALEDIT', toggle= True)

		if abt.expand_tos:
			col.separator(factor=0.3) # -----------------------------------------------
			row = col.row(align=True)
			row.operator('fgt.abt_empty', text='Get Cursor', icon='PIVOT_CURSOR')
			row.operator('fgt.abt_empty', text='Get Active', icon='PIVOT_ACTIVE')

			if abt_cot_pr_val != {}:
				pass


class ABT_MT_PIE_Select_QA(bpy.types.Menu):
	bl_idname = 'ABT_MT_PIE_Select_QA'
	bl_label = 'Quick Angle Selection'


	def draw(self, context):
		abt = context.scene.abt_props

		layout = self.layout
		pie = layout.menu_pie()

		pie.operator('fgt.abt_set_quick_angle', text= 'G     ' + str(round(math.degrees(abt.slice_qa_g),4)) ).sqa_id = 6	#Lef 
		pie.operator('fgt.abt_set_quick_angle', text= 'C     ' + str(round(math.degrees(abt.slice_qa_c),4)) ).sqa_id = 2	#Right
		pie.operator('fgt.abt_set_quick_angle', text= 'E     ' + str(round(math.degrees(abt.slice_qa_e),4)) ).sqa_id = 4	#Bottom
		pie.operator('fgt.abt_set_quick_angle', text= 'A     ' + str(round(math.degrees(abt.slice_qa_a),4)) ).sqa_id = 0	#Top
		pie.operator('fgt.abt_set_quick_angle', text= 'I     ' + str(round(math.degrees(abt.slice_qa_i),4)) ).sqa_id = 7	#Left-Top
		pie.operator('fgt.abt_set_quick_angle', text= 'B     ' + str(round(math.degrees(abt.slice_qa_b),4)) ).sqa_id = 1	#Right-Top
		pie.operator('fgt.abt_set_quick_angle', text= 'F     ' + str(round(math.degrees(abt.slice_qa_f),4)) ).sqa_id = 5	#Left_Bottom
		pie.operator('fgt.abt_set_quick_angle', text= 'D     ' + str(round(math.degrees(abt.slice_qa_d),4)) ).sqa_id = 3	#Right-Bottom


class ABT_OT_Set_Quick_Angle(bpy.types.Operator):
	bl_label = 'ABT_OT_Set_Quick_Angle'
	bl_idname = 'fgt.abt_set_quick_angle'
	bl_description = 'Set quick angle selected from PIE menu'

	sqa_id:	bpr.IntProperty(name='Selected Quick Angle ID', default= 0, min= 0, max= 7, description='ID of quick angle to set')

	def execute(self, context):
		abt = context.scene.abt_props

		abt.slice_angle_set = True
		abt.slice_qa_id = self.sqa_id

		return {'FINISHED'}

class ABT_OT_Rotate_Angle_Ninety(bpy.types.Operator):
	bl_idname = 'fgt.abt_rotate_angle_ninety'
	bl_label = 'ABT_OT_Rotate_Angle_Ninety'
	bl_description = 'Increase/decrease angle by 90 degrees'

	ran: bpr.StringProperty(name = '', default = '')

	def execute(self,context):
		abt = context.scene.abt_props

		if   self.ran[0] == 'A': 
			abt.slice_qa_a = abt.slice_qa_a + 1.5707963267949 if self.ran[1] == '+' else abt.slice_qa_a - 1.5707963267949
			if abs(math.degrees(abt.slice_qa_a)) < 0.0001: abt.slice_qa_a = 0
		elif self.ran[0] == 'B': 
			abt.slice_qa_b = abt.slice_qa_b + 1.5707963267949 if self.ran[1] == '+' else abt.slice_qa_b - 1.5707963267949
			if abs(math.degrees(abt.slice_qa_b)) < 0.0001: abt.slice_qa_b = 0
		elif self.ran[0] == 'C': 
			abt.slice_qa_c = abt.slice_qa_c + 1.5707963267949 if self.ran[1] == '+' else abt.slice_qa_c - 1.5707963267949
			if abs(math.degrees(abt.slice_qa_c)) < 0.0001: abt.slice_qa_c = 0
		elif self.ran[0] == 'D': 
			abt.slice_qa_d = abt.slice_qa_d + 1.5707963267949 if self.ran[1] == '+' else abt.slice_qa_d - 1.5707963267949
			if abs(math.degrees(abt.slice_qa_d)) < 0.0001: abt.slice_qa_d = 0
		elif self.ran[0] == 'E': 
			abt.slice_qa_e = abt.slice_qa_e + 1.5707963267949 if self.ran[1] == '+' else abt.slice_qa_e - 1.5707963267949
			if abs(math.degrees(abt.slice_qa_e)) < 0.0001: abt.slice_qa_e = 0
		elif self.ran[0] == 'F': 
			abt.slice_qa_f = abt.slice_qa_f + 1.5707963267949 if self.ran[1] == '+' else abt.slice_qa_f - 1.5707963267949
			if abs(math.degrees(abt.slice_qa_f)) < 0.0001: abt.slice_qa_f = 0
		elif self.ran[0] == 'G': 
			abt.slice_qa_g = abt.slice_qa_g + 1.5707963267949 if self.ran[1] == '+' else abt.slice_qa_g - 1.5707963267949
			if abs(math.degrees(abt.slice_qa_g)) < 0.0001: abt.slice_qa_g = 0
		elif self.ran[0] == 'I': 
			abt.slice_qa_i = abt.slice_qa_i + 1.5707963267949 if self.ran[1] == '+' else abt.slice_qa_i - 1.5707963267949
			if abs(math.degrees(abt.slice_qa_i)) < 0.0001: abt.slice_qa_i = 0

		return {'FINISHED'}

class ABT_OT_Clear_Angle_Value(bpy.types.Operator):
	bl_idname = 'fgt.sot_clear_angle_value'
	bl_label = ' ABT_OT_Clear_Angle_Value'
	bl_description = 'Reset angle value to zero'

	can: bpr.StringProperty(name = '', default = '')

	def execute(self,context):
		abt = context.scene.abt_props

		if   self.can == 'A': abt.slice_qa_a = 0
		elif self.can == 'B': abt.slice_qa_b = 0
		elif self.can == 'C': abt.slice_qa_c = 0
		elif self.can == 'D': abt.slice_qa_d = 0
		elif self.can == 'E': abt.slice_qa_e = 0
		elif self.can == 'F': abt.slice_qa_f = 0
		elif self.can == 'G': abt.slice_qa_g = 0
		elif self.can == 'I': abt.slice_qa_i = 0

		return {'FINISHED'}

class ABT_MT_PIE_Select_TO(bpy.types.Menu):
	bl_idname = 'ABT_MT_PIE_Select_TO'
	bl_label = 'TO Selection'

	def draw(self, context):
		abt = context.scene.abt_props

		layout = self.layout
		pie = layout.menu_pie()

		#row.enabled = True if pr_values != {} else False

		pie.operator('fgt.abt_set_align_orientation', text= 'Local').sao_id = 1		#Lef 
		pie.operator('fgt.abt_set_align_orientation', text= 'Slice').sao_id = 4		#Right
		pco = pie.row()
		pco.label(text= '')	#Bottom
		pie.operator('fgt.abt_set_align_orientation', text= 'Preset').sao_id = 6	#Top
		pie.operator('fgt.abt_set_align_orientation', text= 'Global').sao_id = 0	#Left-Top
		pie.operator('fgt.abt_set_align_orientation', text= 'Active').sao_id = 3	#Right-Top
		pie.operator('fgt.abt_set_align_orientation', text= 'Cursor').sao_id = 2	#Left_Bottom
		pie.operator('fgt.abt_set_align_orientation', text= 'Gravity').sao_id = 5	#Right-Bottom

class ABT_OT_Set_Align_Orientation(bpy.types.Operator):
	bl_label = 'ABT_OT_Set_Align_Orientation'
	bl_idname = 'fgt.abt_set_align_orientation'
	bl_description = 'Set orientation used for aligning slice'

	sao_id:	bpr.IntProperty(name='Selected Align Orientation ID', default= 0, min= 0, max= 7, description='ID of align orientation')

	def execute(self, context):
		abt = context.scene.abt_props
		abt.orientation_set = True
		abt.orientation_set_id = self.sao_id

		return {'FINISHED'}

class ABT_MT_PIE_View_Align(bpy.types.Menu):
	bl_idname = 'ABT_MT_PIE_View_Align'
	bl_label = 'View Align'

	def draw(self, context):
		abt = context.scene.abt_props

		layout = self.layout
		pie = layout.menu_pie()

		pie.operator('fgt.abt_view_align', text= 'Align View X-').alg_side = 1	#Lef 
		pie.operator('fgt.abt_view_align', text= 'Align View X+').alg_side = 0	#Right
		pie.operator('fgt.abt_view_align', text= 'Align View Y-').alg_side = 3	#Bottom
		pie.operator('fgt.abt_view_align', text= 'Align View Y+').alg_side = 2	#Top
		pie.operator('fgt.abt_clear_view_recover', text= 'Clear Recover')	#Left-Top
		pie.operator('fgt.abt_view_align', text= 'Align View Z+').alg_side = 4	#Right-Top
		pie.operator('fgt.abt_view_align', text= 'Align View Z-').alg_side = 5	#Left_Bottom
		pie.operator('fgt.abt_view_recover', text= 'Recover View')	#Right-Bottom

class ABT_OT_View_Align(bpy.types.Operator):
	bl_label = 'ABT_OT_View_Align'
	bl_idname = 'fgt.abt_view_align'
	bl_description = 'Align view to slice'

	alg_side:	bpr.IntProperty(name='Selected Align Orientation ID', default= 0, min= 0, max= 7, description='ID of align orientation')

	@classmethod
	def poll(cls, context):
		return context.scene.abt_props.align_view_allowed

	def execute(self, context):
		abt = context.scene.abt_props
		abt.align_view_set = True
		abt.align_view_set_id = self.alg_side

		return {'FINISHED'}

class ABT_OT_View_Recover(bpy.types.Operator):
	bl_label = 'ABT_OT_View_Recover'
	bl_idname = 'fgt.abt_view_recover'
	bl_description = 'Recover view to slice after align'

	@classmethod
	def poll(cls, context):
		return context.scene.abt_props.view_rec

	def execute(self, context):
		abt = context.scene.abt_props
		abt.view_rec = False
		mtr_view = Matrix.Identity()
		mtr_view.col[0] = abt.view_rec_mtr_col_a
		mtr_view.col[1] = abt.view_rec_mtr_col_b
		mtr_view.col[2] = abt.view_rec_mtr_col_c
		mtr_view.col[3] = abt.view_rec_mtr_col_d
		context.space_data.region_3d.view_matrix = mtr_view
		return {'FINISHED'}

class ABT_OT_Clear_View_Recover(bpy.types.Operator):
	bl_label = 'ABT_OT_Clear_View_Recover'
	bl_idname = 'fgt.abt_clear_view_recover'
	bl_description = 'Clear view recovery data'

	@classmethod
	def poll(cls, context):
		return context.scene.abt_props.view_rec

	def execute(self, context):
		abt = context.scene.abt_props
		abt.view_rec = False
		abt.view_rec_mtr_col_a = Vector((1,0,0,0))
		abt.view_rec_mtr_col_b = Vector((0,1,0,0))
		abt.view_rec_mtr_col_c = Vector((0,0,1,0))
		abt.view_rec_mtr_col_d = Vector((0,0,0,1))
		return {'FINISHED'}


class ABT_OT_Empty(bpy.types.Operator):
	bl_label = 'ABT_OT_Empty'
	bl_idname = 'fgt.abt_empty'
	bl_description = 'Print something'

	txt_to_p: bpr.StringProperty(name= 'Text_To_Print', default='>> X <<')

	def execute(self,context):
		print(self.txt_to_p)
		return {'FINISHED'}

class ABT_OT_Bisect_Tool(bpy.types.Operator):
	bl_label = 'ABT_OT_Bisect_Tool'
	bl_idname = 'fgt.abt_bisect_tool'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Advanced bisect tool'

	bisect_offset:		bpr.FloatProperty(name= 'Offset Slice', description= 'Offset slice on normal diection', unit='LENGTH')
	bisect_clear_inner:	bpr.BoolProperty(name= 'Clear Inner', description='Remove mesh behind slice plane')
	bisect_clear_outer:	bpr.BoolProperty(name= 'Clear Inner', description='Remove mesh in front of slice plane')
	bisect_use_fill:	bpr.BoolProperty(name= 'Fill Slice',  description='Fill sliced mesh')
	bisect_flip_normal:	bpr.BoolProperty(name= 'Flip Normal',  description='Flip direction of bisect normal')

	orientation_mode:	bpr.EnumProperty(name= 'Orientation Mode',
		items= [('0','Global','Global Orientaion will be used in aligned mode',0),
				('1','Local','Active object Local Orientaion will be used in aligned mode',1),
				('2','Cursor','3D Cursor Orientaion will be used in aligned mode',2),
				('3','Active','Active mesh element Normal Orientaion will be used in aligned mode, if no Active element Local used instead',3),
				('4','Slice','Weirdo',4),
				('5','Gravity','Weirdo',5),
				('6','Preset','Selected in presets Orientaion will be used in aligned mode, if no preset World used instead',6)],
				default= '0')

	align_mode:			bpr.EnumProperty(name= 'Axis Aligned',
		items= [('0','None','Axis Aligned Slice disabled',0),
				('1','X Axis','Slice aligned to X axis',1),
				('2','Y Axis','Slice aligned to Y axis',2),
				('3','Z Axis','Slice aligned to Z axis',3),
				('4','X Plane','Slice aligned to YZ axis',4),
				('5','Y Plane','Slice aligned to XZ axis',5),
				('6','Z Plane','Slice aligned to XY axis',6)],
				default= '0')

	slice_angle:		bpr.FloatProperty(name='Slice Angle', description='Slice angle for Axis Aligned Mode', unit='ROTATION')
	slice_angle_flip:	bpr.BoolProperty(name='Angle Flip', description='Flip angle to opposite, usefull for fast angle mirorring (worl like x -1)')
	switch_align:		bpr.BoolProperty(name='Angle +90', description='Switch align mode to perpendicular (work like +90 degrees)')

	show_hidden:		bpr.BoolProperty(name='Show Hidden', description='Show hidden mesh points', options={'HIDDEN'})

	@classmethod
	def poll(cls, context):
		return context.space_data.type == 'VIEW_3D' and context.mode == 'EDIT_MESH'

	def __init__(self):
		self.cursor_xy = Vector((0,0)) # Cursor coordinates hub for various features that can't read event mouse
		self.mtr_view = None # View matrix preserve for execute
		self.check_mtr_view = False
		self.mtr_execute_orientations = list() #


		self.obs_lst_slice = []
		self.obs_lst_main = []
		self.obs_lst_add = []

		self.switch_input = False

		self.set_angle = False
		self.set_angle_cursor_start = Vector((0,0))

		self.snap_pts = np.empty((0,3), dtype=np.float32)  # Snap points available for marking
		self.snap_pts_res = [] # Snap points reserve for recovering when Ctrl+Z
		self.slice_pts = []  # Marked snap points

		self.vtc_pts_draw = np.empty((0,3), dtype=np.float32) # Numpy array of mesh vertices coordinates to draw
		self.mid_pts_draw = np.empty((0,3), dtype=np.float32) # Numpy array of edges midpoints coordinates to draw
		self.hid_eds_draw = np.empty((0,3), dtype=np.float32) # Numpy array of hidden edges start/end coordinates to draw
		self.slc_lines_draw = np.empty((0,3), dtype=np.float32)
		self.slc_points_draw = np.empty((0,3), dtype=np.float32)
		self.draw_slice = False

		angle_deg = str(round(math.degrees(self.slice_angle),4)) # Convertion of radians to degrees + rounded to string
		offset_val = str(round(self.bisect_offset,5))

		self.am_angle = angle_deg if angle_deg.split('.')[1] != '0' else angle_deg.split('.')[0]
		self.am_angle_min = True if not angle_deg.find('-') else False
		self.am_angle_dot = True if angle_deg.split('.')[1] != '0' else False
		self.am_offset = offset_val if offset_val.split('.')[1] != '0' else offset_val.split('.')[0]
		self.am_offset_min = True if not offset_val.find('-') else False
		self.am_offset_dot = True if offset_val.split('.')[1] != '0' else False		
		self.numbers_dic = {'ONE':'1','TWO':'2','THREE':'3','FOUR':'4','FIVE':'5','SIX':'6','SEVEN':'7','EIGHT':'8','NINE':'9',
							'NUMPAD_1':'1','NUMPAD_2':'2','NUMPAD_3':'3','NUMPAD_4':'4','NUMPAD_5':'5','NUMPAD_6':'6','NUMPAD_7':'7','NUMPAD_8':'8','NUMPAD_9':'9'}

	def invoke(self, context, event):
		if context.space_data.type == 'VIEW_3D':
			#print(context.space_data)
			# DO ONCE STUFF ----------------------------------------------------
			abt = context.scene.abt_props
			if abt.slice_angle_reset: 
				self.am_angle = '-0' if self.am_angle[0] == '-' else '0'
				self.slice_angle = 0
			if abt.slice_offset_reset: 
				self.am_offset = '-0' if self.am_offset[0] == '-' else '0'
				self.bisect_offset = 0			
			if abt.orientation_mode_default != '0':
				self.orientation_mode = str(int(abt.orientation_mode_default)-1)

			# SAVE - If active objects in edit mode was deselected in outliner
			self.obs_lst_main = [ob.name for ob in bpy.context.view_layer.objects if (ob.mode == 'EDIT' and ob.type == 'MESH')]

			for obn in self.obs_lst_main:
				bpy.context.view_layer.objects.active = bpy.data.objects[obn]
				bmd = bmesh.from_edit_mesh(context.edit_object.data)

				for edg in bmd.edges:
					if edg.select:
						self.obs_lst_slice.append(obn)
						break

			if self.obs_lst_slice == []:
				self.report({'WARNING'}, "There is nothing to slice!!! Select some edges or polygons first.")
				return {'CANCELLED'}


			self.reset_points(context)

			# DRAW HANDLERS ---------------------------------------------------

			args = (self,context)
			self.draw_handler_3d = bpy.types.SpaceView3D.draw_handler_add(draw_3d_stuff, args, 'WINDOW', 'POST_VIEW')  # 
			self.draw_handler_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d_stuff, args, 'WINDOW', 'POST_PIXEL')			
			context.window_manager.modal_handler_add(self)

			context.region.tag_redraw()
			return {'RUNNING_MODAL'}
		else:
			self.report({'WARNING'}, "Active space must be a View3d")
			return {'CANCELLED'}

	def modal(self, context, event):
		# CHECK - If context stil exist
		try: 
			bpy.context.space_data.type
		except:
			remove_draw_handlers(self)
			return {'CANCELLED'}					

		# CHECK - Canceling on exit mesh edit
		if context.space_data.type != 'VIEW_3D' or context.mode != 'EDIT_MESH':
			remove_draw_handlers(self)
			context.region.tag_redraw()
			return {'CANCELLED'}

		abt = context.scene.abt_props


		def remove_draw_handlers(self):
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler_3d, 'WINDOW')
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler_2d, 'WINDOW')


		# CHECK - Set new slice angle if quick angle was selected
		if abt.slice_angle_set:
			abt.slice_angle_set = False
			qas = [abt.slice_qa_a, abt.slice_qa_b, abt.slice_qa_c, abt.slice_qa_d,
					abt.slice_qa_e, abt.slice_qa_f, abt.slice_qa_g, abt.slice_qa_i]
			angle_deg = str(round(math.degrees(qas[abt.slice_qa_id]),4))
			self.am_angle = angle_deg if angle_deg.split('.')[1] != '0' else angle_deg.split('.')[0]
			self.am_angle_min = True if not angle_deg.find('-') else False
			self.am_angle_dot = True if angle_deg.split('.')[1] != '0' else False
			self.slice_angle = math.radians(float(self.am_angle))
			self.reset_slice_vizualizetion(context)
			context.region.tag_redraw()

		# CHECK - Set new align orientation
		if abt.orientation_set:
			abt.orientation_set = False
			oms = self.orientation_mode
			self.orientation_mode = str(abt.orientation_set_id)
			print('Orientation Mode Changed from ', oms, ' to >>> ', self.orientation_mode)
			self.reset_slice_vizualizetion(context)
			context.region.tag_redraw()

		# Check if it need to update slice draw data
		if self.check_mtr_view:
			s3d = context.space_data.region_3d
			mtr_view = s3d.view_matrix
			if s3d.view_perspective == 'PERSP' or s3d.view_perspective == 'CAMERA':
				if mtr_view != self.mtr_view:
					self.reset_slice_vizualizetion(context)
					context.region.tag_redraw()
					#print('REDRAW PERSPECTIVE')
			else:
				if mtr_view.to_3x3() !=  self.mtr_view.to_3x3():
					self.reset_slice_vizualizetion(context)
					context.region.tag_redraw()
					#print('REDRAW ORTHOGONAL')

		# Check if aligning view is allowed
		if len(self.slice_pts) != 0:
			if len(self.slice_pts) == 1:
				abt.align_view_allowed = True if self.align_mode != '0' and self.orientation_mode not in ['4','5'] else False
			elif len(self.slice_pts) == 2:
				abt.align_view_allowed = True if self.align_mode != '0' and self.orientation_mode != '4' else False
			else:
				abt.align_view_allowed = True
		else:
			abt.align_view_allowed = False

		# Check if view was aligned
		if abt.align_view_set:
			if not abt.view_rec:
				abt.view_rec = True
				mtr_view = context.space_data.region_3d.view_matrix
				abt.view_rec_mtr_col_a = mtr_view.col[0]
				abt.view_rec_mtr_col_b = mtr_view.col[1]
				abt.view_rec_mtr_col_c = mtr_view.col[2]
				abt.view_rec_mtr_col_d = mtr_view.col[3]
			abt.align_view_set = False
			align_view_to_slice(self, context)


		# Canceling manually
		if event.type in {'RIGHTMOUSE', 'ESC'}:
			remove_draw_handlers(self)
			context.region.tag_redraw()
			return {'CANCELLED'}


		# Check if align view is allowed
		if len(self.slice_pts) != 0:
			if len(self.slice_pts) == 1:
				abt.align_view_allowed = True if self.align_mode != '0' and self.orientation_mode not in ['4','5'] else False
			elif len(self.slice_pts) == 2:
				abt.align_view_allowed = True if self.align_mode != '0' and self.orientation_mode != '4' else False
			else:
				abt.align_view_allowed = True
		else:
			abt.align_view_allowed = False


		self.cursor_xy = Vector((event.mouse_region_x, event.mouse_region_y))

		if event.type == 'L' and event.value == 'PRESS':
			pass

		# Append object points
		elif event.type == 'A' and event.value == 'PRESS':
			print('Append object points')
			self.ray_cast_add_remove_object(context, 'ADD')
			self.reset_points(context)

		# Detach object points
		elif event.type == 'D' and event.value == 'PRESS':
			print('Detach object points')
			self.ray_cast_add_remove_object(context, 'REM')
			self.reset_points(context)


		# Slice points selection
		elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':

			crs_x = event.mouse_region_x
			crs_y = event.mouse_region_y
			v3d_x = context.region.width
			v3d_y = context.region.height

			if crs_x <= 1 or crs_x >= v3d_x or crs_y <= 1 or crs_y >= v3d_y: # Canceled if LMB out of 3D area
				remove_draw_handlers(self)
				context.region.tag_redraw()
				return {'CANCELLED'}

			pt_co, pt_id = self.slise_point_pick(context, event)

			if pt_id != None:
				if len(self.slice_pts) >= 3:
					self.report({'INFO'}, 'You already have 3 points!!!')
				else:
					print(vector_convert_to_matrix_inverted(context.space_data.region_3d.view_matrix))
					self.slice_pts.append(pt_co)
					self.snap_pts = np.delete(self.snap_pts, [pt_id*3,pt_id*3+1,pt_id*3+2])
					self.snap_pts = np.reshape(self.snap_pts, (self.snap_pts.size//3,3))
					self.snap_pts_res.append(pt_co)
					self.reset_slice_vizualizetion(context)

					context.region.tag_redraw()
					self.report({'INFO'}, 'Point ' + str(len(self.slice_pts)) +  ' added.')

		# Undo slice points selection
		elif event.ctrl and event.type == 'Z' and event.value == 'PRESS':
			if len(self.slice_pts):
				pop_id = len(self.slice_pts)-1
				self.slice_pts.pop(pop_id)
				self.snap_pts = np.append(self.snap_pts, self.snap_pts_res[pop_id])
				self.snap_pts = np.reshape(self.snap_pts, (self.snap_pts.size//3,3))
				self.snap_pts_res.pop(pop_id)
				self.reset_slice_vizualizetion(context)

				context.region.tag_redraw()
				self.report({'INFO'}, 'Point ' + str(pop_id + 1) +  ' removerd.')
			else:
				self.report({'INFO'}, 'No points to remove!!!')

		# Transform orientation selection
		elif event.type == 'T' and event.value == 'PRESS':
			#self.orientation_mode = str(int(self.orientation_mode) + 1) if int(self.orientation_mode) + 1 <= 4 else '0'
			bpy.ops.wm.call_menu_pie(name= 'ABT_MT_PIE_Select_TO')

			self.reset_slice_vizualizetion(context)

			context.region.tag_redraw()
			print(self.orientation_mode)

		# XYZ axis aligned mode
		elif not event.ctrl and not event.shift and event.type in {'X','C','Z'} and event.value == 'PRESS':
			axis_id = ['1','2','3'][['X','C','Z'].index(event.type)]
			self.align_mode = axis_id if self.align_mode != axis_id else '0'
			self.reset_slice_vizualizetion(context)

			context.region.tag_redraw()
			print(self.align_mode)

		# XYZ plane aligned mode	
		elif not event.ctrl and event.shift and event.type in {'X','C','Z'} and event.value == 'PRESS':
			axis_id = ['4','5','6'][['X','C','Z'].index(event.type)]
			self.align_mode = axis_id if self.align_mode != axis_id else '0'
			self.reset_slice_vizualizetion(context)

			context.region.tag_redraw()
			print(self.align_mode)

		# Switch align mode to +90
		elif event.type == 'S' and event.value == 'PRESS':
			self.switch_align = True if not self.switch_align else False
			self.reset_slice_vizualizetion(context)
			context.region.tag_redraw()
			print('S > Switch align to +90 degrees')

		# Angle/offset manual input
		elif event.type in {'BACK_SPACE','MINUS','NUMPAD_MINUS','PERIOD','NUMPAD_PERIOD','ZERO','ONE','TWO','THREE','FOUR','FIVE','SIX','SEVEN','EIGHT','NINE',
			'NUMPAD_0','NUMPAD_1','NUMPAD_2','NUMPAD_3','NUMPAD_4','NUMPAD_5','NUMPAD_6','NUMPAD_7','NUMPAD_8','NUMPAD_9','F'} and event.value == 'PRESS':

			if self.switch_input:
				print('START NUM input >> ', event.type, ' | OFFSET >> ', self.am_offset, ' | DOT >> ', self.am_offset_dot, ' | MIN >> ', self.am_offset_min )
			else:
				print('START NUM input >> ', event.type, ' | ANGLE >> ', self.am_angle, ' | DOT >> ', self.am_angle_dot, ' | MIN >> ', self.am_angle_min )


			if event.type == 'BACK_SPACE':
				if self.switch_input:
					if self.am_offset_dot:
						if len(self.am_offset.split('.')[1]) > 0: self.am_offset = self.am_offset[:-1]
						elif len(self.am_offset.split('.')[1]) == 0: self.am_offset, self.am_offset_dot = self.am_offset[:-1], False
						#else: self.am_offset, self.am_offset_dot = self.am_offset[:-2], False
					else:
						if self.am_offset.split('-')[-1][:-1] == '': self.am_offset = '-0' if self.am_offset_min else '0'
						else: self.am_offset = self.am_offset[:-1]
				else:
					if self.am_angle_dot:
						if len(self.am_angle.split('.')[1]) > 0: self.am_angle = self.am_angle[:-1]
						elif len(self.am_angle.split('.')[1]) == 0: self.am_angle, self.am_angle_dot = self.am_angle[:-1], False
						#else: self.am_angle, self.am_angle_dot = self.am_angle[:-2], False
					else:
						if self.am_angle.split('-')[-1][:-1] == '': self.am_angle = '-0' if self.am_angle_min else '0'
						else: self.am_angle = self.am_angle[:-1]


			elif event.type in {'MINUS','NUMPAD_MINUS','F'}:
				if self.switch_input:
					if self.am_offset_min: self.am_offset, self.am_offset_min = self.am_offset[1:], False
					else: self.am_offset, self.am_offset_min = '-' + self.am_offset, True
				else:
					if self.am_angle_min: self.am_angle, self.am_angle_min = self.am_angle[1:], False
					else: self.am_angle, self.am_angle_min = '-' + self.am_angle, True

			elif event.type in {'PERIOD','NUMPAD_PERIOD'}:
				if self.switch_input:
					if not self.am_offset_dot: self.am_offset, self.am_offset_dot = self.am_offset + '.', True
					elif self.am_offset_dot and len(self.am_offset.split('.')[1]) == 0: self.am_offset, self.am_offset_dot = self.am_offset[:-1], False 
				else:
					if not self.am_angle_dot: self.am_angle, self.am_angle_dot = self.am_angle + '.', True
					elif self.am_angle_dot and len(self.am_angle.split('.')[1]) == 0: self.am_angle, self.am_angle_dot = self.am_angle[:-1], False


			elif event.type in {'ZERO','NUMPAD_0'}:
				if self.switch_input:
					if self.am_offset == '0' or self.am_offset == '-0': self.am_offset, self.am_offset_dot = self.am_offset + '.', True
					else: self.am_offset = self.am_offset + '0'
				else:
					if self.am_angle == '0' or self.am_angle == '-0': self.am_angle, self.am_angle_dot = self.am_angle + '.', True
					else: self.am_angle = self.am_angle + '0'
			else:
				if self.switch_input:
					if self.am_offset == '0' or self.am_offset == '-0': self.am_offset = '-' + self.numbers_dic.get(event.type) if self.am_offset_min else self.numbers_dic.get(event.type)
					else: self.am_offset = self.am_offset + self.numbers_dic.get(event.type)
				else:
					if self.am_angle == '0' or self.am_angle == '-0': self.am_angle = '-' + self.numbers_dic.get(event.type) if self.am_angle_min else self.numbers_dic.get(event.type)
					else: self.am_angle = self.am_angle + self.numbers_dic.get(event.type)

			if self.switch_input:
				self.bisect_offset = float(self.am_offset)
			else:
				self.slice_angle = math.radians(float(self.am_angle))

			if self.switch_input:
				print('END NUM input >> ', event.type, ' | OFFSET >> ', self.am_offset, ' | DOT >> ', self.am_offset_dot, ' | MIN >> ', self.am_offset_min )
			else:
				print('END NUM input >> ', event.type, ' | ANGLE >> ', self.am_angle, ' | DOT >> ', self.am_angle_dot, ' | MIN >> ', self.am_angle_min )

			self.reset_slice_vizualizetion(context)
			context.region.tag_redraw()

		# Erase angle/offset value to 0
		elif event.type == 'E' and event.value == 'PRESS':
			if self.switch_input:
				self.am_offset = '-0' if self.am_offset[0] == '-' else '0'
				if self.am_offset_dot: self.am_offset_dot = False
				self.bisect_offset = 0
			else:
				self.am_angle = '-0' if self.am_angle[0] == '-' else '0'
				if self.am_angle_dot: self.am_angle_dot = False
				self.slice_angle = 0

			self.reset_slice_vizualizetion(context)
			context.region.tag_redraw()
			print('E > Erase angle/offset (set to 0)')

		# Normal flip
		elif event.type == 'N' and event.value == 'PRESS':
			self.bisect_flip_normal = True if not self.bisect_flip_normal else False
			context.region.tag_redraw()
			print('N > Invert slice normal')

		# Show/hide hidden mesh
		elif event.type == 'H' and event.value == 'PRESS':
			abt.hid_eds_enabled = not abt.hid_eds_enabled
			#self.show_hidden = not self.show_hidden
			self.reset_points(context)
			context.region.tag_redraw()
			print('H > Show/hide hidden mesh')

		# Turn ON/OFF median points
		elif event.type == 'M' and event.value == 'PRESS':
			print('Midpoints ON/OFF')
			abt.mid_pts_enabled = True if not abt.mid_pts_enabled else False
			self.reset_points(context)

		# Quick angle menu
		elif event.type == 'Q' and event.value == 'PRESS':
			print('Quick anle menu')
			bpy.ops.wm.call_menu_pie(name= 'ABT_MT_PIE_Select_QA')
			self.reset_slice_vizualizetion(context)
			context.region.tag_redraw()

		# View align menu
		elif event.type == 'V' and event.value == 'PRESS':
			print('View align menu')
			bpy.ops.wm.call_menu_pie(name= 'ABT_MT_PIE_View_Align')


		# Switch input
		elif event.type == 'TAB' and event.value == 'PRESS':
			if self.switch_input:
				if self.am_offset_dot and len(self.am_offset.split('.')[1]) == 0: self.am_offset, self.am_offset_dot = self.am_offset[:-1], False
				elif self.am_offset_dot and len(self.am_offset.split('.')[1]) > 5: self.am_offset = self.am_offset[:self.am_offset.find('.')] + str(round(float('0' + self.am_offset[self.am_offset.find('.'):]),5))[1:]
			else:
				if self.am_angle_dot and len(self.am_angle.split('.')[1]) == 0: self.am_angle, self.am_angle_dot = self.am_angle[:-1], False
				elif self.am_angle_dot and len(self.am_angle.split('.')[1]) > 5: self.am_angle = self.am_angle[:self.am_angle.find('.')] + str(round(float('0' + self.am_angle[self.am_angle.find('.'):]),5))[1:]				


			self.switch_input = True if not self.switch_input else False
			context.region.tag_redraw()
			print('TAB > Switch input')		

		# Execute slice
		elif event.type in {'RET', 'SPACE', 'NUMPAD_ENTER'}:
			if self.slice_pts == []:
				print('No points selected')
				remove_draw_handlers(self)
				self.redraw_3d = True
				context.region.tag_redraw()
				return {'CANCELLED'}
			else:
				remove_draw_handlers(self)
				self.redraw_3d = True
				context.region.tag_redraw()
				print('Execute slice')

				# Collect data for execute
				self.mtr_execute_orientations.clear()
				for mode in ['0','1','2','3','4','5','6']:
					self.mtr_execute_orientations.append(get_transform_orientaions_from_mode(context,mode,self.slice_pts))
				self.mtr_view = copy(context.space_data.region_3d.view_matrix)
				return self.execute(context)

		else:
			context.region.tag_redraw()
			return {'PASS_THROUGH'}

		return {'RUNNING_MODAL'}

	def execute(self, context):
		bisect_point, bisect_normal = self.slice_plane_setup(context)
		if bisect_normal.length_squared == 0: return {'CANCELLED'}
		bpy.ops.mesh.bisect(plane_co=bisect_point, plane_no=bisect_normal, use_fill=self.bisect_use_fill, clear_inner=self.bisect_clear_inner, clear_outer=self.bisect_clear_outer)

		return {'FINISHED'}

	def slice_plane_setup(self, context):
		self.slice_pts = [Vector(co) for co in self.slice_pts]
		vct_x, vct_y, vct_z = Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))
		exec_ang = self.slice_angle * -1 if self.slice_angle_flip else self.slice_angle
		exec_pts = copy(self.slice_pts)

		mtr_execute = self.mtr_execute_orientations[int(self.orientation_mode)]
		if len(self.slice_pts) == 1:
			exec_pts = slice_setup_single_point(context, exec_pts[0], self.mtr_view, mtr_execute, self.align_mode, self.switch_align, exec_ang)
		elif len(self.slice_pts) == 2:
			exec_pts = slice_setup_two_points(context, exec_pts, self.mtr_view, mtr_execute, self.align_mode, self.switch_align, exec_ang)
		elif len(self.slice_pts) >= 3:
			exec_pts = slice_setup_triple_point(context, exec_pts, mtr_execute, self.align_mode, self.switch_align, exec_ang)

		bisect_normal = mug_normal(exec_pts[:3]) * -1 if self.bisect_flip_normal else mug_normal(exec_pts[:3])
		bisect_point = exec_pts[0] + bisect_normal * self.bisect_offset

		return bisect_point, bisect_normal

	def slise_point_pick(self, context, event):
		abt_p = context.preferences.addons[__name__].preferences
		s3d = context.space_data.region_3d
		cursor_xy = Vector((event.mouse_region_x, event.mouse_region_y))

		dst_min = abt_p.mrk_pts_dist
		pt_co = None
		pt_id = None

		for enm, pt in enumerate(self.snap_pts):
			pt_2d = convert_global_to_screen(context.region, s3d, Vector(pt))
			if pt_2d != None:
				dst_new = (cursor_xy - pt_2d).length
				if dst_new <= dst_min:
					dst_min = dst_new
					pt_id = enm
					pt_co = pt

		return pt_co, pt_id

	def reset_points(self,context):
		abt = context.scene.abt_props
		vtc_pts = np.empty((0,3), dtype=np.float32)
		mid_pts = np.empty((0,3), dtype=np.float32)
		hid_eds = np.empty((0,3), dtype=np.float32)

		for obn in self.obs_lst_main:
			bpy.context.view_layer.objects.active = bpy.data.objects[obn]
			bmd = bmesh.from_edit_mesh(context.edit_object.data)
			obm = bpy.data.objects[obn].matrix_world

			if abt.hid_eds_enabled:
				vtc_data = np.array([(obm @ vtc.co)[:] for vtc in bmd.verts], dtype=np.float32)
				mid_data = np.array([(obm @ (edg.verts[0].co + 0.5 * (edg.verts[1].co - edg.verts[0].co)))[:] for edg in bmd.edges], dtype=np.float32) if abt.mid_pts_enabled else np.empty((0,3), dtype=np.float32)
				hid_data = np.array([((obm @ edg.verts[0].co)[:], (obm @ edg.verts[1].co)[:]) for edg in bmd.edges if edg.hide], dtype=np.float32)
				hid_data = np.reshape(hid_data, (hid_data.size//3,3))
			else:
				vtc_data = np.array([(obm @ vtc.co)[:] for vtc in bmd.verts if not vtc.hide], dtype=np.float32)
				mid_data = np.array([(obm @ (edg.verts[0].co + 0.5 * (edg.verts[1].co - edg.verts[0].co)))[:] for edg in bmd.edges if not edg.hide], dtype=np.float32) if abt.mid_pts_enabled else np.empty((0,3), dtype=np.float32)
				hid_data = np.empty((0,3), dtype=np.float32)

			vtc_pts = np.append(vtc_pts,vtc_data)
			mid_pts = np.append(mid_pts,mid_data)
			hid_eds = np.append(hid_eds,hid_data)


		for obn in self.obs_lst_add:
			obd = bpy.data.objects[obn].data
			obm = bpy.data.objects[obn].matrix_world

			vtc_data = np.array([(obm @ vtc.co)[:] for vtc in obd.vertices], dtype=np.float32)
			mid_data = np.array([(obm @ (obd.vertices[edg.vertices[0]].co + 0.5 * (obd.vertices[edg.vertices[1]].co - obd.vertices[edg.vertices[0]].co)))[:] for edg in obd.edges], dtype=np.float32) if abt.mid_pts_enabled else np.empty((0,3), dtype=np.float32)

			vtc_pts = np.append(vtc_pts,vtc_data)
			mid_pts = np.append(mid_pts,mid_data)

		vtc_pts	= np.reshape(vtc_pts, (vtc_pts.size//3,3))
		mid_pts	= np.reshape(mid_pts, (mid_pts.size//3,3))
		hid_eds	= np.reshape(hid_eds, (hid_eds.size//3,3))

		self.vtc_pts_draw = vtc_pts
		self.mid_pts_draw = mid_pts
		self.hid_eds_draw = hid_eds

		if abt.mid_pts_enabled:
			snp_pts = np.append(vtc_pts,mid_pts)
			self.snap_pts = np.reshape(snp_pts, (snp_pts.size//3,3))
		else:
			self.snap_pts = vtc_pts

	def reset_slice_vizualizetion(self, context):
		if len(self.slice_pts) != 0: #(len(self.slice_pts) >= 3) or ((len(self.slice_pts) == 1 or len(self.slice_pts) == 2) and self.align_mode != '0'):
			slc_lines = np.empty((0,3), dtype=np.float32)
			slc_points = np.empty((0,3), dtype=np.float32)


			self.mtr_execute_orientations.clear()
			for mode in ['0','1','2','3','4','5','6']:
				self.mtr_execute_orientations.append(get_transform_orientaions_from_mode(context,mode,self.slice_pts))

			self.mtr_view = copy(context.space_data.region_3d.view_matrix)
			bisect_point, bisect_normal = self.slice_plane_setup(context)

			for obn in self.obs_lst_slice:
				bpy.context.view_layer.objects.active = bpy.data.objects[obn]
				bmd = bmesh.from_edit_mesh(context.edit_object.data)
				obm = bpy.data.objects[obn].matrix_world

				edgs_sel_ids = np.array([edg.index for edg in bmd.edges if edg.select], dtype=np.int32)
				edgs_fac_ids = np.empty(0, dtype=np.int32)
				lines_data = np.empty((0,3), dtype=np.float32)
				points_data = np.empty((0,3), dtype=np.float32)

				for fac in bmd.faces:
					if fac.select:
						edgs_ids = []
						slc_pts = []
						for edg in fac.edges:
							edg_vtc_a, edg_vtc_b = obm @ edg.verts[0].co, obm @ edg.verts[1].co
							edgs_ids.append(edg.index)
							slc_pt = intersect_line_plane(edg_vtc_a, edg_vtc_b, bisect_point, bisect_normal)
							if slc_pt != None:
								vct_edge = edg_vtc_b - edg_vtc_a
								vct_point = edg_vtc_b - slc_pt
								if 0 <= vectors_dot_product(vct_edge, vct_point) <= 1:
									slc_pts.append(slc_pt[:])

						if len(slc_pts) >= 2:
							ids_to_merge = []
							for enm_a,pt_a in enumerate(slc_pts):
								if not enm_a in ids_to_merge: 
									for enm_b,pt_b in enumerate(slc_pts):
										if enm_b != enm_a:
											if round(pt_a[0],5) == round(pt_b[0],5) and round(pt_a[1],5) == round(pt_b[1],5) and round(pt_a[2],5) == round(pt_b[2],5):
												ids_to_merge.append(enm_b)
							ids_to_merge.sort()
							if ids_to_merge != []:
								for pt_id in ids_to_merge[::-1]:
									slc_pts.pop(pt_id)

						if len(slc_pts) >= 2:
							if len(slc_pts) % 2 != 0:
								slc_pts.pop(-1)

							slc_pts = np.array(slc_pts, dtype=np.float32)
							lines_data = np.append(lines_data, slc_pts)

						edgs_fac_ids = np.append(edgs_fac_ids, edgs_ids)

				edgs_sel_ids = np.setdiff1d(edgs_sel_ids, edgs_fac_ids)

				if edgs_sel_ids.size != 0:
					for edg_id in edgs_sel_ids:
						edg_vtc_a, edg_vtc_b = obm @ bmd.edges[edg_id].verts[0].co, obm @ bmd.edges[edg_id].verts[1].co
						slc_pt = intersect_line_plane(edg_vtc_a, edg_vtc_b, bisect_point, bisect_normal)
						if slc_pt != None:
							vct_edge = edg_vtc_b - edg_vtc_a
							vct_point = edg_vtc_b - slc_pt
							if 0 <= vectors_dot_product(vct_edge, vct_point) <= 1:
								points_data = np.append(points_data, slc_pt[:])
					points_data = np.array(points_data, dtype=np.float32)


				slc_lines = np.append(slc_lines, lines_data)
				slc_points = np.append(slc_points, lines_data)
				slc_points = np.append(slc_points, points_data)

			slc_lines = np.reshape(slc_lines, (slc_lines.size//3,3))
			slc_points = np.reshape(slc_points, (slc_points.size//3,3))

			self.slc_lines_draw = slc_lines
			self.slc_points_draw = slc_points
			self.draw_slice = True
			# Update if view matrix changed when 1 point and align mode 0 (screen aligned), 0 and orientation modes 4 (slice) or 5 (gravity)
			if  len(self.slice_pts) == 1 and (self.align_mode == '0' or (self.align_mode != '0' and self.orientation_mode in ['4','5'])):
				self.check_mtr_view = True
				self.mtr_view = copy(context.space_data.region_3d.view_matrix)
			# Update if view matrix changed when 2 points and align mode 0 (screen aligned), 0 and orientation modes 4 (slice)
			elif len(self.slice_pts) == 2 and (self.align_mode == '0' or (self.align_mode != '0' and self.orientation_mode == '4')):
				self.check_mtr_view = True
				self.mtr_view = copy(context.space_data.region_3d.view_matrix)
			else:
				self.check_mtr_view = False
				self.mtr_view = None

		else:
			self.draw_slice = False
			self.slc_lines_draw = np.empty((0,3), dtype=np.float32)
			self.slc_points_draw = np.empty((0,3), dtype=np.float32)
			self.check_mtr_view = False
			self.mtr_view = None

	def ray_cast_add_remove_object(self, context, ray_mode):
		hit_vallid_object = False
		no_hit = False
		raycast_n = 0
		hit_loc = Vector((0,0,0))
		hit_obn = ''

		while not hit_vallid_object and not no_hit:
			ray_result = cast_ray(context, self.cursor_xy) if raycast_n == 0 else cast_ray(context, self.cursor_xy, hit_loc, True)
			ray_hit = ray_result[0]

			if ray_hit:
				hit_loc = ray_result[1]
				hit_obn = ray_result[4].name

				if ray_mode == 'ADD':
					if not hit_obn in self.obs_lst_add and not hit_obn in self.obs_lst_main and bpy.data.objects[hit_obn].type == 'MESH':
						hit_vallid_object = True
						self.obs_lst_add.append(hit_obn)
				else:
					if hit_obn in self.obs_lst_add:
						hit_vallid_object = True
						self.obs_lst_add.pop(self.obs_lst_add.index(hit_obn))
			else:
				no_hit = True
			raycast_n += 1


class ABT_Addon_Preferences(bpy.types.AddonPreferences):

	bl_idname = __name__

	mrk_pts_dist:	bpr.IntProperty(name= 'Mark Points Distance', default= 10,  min= 1, soft_max= 100, subtype= 'FACTOR',
		description = 'Distance threshold (in screen pixels) for marking points')

	mrk_pts_size:	bpr.FloatProperty(name='Marked Points Size', default= 20, precision= 1, min= 1, max= 100, subtype= 'FACTOR',
		description='Size of marked points')
	mrk_pts_color:	bpr.FloatVectorProperty(name='Marked Points Color', size= 4, default=(0.9, 1.0, 0.2, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Color of marked points')

	vtc_pts_size:	bpr.FloatProperty(name='Vertex Points Size', default= 15, precision= 1, min= 1, max= 100, subtype= 'FACTOR',
		description='Size of vertices snap points')
	vtc_pts_color:	bpr.FloatVectorProperty(name='Vertex Points Color', size= 4, default=(0.0, 1.0, 1.0, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Color of vertices snap points')

	mid_pts_size:	bpr.FloatProperty(name='Median Points Size', default= 10, precision= 1, min= 1, max= 100, subtype= 'FACTOR',
		description='Size of edge median snap points')
	mid_pts_color:	bpr.FloatVectorProperty(name='Median Points Color', size= 4, default=(0.9, 0.5, 1.0, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Color of edge median snap points')

	slc_pts_size:	bpr.FloatProperty(name='Slice Points Size', default= 15, precision= 1, min= 1, max= 100, subtype= 'FACTOR',
		description='Size of slice preview points')
	slc_pts_color:	bpr.FloatVectorProperty(name='Slice Points Color', size= 4, default=(0.0, 0.9, 0.35, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Color of slice preview points')

	slc_lns_width:	bpr.FloatProperty(name='Slice Preview Thickness', default= 6, precision= 1, min= 1, max= 20, subtype= 'FACTOR',
		description='Thickness of slice preview lines')
	slc_lns_color:	bpr.FloatVectorProperty(name='Slice Preview Color', size= 4, default=(0.45, 0.9, 0.63, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Color of hidden edges lines',)

	hid_eds_width:	bpr.FloatProperty(name='Hidden Edges Thickness', default= 3, precision= 1, min= 1, max= 20, subtype= 'FACTOR',
		description='Thickness of hidden edges lines')
	hid_eds_color:	bpr.FloatVectorProperty(name='Hidden Edges Color', size= 4, default=(0.2, 0.55, 1.0, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Color of hidden edges lines')

	grid_lns_width: bpr.FloatProperty(name='Grid Lines Thickness', default= 3, precision= 1, min= 1, max= 20, subtype= 'FACTOR',
		description='Thickness of grid lines')
	grid_lns_color: bpr.FloatVectorProperty(name='Grid Lines Color', size= 4, default=(0.8, 0.8, 0.8, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Color of grid (3 points) lines')

	gizmo_lns_width: bpr.FloatProperty(name='Gizmo Lines Thickness', default= 7, precision= 1, min= 1, max= 20, subtype= 'FACTOR',
		description='Thickness of grid lines')
	axis_lns_width: bpr.FloatProperty(name='Axis Lines Thickness', default= 3, precision= 1, min= 1, max= 20, subtype= 'FACTOR',
		description='Thickness of grid lines')

	orientation_axis_size: 	bpr.FloatProperty(name='Orientaion Axis Size', default= 20, precision= 1, min= 1, max= 100, subtype= 'FACTOR',
		description='Size of orientation axis gizmo')
	orientation_axis_col_x:	bpr.FloatVectorProperty(name='X Axis color', size= 4, default=(1.0, 0.32, 0.2, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='X Axis color')
	orientation_axis_col_y: bpr.FloatVectorProperty(name='Y Axis color', size= 4, default=(0.55, 1.0, 0.3, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Y Axis color')
	orientation_axis_col_z: bpr.FloatVectorProperty(name='Z Axis color', size= 4, default=(0.35, 0.7, 1.0, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Z Axis color')

	scr_ui_show:	bpr.BoolProperty(name='Show Screen Text UI', default= True, description='Show screen text UI')
	crs_ui_show:	bpr.BoolProperty(name='Show Cursor Text UI', default= True, description='Show cursor text UI')

	slc_obs_show:	bpr.BoolProperty(name='Show Objects To Slice Names', default= True, description='Show names of objects to slice in Text UI')
	snp_obs_show:	bpr.BoolProperty(name='Show Objects To Snap Names', default= True, description='Show names of objects to snap in Text UI')

	scr_ui_txt_size:	bpr.FloatProperty(name='Screen Text UI Size', default= 1, precision= 2, min= 0.01, soft_max= 2, subtype= 'FACTOR',
		description='Size of screen UI text')
	crs_ui_txt_size:	bpr.FloatProperty(name='Cursor Text UI Size', default= 1, precision= 2, min= 0.01, soft_max= 2, subtype= 'FACTOR',
		description='Size of cursor UI text')

	scr_ui_txt_pos_x:	bpr.FloatProperty(name='Screen Text UI Position X', default= 5.5, precision= 1, min= 1, max= 99, subtype= 'FACTOR',
		description='X position of screen UI text (in area %)')
	scr_ui_txt_pos_y:	bpr.FloatProperty(name='Screen Text UI Position Y', default= 10, precision= 1, min= 1, max= 99, subtype= 'FACTOR',
		description='Y position of screen UI text (in area %)')

	ui_txt_shadow_x:	bpr.IntProperty(name='Text UI X Offset', default= 2, min= -10, max= 10, subtype= 'FACTOR',
		description='X offset for UI text shadow (in pixels)')
	ui_txt_shadow_y:	bpr.IntProperty(name='Text UI Y Offset', default= -2, min= -10, max= 10, subtype= 'FACTOR',
		description='Y offset for UI text shadow (in pixels)')

	ui_txt_base_color:	bpr.FloatVectorProperty(name='Text UI Base Color', size= 4, default=(1.0, 1.0, 1.0, 1.0), min= 0, max= 1, subtype= 'COLOR',
		description='Text UI base color')
	ui_txt_shadow_color:	bpr.FloatVectorProperty(name='Text UI Shadow Color', size= 4, default=(0.0, 0.0, 0.0, 0.5), min= 0, max= 1, subtype= 'COLOR',
		description='Text UI shadow color')

	def draw(self,context):
		layout = self.layout
		col = layout.column(align=True) 

		row = col.row(align=True)
		row.label(text= 'Marking points threshold (in pixels)')
		srow = row.row(align=True)
		srow.scale_x = 1.422
		srow.prop(self, 'mrk_pts_dist', text= '')

		col.separator(factor=0.5) # -----------------------------------------------

		row = col.row(align=True)
		row.label(text= 'Marked points size/color')
		row.prop(self, 'mrk_pts_size', text= '')
		row.prop(self, 'mrk_pts_color', text= '')		

		row = col.row(align=True)
		row.label(text= 'Vertex points size/color')
		row.prop(self, 'vtc_pts_size', text= '')
		row.prop(self, 'vtc_pts_color', text= '')

		row = col.row(align=True)
		row.label(text= 'median points size/color')
		row.prop(self, 'mid_pts_size', text= '')
		row.prop(self, 'mid_pts_color', text= '')

		row = col.row(align=True)
		row.label(text= 'Slice points size/color')
		row.prop(self, 'slc_pts_size', text= '')
		row.prop(self, 'slc_pts_color', text= '')

		row = col.row(align=True)
		row.label(text= 'Slice lines thickness/color')
		row.prop(self, 'slc_lns_width', text= '')
		row.prop(self, 'slc_lns_color', text= '')

		row = col.row(align=True)
		row.label(text= 'Hidden mesh thickness/color')
		row.prop(self, 'hid_eds_width', text= '')
		row.prop(self, 'hid_eds_color', text= '')

		row = col.row(align=True)
		row.label(text= 'Grid lines thickness/color')
		row.prop(self, 'grid_lns_width', text= '')
		row.prop(self, 'grid_lns_color', text= '')

		col.separator(factor=0.5) # -----------------------------------------------

		row = col.row(align=True)
		row.label(text= 'Gizmo/Axis lines thickness')
		row.prop(self, 'gizmo_lns_width', text= '')
		row.prop(self, 'axis_lns_width', text= '')

		row = col.row(align=True)
		row.label(text= 'Orientation gizmo size/colors')
		row.prop(self, 'orientation_axis_size', text= '')
		srow = row.row(align=True)
		srow.scale_x = 0.579
		srow.prop(self, 'orientation_axis_col_x', text= '')
		srow.prop(self, 'orientation_axis_col_y', text= '')
		srow.prop(self, 'orientation_axis_col_z', text= '')

		col.separator(factor=0.5) # -----------------------------------------------

		row = col.row(align=True)
		row.label(text= 'Screen/Cursor text UI enabled')
		row.prop(self, 'scr_ui_show', text= 'Screen UI', toggle=True)
		row.prop(self, 'crs_ui_show', text= 'Cursor UI', toggle=True)

		row = col.row(align=True)
		row.label(text= 'Slice/Snap objects names in UI')
		row.prop(self, 'slc_obs_show', text= 'Slice Objects', toggle=True)
		row.prop(self, 'snp_obs_show', text= 'Snap Objects', toggle=True)

		row = col.row(align=True)
		row.label(text= 'Screen/Cursor text UI size')
		row.prop(self, 'scr_ui_txt_size', text= '')
		row.prop(self, 'crs_ui_txt_size', text= '')

		row = col.row(align=True)
		row.label(text= 'Screen text UI XY position')
		row.prop(self, 'scr_ui_txt_pos_x', text= '')
		row.prop(self, 'scr_ui_txt_pos_y', text= '')

		row = col.row(align=True)
		row.label(text= 'Text UI shadow XY offset')
		row.prop(self, 'ui_txt_shadow_x', text= '')
		row.prop(self, 'ui_txt_shadow_y', text= '')

		row = col.row(align=True)
		row.label(text= 'Base/Shadow color for text UI')
		row.prop(self, 'ui_txt_base_color', text= '')
		row.prop(self, 'ui_txt_shadow_color', text= '')

def prop_update_vtc_pts_enabled(self, context):
	abt = context.scene.abt_props
	if not abt.vtc_pts_enabled and not abt.mid_pts_enabled:
		abt.mid_pts_enabled = True

def prop_update_mid_pts_enabled(self, context):
	abt = context.scene.abt_props
	if not abt.mid_pts_enabled and not abt.vtc_pts_enabled:
		abt.vtc_pts_enabled = True


class ABT_Scene_Properties(bpy.types.PropertyGroup):

	vtc_pts_enabled: bpr.BoolProperty(name='Vertex Points Enabled', default= True, update= prop_update_vtc_pts_enabled,
		description='Use/visualize vertices slice points')

	mid_pts_enabled: bpr.BoolProperty(name='Median Points Enabled', default= True, update= prop_update_mid_pts_enabled,
		description='Use/visualize edge median slice points')

	hid_eds_enabled: bpr.BoolProperty( name='Hidden Mesh Edges Visible', default= True, description='Visualize hidden mesh edges')

	orientation_axis_enabled:	bpr.BoolProperty(name='Orientaion Axis Enabled', default= True, description='Visualize selected orientaion axis gizmo')
	orientation_set:			bpr.BoolProperty(name='Orientaion Set', default= True, description='Set align orientation when new selected in PIE')
	orientation_set_id:			bpr.IntProperty(name='Orientaaton ID To Set', default= 0, min= 0, max= 6, description='Orientation ID in orientations list')

	slice_plane_grid_enabled: bpr.BoolProperty(name='Slice Plane Grid Visible', default= True, description='Visualize slice plane preview grig')

	slice_offset_reset:	bpr.BoolProperty(name='Slice Offset Reset', default= False, description='Reset offset each time you start ABT')
	slice_angle_reset:	bpr.BoolProperty(name='Slice Angle Reset', default= False, description='Reset angle each time you start ABT')
	slice_angle_set:	bpr.BoolProperty(name='Slice Angle Set', default= False, description='Set slice angle when quick angle is selected in PIE')
	slice_qa_id:		bpr.IntProperty(name='Quick Angle To Set', default= 0, min= 0, max= 7, description='Quick angle to set as a slice angle')
	slice_qa_a:			bpr.FloatProperty(name='Quick Angle A', description='Quick angle to set as a slice angle', unit='ROTATION')
	slice_qa_b:			bpr.FloatProperty(name='Quick Angle B', description='Quick angle to set as a slice angle', unit='ROTATION')
	slice_qa_c:			bpr.FloatProperty(name='Quick Angle C', description='Quick angle to set as a slice angle', unit='ROTATION')
	slice_qa_d:			bpr.FloatProperty(name='Quick Angle D', description='Quick angle to set as a slice angle', unit='ROTATION')
	slice_qa_e:			bpr.FloatProperty(name='Quick Angle E', description='Quick angle to set as a slice angle', unit='ROTATION')
	slice_qa_f:			bpr.FloatProperty(name='Quick Angle F', description='Quick angle to set as a slice angle', unit='ROTATION')
	slice_qa_g:			bpr.FloatProperty(name='Quick Angle G', description='Quick angle to set as a slice angle', unit='ROTATION')
	slice_qa_i:			bpr.FloatProperty(name='Quick Angle I', description='Quick angle to set as a slice angle', unit='ROTATION')

	align_view_allowed:	bpr.BoolProperty(name='Align View Allowed', default= False, description='Whether or not aligning view is allowed in current mode')
	align_view_set:		bpr.BoolProperty(name='Set Align View', default= False, description='Align view to chosen side')
	align_view_set_id:	bpr.IntProperty(name='Align Orientation ID To Set View', default= 0, min= 0, max= 6, description='Align orientation ID in orientations list')
	view_rec:			bpr.BoolProperty(name='Recover View', default= False, description='Recover view after align')
#	view_rec_mtr:		bpr.FloatVectorProperty(name= 'VRV', subtype= 'MATRIX', size= [4,4])
	view_rec_mtr_col_a:	bpr.FloatVectorProperty(name= 'VRV_CA', size = 4)
	view_rec_mtr_col_b:	bpr.FloatVectorProperty(name= 'VRV_CB', size = 4)
	view_rec_mtr_col_c:	bpr.FloatVectorProperty(name= 'VRV_CC', size = 4)
	view_rec_mtr_col_d:	bpr.FloatVectorProperty(name= 'VRV_CD', size = 4)

	orientation_mode_default:	bpr.EnumProperty(name= 'Orientation Mode Default',
		items= [('0','None','Not override orientation mode on operator start',0),
				('1','Global','Will swap last used orientation mode to Global on operator start',1),
				('2','Local', 'Will swap last used orientation mode to Local on operator start', 2),
				('3','Cursor','Will swap last used orientation mode to Cursor on operator start',3),
				('4','Active','Will swap last used orientation mode to Active on operator start',4),
				('5','Slice','Will swap last used orientation mode to Active on operator start',5),
				('6','Gravity','Will swap last used orientation mode to Active on operator start',6),
				('7','Preset','Will swap last used orientation mode to Preset on operator start',7)],
				default= '0')


	expand_opt:		bpr.BoolProperty(name='Expand Options', default= True, description='Expand operator options UI')
	expand_qas:		bpr.BoolProperty(name='Expand Quick Angles', default= True, description='Expand quick angles UI')
	expand_tos:		bpr.BoolProperty(name='Expand Transform Orientations', default= True, description='Expand transform orientations presets UI')

CTR = [
	ABT_PT_Panel,
	ABT_MT_PIE_Select_QA,
	ABT_OT_Set_Quick_Angle,
	ABT_OT_Rotate_Angle_Ninety,
	ABT_OT_Clear_Angle_Value,
	ABT_MT_PIE_Select_TO,
	ABT_OT_Set_Align_Orientation,
	ABT_MT_PIE_View_Align,
	ABT_OT_View_Align,
	ABT_OT_View_Recover,
	ABT_OT_Clear_View_Recover,
	ABT_OT_Empty,
	ABT_OT_Bisect_Tool,
	ABT_Addon_Preferences,
	ABT_Scene_Properties
	]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)

	# Register properties
	bpy.types.Scene.abt_props = bpr.PointerProperty(type=ABT_Scene_Properties)


def unregister():
	for cls in CTR:
		bpy.utils.unregister_class(cls)

	# Delete properties
	del bpy.types.Scene.abt_props