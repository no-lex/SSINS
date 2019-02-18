from __future__ import absolute_import, division, print_function

"""
The incoherent noise spectrum class.
"""

import numpy as np
from scipy.special import erfcinv
import os
import warnings
import pickle
from hera_qm import UVFlag


class INS(UVFlag):
    """
    Defines the incoherent noise spectrum (INS) class.
    """

    def __init__(self, input, history='', label='', weights=None, order=0):

        """
        init function for the INS class. Can set the attributes manually, or
        read some in using the read_paths dictionary. The keys for read_paths
        are the attribute names as strings, while the values are paths to
        numpy loadable binary files (pickle is used for masked arrays). The init
        function will calculate the Calculated Attributes (see below).

        Args:
            data: The data which will be assigned to the data attribute. (Required)
            Nbls: The number of baselines that went into each element of the
                  data array. (Required)
            freq_array: The frequencies (in hz) that describe the data, as found
                        in a UVData object. (Required)
            pols: The polarizations present in the data, in the order of the data array.
            flag_choice: The flag choice used in the original SS object.
            vis_units: The units for the visibilities.
            obs: The obsid for the data.
            outpath: The base directory for data outputs.
            match_events: A list of events found by the filter in the MF class.
                          Usually not assigned initially.
            match_hists: Histograms describing the match_events.
                         Usually not assigned initially.
            chsq_events: Events found by the chisq_test in the MF class.
                         Usually not assigned initially.
            chisq_hists: Histograms describing the chisq events.
                         Usually not assigned initially.
            read_paths: A dictionary that can be used to read in a match filter,
                        rather than passing attributes to init or constructing
                        from an SS object. The keys are the attributes to be
                        passed in, while the values are paths to files that
                        contain the attribute data.
            samp_thresh_events: Events using the samp_thresh_test in the MF class.
                                Usually not assigned initially.
            order: The order of polynomial fit for each frequency channel when
                   calculating the mean-subtracted spectrum. Setting order=0
                   just calculates the mean in each frequency channel.
            coeff_write: An option to write out the coefficients of the polynomial
                         fit to each frequency channel.
        """

        super(INS, self).__init__(input, mode='metric', copy_flags=False,
                                  waterfall=False, history='', label='')
        if self.type is 'baseline':
            # Set the metric array to the data array without the spw axis
            self.metric_array = input.data_array[:, 0]
            self.weights_array = np.logical_not(input.data_array.mask)
            super(INS, self).to_waterfall(method='mean')

        self.order = order
        self.metric_ms = self.mean_subtract()
        """The mean-subtracted data."""

    def mean_subtract(self, f=slice(None)):

        """
        A function which calculated the mean-subtracted spectrum from the
        regular spectrum. A spectrum made from a perfectly clean observation
        will be standardized (written as a z-score) by this operation.

        Args:
            f: The frequency slice over which to do the calculation. Usually not
               set by the user.
            order: The order of the polynomial fit for each frequency channel, by LLSE.
                   Setting order=0 just calculates the mean.
            coeff_write: Option to write out the polynomial fit coefficients for
                         each frequency channel when this function is run.

        Returns:
            MS (masked array): The mean-subtracted data array.
        """

        # This constant is determined by the Rayleigh distribution, which
        # describes the ratio of its rms to its mean
        C = 4 / np.pi - 1
        if not self.order:
            MS = (self.data[:, :, f] / self.data[:, :, f].mean(axis=0) - 1) * np.sqrt(self.Nbls[:, :, f] / C)
        else:
            MS = np.zeros_like(self.data[:, :, f])
            # Make sure x is not zero so that np.polyfit can proceed without nans
            x = np.arange(1, self.data.shape[0] + 1)
            for i in range(self.data.shape[-1]):
                y = self.data[:, 0, f, i]
                # Only iterate over channels that are not fully masked
                good_chans = np.where(np.logical_not(np.all(y.mask, axis=0)))[0]
                # Create a subarray mask of only those good channels
                good_data = y[:, good_chans]
                # Find the set of unique masks so that we can iterate over only those
                unique_masks, mask_inv = np.unique(good_data.mask, axis=1,
                                                   return_inverse=True)
                for k in range(unique_masks.shape[1]):
                    # Channels which share a mask
                    chans = np.where(mask_inv == k)[0]
                    coeff = np.ma.polyfit(x, good_data[:, chans], self.order)
                    if coeff_write:
                        with open('%s/%s_ms_poly_coeff_order_%i_%s.npy' %
                                  (self.outpath, self.obs, self.order, self.pols[i]), 'wb') as file:
                            pickle.dump(coeff, file)
                    mu = np.sum([np.outer(x**(self.order - k), coeff[k]) for k in range(self.order + 1)],
                                axis=0)
                    MS[:, 0, good_chans[chans], i] = (good_data[:, chans] / mu - 1) * np.sqrt(self.Nbls[:, 0, f, i][:, good_chans[chans]] / C)

        return(MS)

    def save(self, sig_thresh=None):
        """
        Writes out relevant data products.

        Args:
            sig_thresh: Can give a little sig_thresh tag at the end of the
                        filename if desired. (Technically this does not have
                        to be an integer, so you can tag it however you want.)
        """
        tags = ['match', 'chisq', 'samp_thresh']
        tag = ''
        if sig_thresh is not None:
            tag += '_%s' % sig_thresh
        for subtag in tags:
            if len(getattr(self, '%s_events' % (subtag))):
                tag += '_%s' % subtag

        for string in ['arrs', 'metadata']:
            if not os.path.exists('%s/%s' % (self.outpath, string)):
                os.makedirs('%s/%s' % (self.outpath, string))

        for attr in ['data', 'data_ms', 'Nbls']:
            with open('%s/arrs/%s_%s_INS_%s%s.npym' %
                      (self.outpath, self.obs, self.flag_choice, attr, tag), 'wb') as f:
                pickle.dump(getattr(self, attr), f)
        for attr in ['counts', 'bins']:
            np.save('%s/arrs/%s_%s_INS_%s%s.npy' %
                    (self.outpath, self.obs, self.flag_choice, attr, tag),
                    getattr(self, attr))

        for attr in ['freq_array', 'pols', 'vis_units']:
            if hasattr(self, attr):
                np.save('%s/metadata/%s_%s.npy' % (self.outpath, self.obs, attr),
                        getattr(self, attr))

    def _read(self, read_paths):
        """
        Reads in attributes from numpy loadable (or depicklable) files.

        Args:
            read_paths: A dictionary whose keys are the attributes to be read in
                        and whose values are paths to files where the attribute
                        data is written.
        """

        for arg in ['data', 'Nbls', 'freq_array']:
            assert arg in read_paths,\
                'You must supply a path to a numpy loadable %s file for read_paths entry' % (arg)
            setattr(self, arg, np.load(read_paths[arg]))
        if not len(self.data.mask.shape):
            data.mask = np.zeros(self.data.shape, dtype=bool)
        for attr in ['pols', 'vis_units']:
            if attr not in read_paths:
                warnings.warn('In order to use Catalog_Plot.py, please supply\
                               path to numpy loadable %s attribute for read_paths entry' % (attr))
            else:
                setattr(self, attr, np.load(read_paths[attr]))
