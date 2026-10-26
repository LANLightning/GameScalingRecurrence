"""Minecraft coordinates: +Y up; yaw 0 points +Z, yaw +90 points -X; pitch +90 points down."""
import math

def look_vector(yaw_deg,pitch_deg):
    y,p=map(math.radians,(yaw_deg,pitch_deg))
    return (-math.sin(y)*math.cos(p),-math.sin(p),math.cos(y)*math.cos(p))

def angles_to_target(eye,target):
    x,y,z=(b-a for a,b in zip(eye,target));horizontal=math.hypot(x,z)
    if horizontal==0 and y==0:raise ValueError('Eye and target coincide.')
    return math.degrees(math.atan2(-x,z)),math.degrees(math.atan2(-y,horizontal))

def movement_world(keys,yaw_deg,speed=4.317):
    y=math.radians(yaw_deg);forward=int('W' in keys)-int('S' in keys);right=int('D' in keys)-int('A' in keys)
    scale=speed/max(1,math.hypot(forward,right))
    return (scale*(-math.sin(y)*forward-math.cos(y)*right),0.0,scale*(math.cos(y)*forward-math.sin(y)*right))

def target_in_local_ground_frame(position,target,yaw_deg):
    dx,dy,dz=(b-a for a,b in zip(position,target));y=math.radians(yaw_deg)
    return {'right':-math.cos(y)*dx-math.sin(y)*dz,'up':dy,'forward':-math.sin(y)*dx+math.cos(y)*dz}

if __name__=='__main__':
    assert look_vector(0,0)==(0.0,0.0,1.0)
    assert angles_to_target((0,0,0),(0,0,10))==(0.0,0.0)
    assert math.isclose(angles_to_target((0,0,0),(-10,0,0))[0],90)
    assert movement_world(['W'],0)==(0.0,0.0,4.317)
    print('Coordinate conventions verified. This is a transform, not collision/pathfinding or game-state access.')
