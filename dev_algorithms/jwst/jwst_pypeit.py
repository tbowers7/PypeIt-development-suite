
import os
import numpy as np
import scipy
from matplotlib import pyplot as plt
from astropy.stats import sigma_clipped_stats

from IPython import embed
# set environment variables
os.environ['CRDS_PATH'] = '/Users/joe/crds_cache/jwst_pub'
os.environ['CRDS_SERVER_URL'] = 'https://jwst-crds-pub.stsci.edu'
from matplotlib import pyplot as plt
from astropy.io import fits
from gwcs import wcstools


## JWST imports
# The calwebb_spec and spec3 pipelines
from jwst.pipeline import Spec2Pipeline
from jwst.pipeline import Spec3Pipeline
# individual steps
from jwst.assign_wcs import AssignWcsStep
from jwst.background import BackgroundStep
from jwst.imprint import ImprintStep
from jwst.msaflagopen import MSAFlagOpenStep
from jwst.extract_2d import Extract2dStep
from jwst.srctype import SourceTypeStep
from jwst.wavecorr import WavecorrStep
from jwst.flatfield import FlatFieldStep
from jwst.pathloss import PathLossStep
from jwst.barshadow import BarShadowStep
from jwst.photom import PhotomStep
from jwst.resample import ResampleSpecStep
from jwst.extract_1d import Extract1dStep
from jwst import datamodels
DO_NOT_USE = datamodels.dqflags.pixel['DO_NOT_USE']


# PypeIt imports
from jwst_utils import compute_diff, get_cuts, show_2dspec, get_jwst_slits
from pypeit.display import display
from pypeit.utils import inverse
from pypeit.core import findobj_skymask
from pypeit.core import skysub, coadd

det = 'nrs1'
disperser = 'G395M'
if 'PRISM' in disperser:
    # PRISM data
    rawpath_level2 = '/Users/joe/jwst_redux/redux/NIRSPEC_PRISM/01133_COM_CLEAR_PRISM/calwebb/Raw'
    output_dir = '/Users/joe/jwst_redux/redux/NIRSPEC_PRISM/01133_COM_CLEAR_PRISM/calwebb/output'

    # NIRSPEC 3-point dither
    # dither center
    scifile  = os.path.join(rawpath_level2, 'jw01133003001_0310x_00001_' + det + '_rate.fits')
    bkgfile1 = os.path.join(rawpath_level2, 'jw01133003001_0310x_00002_' + det + '_rate.fits')
    bkgfile2 = os.path.join(rawpath_level2, 'jw01133003001_0310x_00003_' + det + '_rate.fits')

    # dither offset
    #scifile  = os.path.join(rawpath_level2, 'jw01133003001_0310x_00003_' + det + '_rate.fits')
    #bkgfile1 = os.path.join(rawpath_level2, 'jw01133003001_0310x_00001_' + det + '_rate.fits')
    #bkgfile2 = os.path.join(rawpath_level2, 'jw01133003001_0310x_00002_' + det + '_rate.fits')
elif 'G395M' in disperser:
    # Use islit = 37 for nrs1
    # G395M data
    rawpath_level2 = '/Users/joe/jwst_redux/redux/NIRSPEC_ERO/02736_ERO_SMACS0723_G395MG235M/calwebb/Raw'
    output_dir = '/Users/joe/jwst_redux/redux/NIRSPEC_ERO/02736_ERO_SMACS0723_G395MG235M/calwebb/output'

    # NIRSPEC 3-point dither
    scifile = os.path.join(rawpath_level2, 'jw02736007001_03103_00001_' + det + '_rate.fits')
    bkgfile1 = os.path.join(rawpath_level2, 'jw02736007001_03103_00002_' + det + '_rate.fits')
    bkgfile2 = os.path.join(rawpath_level2, 'jw02736007001_03103_00003_' + det + '_rate.fits')


# Plot the 2d differnence image
rawscience, diff = compute_diff(scifile, bkgfile1, bkgfile2, )

#viewer_diff, ch_diff = display.show_image(diff.T, cuts=get_cuts(diff), chname='diff2d')
#viewer_sci,  ch_sci = display.show_image(sci.T, cuts=get_cuts(sci), chname='raw', wcs_match=True)
basename = os.path.basename(scifile).replace('rate.fits', '')

param_dict = {
    'bkg_subtract': {'skip': True},
    'master_background_mos': {'skip': True},
    'srctype': {'source_type':'EXTENDED'},
    'flat_field': {'save_interpolated_flat':True},
}


runflag = False
if runflag:
    spec2 = Spec2Pipeline(steps=param_dict)
    spec2.save_results = True
    spec2.output_dir = output_dir
    result = spec2(scifile)

# Read in the files
intflat_output_file = os.path.join(output_dir, basename + 'interpolatedflat.fits')
cal_output_file = os.path.join(output_dir, basename + 'cal.fits')
s2d_output_file = os.path.join(output_dir, basename + 's2d.fits')
# TESTING
#final2d = datamodels.open(s2d_output_file)
#intflat = None
final2d = datamodels.open(cal_output_file)
intflat = datamodels.open(intflat_output_file)
#islit = 10
islit = 37

show_2dspec(rawscience, final2d, islit, intflat=intflat, emb=False, clear=True)


slit_name = final2d.slits[islit].name
scale_fact = 1e9 # There images are in stupid units with very large numbers
science = np.array(final2d.slits[islit].data.T, dtype=float)/scale_fact
# TESTING!!  kludge the error by multiplying by a small number
#kludge_err = 0.1667
kludge_err = 0.28
err = kludge_err*np.array(final2d.slits[islit].err.T, dtype=float)/scale_fact
base_var = np.array(final2d.slits[islit].var_rnoise.T, dtype=float)/scale_fact**2

dq = np.array(final2d.slits[islit].dq.T, dtype=int)
waveimg = np.array(final2d.slits[islit].wavelength.T, dtype=float)

slit_wcs = final2d.slits[islit].meta.wcs
x, y = wcstools.grid_from_bounding_box(slit_wcs.bounding_box, step=(1, 1))
calra, caldec, calwave = slit_wcs(x, y)
ra = calra.T

gpm = np.logical_not(dq & DO_NOT_USE)
thismask = np.isfinite(science)
nanmask = np.logical_not(thismask)
science[nanmask]= 0.0
err[nanmask] = 0.0
sciivar = inverse(err**2)*gpm
base_var[nanmask] = 0.0
# Wave nanmask is different from data nanmask
nanmask_wave = np.logical_not(np.isfinite(waveimg))
wave_min = np.min(waveimg[np.logical_not(nanmask_wave)])
wave_max = np.max(waveimg[np.logical_not(nanmask_wave)])
nanmask_ra = np.logical_not(np.isfinite(ra))
ra_min = np.min(ra[np.logical_not(nanmask_ra)])
ra_max = np.max(ra[np.logical_not(nanmask_ra)])
waveimg[nanmask_wave] = 0.0
ra[nanmask_ra]=0.0

nspec, nspat = science.shape


slit_left, slit_righ = get_jwst_slits(thismask)
# Generate some tilts and a spatial image
tilts = np.zeros_like(waveimg)
tilts[np.isfinite(waveimg)] = (waveimg[np.isfinite(waveimg)] - wave_min)/(wave_max-wave_min)
# TODO Fix this spat_pix to make it increasing with pixel. For now don't use
spat_pix = (ra - ra_min)/(ra_max - ra_min)*(nspat-1)
spat_pix[nanmask_ra] = 0.0


trim_edg = (0,0)
boxcar_rad_pix = 8.0
fwhm = 2.0
bsp = 2.5
sn_gauss=3.0
nperslit = 2
no_poly=False
ncoeff = 5
snr_thresh = 5.0

# First pass sky-subtraction and object finding
initial_sky0 = np.zeros_like(science)
initial_sky0[thismask] = skysub.global_skysub(science, sciivar, tilts, thismask, slit_left, slit_righ,
                                              inmask = gpm, bsp=bsp, pos_mask=True, no_poly=no_poly, show_fit=True,
                                              trim_edg=trim_edg)
sobjs_slit0 = findobj_skymask.objs_in_slit(science-initial_sky0, sciivar, thismask, slit_left, slit_righ, inmask=gpm, ncoeff=ncoeff,
                                          snr_thresh=snr_thresh, show_peaks=True, show_trace=True,
                                          trim_edg=trim_edg,  fwhm=fwhm, boxcar_rad=boxcar_rad_pix, maxdev = 2.0, find_min_max=None,
                                          qa_title='objfind_QA_' + slit_name, nperslit=nperslit,
                                          objfindQA_filename=None, debug_all=False)
# Create skymask and perfrom second pass sky-subtraction and object finding
skymask = np.ones_like(thismask)
skymask[thismask] = findobj_skymask.create_skymask(sobjs_slit0, thismask,
                                                   slit_left, slit_righ,
                                                   trim_edg=trim_edg) #, box_rad_pix=boxcar_rad_pix,)
initial_sky = np.zeros_like(science)
initial_sky[thismask] = skysub.global_skysub(science, sciivar, tilts, thismask, slit_left, slit_righ,
                                             inmask = (gpm & skymask), bsp=bsp, pos_mask=True, no_poly=no_poly, show_fit=True,
                                             trim_edg=trim_edg)
sobjs_slit = findobj_skymask.objs_in_slit(science-initial_sky, sciivar, thismask, slit_left, slit_righ, inmask=gpm, ncoeff=ncoeff,
                                          snr_thresh=snr_thresh, show_peaks=True, show_trace=True,
                                          trim_edg=trim_edg,  fwhm=fwhm, boxcar_rad=boxcar_rad_pix, maxdev = 2.0, find_min_max=None,
                                          qa_title='objfind_QA_' + slit_name, nperslit=nperslit,
                                          objfindQA_filename=None, debug_all=False)

viewer, ch = display.show_image(science-initial_sky, cuts=get_cuts(science), chname='science', wcs_match=True)
display.show_slits(viewer, ch, slit_left, slit_righ, pstep=1, slit_ids=np.array([int(slit_name)]))
for spec in sobjs_slit:
    if spec.hand_extract_flag == False:
        color = 'orange'
    else:
        color = 'blue'
    display.show_trace(viewer, ch, spec.TRACE_SPAT, trc_name=spec.NAME, color=color)

#initial_sky = initial_sky*0.0
# Local sky subtraction and extraction
skymodel = initial_sky.copy()
objmodel = np.zeros_like(science)
ivarmodel = sciivar.copy()
extractmask = gpm.copy()
sobjs = sobjs_slit.copy()
# TODO Need to figure out what the count_scale is order to update the noise in the low-background regime.
skymodel[thismask], objmodel[thismask], ivarmodel[thismask], extractmask[thismask] = skysub.local_skysub_extract(
    science, sciivar, tilts, waveimg, initial_sky, thismask, slit_left, slit_righ, sobjs, ingpm = gpm,
    base_var = base_var, bsp = bsp, sn_gauss = sn_gauss, trim_edg=trim_edg, spat_pix=None, model_full_slit=True, model_noise=True, show_profile=True, show_resids=True, debug_bkpts=True)

n_bins = 50
sig_range = 7.0
binsize = 2.0 * sig_range / n_bins
bins_histo = -sig_range + np.arange(n_bins) * binsize + binsize / 2.0

xvals = np.arange(-10.0, 10, 0.02)
gauss = scipy.stats.norm(loc=0.0, scale=1.0)
gauss_corr = scipy.stats.norm(loc=0.0, scale=1.0)

chi = (science-objmodel-skymodel)*np.sqrt(ivarmodel)
chi = chi.flatten()
maskchi = extractmask.flatten()
sigma_corr, maskchi = coadd.renormalize_errors(chi, maskchi, max_corr = 20.0, title='jwst_sigma_corr', debug=True)

plt.plot(sobjs[0].OPT_WAVE,sobjs[0].OPT_COUNTS, drawstyle='steps-mid', color='black', label='optimal')
plt.plot(sobjs[0].OPT_WAVE,sobjs[0].OPT_COUNTS_SIG, drawstyle='steps-mid', color='red', label='optimal')
plt.plot(sobjs[0].BOX_WAVE,sobjs[0].BOX_COUNTS, drawstyle='steps-mid', color='green', label='boxcar')
plt.plot(sobjs[0].BOX_WAVE,sobjs[0].BOX_COUNTS_SIG, drawstyle='steps-mid', color='blue', label='boxcar')
plt.legend()
plt.show()


# Now play around with a PypeIt extraction



