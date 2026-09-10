"""Oriental Pearl exterior and arrival plaza, based on the archived CC BY photo.
The three inclined legs, small spheres, lattice belts and glazed canopy are
modeled explicitly. Planting and entrance dimensions are visual estimates.
"""
import math
def build(bpy,Mesh,material):
 root=bpy.data.objects.new('pearl',None);bpy.context.collection.objects.link(root)
 root['sourcePhoto']='assets/streets/references/pearl-base.jpg'
 mesh=Mesh(root)
 concrete=material('pearl-concrete',(.47,.475,.445),.84)
 silver=material('pearl-silver-panels',(.57,.60,.585),.42)
 red=material('pearl-rose-glass',(.32,.067,.113),.28)
 dark=material('pearl-wine-glass',(.105,.071,.11),.22)
 window=material('pearl-blue-glass',(.125,.225,.265),.24)
 frame=material('pearl-white-frame',(.64,.68,.66),.35)
 paving=material('pearl-plaza-pavers',(.45,.35,.285),.95)
 paving2=material('pearl-plaza-inlay',(.58,.54,.43),.88)
 green=material('pearl-hedge',(.075,.15,.055),.99)
 flower=material('pearl-flower-border',(.215,.07,.105),.95)
 for m in [red,dark,window]:m.node_tree.nodes.get('Principled BSDF').inputs['Metallic'].default_value=.24
 def ring(z,r,thickness,mat,cx=0,cy=0,n=96):
  for i in range(n):
   a=i*math.tau/n;b=(i+1)*math.tau/n
   mesh.rod((cx+r*math.cos(a),cy+r*math.sin(a),z),(cx+r*math.cos(b),cy+r*math.sin(b),z),thickness,mat,6)
 def sphere(center,r,main=True):
  cx,cy,cz=center;n=64 if main else 32;rows=32 if main else 16
  def pos(i,j):
   phi=-math.pi/2+j*math.pi/rows;a=i*math.tau/n
   return (cx+r*math.cos(phi)*math.cos(a),cy+r*math.cos(phi)*math.sin(a),cz+r*math.sin(phi))
  for j in range(rows):
   lat=-math.pi/2+(j+.5)*math.pi/rows
   for i in range(n):
    v=[pos(i,j),pos(i+1,j),pos(i+1,j+1),pos(i,j+1)]
    if main and abs(lat)<.38:
     mesh.face([v[0],v[1],v[2]],red if (i+j)%2 else dark,smooth=True)
     mesh.face([v[0],v[2],v[3]],dark if (i+j)%2 else red,smooth=True)
     # Triangular lattice follows the curved glass instead of floating hoops.
     mesh.rod(v[0],v[2],.075,frame,5)
     mesh.rod(v[0],v[1],.085,frame,5)
    else:mesh.face(v,silver,smooth=True)
   if j%3==0 and j>0:ring(cz+r*math.sin(-math.pi/2+j*math.pi/rows),r*math.cos(-math.pi/2+j*math.pi/rows)+.02,.038,frame,cx,cy,n)
  # Fine vertical panel joints on the silver shell.
  for i in range(0,n,2):
   for j in range(1,rows-1):mesh.rod(pos(i,j),pos(i,j+1),.029,frame,5)
 def annulus(r0,r1,z,mat,n=96):
  for i in range(n):
   a=i*math.tau/n;b=(i+1)*math.tau/n
   mesh.face([(r0*math.cos(a),r0*math.sin(a),z),(r1*math.cos(a),r1*math.sin(a),z),(r1*math.cos(b),r1*math.sin(b),z),(r0*math.cos(b),r0*math.sin(b),z)],mat)
 # Broad circular entry forecourt; modest dimensions stay inside the tower site.
 annulus(0,49,.18,paving)
 for r in [18,22,35,45,48]:annulus(r,r+.3,.20,paving2)
 for i in range(32):
  a=i*math.tau/32;mesh.rod((22*math.cos(a),22*math.sin(a),.22),(47*math.cos(a),47*math.sin(a),.22),.09,paving2,5)
 for a in [0,math.tau/3,math.tau*2/3]:
  x,y=math.cos(a),math.sin(a)
  mesh.rod((x*31,y*31,.2),(x*10,y*10,95),4.1,concrete,32)
  mesh.rod((x*10,y*10,30),(x*10,y*10,286),4.2,concrete,32)
  sphere((x*22,y*22,42),5.7,False)
  ring(.4,6,.25,paving2,x*31,y*31,48)
 mesh.rod((0,0,10),(0,0,348),4.5,concrete,32)
 for z,r in [(95,25),(263,22.5),(350,7.5)]:sphere((0,0,z),r)
 # Suspended lift bridges and exposed service glazing between the concrete legs.
 for z in [53,61,122,143,159,175,191,207,223,280,306,326]:
  mesh.box((0,0,z),(16,12,1.1),silver)
  mesh.box((0,0,z+1.8),(13,10,2.6),window)
 mesh.rod((0,0,357),(0,0,410),1.6,concrete,24,r2=.65)
 mesh.rod((0,0,410),(0,0,468),.42,frame,12,r2=.12)
 # Low glazed arc canopy, photo-visible at the tower's entry, with real mullions.
 for i in range(36):
  a=-math.pi*.83+i*math.pi*1.66/36;b=-math.pi*.83+(i+1)*math.pi*1.66/36
  v=[(r*math.cos(t),r*math.sin(t),z) for r,z,t in [(35,6,a),(48,3.8,a),(48,3.8,b),(35,6,b)]]
  mesh.face(v,window);mesh.rod(v[0],v[1],.08,frame,6);mesh.rod(v[1],v[2],.09,frame,6)
  if i%4==0:mesh.rod((v[1][0],v[1][1],.2),v[1],.13,frame,8)
 # Low clipped planting beds; gap toward the entrance remains open.
 for i in range(48):
  a=i*math.tau/48
  if abs(a-math.pi/2)<.45:continue
  x,y=math.cos(a)*42,math.sin(a)*42
  mesh.box((x,y,.60),(2.1,2.1,.85),green)
  mesh.box((x*1.06,y*1.06,.44),(1.2,1.2,.55),flower)
 mesh.flush();return root
