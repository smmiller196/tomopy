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
Module for pre-processing tasks.

:Author: Doga Gursoy
:Organization: Argonne National Laboratory

"""

from __future__ import absolute_import, division, print_function

import numpy as np
import pywt
import tomopy.const as const
import logging
import os
import ctypes
from scipy.ndimage import filters
import tomopy.multiprocess as mp


__docformat__ = 'restructuredtext en'
__all__ = ['normalize',
           'stripe_removal',
           'phase_retrieval',
           'zinger_removal',
           'median_filter',
           'circular_roi',
           'focus_region',
           'correct_air']


# Get the path and import the C-shared library.
try:
    if os.name == 'nt':
        libpath = os.path.join(
            os.path.dirname(__file__), 'lib/libtomopy_prep.pyd')
        libtg = ctypes.CDLL(os.path.abspath(libpath))
    else:
        libpath = os.path.join(
            os.path.dirname(__file__), 'lib/libtomopy_prep.so')
        libtg = ctypes.CDLL(os.path.abspath(libpath))
except OSError as e:
    pass


def normalize(data, white, dark, cutoff=None, ind=None):
    """
    Normalize raw projection data with
    the white field projection data.

    Parameters
    ----------
    data : ndarray
        3-D tomographic data.

    white : ndarray
        2-D white field projection data.

    dark : ndarray
        2-D dark field projection data.

    cutoff : scalar
        Permitted maximum vaue of the normalized data.

    Returns
    -------
    data : ndarray
        Normalized data.
    """
    # Calculate average white and dark fields for normalization.
    white = white.mean(axis=0)
    dark = dark.mean(axis=0)

    # Avoid zero division in normalization
    denom = white - dark
    denom[denom == 0] = 1e-6

    if ind is None:
        ind = np.arange(0, data.shape[0])
    for m in ind:
        proj = data[m, :, :]
        proj = np.divide(proj-dark, denom)
        if cutoff is not None:
            proj[proj > cutoff] = cutoff
        data[m, :, :] = proj


def stripe_removal(
        data, level=None, wname='db5',
        sigma=2, pad=True):
    """
    Remove stripes from sinogram data using
    the Fourier-Wavelet based method.

    Parameters
    ----------
    data : ndarray
        3-D tomographic data.

    level : scalar
        Number of DWT levels.

    wname : str
        Type of wavelet filter.

    sigma : scalar
        Damping parameter in Fourier space.

    Returns
    -------
    output : ndarray
        Corrected data.

    References
    ----------
    - `Optics Express, Vol 17(10), 8567-8591(2009) \
    <http://www.opticsinfobase.org/oe/abstract.cfm?uri=oe-17-10-8567>`_
    """
    # Find the higest level possible.
    if level is None:
        size = np.max(data.shape)
        level = int(np.ceil(np.log2(size)))

    # pad temp image.
    dx, nslices, dy = data.shape
    nx = dx
    if pad:
        nx = dx + dx / 8

    xshft = int((nx - dx) / 2.)
    sli = np.zeros((nx, dy), dtype='float32')

    ind = np.arange(0, data.shape[1])
    for n in ind:
        sli[xshft:dx + xshft, :] = data[:, n, :]

        # Wavelet decomposition.
        cH = []
        cV = []
        cD = []
        for m in range(level):
            sli, (cHt, cVt, cDt) = pywt.dwt2(sli, wname)
            cH.append(cHt)
            cV.append(cVt)
            cD.append(cDt)

        # FFT transform of horizontal frequency bands.
        for m in range(level):
            # FFT
            fcV = np.fft.fftshift(np.fft.fft(cV[m], axis=0))
            my, mx = fcV.shape

            # Damping of ring artifact information.
            y_hat = (np.arange(-my, my, 2, dtype='float') + 1) / 2
            damp = 1 - np.exp(-np.power(y_hat, 2) / (2 * np.power(sigma, 2)))
            fcV = np.multiply(fcV, np.transpose(np.tile(damp, (mx, 1))))

            # Inverse FFT.
            cV[m] = np.real(np.fft.ifft(np.fft.ifftshift(fcV), axis=0))

        # Wavelet reconstruction.
        for m in range(level)[::-1]:
            sli = sli[0:cH[m].shape[0], 0:cH[m].shape[1]]
            sli = pywt.idwt2((sli, (cH[m], cV[m], cD[m])), wname)

        data[:, n, :] = sli[xshft:dx + xshft, 0:dy]


def phase_retrieval(
        data, psize=1e-4, dist=50,
        energy=20, alpha=1e-4, pad=True):
    """
    Perform single-material phase retrieval
    using projection data.

    Parameters
    ----------
    data : ndarray
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    psize : scalar
        Detector pixel size in cm.

    dist : scalar
        Propagation distance of x-rays in cm.

    energy : scalar
        Energy of x-rays in keV.

    alpha : scalar, optional
        Regularization parameter.

    pad : bool, optional
        Applies pad for Fourier transform. For quick testing
        you can use False for faster results.

    Returns
    -------
    phase : ndarray
        Retrieved phase.

    References
    ----------
    - `J. of Microscopy, Vol 206(1), 33-40, 2001 \
    <http://onlinelibrary.wiley.com/doi/10.1046/j.1365-2818.2002.01010.x/abstract>`_
    """

    # Compute the filter.
    H, xshft, yshft, prj = paganin_filter(
        data, psize, dist, energy, alpha, pad)

    nprojs, dx, dy = data.shape  # dx:slices

    ind = np.arange(0, data.shape[0])
    for m in ind:
        proj = data[m, :, :]

        if pad:
            prj[xshft:dx+xshft, yshft:dy+yshft] = proj
            fproj = np.fft.fft2(prj)
            filtproj = np.multiply(H, fproj)
            tmp = np.real(np.fft.ifft2(filtproj)) / np.max(H)
            proj = tmp[xshft:dx+xshft, yshft:dy+yshft]

        elif not pad:
            fproj = np.fft.fft2(proj)
            filtproj = np.multiply(H, fproj)
            proj = np.real(np.fft.ifft2(filtproj)) / np.max(H)
        data[m, :, :] = proj


def paganin_filter(data, psize, dist, energy, alpha, pad):
    """
    Calculates Paganin-type filter.

    Parameters
    ----------
    data : ndarray
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    psize : scalar
        Detector pixel size in cm.

    dist : scalar
        Propagation distance of x-rays in cm.

    energy : scalar
        Energy of x-rays in keV.

    alpha : scalar, optional
        Regularization parameter.

    pad : bool, optional
        Applies pad for Fourier transform. For quick testing
        you can use False for faster results.

    Returns
    -------
    phase : ndarray
        Paganin filter.

    References
    ----------
    - `J. of Microscopy, Vol 206(1), 33-40, 2001 \
    <http://onlinelibrary.wiley.com/doi/10.1046/j.1365-2818.2002.01010.x/abstract>`_
    """
    nprojs, dx, dy = data.shape  # dx:slices, dy:pixels
    wavelen = 2*const.PI*const.PLANCK_CONSTANT*const.SPEED_OF_LIGHT/energy

    if pad:
        # Find pad values.
        val = np.mean((data[:, :, 0] + data[:, :, dy-1])/2)

        # Fourier pad in powers of 2.
        padpix = np.ceil(const.PI*wavelen*dist/psize**2)

        nx = pow(2, np.ceil(np.log2(dx + padpix)))
        ny = pow(2, np.ceil(np.log2(dy + padpix)))
        xshft = int((nx-dx)/2.)
        yshft = int((ny-dy)/2.)

        # Template pad image.
        prj = val * np.ones((nx, ny), dtype='float32')

    elif not pad:
        nx, ny = dx, dy
        xshft, yshft, prj = None, None, None
        prj = np.ones((dx, dy), dtype='float32')

    # Sampling in reciprocal space.
    indx = (1/((nx-1)*psize)) * np.arange(-(nx-1)*0.5, nx*0.5)
    indy = (1/((ny-1)*psize)) * np.arange(-(ny-1)*0.5, ny*0.5)
    du, dv = np.meshgrid(indy, indx)
    w2 = np.square(du) + np.square(dv)

    # Filter in Fourier space.
    H = 1 / (wavelen*dist*w2 / (4*const.PI)+alpha)
    H = np.fft.fftshift(H)
    return H, xshft, yshft, prj


def circular_roi(data, ratio=1, val=None):
    """
    Apply circular mask to projection data.

    Parameters
    ----------
    data : ndarray, float32
        3-D reconstructed data with dimensions:
        [projections, slices, pixels]

    ratio : scalar, int
        Ratio of the circular mask's diameter in pixels
        to the number of reconstructed image pixels
        (i.e., the dimension of the images).

    val : scalar, int
        Value for the masked region.

    Returns
    -------
    output : ndarray
        Masked data.
    """
    nprojs = data.shape[0]
    nslices = data.shape[1]
    npixels = data.shape[2]

    if nslices < npixels:
        ind1 = nslices
        ind2 = npixels
    else:
        ind1 = npixels
        ind2 = nslices

    # Apply circular mask.
    rad1 = ind1/2
    rad2 = ind2/2
    y, x = np.ogrid[-rad1:rad1, -rad2:rad2]
    mask = x*x+y*y > ratio*ratio*rad1*rad2
    if val is None:
        val = np.mean(data[:, ~mask])
    for m in range(nprojs):
        data[m, mask] = val


def focus_region(
        data, xcoord=0, ycoord=0,
        dia=256, center=None, pad=False, corr=True):
    """
    Uses only a portion of the sinogram for reconstructing
    a circular region of interest (ROI).

    Note: Only valid for 0-180 degree span data.

    Parameters
    ----------
    data : ndarray
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    xcoord, ycoord : scalar
        X- and Y-coordinates of the center
        location of the circular ROI.

    dia : scalar
        dia of the circular ROI.

    center : scalar
        Center of rotation of the original dataset.

    pad : bool, optional
        True if the original sinogram size is preserved.

    corr : bool, optional
        True if the correct_drift is
        applied after ROI selection.

    Returns
    -------
    roi : ndarray
        Modified ROI data.
    """
    nprojs = data.shape[0]
    npixels = data.shape[2]

    if center is None:
        center = npixels/2.

    rad = np.sqrt(xcoord*xcoord + ycoord*ycoord)
    alpha = np.arctan2(xcoord, ycoord)

    l1 = center - dia/2
    l2 = center - dia/2 + rad

    dx, dy, dz = data.shape
    roi = np.ones((dx, dy, dia), dtype='float32')
    if pad:
        roi = np.ones((dx, dy, dz), dtype='float32')

    delphi = const.PI/nprojs
    for m in range(nprojs):
        ind1 = np.ceil(np.cos(alpha-m * delphi) * (l2-l1)+l1)
        ind2 = np.floor(np.cos(alpha-m * delphi) * (l2-l1)+l1+dia)

        if ind1 < 0:
            ind1 = 0
        if ind2 < 0:
            ind2 = 0
        if ind1 > npixels:
            ind1 = npixels
        if ind2 > npixels:
            ind2 = npixels

        arr = np.expand_dims(data[m, :, ind1:ind2], axis=0)
        if pad:
            if corr:
                roi[m, :, ind1:ind2] = correct_air(arr, air=5)
            else:
                roi[m, :, ind1:ind2] = arr
        else:
            if corr:
                roi[m, :, 0:(ind2-ind1)] = correct_air(arr, air=5)
            else:
                roi[m, :, 0:(ind2-ind1)] = arr

        # New center
        if not pad:
            center = npixels/2.
    return roi, center


def median_filter(data, size=3, axis=0):
    """
    Apply median filter to data.

    Parameters
    ----------
    data : ndarray
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    size : scalar
        The size of the filter.

    axis : scalar
        Define the axis of data for filtering.
        0: projections, 1:sinograms, 2:pixels

    Returns
    -------
    output : ndarray
        Median filtered data.
    """

    if axis == 0:
        ind = np.arange(0, data.shape[0])
        for m in ind:
            data[m, :, :] = filters.median_filter(
                data[m, :, :], (size, size))
    elif axis == 1:
        ind = np.arange(0, data.shape[1])
        for m in ind:
            data[:, m, :] = filters.median_filter(
                data[:, m, :], (size, size))
    elif axis == 2:
        ind = np.arange(0, data.shape[2])
        for m in ind:
            data[:, :, m] = filters.median_filter(
                data[:, :, m], (size, size))


def zinger_removal(data, dif=1000, size=3):
    """
    Zinger removal.

    Parameters
    ----------
    data : ndarray
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    dif : scalar
        Threshold for difference of fileterd
        and unfiltered counts to cut zingers.

    size : scalar
        Median filter size.

    Returns
    -------
    output : ndarray
        Zinger removed data.
    """
    mask = np.zeros((1, data.shape[1], data.shape[2]))

    ind = np.arange(0, data.shape[0])
    for m in ind:
        tmp = filters.median_filter(data[m, :, :], (size, size))
        mask = ((data[m, :, :]-tmp) >= dif).astype(int)
        data[m, :, :] = tmp*mask + data[m, :, :]*(1-mask)


def correct_air(data, air=10):
    """
    Corrects for drifts in the sinogram.

    It normalizes sinogram such that the left and
    the right boundaries are set to one and
    all intermediate values between the boundaries
    are normalized linearly. It can be used if white
    field is absent.

    Parameters
    ----------
    data : ndarray, float32
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    air : scalar, int32
        number of pixels at each boundaries that
        the white field will be approximated
        for normalization.

    Returns
    -------
    output : ndarray
        Normalized data.
    """

    nprojs = np.array(data.shape[0], dtype='int32')
    nslices = np.array(data.shape[1], dtype='int32')
    npixels = np.array(data.shape[2], dtype='int32')

    if air <= 0:
        return data

    # Call C function.
    c_float_p = ctypes.POINTER(ctypes.c_float)
    libtg.correct_air.restype = ctypes.POINTER(ctypes.c_void_p)
    libtg.correct_air(
        data.ctypes.data_as(c_float_p),
        ctypes.c_int(nprojs), ctypes.c_int(nslices),
        ctypes.c_int(npixels), ctypes.c_int(air))
    return data


def apply_padding(data, npad=None, val=0.):
    """
    Applies padding to each projection data.

    Parameters
    ----------
    data : ndarray, float32
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    npad : scalar, int32
        New dimension of the projections
        after padding.

    val : scalar, float32
        Pad value.

    Returns
    -------
    padded : ndarray
        Padded data.
    """
    nprojs = np.array(data.shape[0], dtype='int32')
    nslices = np.array(data.shape[1], dtype='int32')
    npixels = np.array(data.shape[2], dtype='int32')

    # Set default parameters.
    if npad is None:
        npad = np.ceil(npixels * np.sqrt(2))
    elif npad < npixels:
        npad = npixels

    if npad < npixels:
        return data

    if not isinstance(npad, np.int32):
        npad = np.array(npad, dtype='int32')

    padded = val * np.ones((nprojs, nslices, npad), dtype='float32')

    # Call C function.
    c_float_p = ctypes.POINTER(ctypes.c_float)
    libtg.apply_padding.restype = ctypes.POINTER(ctypes.c_void_p)
    libtg.apply_padding(
        data.ctypes.data_as(c_float_p),
        ctypes.c_int(nprojs), ctypes.c_int(nslices),
        ctypes.c_int(npixels), ctypes.c_int(npad),
        padded.ctypes.data_as(c_float_p))
    return padded


def downsample2d(data, level=1):
    """
    Downsample the slices by binning.

    Parameters
    ----------
    data : ndarray, float32
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    level : scalar, int32
        Downsampling level. For example level=2
        means, the sinogram will be downsampled by 4,
        and level=3 means upsampled by 8.

    Returns
    -------
    output : ndarray
        Downsampled 3-D tomographic data with dimensions:
        [projections, slices/level^2, pixels]
    """
    nprojs = np.array(data.shape[0], dtype='int32')
    nslices = np.array(data.shape[1], dtype='int32')
    npixels = np.array(data.shape[2], dtype='int32')
    level = np.array(level, dtype='int32')

    if level < 0:
        return data

    binsize = np.power(2, level)
    downdat = np.zeros(
        (nprojs, nslices, npixels/binsize),
        dtype='float32')

    # Call C function.
    c_float_p = ctypes.POINTER(ctypes.c_float)
    libtg.downsample2d.restype = ctypes.POINTER(ctypes.c_void_p)
    libtg.downsample2d(
        data.ctypes.data_as(c_float_p),
        ctypes.c_int(nprojs), ctypes.c_int(nslices),
        ctypes.c_int(npixels), ctypes.c_int(level),
        downdat.ctypes.data_as(c_float_p))
    return downdat


def downsample3d(data, level=1):
    """
    Downsample the slices and pixels by binning.

    Parameters
    ----------
    data : ndarray, float32
        3-D tomographic data with dimensions:
        [projections, slices, pixels]

    level : scalar, int32
        Downsampling level. For example level=2
        means, the sinogram will be downsampled by 4,
        and level=3 means upsampled by 8.

    Returns
    -------
    downdat : ndarray
        Downsampled 3-D tomographic data with dimensions:
        [projections, slices/level^2, pixels/level^2]
    """
    nprojs = np.array(data.shape[0], dtype='int32')
    nslices = np.array(data.shape[1], dtype='int32')
    npixels = np.array(data.shape[2], dtype='int32')
    level = np.array(level, dtype='int32')

    if level < 0:
        return data

    binsize = np.power(2, level)
    downdat = np.zeros(
        (nprojs, nslices/binsize, npixels/binsize),
        dtype='float32')

    # Call C function.
    c_float_p = ctypes.POINTER(ctypes.c_float)
    libtg.downsample3d.restype = ctypes.POINTER(ctypes.c_void_p)
    libtg.downsample3d(
        data.ctypes.data_as(c_float_p),
        ctypes.c_int(nprojs), ctypes.c_int(nslices),
        ctypes.c_int(npixels), ctypes.c_int(level),
        downdat.ctypes.data_as(c_float_p))
    return downdat