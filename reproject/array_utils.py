import numpy as np
from functools import reduce


def iterate_over_celestial_slices(array_in, array_out, wcs):
    """
    Given two arrays with the same number of dimensions, iterate over the
    celestial slices in each.

    The index of the celestial axes should match between the two arrays and
    will be taken from ``wcs``. The iterator returns views, so these can be
    used to modify the original arrays.

    Parameters
    ----------
    array_in : `~numpy.ndarray`
        The input array for the reprojection
    array_out : `~numpy.ndarray`
        The output array for the reprojection
    wcs : `~astropy.wcs.WCS`
        The WCS for the input array (only used to identify the celestial axes).

    Returns
    -------
    slice_in : `~numpy.ndarray`
        A view to a celestial slice in ``array_in``
    slice_out : `~numpy.ndarray`
        A view to the corresponding slice in ``array_out``
    """

    # First put lng/lat as first two dimensions in WCS/last two in Numpy
    if wcs.wcs.lng == 1 and wcs.wcs.lat == 0:
        array_in_view = array_in.swapaxes(-1, -2)
        array_out_view = array_out.swapaxes(-1, -2)
    else:
        array_in_view = array_in.swapaxes(-2, -1 - wcs.wcs.lat).swapaxes(-1, -1 - wcs.wcs.lng)
        array_out_view = array_out.swapaxes(-2, -1 - wcs.wcs.lat).swapaxes(-1, -1 - wcs.wcs.lng)

    # Flatten remaining dimensions to make it easier to loop over
    from operator import mul

    nx_in = array_in_view.shape[-1]
    ny_in = array_in_view.shape[-2]
    n_remaining_in = reduce(mul, array_in_view.shape, 1) // nx_in // ny_in

    nx_out = array_out_view.shape[-1]
    ny_out = array_out_view.shape[-2]
    n_remaining_out = reduce(mul, array_out_view.shape, 1) // nx_out // ny_out

    if n_remaining_in != n_remaining_out:
        raise ValueError("Number of non-celestial elements should match")

    array_in_view = array_in_view.reshape(n_remaining_in, ny_in, nx_in)
    array_out_view = array_out_view.reshape(n_remaining_out, ny_out, nx_out)

    for slice_index in range(n_remaining_in):
        yield array_in_view[slice_index], array_out_view[slice_index]


def pad_edge_1(array):
    try:
        return np.pad(array, 1, mode='edge')
    except:  # numpy < 1.7 workaround
        new_array = np.zeros((array.shape[0] + 2,
                              array.shape[1] + 2),
                             dtype=array.dtype)
        new_array[1:-1, 1:-1] = array
        new_array[0, 1:-1] = new_array[1, 1:-1]
        new_array[-1, 1:-1] = new_array[-2, 1:-1]
        new_array[:, 0] = new_array[:, 1]
        new_array[:, -1] = new_array[:, -2]
        return new_array
