# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import absolute_import, division, print_function

import numpy as np
from astropy import wcs

from ..wcs_utils import convert_world_coordinates
from ..array_utils import iterate_over_celestial_slices, pad_edge_1


def map_coordinates(image, coords, **kwargs):

    # In the built-in scipy map_coordinates, the values are defined at the
    # center of the pixels. This means that map_coordinates does not
    # correctly treat pixels that are in the outer half of the outer pixels.
    # We solve this by extending the array, updating the pixel coordinates,
    # then getting rid of values that were sampled in the range -1 to -0.5
    # and n to n - 0.5.

    from scipy.ndimage import map_coordinates as scipy_map_coordinates

    if image.ndim == 2:
        ny, nx = image.shape

        image = pad_edge_1(image)

        values = scipy_map_coordinates(image, coords + 1, **kwargs)

        reset = ((coords[0] < -0.5) | (coords[0] > ny - 0.5) |
                 (coords[1] < -0.5) | (coords[1] > nx - 0.5))
        values[reset] = kwargs.get('cval', 0.)

        return values
    else:
        # don't worry about those tricksy edge pixels, just give up...
        return scipy_map_coordinates(image, coords, **kwargs)


def get_input_pixels(wcs_in, wcs_out, shape_out):
    """
    Get the pixel coordinates of the pixels in an array of shape ``shape_out``
    in the input WCS.
    """

    # TODO: for now assuming that coordinates are spherical, not
    # necessarily the case. Also assuming something about the order of the
    # arguments.

    # Generate pixel coordinates of output image
    # reversed because numpy and wcs index in opposite directions
    # z,y,x if ::1
    # x,y,z if ::-1
    pixels_out = np.indices(shape_out)[::-1].astype('float')

    # Convert output pixel coordinates to pixel coordinates in original image
    # (using pixel centers).
    # x,y,z
    args = tuple(pixels_out) + (0,)
    out_world = wcs_out.wcs_pix2world(*args)

    args = tuple(out_world[:2]) + (wcs_out.celestial, wcs_in.celestial)
    xw_in, yw_in = convert_world_coordinates(*args)

    xp_in, yp_in = wcs_in.celestial.wcs_world2pix(xw_in, yw_in, 0)

    input_pixels = [xp_in, yp_in,]
    if pixels_out[0].ndim == 3:
        zw_out = out_world[2]
        zp_in = wcs_in.sub([wcs.WCSSUB_SPECTRAL]).wcs_world2pix(zw_out.ravel(),
                                                                0)[0].reshape(zw_out.shape)
        input_pixels += [zp_in]
    elif pixels_out[0].ndim > 3:
        raise ValueError(">3 dimensional cube")

    # x,y,z
    retval = np.array(input_pixels)
    assert retval.shape == (len(shape_out),)+tuple(shape_out)
    return retval

def _reproject(array, wcs_in, wcs_out, shape_out, order=1):
    """
    Reproject data with celestial axes to a new projection using interpolation.
    """

    # Make sure image is floating point
    array = np.asarray(array, dtype=float)

    # For now, assume axes are independent in this routine

    # Check that WCSs are equivalent
    if (wcs_in.naxis == wcs_out.naxis and np.any(wcs_in.wcs.axis_types !=
                                                 wcs_out.wcs.axis_types)):
        raise ValueError("The input and output WCS are not equivalent")

    if len(shape_out)>=3 and (shape_out[0] != array.shape[0]):
        # do full 3D interpolation
        xp_in, yp_in, zp_in = get_input_pixels(wcs_in, wcs_out,
                                               shape_out)
        coordinates = np.array([zp_in.ravel(), yp_in.ravel(), xp_in.ravel()])
        bad_data = ~np.isfinite(array)
        array[bad_data] = 0
        array_new = map_coordinates(array, coordinates, order=order,
                                    cval=np.nan,
                                    mode='constant').reshape(shape_out)

    else:

        # We create an output array with the required shape, then create an array
        # that is in order of [rest, lat, lon] where rest is the flattened
        # remainder of the array. We then operate on the view, but this will change
        # the original array with the correct shape.

        array_new = np.zeros(shape_out)

        xp_in = yp_in = None

        # Loop over slices and interpolate
        for slice_in, slice_out in iterate_over_celestial_slices(array,
                                                                 array_new,
                                                                 wcs_in):

            if xp_in is None:  # Get position of output pixel centers in input image
                xp_in, yp_in = get_input_pixels(wcs_in.celestial,
                                                wcs_out.celestial,
                                                slice_out.shape)
                coordinates = np.array([yp_in.ravel(), xp_in.ravel()])

            slice_out[:,:] = map_coordinates(slice_in,
                                             coordinates,
                                             order=order, cval=np.nan,
                                             mode='constant'
                                             ).reshape(slice_out.shape)

    return array_new, (~np.isnan(array_new)).astype(float)
