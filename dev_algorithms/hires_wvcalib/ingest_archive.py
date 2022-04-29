

import os
import numpy as np
import jax
from jax import numpy as jnp
from jax import jit
import optax
import itertools
from tqdm.auto import trange
from astropy.table import Table
from pkg_resources import resource_filename
from matplotlib import pyplot as plt
from pypeit.spectrographs.util import load_spectrograph
from pypeit.core.wavecal import templates
from pypeit.core.wavecal import wvutils
from pypeit.core.fitting import robust_fit
from pypeit.core import coadd
from pypeit.core.wavecal import autoid, waveio, wv_fitting
from pypeit.core.wavecal.wvutils import  smooth_ceil_cont, xcorr_shift
from pypeit import utils
from astropy import table
from scipy import interpolate
from IPython import embed

@jit
def poly_transform_y2(theta, x1, wave2, y2, wave2_min, wave2_max):

    wave1 = wave2_min + (wave2_max - wave2_min)*jnp.polyval(theta, x1)
    y2_corr = jnp.interp(wave1, wave2, y2)
    return wave1, y2_corr

@jit
def zerolag_poly_corr(theta, x1, y1, wave2, y2,  wave2_min, wave2_max):

    """
    Utility function which is run by the differential evolution
    optimizer in scipy. These is the fucntion we optimize.  It is the
    zero lag cross-correlation coefficient of spectrum with a shift and
    stretch applied.

    Parameters
    ----------
    theta (float `numpy.ndarray`_):
        Function parameters to optmize over. theta[0] = shift, theta[1] = stretch
    y1 (float `numpy.ndarray`_):  shape = (nspec,)
        First spectrum which acts as the refrence
    y2 (float `numpy.ndarray`_):  shape = (nspec,)
        Second spectrum which will be transformed by a shift and stretch to match y1

    Returns
    -------
    corr_norm: float
        Negative of the zero lag cross-correlation coefficient (since we
        are miniziming with scipy.optimize). scipy.optimize will thus
        determine the shift,stretch that maximize the cross-correlation.

    """


    wave1, y2_corr = poly_transform_y2(theta, x1, wave2, y2, wave2_min, wave2_max)
    # Zero lag correlation
    corr_zero = jnp.sum(y1*y2_corr)
    corr_denom = jnp.sqrt(jnp.sum(y1*y1)*jnp.sum(y2_corr*y2_corr))
    corr_norm = corr_zero/corr_denom
    return -corr_norm


def xcorr_poly(wave1_in, inspec1, wave2, inspec2, smooth=1.0, percent_ceil=80.0, use_raw_arc=False,
               sigdetect = 10.0, fwhm = 4.0, debug=False, seed = 42):

    """ Determine the shift and stretch of inspec2 relative to inspec1.  This routine computes an initial
    guess for the shift via maximimizing the cross-correlation. It then performs a two parameter search for the shift and stretch
    by optimizing the zero lag cross-correlation between the inspec1 and the transformed inspec2 (shifted and stretched via
    wvutils.shift_and_stretch()) in a narrow window about the initial estimated shift. The convention for the shift is that
    positive shift means inspec2 is shifted to the right (higher pixel values) relative to inspec1. The convention for the stretch is
    that it is float near unity that increases the size of the inspec2 relative to the original size (which is the size of inspec1)

    Parameters
    ----------
    inspec1 : ndarray
        Reference spectrum
    inspec2 : ndarray
        Spectrum for which the shift and stretch are computed such that it will match inspec1
    cc_thresh: float, default = -1.0
        A number in the range [-1.0,1.0] which is the threshold on the
        initial cross-correlation coefficient for the shift/stretch.  If
        the value of the initial cross-correlation is < cc_thresh the
        code will just exit and return this value and the best shift.
        This is desirable behavior since the shif/stretch optimization
        is slow and this allows one to test how correlated the spectra
        are before attempting it, since there is little value in that
        expensive computation for spectra with little overlap. The
        default cc_thresh =-1.0 means shift/stretch is always attempted
        since the cross correlation coeficcient cannot be less than
        -1.0.
    smooth: float, default
        Gaussian smoothing in pixels applied to both spectra for the computations. Default is 5.0
    percent_ceil: float, default=90.0
        Apply a ceiling to the input spectra at the percent_ceil
        percentile level of the distribution of peak amplitudes.  This
        prevents extremely strong lines from completely dominating the
        cross-correlation, which can causes the cross-correlation to
        have spurious noise spikes that are not the real maximum.
    use_raw_arc: bool, default = False
        If this parameter is True the raw arc will be used rather than the continuum subtracted arc
    shift_mnmx: tuple of floats, default = (-0.05,0.05)
        Range to search for the shift in the optimization about the
        initial cross-correlation based estimate of the shift.  The
        optimization will search the window (shift_cc +
        nspec*shift_mnmx[0],shift_cc + nspec*shift_mnmx[1]) where nspec
        is the number of pixels in the spectrum
    stretch_mnmx: tuple of floats, default = (0.97,1.03)
        Range to search for the stretch in the optimization. The code
        may not work well if this range is significantly expanded
        because the linear approximation used to transform the arc
        starts to break down.
    seed: int or np.random.RandomState, optional, default = None
        Seed for scipy.optimize.differential_evolution optimizer. If not
        specified, the calculation will not be repeatable
    toler (float):
        Tolerance for differential evolution optimizaiton.
    debug = False
       Show plots to the screen useful for debugging.

    Returns
    -------
    success: int
        A flag indicating the exist status.  Values are:

          - success = 1, shift and stretch performed via sucessful
            optimization
          - success = 0, shift and stretch optimization failed
          - success = -1, initial x-correlation is below cc_thresh (see
            above), so shift/stretch optimization was not attempted

    shift: float
        the optimal shift which was determined.  If cc_thresh is set,
        and the initial cross-correlation is < cc_thresh,  then this
        will be just the cross-correlation shift
    stretch: float
        the optimal stretch which was determined.  If cc_thresh is set,
        and the initial cross-correlation is < cc_thresh,  then this
        will be just be 1.0
    cross_corr: float
        the value of the cross-correlation coefficient at the optimal
        shift and stretch. This is a number between zero and unity,
        which unity indicating a perfect match between the two spectra.
        If cc_thresh is set, and the initial cross-correlation is <
        cc_thresh, this will be just the initial cross-correlation
    shift_init:
        The initial shift determined by maximizing the cross-correlation
        coefficient without allowing for a stretch.  If cc_thresh is
        set, and the initial cross-correlation is < cc_thresh, this will
        be just the shift from the initial cross-correlation
    cross_corr_init:
        The maximum of the initial cross-correlation coefficient
        determined without allowing for a stretch.  If cc_thresh is set,
        and the initial cross-correlation is < cc_thresh, this will be
        just the initial cross-correlation

    """

    nspec1 = inspec1.size
    nspec2 = inspec2.size
    x1 = jnp.arange(nspec1, dtype=float)/float(nspec1-1)
    x2 = jnp.arange(nspec2, dtype=float)/float(nspec2-1)

    wave2_min, wave2_max = wave2.min(), wave2.max()

    y1 = jnp.fmax(jnp.array(smooth_ceil_cont(inspec1,smooth,percent_ceil=percent_ceil,use_raw_arc=use_raw_arc, sigdetect = sigdetect, fwhm = fwhm)), -10.0)
    y2 = jnp.fmax(jnp.array(smooth_ceil_cont(inspec2,smooth,percent_ceil=percent_ceil,use_raw_arc=use_raw_arc, sigdetect = sigdetect, fwhm = fwhm)), -10.0)


    #start_learning_rate = 5e-4
    start_learning_rate = 1e-3
    optimizer = optax.adam(start_learning_rate)


    # Initialize parameters of the model + optimizer.
    norder = 3

    # Random central wavelength noise
    wave1_min, wave1_max = wave1_in.min(), wave1_in.max()
    key = jax.random.PRNGKey(423)
    dwave1 = (wave1_max- wave1_min)/nspec1
    dwave = 10.0*dwave1*jax.random.normal(key, shape=(2,))
    wave1_min_guess, wave1_max_guess = wave1_min + dwave[0], wave1_max + dwave[1]
    wave1_guess = wave1_min_guess + x1*(wave1_max_guess - wave1_min_guess)
    params = jnp.polyfit(x1, (wave1_guess - wave2_min)/(wave2_max -wave2_min), norder)
    params_true = jnp.polyfit(x1, (wave1_in - wave2_min)/(wave2_max -wave2_min), norder)
    corr_true = -zerolag_poly_corr(params_true, x1, y1, wave2, y2, wave2_min, wave2_max)
    #params = jnp.polyfit(x2, wave2, norder)
    #params = jax.random.uniform(key, minval=0.0, maxval=0.1, shape=(norder+1,))

    # Vanilla optimizaton
    #opt_state = optimizer.init(params)

    nsteps =2000
    # Exponential decay of the learning rate.
    scheduler = optax.exponential_decay(init_value=start_learning_rate,transition_steps=nsteps, decay_rate=0.99)

    # Combining gradient transforms using `optax.chain`.
    gradient_transform = optax.chain(
        optax.clip_by_global_norm(1.0),  # Clip by the gradient by the global norm.
        optax.scale_by_adam(),  # Use the updates from adam.
        optax.scale_by_schedule(scheduler),  # Use the learning rate from the scheduler.
        # Scale updates by -1 since optax.apply_updates is additive and we want to descend on the loss.
        optax.scale(-1.0)
    )
    opt_state = gradient_transform.init(params)

    iterator = trange(nsteps, leave=True)
    losses = np.zeros(nsteps)

    best_loss = np.inf  # Models are only saved if they reduce the loss
    params_out = params.copy()
    for i in iterator:
        #losses[i] = zerolag_poly_corr(params, x1, y1, wave2, y2, wave2_min, wave2_max)
        losses[i], grads = jax.value_and_grad(zerolag_poly_corr, argnums=0, has_aux=False)(params, x1, y1, wave2, y2, wave2_min, wave2_max)
        if losses[i] < best_loss:
            params_out = params.copy()
            best_loss = losses[i]
        #grads = jax.grad(zerolag_poly_corr)(params, x1, y1, wave2, y2, wave2_min, wave2_max)
        iterator.set_description(
            'Loss: {:f}'.format(losses[i]) + ", Grads: {:5.3f},{:5.3f},{:5.3f},{:5.3f}, Best Loss: {:5.3f}".format(*grads, best_loss) + ", iter no: " + str(i))
        updates, opt_state = gradient_transform.update(grads, opt_state)
        #updates, opt_state = optimizer.update(grads, opt_state)
        params = optax.apply_updates(params, updates)

    if debug:
        wave1, y2_trans = poly_transform_y2(params_out, x1, wave2, y2, wave2_min, wave2_max)
        plt.figure(figsize=(14, 6))
        plt.plot(wave1, y1, 'k-', drawstyle='steps', label='inspec1, input spectrum')
        plt.plot(wave1, y2_trans, 'r-', drawstyle='steps', label='inspec2, polynomial transformed archive')
        plt.title('corr = {:5.3f}, corr_true={:5.3f}'.format(-best_loss, corr_true))
        plt.legend()
        plt.show()



def get_variable_dlam_wavegrid(lam_min, lam_max, wave_grid_fit, dwave_fit):

    lam_out = [lam_min]
    while lam_out[-1] < lam_max:
        lam_next = lam_out[-1] + np.interp(lam_out[-1], wave_grid_fit, dwave_fit)
        lam_out.append(lam_next)

    return np.array(lam_out, dtype=float)

# Read template file
templ_table_file = os.path.join(
    resource_filename('pypeit', 'data'), 'arc_lines',
    'hires', 'hires_templ.dat')
tbl = Table.read(templ_table_file, format='ascii')
nrows = len(tbl)

order_min = tbl['IOrder'].min()
order_max = 118

order_vec = np.arange(order_min, order_max +1, 1)
norders = order_vec.size

# Subset of orders in every file. Populated indicates whether a given order is populated
lambda_cen = np.zeros((norders, nrows))
ech_angle = np.zeros((norders, nrows))
populated = np.zeros((norders, nrows), dtype=bool)
XDISP_is_red = np.zeros((norders, nrows), dtype=bool)
binspec = np.zeros((norders, nrows), dtype=int)
det = np.zeros((norders, nrows), dtype=int)
xd_angle = np.zeros((norders, nrows))

bluest_order = np.zeros(nrows, dtype=int)
xd_angle_file = np.zeros(nrows)
ech_angle_file = np.zeros(nrows)
det_file = np.zeros(nrows)
XDISP_is_red_file = np.zeros(nrows, dtype=bool)

for irow in np.arange(nrows):
    this_order_vec_raw, this_wave, this_arc = templates.xidl_hires(
        os.path.join(os.getenv('HIRES_CALIBS'), 'ARCS', tbl[irow]['Name']), specbin=tbl[irow]['Rbin'])
    if irow == 0:
        nspec = this_wave.shape[1]
        wave = np.zeros((norders, nrows, nspec))
        arcspec = np.zeros((norders, nrows, nspec))
    else:
        assert this_wave.shape[1] == nspec
    # Restrict to what is labeled as good in the Table
    igood = (this_order_vec_raw >= tbl[irow]['IOrder']) & (this_order_vec_raw <= tbl[irow]['EOrder'])
    this_order_vec = this_order_vec_raw[igood]
    indx = this_order_vec - order_min
    populated[indx, irow] = True
    ech_angle[indx, irow] = tbl[irow]['ECH']
    xd_angle[indx, irow] = tbl[irow]['XDAng']
    XDISP_is_red[indx, irow] = tbl[irow]['XDISP'] == 'RED'
    binspec[indx, irow] =  tbl[irow]['Rbin']
    det[indx, irow] =  tbl[irow]['Chip']

    wave[indx, irow, :] = this_wave[igood, :]
    arcspec[indx, irow, :] = this_arc[igood, :]
    lambda_cen[indx, irow] = np.median(this_wave[igood, :], axis=1)
    # file specific
    bluest_order[irow] = this_order_vec[-1]
    ech_angle_file[irow] = tbl[irow]['ECH']
    xd_angle_file[irow] = tbl[irow]['XDAng']
    det_file[irow] = tbl[irow]['Chip']
    XDISP_is_red_file[irow] = tbl[irow]['XDISP'] == 'RED'

#all_dlam = []
#all_lam = []
#all_orders = []

color_tuple = ('green', 'cyan', 'magenta', 'blue', 'darkorange', 'yellow', 'dodgerblue', 'purple',
               'lightgreen', 'cornflowerblue')
colors = itertools.cycle(color_tuple)

use_unknowns = True
line_lists_all = waveio.load_line_lists(['ThAr'])
line_lists = line_lists_all[np.where(line_lists_all['ion'] != 'UNKNWN')]
unknwns = line_lists_all[np.where(line_lists_all['ion'] == 'UNKNWN')]
tot_line_list = table.vstack([line_lists, unknwns]) if use_unknowns else line_lists
spectrograph = load_spectrograph('keck_hires')
par = spectrograph.default_pypeit_par()['calibrations']['wavelengths']
n_final = 4

# Plot lam vs dlam/lam for each order
debug_all=False
for indx, iorder in enumerate(order_vec):
    if np.any(populated[indx, :]):
        nsolns = np.sum( populated[indx, :])
        this_ech = ech_angle[indx, populated[indx, :]]
        this_xd_angle = xd_angle[indx, populated[indx, :]]
        this_lambda_cen = lambda_cen[indx, populated[indx, :]]
        this_wave = wave[indx, populated[indx, :], :]
        this_arc = arcspec[indx, populated[indx, :], :]

        this_dwave = np.zeros_like(this_wave)
        for ii, iwave in enumerate(this_wave):
            this_dwave[ii, :] = wvutils.get_delta_wave(iwave, (iwave > 0.0))

        # Now try a fit
        med_dlam = np.median(this_dwave[this_wave > 1.0])
        fit = robust_fit(this_wave.flatten(), this_dwave.flatten(), 3, maxiter=25, maxdev = 0.10*med_dlam, groupbadpix=True)
        wave_grid_fit, wave_grid_fit_mid, dsamp = wvutils.get_wave_grid(this_wave.T,wave_method='log10')
        dwave_fit = fit.eval(wave_grid_fit)
        gpm = fit.bool_gpm.copy()
        gpm.resize(this_wave.shape)

        for ii, iwave in enumerate(this_wave):
            this_color=next(colors)
            this_gpm = gpm[ii, :]
            plt.plot(iwave[this_gpm], this_dwave[ii, this_gpm], marker='o', markersize=1.0, mfc=this_color,
                     fillstyle='full',  linestyle='None', zorder=1)
            plt.plot(iwave[np.logical_not(this_gpm)], this_dwave[ii, np.logical_not(this_gpm)], marker='o',
                     markersize=2.0, mfc='red', fillstyle='full', zorder=3, linestyle='None')

        plt.plot(wave_grid_fit, dwave_fit, color='black', label='fit', zorder=10)
        plt.title(f'order={iorder}', fontsize=14)
        plt.legend()
        plt.show()
        lam_min, lam_max = this_wave[gpm].min(), this_wave[gpm].max()
        wave_grid = get_variable_dlam_wavegrid(lam_min, lam_max, wave_grid_fit, dwave_fit)
        nspec_tmpl = wave_grid.shape[0]
        # TESTING
        #dwave_chk = wvutils.get_delta_wave(wave_grid, (wave_grid > 0.0))
        #plt.plot(wave_grid, dwave_chk, color='red', label='our new grid')
        #plt.plot(wave_grid_fit, dwave_fit, color='black', label='fit')
        #plt.title('dwave compared to our fit')
        #plt.legend()
        #plt.show()
        tmpl_iord = np.zeros((nsolns, nspec_tmpl))
        gpm_tmpl = np.zeros((nsolns, nspec_tmpl), dtype=bool)
        # Interpolate our arcs onto the new grid
        for ii, iwave in enumerate(this_wave):
            in_gpm = this_arc[ii, :] != 0.0
            tmpl_iord[ii, :] = interpolate.interp1d(iwave[in_gpm], this_arc[ii, in_gpm], kind='cubic', bounds_error=False, fill_value=-1e10)(wave_grid)
            gpm_tmpl[ii, :] = tmpl_iord[ii, :] > -1e9
            #plt.plot(iwave[in_gpm], this_arc[ii, in_gpm], color=next(colors), alpha=0.7)
            plt.plot(wave_grid[gpm_tmpl[ii, :]], tmpl_iord[ii, gpm_tmpl[ii, :]], color=next(colors), alpha=0.7)

        plt.show()
        sn_smooth_npix = 1 # Should not matter since we use uniform weights
        wave_grid_in = np.repeat(wave_grid[:, np.newaxis], nsolns, axis=1)
        ivar_tmpl_iord = utils.inverse(np.abs(tmpl_iord) + 10.0)
        wave_grid_mid, wave_grid_stack, arcspec_tmpl, _, arcspec_tmpl_gpm = coadd.combspec(
            wave_grid_in, tmpl_iord.T, ivar_tmpl_iord.T, gpm_tmpl.T, sn_smooth_npix,
            wave_method='iref',  ref_percentile=70.0, maxiter_scale=5, sigrej_scale=3.0, scale_method='median',
            sn_min_polyscale=2.0, sn_min_medscale=0.5, const_weights=True, maxiter_reject=5, sn_clip=30.0, lower=5.0, upper=5.0,
            debug=debug_all, debug_scale=debug_all, show_scale=debug_all, show=True, verbose=True)

        all_patt_dict = {}
        detections = {}
        wv_calib = {}

        for slit, iwave in enumerate(this_wave):
            print('Working on soln={:d}'.format(slit))
            # Trim the template to the relevant range. Hack this for now
            #itmpl = (wave_grid_mid >= 0.999*iwave.min()) & (wave_grid_mid <= 1.001*iwave.max())
            #arcspec_tmpl_trim = arcspec_tmpl[itmpl]
            #wave_grid_mid_trim = wave_grid_mid[itmpl]
            #arc_in_pad = np.zeros_like(arcspec_tmpl_trim)
            in_gpm = this_arc[slit, :] != 0.0
            #npix = np.sum(in_gpm)
            #arc_in_pad[:npix] = this_arc[slit, in_gpm]
            xcorr_poly(this_wave[slit, in_gpm], this_arc[slit, in_gpm], wave_grid_mid, arcspec_tmpl, smooth=1.0, percent_ceil=50.0, use_raw_arc=False,
                       sigdetect=10.0, fwhm=4.0, debug=True, seed=42)

#            detections[str(slit)], spec_cont_sub, all_patt_dict[str(slit)] = autoid.reidentify(
#                arc_in_pad, arcspec_tmpl_trim, wave_grid_mid,  tot_line_list, par['nreid_min'],
#                cc_thresh=par['cc_thresh'], match_toler=par['match_toler'], cc_local_thresh=par['cc_local_thresh'],
#                nlocal_cc=par['nlocal_cc'], nonlinear_counts=1e10,
#                sigdetect=par['sigdetect'], fwhm=par['fwhm'], debug_peaks=True, debug_xcorr=True, debug_reid=True)

            # Check if an acceptable reidentification solution was found
            #if not all_patt_dict[str(slit)]['acceptable']:
            #    wv_calib[str(slit)] = None
            #    continue

            #final_fit = wv_fitting.fit_slit(spec_cont_sub, all_patt_dict[str(slit)], detections[str(slit)],
            #                             tot_line_list, match_toler=par['match_toler'],func=par['func'], n_first=par['n_first'],
            #                             sigrej_first=par['sigrej_first'], n_final=n_final,sigrej_final=par['sigrej_final'])

            #autoid.arc_fit_qa(final_fit, title='Silt: {}'.format(str(slit)))


#        dlam = []
#        lam = []
#        for iwave in this_wave:
#            dlam += list(wvutils.get_delta_wave(iwave, np.ones_like(iwave,dtype=bool)))
#            lam += iwave.tolist()
#            #xlam += ((np.array(iwave) - np.array(iwave).min())/(np.array(iwave).max() - np.array(iwave).min())).tolist()
#        plt.plot(lam, 3.0e5*np.array(dlam)/np.array(lam), '.', label=f'order={iorder}')
#        plt.legend()
#        plt.show()

 #       all_dlam += dlam
 #       all_lam += lam
 #       all_orders += [iorder]*len(lam)


#plt.plot(all_lam, 3.0e5*np.array(all_dlam)/np.array(all_lam), '.')
#plt.legend()
#plt.show()

# Plot the central wavelength vs echelle angle order by order
for indx, iorder in enumerate(order_vec):
    if np.any(populated[indx, :]):
        this_ech = ech_angle[indx, populated[indx, :]]
        this_xd_angle = xd_angle[indx, populated[indx, :]]
        this_lambda_cen = lambda_cen[indx, populated[indx, :]]
        plt.plot(this_ech, this_lambda_cen, 'k.', label=f'order={iorder}')
        plt.legend()
        plt.show()


for xdisp in ['UV', 'RED']:
    for idet in [1,2,3]:
        indx = (XDISP_is_red_file == (xdisp == 'RED')) & (det_file == idet)
        plt.plot(xd_angle_file[indx], bluest_order[indx], 'k.', label=f'XDISP={xdisp}, det={idet}')
        plt.legend()
        plt.show()





