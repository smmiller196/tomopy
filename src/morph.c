// Copyright (c) 2015, UChicago Argonne, LLC. All rights reserved.

// Copyright 2015. UChicago Argonne, LLC. This software was produced 
// under U.S. Government contract DE-AC02-06CH11357 for Argonne National 
// Laboratory (ANL), which is operated by UChicago Argonne, LLC for the 
// U.S. Department of Energy. The U.S. Government has rights to use, 
// reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR 
// UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR 
// ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is 
// modified to produce derivative works, such modified software should 
// be clearly marked, so as not to confuse it with the version available 
// from ANL.

// Additionally, redistribution and use in source and binary forms, with 
// or without modification, are permitted provided that the following 
// conditions are met:

//     * Redistributions of source code must retain the above copyright 
//       notice, this list of conditions and the following disclaimer. 

//     * Redistributions in binary form must reproduce the above copyright 
//       notice, this list of conditions and the following disclaimer in 
//       the documentation and/or other materials provided with the 
//       distribution. 

//     * Neither the name of UChicago Argonne, LLC, Argonne National 
//       Laboratory, ANL, the U.S. Government, nor the names of its 
//       contributors may be used to endorse or promote products derived 
//       from this software without specific prior written permission. 

// THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS 
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
// FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago 
// Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, 
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
// BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; 
// LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER 
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT 
// LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN 
// ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE 
// POSSIBILITY OF SUCH DAMAGE.

#include "morph.h"


DLL void 
apply_padding(
    float* data, int dx, int dy, int dz, 
    int npad, float* out) 
{
    int n, m, i, j, k, iproj, ipproj;
    int pad_width = (int)(npad-dz)/2;
    
    for (m = 0; m < dx; m++) {
        iproj = m * (dz * dy);
        ipproj = pad_width + m * (npad * dy);

        for (n = 0; n < dy; n++) {
            i = iproj + n * dz;
            j = ipproj + n * npad;

            for (k = 0; k < dz; k++) {
                out[j+k] = data[i+k];
            }
        }
    }
}


DLL void 
downsample2d(
    float* data, int dx, int dy, int dz,
    int level, float* out) 
{
    int m, n, k, i, p, iproj, ind;
    int binsize;
    
    binsize = pow(2, level);
    
    dz /= binsize;

    for (m = 0, ind = 0; m < dx; m++) 
    {
        iproj = m * (dz * dy);
            
        for (n = 0; n < dy; n++) 
        {
            i = iproj + n * dz;
            for (k = 0; k < dz; k++) 
            {
                for (p = 0; p < binsize; p++) 
                {
                    out[i+k] += data[ind]/binsize;
                    ind++;
                }
            }
        }
    }
}


DLL void 
downsample3d(
    float* data, int dx, int dy, int dz,
    int level, float* out) 
{
    int m, n, k, i, p, q, iproj, ind;
    int binsize, binsize2;
    
    binsize = pow(2, level);
    binsize2 = binsize * binsize;
    
    dy /= binsize;
    dz /= binsize;

    for (m = 0, ind = 0; m < dx; m++) 
    {
        iproj = m * (dz * dy);
        for (n = 0; n < dy; n++) 
        {
            i = iproj + n * dz;
            for (q = 0; q < binsize; q++) 
            {
                for (k = 0; k < dz; k++) 
                { 
                    for (p = 0; p < binsize; p++) 
                    {
                        out[i+k] += data[ind]/binsize2;
                        ind++;
                    }
                }
            }
        }
    }
}


DLL void 
upsample2d(
    float* data, int dy, int dz,
    int level, float* out) {

    long m, n, k, i, p, q, iproj, ind;
    int binsize;
    
    binsize = pow(2, level);
    
    for (m = 0, ind = 0; m < dy; m++) 
    {
        iproj = m * (dz * dz);
        for (n = 0; n < dz; n++) 
        {
            i = iproj + n * dz;
            for (q = 0; q < binsize; q++) 
            {
                for (k = 0; k < dz; k++) 
                {
                    for (p = 0; p < binsize; p++) 
                    {
                        out[ind] = data[i+k];
                        ind++;
                    }
                }
            }
        }
    }
}


DLL void 
upsample3d(
    float* data, int dy, int dz,
    int level, float* out) {

    int m, n, k, i, p, q, j, iproj, ind;
    int binsize;

    binsize = pow(2, level);

    for (m = 0, ind = 0; m < dy; m++) 
    {
        iproj = m * (dz * dz);
        for (j = 0; j < binsize; j++) 
        {
            for (n = 0; n < dz; n++) 
            {
                i = iproj + n * dz;
                for (q = 0; q < binsize; q++) 
                {
                    for (k = 0; k < dz; k++) 
                    {
                        for (p = 0; p < binsize; p++) 
                        {
                            out[ind] = data[i+k];
                            ind++;
                        }
                    }
                }
            }
        }
    }
}