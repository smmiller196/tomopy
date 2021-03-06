#!/usr/bin/env python
# -*- coding: utf-8 -*-

# #########################################################################
# Copyright (c) 2015, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2015. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# #########################################################################

"""
Module for data size morphing functions.
"""

from __future__ import absolute_import, division, print_function

import numpy as np
import pywt
import os
import ctypes
import tomopy.misc.mproc as mp
from scipy.ndimage import filters
from tomopy.prep import correct_air
import logging
logger = logging.getLogger(__name__)


__author__ = "Doga Gursoy"
__copyright__ = "Copyright (c) 2015, UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['apply_pad',
           'focus_region']


PI = 3.14159265359


def _import_shared_lib(lib_name):
    """
    Get the path and import the C-shared library.
    """
    try:
        if os.name == 'nt':
            libpath = os.path.join('lib', lib_name + '.pyd')
            return ctypes.CDLL(os.path.abspath(libpath))
        else:
            libpath = os.path.join('lib', lib_name + '.so')
            return ctypes.CDLL(os.path.abspath(libpath))
    except OSError as e:
        logger.warning('OSError: Shared library missing.')


LIB_TOMOPY = _import_shared_lib('libtomopy')


def apply_pad(arr, npad=None, val=0.):
    """
    Extend size of a 3D array by padding with specified values.

    Parameters
    ----------
    arr : ndarray
        Arbitrary 3D array.
    npad : int, optional
        New dimensions after padding.
    val : float, optional
        Pad value.

    Returns
    -------
    ndarray
        Padded 3D array.
    """
    dx, dy, dz = arr.shape
    if npad is None:
        npad = np.ceil(dz * np.sqrt(2))
    elif npad < dz:
        npad = dz

    npad = np.array(npad, dtype='int32')
    out = val * np.ones((dx, dy, npad), dtype='float32')

    c_float_p = ctypes.POINTER(ctypes.c_float)
    LIB_TOMOPY.apply_padding.restype = ctypes.POINTER(ctypes.c_void_p)
    LIB_TOMOPY.apply_padding(
        arr.ctypes.data_as(c_float_p),
        ctypes.c_int(dx), ctypes.c_int(dy),
        ctypes.c_int(dz), ctypes.c_int(npad),
        out.ctypes.data_as(c_float_p))
    return out


def focus_region(
        data, dia, xcoord=0, ycoord=0,
        center=None, pad=False, corr=True):
    """
    Trims sinogram for reconstructing a circular region of interest (ROI).

    Note: Only valid for 0-180 degree span data.

    Parameters
    ----------
    data : ndarray
        3D Tomographic data.
    xcoord, ycoord : float, optional
        x- and y-coordinates of the center location of the circular
        ROI in reconstruction image.
    dia : float, optional
        Diameter of the circular ROI.
    center : float, optional
        Rotation axis location of the tomographic data.
    pad : bool, optional
        If True, extend the size of the projections by padding with zeros.
    corr : bool, optional
        If True, correct_air is applied after data is trimmed.

    Returns
    -------
    ndarray
        Modified 3D tomographic data.
    float
        New rotation axis location.
    """
    dx, dy, dz = data.shape
    ind = np.arange(0, dx)

    if center is None:
        center = dz / 2.

    rad = np.sqrt(xcoord * xcoord + ycoord * ycoord)
    alpha = np.arctan2(xcoord, ycoord)
    l1 = center - dia / 2
    l2 = center - dia / 2 + rad

    roi = np.ones((dx, dy, dia), dtype='float32')
    if pad:
        roi = np.ones((dx, dy, dz), dtype='float32')

    delphi = PI / dx
    for m in ind:
        ind1 = np.ceil(np.cos(alpha - m * delphi) * (l2 - l1) + l1)
        ind2 = np.floor(np.cos(alpha - m * delphi) * (l2 - l1) + l1 + dia)

        if ind1 < 0:
            ind1 = 0
        if ind2 < 0:
            ind2 = 0
        if ind1 > dz:
            ind1 = dz
        if ind2 > dz:
            ind2 = dz

        arr = np.expand_dims(data[m, :, ind1:ind2], axis=0)
        if pad:
            if corr:
                roi[m, :, ind1:ind2] = correct_air(arr.copy(), air=5)
            else:
                roi[m, :, ind1:ind2] = arr
        else:
            if corr:
                roi[m, :, 0:(ind2 - ind1)] = correct_air(arr, air=5)
            else:
                roi[m, :, 0:(ind2 - ind1)] = arr
        if not pad:
            center = dz / 2.
    return roi, center
