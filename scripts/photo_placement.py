"""Orient an extruded photo facade into its mapped building footprint."""
import math


def facade_heading(front, footprint):
    a, b = front
    center = [(a[i] + b[i]) / 2 for i in range(2)]
    heading = math.atan2(-(b[1] - a[1]), b[0] - a[0])
    points = footprint[:-1] if footprint[0] == footprint[-1] else footprint
    # Source photo models face local -Z and extend behind the facade in +Z.
    # Front-edge ordering alone does not identify the interior side.
    interior = [sum(p[i] for p in points) / len(points) for i in range(2)]
    inward = math.sin(heading) * (interior[0] - center[0]) + math.cos(heading) * (interior[1] - center[1])
    if abs(inward) < .1:
        raise ValueError('Front facade has no unambiguous mapped interior side')
    return heading + (math.pi if inward < 0 else 0)
