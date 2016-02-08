#!/usr/bin/env python
# coding: UTF-8
from __future__ import division

import numpy as np
from .knots import Knots

from .geometry import Geometry

class BSpline(object):
    def __init__(self, knots, control_points, geometry=Geometry()):
        self.degree = len(knots) - len(control_points) + 1
        self.control_points = np.array(control_points)
        self.geometry = geometry
        self.splines = list(get_splines(knots, control_points, self.geometry))

    def __call__(self, t):
        for s in self.splines:
            a,b = s.interval
            if a <= t <= b:
                return s(t)
        raise ValueError("Outside interval")

def get_bezier_knots(degree):
    knots = np.zeros(2*degree)
    knots[degree:] = 1
    return knots

def get_single_bspline(spline):
    return BSpline(knots=spline.knots, control_points=spline.control_points)

class Spline(object):
    def __init__(self, control_points, knots=None, geometry=Geometry()):
        self.control_points = np.array(control_points)
        self.degree = len(self.control_points) - 1
        self.data_dim = np.ndim(self.control_points[0])

        if knots is None:
            knots = get_bezier_knots(self.degree)
        self.knots = knots

        self.interval = knots[self.degree-1], knots[self.degree]

        self.geometry = geometry

    def __call__(self, t):
        t = np.array(t)
        kns = self.knots
        pts = self.control_points
        data_dim = self.data_dim # data dim to use for broadcasting

        time_shape = (1,)*len(np.shape(t)) # time shape to add for broadcasting
        # we put the time on the last index
        kns = np.reshape(self.knots, self.knots.shape + time_shape) # (K, 1)
        pts = np.reshape(self.control_points, self.control_points.shape + time_shape) # (K, D, 1)

        # reshape the coefficients using data dimension and possible time shape
        # for vectorial data, this amounts to the slice (:, np.newaxis,...)
        rcoeff_slice = (slice(None),) + (np.newaxis,)*data_dim + (Ellipsis,)

        degree = len(kns) - len(pts) + 1
        for i in range(degree):
            n = len(kns)//2
            diffs = kns[n:] - kns[:-n] # (K,1)
            # trick to handle cases of equal knots:
            diffs[diffs==0.] = np.finfo(kns.dtype).eps
            rcoeff = (t - kns[:-n])/diffs # (K,T)
            pts = self.geometry.geodesic(pts[:-1], pts[1:], rcoeff[rcoeff_slice]) # (K, D, 1), (K, 1, T)
            kns = kns[1:-1]

        result = pts[0] # (D, T)
        # put time first by permuting the indices; in the vector case, this is a standard permutation
        permutation = len(np.shape(t))*(data_dim,) + tuple(range(data_dim))
        return result.transpose(permutation) # (T, D)


def get_splines(knots, points, geometry):
    degree = len(knots) - len(points) + 1
    K = Knots(knots, degree)
    for k in range(K.nb_curves):
        kns = knots[k:k+2*degree]
        pts = points[k:k+degree+1]
        yield Spline(knots=kns, control_points=pts, geometry=geometry)
