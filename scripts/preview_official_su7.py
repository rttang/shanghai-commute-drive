import bpy,pathlib
from mathutils import Vector,Matrix
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'assets/vehicles/source/su7'
bpy.context.preferences.filepaths.use_scripts_auto_execute=False
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'sketchfab-official.glb'))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
for o in objects:
 matrix=o.matrix_world.copy();o.data=o.data.copy();o.data.transform(matrix);o.parent=None;o.matrix_world=Matrix.Identity(4)
points=[v.co for o in objects for v in o.data.vertices]
lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)];scale=4.997/(hi[1]-lo[1])
for o in objects:
 for v in o.data.vertices:
  v.co.x*=scale;v.co.y=(v.co.y-(lo[1]+hi[1])/2)*scale;v.co.z=(v.co.z-lo[2])*scale
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=780;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True
scene.world.use_nodes=True;nt=scene.world.node_tree;nt.nodes.clear();env=nt.nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(ROOT/'public/environment/sky.hdr'));bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.5;output=nt.nodes.new('ShaderNodeOutputWorld');nt.links.new(env.outputs['Color'],bg.inputs['Color']);nt.links.new(bg.outputs['Background'],output.inputs['Surface'])
for location,power,size in [((2,4,6),950,5),((-5,0,4),1100,4),((2,-4,5),950,4)]:
    data=bpy.data.lights.new('Studio softbox','AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new('Studio softbox',data);bpy.context.collection.objects.link(o);o.location=location;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
camdata=bpy.data.cameras.new('Vehicle reference');cam=bpy.data.objects.new('Vehicle reference',camdata);bpy.context.collection.objects.link(cam);scene.camera=cam;camdata.lens=56
for name,location in [('front',(6.4,8.5,3.4)),('rear',(-6.4,-8.5,3.4)),('side',(9.5,0,2.0))]:
    cam.location=location;cam.rotation_euler=(Vector((0,0,.75))-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/f'su7-official-{name}.png');bpy.ops.render.render(write_still=True)
