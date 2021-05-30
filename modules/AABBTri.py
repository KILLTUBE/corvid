from .Vector3 import Vector3

class AABB:
    def __init__(self, center: Vector3, size=8):
        self.size = size
        self.center = center
        self.extents = (Vector3(self.size, -self.size, -self.size) - Vector3(-self.size, self.size, self.size)) / 2
    
class Tri:
    def __init__(self, p0: Vector3, p1: Vector3, p2: Vector3):
        self.p0, self.p1, self.p2 = p0, p1, p2
    
    def center(self):
        return (self.p1 + self.p2 + self.p3) / 3
    
    def normal(self):
        u = self.p1 - self.p0
        v = self.p2 - self.p0
        return u.cross(v)

    # based on https://gdbooks.gitbooks.io/3dcollisions/content/Chapter4/aabb-triangle.html
    def intersects(self, box: AABB):
        # align the tri to the box
        v0 = self.p0 - box.center
        v1 = self.p1 - box.center
        v2 = self.p2 - box.center
    
        e = box.extents

        f0 = v1 - v0
        f1 = v2 - v1
        f2 = v0 - v2

        u0 = Vector3(1.0, 0.0, 0.0)
        u1 = Vector3(0.0, 1.0, 0.0)
        u2 = Vector3(0.0, 0.0, 1.0)

        # compute 9 axes
        axis_u0_f0 = u0.cross(f0)
        axis_u0_f1 = u0.cross(f1)
        axis_u0_f2 = u0.cross(f2)

        axis_u1_f0 = u1.cross(f0)
        axis_u1_f1 = u1.cross(f1)
        axis_u1_f2 = u1.cross(f2)

        axis_u2_f0 = u2.cross(f0)
        axis_u2_f1 = u2.cross(f1)
        axis_u2_f2 = u2.cross(f2)

        # test an axis
        def T(axis: Vector3):
            p0 = v0.dot(axis)
            p1 = v1.dot(axis)
            p2 = v2.dot(axis)

            r = e.x * abs(u0.dot(axis)) + e.y * abs(u1.dot(axis)) + e.z * abs(u2.dot(axis))
        
            if max(-max(p0, p1, p2), min(p0, p1, p2)) > r:
                return True
            return False
        
        # test each of 9 axes
        if T(axis_u0_f0) or T(axis_u0_f1) or T(axis_u0_f2) or T(axis_u1_f0) or T(axis_u1_f1) or T(axis_u1_f2) or T(axis_u2_f0) or T(axis_u2_f1) or T(axis_u2_f2):
            print("9 axes")
            return False
        
        # test with conceptual normals
        if T(u0) or T(u1) or T(u2):
            print("normals")
            return False
        
        # test with triangle's normal
        if T(self.normal()):
            print("normal")
            return False

        return True
