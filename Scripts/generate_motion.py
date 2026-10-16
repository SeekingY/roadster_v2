"""Initial constrained motion hypothesis. NOT measured Tesla trajectory or physics.
Only first 16 seconds of official The Ramp; no replay angles or Kickflip concatenation.
"""
from pathlib import Path
import math,json,csv,bisect
ROOT=Path(__file__).resolve().parents[1]
parameters=json.loads((ROOT/'Data/ramp_parameters.json').read_text(encoding='utf-8-sig'))
vehicle=json.loads((ROOT/'AssetsSource/vehicle_manifest.json').read_text(encoding='utf-8-sig'))['parameters']
HALF_AXLE=vehicle['wheelbase_cm']/2
RADIUS=vehicle['rear_tire_radius_cm']
points=[]
for seg in parameters['segments']:
    p=[seg['p%d_cm'%i] for i in range(4)]
    for k in range(121):
        if points and k==0:continue
        u=k/120; v=1-u
        pos=[v**3*p[0][j]+3*v*v*u*p[1][j]+3*v*u*u*p[2][j]+u**3*p[3][j] for j in range(3)]
        tangent=[3*v*v*(p[1][j]-p[0][j])+6*v*u*(p[2][j]-p[1][j])+3*u*u*(p[3][j]-p[2][j]) for j in range(3)]
        s=0 if not points else points[-1]['s']+math.dist(pos,points[-1]['p'])
        points.append({'s':s,'p':pos,'pitch':math.degrees(math.atan2(tangent[2],tangent[0]))})
length=points[-1]['s']
def path(s):
    if s<0:return [s,0,0],0
    if s>length:
        a=math.radians(points[-1]['pitch']); e=points[-1]['p'];d=s-length
        return [e[0]+d*math.cos(a),0,e[2]+d*math.sin(a)],points[-1]['pitch']
    i=max(1,bisect.bisect_left([p['s'] for p in points],s)); p0,p1=points[i-1],points[i]
    u=(s-p0['s'])/(p1['s']-p0['s'])
    return [p0['p'][j]*(1-u)+p1['p'][j]*u for j in range(3)],p0['pitch']*(1-u)+p1['pitch']*u
def smooth(u):return u*u*(3-2*u)
def interpolate(t,keys):
    for i in range(1,len(keys)):
        if t<=keys[i][0]:
            a,b=keys[i-1],keys[i];u=(t-a[0])/(b[0]-a[0]);return a[1]+u*(b[1]-a[1])
    return keys[-1][1]
# Timing constrained coarsely by observed browser frames. Values are editable fit seeds.
travel=[(0,-220),(2.127125,-220),(3,-80),(4,length*.05),(5,length*.16),(6,length*.32),(7,length*.50),(8,length*.70),(9,length*.90),(9.54,length+70),(9.75,length+180)]
release,_=path(length+180)
flight=[(9.75,release),(10.0,[release[0]-170,0,1940]),(10.54,[release[0]-580,0,1440]),(11.04,[release[0]-1020,0,820]),(11.54,[release[0]-1430,0,360]),(12.04,[release[0]-1840,0,230]),(12.54,[release[0]-2250,0,120]),(13.25,[release[0]-2750,0,0]),(14,[release[0]-3100,0,0]),(16,[release[0]-3500,0,0])]
rows=[]
for f in range(419):
    t=f*1001/24000
    if t<=9.75:
        s=interpolate(t,travel)
        p,pitch=path(s)
        if s<=length+180:
            front,_=path(s+HALF_AXLE);rear,_=path(s-HALF_AXLE)
            p=[(front[j]+rear[j])/2 for j in range(3)]
            pitch=math.degrees(math.atan2(front[2]-rear[2],front[0]-rear[0]))
        roll=0; phase='ground' if s<0 else ('ramp_contact_hypothesis' if s+HALF_AXLE<=length else 'partial_release_hypothesis')
        spin=-math.degrees((s+220)/RADIUS)
    else:
        p=[interpolate(t,[(k,v[j]) for k,v in flight]) for j in range(3)]
        u=max(0,min(1,(t-9.75)/1.29));roll=-180*smooth(u);pitch=170+10*smooth(u)
        phase='flight_kinematic_hypothesis' if t<13.25 else 'landing_occluded_hypothesis'
        if t<13.25:
            spin=-math.degrees((length+400+(t-9.75)*650)/RADIUS)
        else:
            spin=rows[-1]['wheel_pitch_deg_unwrapped']-math.degrees(math.dist(p,[rows[-1]['x_cm'],rows[-1]['y_cm'],rows[-1]['z_cm']])/RADIUS)
    rows.append({'frame':f,'source_clip_time_s':t,'x_cm':p[0],'y_cm':p[1],'z_cm':p[2],'roll_deg_unwrapped':roll,'pitch_deg_unwrapped':pitch,'yaw_deg_unwrapped':0,'wheel_pitch_deg_unwrapped':spin,'phase':phase,'confidence':'hypothesis_pending_camera_fit'})
with (ROOT/'Data/trajectory_initial.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(ROOT/'Data/ramp_dense.json').write_text(json.dumps(points,indent=2),encoding='utf-8')
(ROOT/'Data/motion_assumptions.json').write_text(json.dumps({'status':'rough_visual_hypothesis_NOT_validated_replay','source':'https://x.com/Tesla/status/2110913438293647789','source_interval_frames':[0,418],'time_basis':'original CFR video; exact PTS mapping research/ramp_source_frame_pts.json','frame_rate':[24000,1001],'ramp_arc_length_cm':length,'release_time_s':9.75,'release_time_status':'interpolation seed, not contact measurement; observed complete projection gap at frame241','roll_angle_deg':-180,'roll_sign_status':'chosen for clockwise half-roll in front-facing camera; verify rendered projection before acceptance','landing_time_s':13.25,'landing_time_status':'occluded interpolation assumption; cannot certify first tire contact','world_units':'cm','gravity_not_simulated':True,'authority':'one native LevelSequence transform track per object','quaternion_policy':'dense continuous unwrapped Euler pitch170->180 with roll0->-180; no shortest-path slerp and no additional revolution','suspension':'not reconstructed; wheel centers fixed relative to body','not_a_physics_validation':True},indent=2),encoding='utf-8')
print('Wrote 419 explicit hypothesis poses and ramp centerline')
