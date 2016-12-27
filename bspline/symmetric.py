
import numpy as np

from .geometry import Flat
from . import BSpline
from .boundary import make_boundaries


def cubic_spline(InterpolationClass, interpolation_points, boundaries=(None, None), geometry=Flat()):
    I = InterpolationClass(interpolation_points, make_boundaries(*boundaries), geometry)
    return I.compute_spline()

class Interpolator():
    max_iter = 500
    tolerance = 1e-12

    def __init__(self, interpolation_points, boundaries, geometry=Flat()):
        self.interpolation_points = interpolation_points
        self.boundaries = boundaries
        self.geometry = geometry
        self.size = len(self.interpolation_points)
        [boundary.initialize(self) for boundary in self.boundaries]
        self.postmortem = {}

    def compute_controls(self):
        """
        Main fixed point algorithm.
        """
        velocities = np.zeros_like(self.interpolation_points)
        for iter in range(self.max_iter):
            [boundary.enforce(velocities) for boundary in self.boundaries]
            qRs, qLs, delta = self.iterate(velocities)
            velocities[1:-1] += delta
            error = np.max(np.abs(delta))
            if error < self.tolerance:
                break
        self.postmortem['error'] = error
        self.postmortem['iterations'] = iter
        return qRs, qLs

    def compute_spline_control_points(self, qRs, qLs):
        """
        Produces a spline control points from the given control points
        in an array.
        """
        geo_shape = np.shape(self.interpolation_points[0])
        new_shape = (3*self.size-2,) + geo_shape
        all_points = np.zeros(new_shape)
        all_points[::3] = self.interpolation_points
        all_points[1::3] = qRs
        all_points[2::3] = qLs
        return all_points

    def get_knots(self):
        knots = np.arange(self.size, dtype='f').repeat(3)
        return knots

    def compute_spline(self):
        """
        Produces a spline object.
        """
        qRs, qLs = self.compute_controls()
        spline_control_points = self.compute_spline_control_points(qRs, qLs)
        return BSpline(control_points=spline_control_points,
                       knots=self.get_knots(),
                       geometry=self.geometry)

class Symmetric(Interpolator):
    def generate_controls(self, points, velocities):
        """
        Generate movements and control points.
        """
        for p, v in zip(points, velocities):
            g = self.geometry.redexp(p, v)
            control = self.geometry.action(g, p)
            yield g, control

    def iterate(self, velocities):
        gRs, qRs = list(zip(*self.generate_controls(self.interpolation_points[:-1], velocities[:-1])))
        gLs, qLs = list(zip(*self.generate_controls(self.interpolation_points[1:], -velocities[1:])))
        delta = np.zeros_like(velocities[1:-1])
        gen = zip(
            self.interpolation_points[1:-1],
            velocities[1:-1],
            gLs[:-1],
            qLs[1:],
            gRs[1:],
            qRs[:-1],
        )
        for i, (p, v, gL, qL, gR, qR) in enumerate(gen):
            delta[i] = self.geometry.log(p, self.geometry.action(gL, qL)) - self.geometry.log(p, self.geometry.action(gR, qR)) - 2*v
        return qRs, qLs, delta/4


class Riemann(Interpolator):
    def generate_controls(self, points, velocities):
        for P, V in zip(points, velocities):
            yield self.geometry.exp(P, V)

    def generate_logs(self, q1s, q2s):
        for q1, q2 in zip (q1s, q2s):
            yield self.geometry.log(q1, q2)

    def iterate(self, velocities):
        qRs = list(self.generate_controls(self.interpolation_points[:-1], velocities[:-1]))
        qLs = list(self.generate_controls(self.interpolation_points[1:], -velocities[1:]))
        wRs = self.generate_logs(qRs[1:], qLs[1:])
        wLs = self.generate_logs(qLs[:-1], qRs[:-1])
        gen = zip(
            self.interpolation_points[1:-1],
            velocities[1:-1],
            wRs,
            wLs,
        )
        delta = np.zeros_like(velocities[1:-1])
        for i, (P, V, wR, wL) in enumerate(gen):
            delta[i] = self.geometry.dexpinv(P, V, wR) - self.geometry.dexpinv(P, -V, wL) - 2*V
        return qRs, qLs, delta/4



