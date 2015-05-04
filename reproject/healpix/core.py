"""
HEALPIX (Hierarchical Equal-Area and Isolatitude Pixelization) utility functions.

These are convenience functions that are thin wrappers around `healpy`
(http://code.google.com/p/healpy/) functionality.

See https://github.com/healpy/healpy/issues/129 and https://github.com/gammapy/gammapy/blob/master/gammapy/image/healpix.py
"""

from __future__ import print_function, division

import numpy as np

from astropy import units as u

from ..wcs_utils import convert_world_coordinates
from .utils import parse_coord_system

__all__ = ['healpix_to_image', 'image_to_healpix']




def healpix_to_image(healpix_data, coord_system_in, wcs_out, shape_out,
                     interp=True, nest=False):
    """
    Convert image in HEALPIX format to a normal FITS projection image (e.g.
    CAR or AIT).

    Parameters
    ----------
    healpix_data : `numpy.ndarray`
        HEALPIX data array
    coord_system_in : str or `~astropy.coordinates.BaseCoordinateFrame`
        The coordinate system for the input HEALPIX data, as an Astropy
        coordinate frame or corresponding string alias (e.g. ``'icrs'`` or
        ``'galactic'``)
    wcs_out : `~astropy.wcs.WCS`
        The WCS of the output array
    shape_out : tuple
        The shape of the output array
    nest : bool
        The order of the healpix_data, either nested or ring.  Stored in
        FITS headers in the ORDERING keyword.
    interp : bool
        Get the bilinear interpolated data?  If not, returns a set of neighbors

    Returns
    -------
    reprojected_data : `numpy.ndarray`
        HEALPIX image resampled onto the reference image
    """
    import healpy as hp

    # Look up lon, lat of pixels in reference system
    yinds, xinds = np.indices(shape_out)
    lon_out, lat_out = wcs_out.wcs_pix2world(xinds, yinds, 0)

    # Convert between celestial coordinates
    coord_system_in = parse_coord_system(coord_system_in)
    lon_in, lat_in = convert_world_coordinates(lon_out, lat_out, wcs_out, (coord_system_in, u.deg, u.deg))

    # Convert from lon, lat in degrees to colatitude theta, longitude phi,
    # in radians
    theta = np.radians(90. - lat_in)
    phi = np.radians(lon_in)

    # hp.ang2pix() raises an exception for invalid values of theta, so only
    # process values for which WCS projection gives non-nan value
    good = np.isfinite(theta)
    data = np.empty(theta.shape, healpix_data.dtype)
    data[~good] = np.nan

    if interp:
        data[good] = hp.get_interp_val(healpix_data, theta[good], phi[good], nest)
    else:
        npix = len(healpix_data)
        nside = hp.npix2nside(npix)
        ipix = hp.ang2pix(nside, theta[good], phi[good], nest)
        data[good] = healpix_data[ipix]

    return data


def image_to_healpix(data, wcs_in, coord_system_out,
                     nside, interp=True, nest=False):
    """
    Convert image in a normal WCS projection to HEALPIX format.

    Parameters
    ----------
    data : `numpy.ndarray`
        Input data array to reproject
    wcs_in : `~astropy.wcs.WCS`
        The WCS of the input array
    coord_system_out : str or `~astropy.coordinates.BaseCoordinateFrame`
        The target coordinate system for the HEALPIX projection, as an Astropy
        coordinate frame or corresponding string alias (e.g. ``'icrs'`` or
        ``'galactic'``)
    nest : bool
        The order of the healpix_data, either nested or ring.  Stored in
        FITS headers in the ORDERING keyword.
    interp : bool
        Get the bilinear interpolated data?  If not, returns a set of neighbors

    Returns
    -------
    reprojected_data : `numpy.ndarray`
        A HEALPIX array of values
    """
    import healpy as hp
    from scipy.ndimage import map_coordinates

    npix = hp.nside2npix(nside)

    if interp:
        raise NotImplementedError

    # Look up lon, lat of pixels in output system and convert colatitude theta
    # and longitude phi to longitude and latitude.
    theta, phi = hp.pix2ang(nside, np.arange(npix), nest)
    lon_out = np.degrees(phi)
    lat_out = 90. - np.degrees(theta)

    # Convert between celestial coordinates
    coord_system_out = parse_coord_system(coord_system_out)
    lon_in, lat_in = convert_world_coordinates(lon_out, lat_out, (coord_system_out, u.deg, u.deg), wcs_in)

    # Look up pixels in input system
    yinds, xinds = wcs_in.wcs_world2pix(lon_in, lat_in, 0)

    # Interpolate
    healpix_data = map_coordinates(data, [xinds, yinds],
                                   order=(3 if interp else 0),
                                   mode='constant', cval=np.nan)

    return healpix_data
