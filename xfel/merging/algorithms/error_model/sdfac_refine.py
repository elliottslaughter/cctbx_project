from __future__ import division
from six.moves import range
from scitbx.array_family import flex
import math, sys

from xfel.merging.algorithms.error_model.error_modeler_base import error_modeler_base
from xfel import compute_normalized_deviations, apply_sd_error_params

from xfel.cxi.postrefinement_legacy_rs import unpack_base
class sdfac_parameterization(unpack_base):
  def __getattr__(YY,item):
    if item=="SDFAC" : return YY.reference[0]
    if item=="SDB"   : return YY.reference[1]
    if item=="SDADD" : return YY.reference[2]
    if item=="SDFACSQ" : return YY.reference[0]**2
    if item=="SDBSQ"   : return YY.reference[1]**2
    if item=="SDADDSQ" : return YY.reference[2]**2
    raise AttributeError(item)

  def show(YY, out):
    print >> out, "sdfac: %8.5f, sdb: %8.5f, sdadd: %8.5f"%(YY.SDFAC, YY.SDB, YY.SDADD)

from scitbx.simplex import simplex_opt
class simplex_minimizer(object):
  """Class for refining sdfac, sdb and sdadd"""
  def __init__(self, values, parameterization, data, indices, bins, seed = None, log=None):
    """
    @param values parameterization of the SD terms
    @param data ISIGI dictionary of unmerged intensities
    @param indices array of miller indices to refine against
    @param bins array of flex.bool object specifying the bins to use to calculate the functional
    @param log Log to print to (none for stdout)
    """
    if log is None:
      log = sys.stdout
    self.log = log
    self.data = data
    self.intensity_bin_selections = bins
    self.indices = indices
    self.parameterization = parameterization
    self.n = 3
    self.x = flex.double([values.SDFAC, values.SDB, values.SDADD])
    self.starting_simplex = []
    if seed is None:
      random_func = flex.random_double
    else:
      print >> self.log, "Using random seed %d"%seed
      mt = flex.mersenne_twister(seed)
      random_func = mt.random_double

    for i in range(self.n+1):
      self.starting_simplex.append(random_func(self.n))

    self.optimizer = simplex_opt( dimension = self.n,
                                  matrix    = self.starting_simplex,
                                  evaluator = self,
                                  tolerance = 1e-1)
    self.x = self.optimizer.get_solution()

  def target(self, vector):
    """ Compute the functional by first applying the current values for the sd parameters
    to the input data, then computing the complete set of normalized deviations and finally
    using those normalized deviations to compute the functional."""

    values = self.parameterization(vector)

    if values.SDFAC < 0 or values.SDB < 0 or values.SDADD < 0:
      f = 1e6
    else:
      data = self.apply_sd_error_params(self.data, values)
      all_sigmas_normalized = compute_normalized_deviations(data, self.indices)

      f = 0
      for bin in self.intensity_bin_selections:
        binned_normalized_sigmas = all_sigmas_normalized.select(bin)
        n = len(binned_normalized_sigmas)
        if n == 0: continue
        # weighting scheme from Evans, 2011
        w = math.sqrt(n)
        # functional is weight * (1-rms(normalized_sigmas))^s summed over all intensitiy bins
        f += w * ((1-math.sqrt(flex.mean(binned_normalized_sigmas*binned_normalized_sigmas)))**2)

    print >> self.log, "f: % 12.1f,"%f,
    values.show(self.log)
    return f

  def apply_sd_error_params(self, data, values):
    return apply_sd_error_params(data, values.SDFAC, values.SDB, values.SDADD)

  def get_refined_params(self):
    return self.parameterization(self.x)

class sdfac_refine(error_modeler_base):
  def __init__(self, scaler):
    error_modeler_base.__init__(self, scaler)
    self.parameterization = sdfac_parameterization

  def get_overall_correlation_flex (self, data_a, data_b) :
    """
    Correlate any two sets of data.
    @param data_a data set a
    @param data_b data set b
    @return tuple containing correlation coefficent, slope and offset.
    """
    import math

    assert len(data_a) == len(data_b)
    corr = 0
    slope = 0
    offset = 0
    try:
      sum_xx = 0
      sum_xy = 0
      sum_yy = 0
      sum_x  = 0
      sum_y  = 0
      N      = 0
      for i in range(len(data_a)):
        I_r       = data_a[i]
        I_o       = data_b[i]
        N      += 1
        sum_xx += I_r**2
        sum_yy += I_o**2
        sum_xy += I_r * I_o
        sum_x  += I_r
        sum_y  += I_o
      slope = (N * sum_xy - sum_x * sum_y) / (N * sum_xx - sum_x**2)
      offset = (sum_xx * sum_y - sum_x * sum_xy) / (N * sum_xx - sum_x**2)
      corr  = (N * sum_xy - sum_x * sum_y) / (math.sqrt(N * sum_xx - sum_x**2) *
                 math.sqrt(N * sum_yy - sum_y**2))
    except ZeroDivisionError:
      pass

    return corr, slope, offset

  def normal_probability_plot(self, data, rankits_sel=None, plot=False):
    """ Use normal probability analysis to determine if a set of data is normally distributed
    See https://en.wikipedia.org/wiki/Normal_probability_plot.
    Rankits are computed in the same way as qqnorm does in R.
    @param data flex array
    @param rankits_sel only use the rankits in a certain range. Useful for outlier rejection. Should be
    a tuple such as (-0.5,0.5).
    @param plot whether to show the normal probabilty plot
    """
    from scitbx.math import distributions
    import numpy as np
    norm = distributions.normal_distribution()

    n = len(data)
    if n <= 10:
      a = 3/8
    else:
      a = 0.5

    sorted_data = flex.sorted(data)
    rankits = flex.double([norm.quantile((i+1-a)/(n+1-(2*a))) for i in range(n)])

    if rankits_sel is None:
      corr, slope, offset = self.get_overall_correlation_flex(sorted_data, rankits)
    else:
      sel = (rankits >= rankits_sel[0]) & (rankits <= rankits_sel[1])
      corr, slope, offset = self.get_overall_correlation_flex(sorted_data.select(sel), rankits.select(sel))

    if plot:
      from matplotlib import pyplot as plt
      f = plt.figure(0)
      lim = -5, 5
      x = np.linspace(lim[0],lim[1],100) # 100 linearly spaced numbers
      y = slope * x + offset
      plt.plot(sorted_data, rankits, '-')
      #plt.plot(x,y)
      plt.title("CC: %.3f Slope: %.3f Offset: %.3f"%(corr, slope, offset))
      plt.xlabel("Sorted data")
      plt.ylabel("Rankits")
      plt.xlim(lim); plt.ylim(lim)
      plt.axes().set_aspect('equal')

      f = plt.figure(1)
      h = flex.histogram(sorted_data, n_slots=100, data_min = lim[0], data_max = lim[1])
      stats = flex.mean_and_variance(sorted_data)
      plt.plot(h.slot_centers().as_numpy_array(), h.slots().as_numpy_array(), '-')
      plt.xlim(lim)
      plt.xlabel("Sorted data")
      plt.ylabel("Count")
      plt.title("Normalized data mean: %.3f +/- %.3f"%(stats.mean(), stats.unweighted_sample_standard_deviation()))

      if self.scaler.params.raw_data.error_models.sdfac_refine.plot_refinement_steps:
        plt.ion()
        plt.pause(0.05)

    return corr, slope, offset

  def get_initial_sdparams_estimates(self):
    """
    Use normal probability analysis to compute intial sdfac and sdadd parameters.
    """
    from xfel import compute_normalized_deviations
    all_sigmas_normalized = compute_normalized_deviations(self.scaler.ISIGI, self.scaler.miller_set.indices())
    assert ((all_sigmas_normalized > 0) | (all_sigmas_normalized <= 0)).count(True) == len(all_sigmas_normalized) # no nans allowed

    # remove zeros (miller indices with only one observation will have a normalized deviation of 0 which shouldn't contribute to
    # the normal probability plot analysis and initial parameter estimation
    all_sigmas_normalized = all_sigmas_normalized.select(all_sigmas_normalized != 0)

    corr, slope, offset = self.normal_probability_plot(all_sigmas_normalized, (-0.5, 0.5))
    sdfac = 1/slope
    sdadd = offset
    #sdadd = -offset/slope
    sdb = math.sqrt(sdadd)

    return sdfac, sdb, sdadd


  def get_binned_intensities(self, n_bins=100):
    """
    Using self.ISIGI, bin the intensities using the following procedure:
    1) Find the minimum and maximum intensity values.
    2) Divide max-min by n_bins. This is the bin step size
    The effect is
    @param n_bins number of bins to use.
    @return a tuple with an array of selections for each bin and an array of median
    intensity values for each bin.
    """
    print >> self.log, "Computing intensity bins.",
    all_mean_Is = flex.double()
    only_means = flex.double()
    for hkl_id in range(self.scaler.n_refl):
      hkl = self.scaler.miller_set.indices()[hkl_id]
      if hkl not in self.scaler.ISIGI: continue
      n = len(self.scaler.ISIGI[hkl])
      # get scaled intensities
      intensities = flex.double([self.scaler.ISIGI[hkl][i][0] for i in range(n)])
      meanI = flex.mean(intensities)
      only_means.append(meanI)
      all_mean_Is.extend(flex.double([meanI]*n))
    step = (flex.max(only_means)-flex.min(only_means))/n_bins
    print >> self.log, "Bin size:", step

    sels = []
    binned_intensities = []
    min_all_mean_Is = flex.min(all_mean_Is)
    for i in range(n_bins):
      sel = (all_mean_Is > (min_all_mean_Is + step * i)) & (all_mean_Is < (min_all_mean_Is + step * (i+1)))
      if sel.all_eq(False): continue
      sels.append(sel)
      binned_intensities.append((step/2 + step*i)+min(only_means))

    for i, (sel, intensity) in enumerate(zip(sels, binned_intensities)):
      print >> self.log, "Bin %02d, number of observations: % 10d, midpoint intensity: %f"%(i, sel.count(True), intensity)

    return sels, binned_intensities

  def run_minimzer(self, values, sels, **kwargs):
    return simplex_minimizer(values, self.parameterization, self.scaler.ISIGI, self.scaler.miller_set.indices(), sels, kwargs['seed'], self.log)

  def adjust_errors(self):
    """
    Adjust sigmas according to Evans, 2011 Acta D and Evans and Murshudov, 2013 Acta D
    """
    print >> self.log, "Starting adjust_errors"
    print >> self.log, "Computing initial estimates of sdfac, sdb and sdadd"
    values = self.parameterization(flex.double(self.get_initial_sdparams_estimates()))

    print >> self.log, "Initial estimates:",
    values.show(self.log)
    print >> self.log, "Refining error correction parameters sdfac, sdb, and sdadd"
    sels, binned_intensities = self.get_binned_intensities()
    seed = self.scaler.params.raw_data.error_models.sdfac_refine.random_seed
    minimizer = self.run_minimzer(values, sels, seed=seed)
    values = minimizer.get_refined_params()
    print >> self.log, "Final",
    values.show(self.log)

    print >> self.log, "Applying sdfac/sdb/sdadd 1"
    self.scaler.ISIGI = minimizer.apply_sd_error_params(self.scaler.ISIGI, values)

    self.scaler.summed_weight= flex.double(self.scaler.n_refl, 0.)
    self.scaler.summed_wt_I  = flex.double(self.scaler.n_refl, 0.)

    print >> self.log, "Applying sdfac/sdb/sdadd 2"
    for hkl_id in range(self.scaler.n_refl):
      hkl = self.scaler.miller_set.indices()[hkl_id]
      if hkl not in self.scaler.ISIGI: continue

      n = len(self.scaler.ISIGI[hkl])

      for i in range(n):
        Intensity = self.scaler.ISIGI[hkl][i][0] # scaled intensity
        sigma = Intensity / self.scaler.ISIGI[hkl][i][1] # corrected sigma
        variance = sigma * sigma
        self.scaler.summed_wt_I[hkl_id] += Intensity / variance
        self.scaler.summed_weight[hkl_id] += 1 / variance

    if False:
      # validate using http://ccp4wiki.org/~ccp4wiki/wiki/index.php?title=Symmetry%2C_Scale%2C_Merge#Analysis_of_Standard_Deviations
      print >> self.log, "Validating"
      from matplotlib import pyplot as plt
      all_sigmas_normalized = compute_normalized_deviations(self.scaler.ISIGI, self.scaler.miller_set.indices())

      plt.hist(all_sigmas_normalized, bins=100)
      plt.figure()

      binned_rms_normalized_sigmas = []

      for i, sel in enumerate(sels):
        binned_rms_normalized_sigmas.append(math.sqrt(flex.mean(all_sigmas_normalized.select(sel)*all_sigmas_normalized.select(sel))))

      plt.plot(binned_intensities, binned_rms_normalized_sigmas, 'o')
      plt.show()

      all_sigmas_normalized = all_sigmas_normalized.select(all_sigmas_normalized != 0)
      self.normal_probability_plot(all_sigmas_normalized, (-0.5, 0.5), plot = True)


def setup_isigi_stats(ISIGI, indices):
  """ Jiffy function to compute statistics needed downstream
  For every observstion, computes:
  mean_scaled_intensity: mean of all observations of this miller index
  meanprime_scaled_intensity: mean of all observations of this miller index except this observation
  n_refl: count of observed reflections for this miller index
  nn: n_refl-1/n_refl
  """
  sumI = flex.double(len(indices), 0)
  n_refl = flex.double(len(indices), 0)
  for i in range(len(ISIGI)):
    hkl_id = ISIGI['miller_id'][i]
    sumI[hkl_id] += ISIGI['scaled_intensity'][i]
    n_refl[hkl_id] += 1

  all_meanI = flex.double(len(ISIGI), 0)
  all_n_refl = flex.double(len(ISIGI), 0)
  all_imeanprime = flex.double(len(ISIGI), 0)
  for i in range(len(ISIGI)):
    hkl_id = ISIGI['miller_id'][i]
    all_meanI[i] = sumI[hkl_id]/n_refl[hkl_id]
    all_n_refl[i] = n_refl[hkl_id]
    assert n_refl[hkl_id] > 0
    if n_refl[hkl_id] > 1:
      all_imeanprime[i] = (sumI[hkl_id]-ISIGI['scaled_intensity'][i])/(n_refl[hkl_id]-1)
  ISIGI['mean_scaled_intensity'] = all_meanI
  ISIGI['n_refl'] = all_n_refl
  ISIGI['nn'] = (all_n_refl - 1)/all_n_refl
  ISIGI['meanprime_scaled_intensity'] = all_imeanprime

class simplex_minimizer_refltable(simplex_minimizer):
  """Class for refining sdfac, sdb and sdadd"""

  def target(self, vector):
    """ Compute the functional by first applying the current values for the sd parameters
    to the input data, then computing the complete set of normalized deviations and finally
    using those normalized deviations to compute the functional."""
    values = self.parameterization(vector)

    if values.SDFAC < 0 or values.SDB < 0 or values.SDADD < 0:
      f = 1e6
    else:
      orig_isigi = self.data['isigi'] * 1

      self.apply_sd_error_params(self.data, values)
      all_sigmas_normalized = compute_normalized_deviations(self.data, self.indices)
      self.data['isigi'] = orig_isigi

      f = 0
      for bin in self.intensity_bin_selections:
        binned_normalized_sigmas = all_sigmas_normalized.select(bin)
        n = len(binned_normalized_sigmas)
        if n == 0: continue
        # weighting scheme from Evans, 2011
        w = math.sqrt(n)
        # functional is weight * (1-rms(normalized_sigmas))^s summed over all intensitiy bins
        f += w * ((1-math.sqrt(flex.mean(binned_normalized_sigmas*binned_normalized_sigmas)))**2)

    print >> self.log, "f: % 12.1f,"%f,
    values.show(self.log)
    return f

  def apply_sd_error_params(self, data, values):
    apply_sd_error_params(data, values.SDFAC, values.SDB, values.SDADD, False)

class sdfac_refine_refltable(sdfac_refine):
  def __init__(self, scaler):
    super(sdfac_refine_refltable, self).__init__(scaler)

    if isinstance(scaler.ISIGI, dict):
      # work around for cxi.xmerge which doesn't make a reflection table
      from xfel.merging.command_line.dev_cxi_merge_refltable import merging_reflection_table
      self._isigi_dict = scaler.ISIGI
      reflections = merging_reflection_table()
      for i, hkl in enumerate(scaler.miller_set.indices()):
        if hkl not in scaler.ISIGI: continue
        for j, refl in enumerate(scaler.ISIGI[hkl]):
          reflections.append({'miller_index':hkl,
                              'scaled_intensity': refl[0],
                              'isigi': refl[1],
                              'slope': refl[2],
                              'miller_id':i,
                              'crystal_id':0,
                              'iobs':0,
                              'miller_index_original':(0,0,0)})
      scaler.ISIGI = reflections

  def get_binned_intensities(self, n_bins=100):
    """
    Using self.ISIGI, bin the intensities using the following procedure:
    1) Find the minimum and maximum intensity values.
    2) Divide max-min by n_bins. This is the bin step size
    The effect is
    @param n_bins number of bins to use.
    @return a tuple with an array of selections for each bin and an array of median
    intensity values for each bin.
    """
    print >> self.log, "Computing intensity bins.",
    ISIGI = self.scaler.ISIGI
    setup_isigi_stats(ISIGI, self.scaler.miller_set.indices())
    meanI = ISIGI['mean_scaled_intensity']

    sels = []
    binned_intensities = []

    if True:
      # intensity range per bin is the same
      min_meanI = flex.min(meanI)
      step = (flex.max(meanI)-min_meanI)/n_bins
      print >> self.log, "Bin size:", step

      for i in range(n_bins):
        if i+1 == n_bins:
          sel = (meanI >= (min_meanI + step * i))
        else:
          sel = (meanI >= (min_meanI + step * i)) & (meanI < (min_meanI + step * (i+1)))
        if sel.all_eq(False): continue
        sels.append(sel)
        binned_intensities.append((step/2 + step*i)+min(meanI))
    else:
      # n obs per bin is the same
      sorted_meanI = meanI.select(flex.sort_permutation(meanI))
      bin_size = len(meanI)/n_bins
      for i in range(n_bins):
        bin_min = sorted_meanI[int(i*bin_size)]
        sel = meanI >= bin_min
        if i+1 == n_bins:
          bin_max = sorted_meanI[-1]
        else:
          bin_max = sorted_meanI[int((i+1)*bin_size)]
          sel &= meanI < bin_max
        sels.append(sel)
        binned_intensities.append(bin_min + ((bin_max-bin_min)/2))

    for i, (sel, intensity) in enumerate(zip(sels, binned_intensities)):
      print >> self.log, "Bin %02d, number of observations: % 10d, midpoint intensity: %f"%(i, sel.count(True), intensity)

    return sels, binned_intensities

  def run_minimzer(self, values, sels, **kwargs):
   return simplex_minimizer_refltable(values, self.parameterization, self.scaler.ISIGI, self.scaler.miller_set.indices(), sels, kwargs['seed'], self.log)

  def adjust_errors(self):
    """
    Adjust sigmas according to Evans, 2011 Acta D and Evans and Murshudov, 2013 Acta D
    """
    print >> self.log, "Starting adjust_errors"
    print >> self.log, "Computing initial estimates of sdfac, sdb and sdadd"
    values = self.parameterization(flex.double(self.get_initial_sdparams_estimates()))

    print >> self.log, "Initial estimates:",
    values.show(self.log)
    print >> self.log, "Refining error correction parameters sdfac, sdb, and sdadd"
    sels, binned_intensities = self.get_binned_intensities()
    seed = self.scaler.params.raw_data.error_models.sdfac_refine.random_seed
    minimizer = self.run_minimzer(values, sels, seed=seed)
    values = minimizer.get_refined_params()
    print >> self.log, "Final",
    values.show(self.log)

    print >> self.log, "Applying sdfac/sdb/sdadd 1"
    minimizer.apply_sd_error_params(self.scaler.ISIGI, values)

    self.scaler.summed_weight= flex.double(self.scaler.n_refl, 0.)
    self.scaler.summed_wt_I  = flex.double(self.scaler.n_refl, 0.)

    print >> self.log, "Applying sdfac/sdb/sdadd 2"
    for i in range(len(self.scaler.ISIGI)):
      hkl_id = self.scaler.ISIGI['miller_id'][i]
      Intensity = self.scaler.ISIGI['scaled_intensity'][i] # scaled intensity
      sigma = Intensity / self.scaler.ISIGI['isigi'][i] # corrected sigma
      variance = sigma * sigma
      self.scaler.summed_wt_I[hkl_id] += Intensity / variance
      self.scaler.summed_weight[hkl_id] += 1 / variance

    if self.scaler.params.raw_data.error_models.sdfac_refine.plot_refinement_steps:
      from matplotlib.pyplot import cm
      from matplotlib import pyplot as plt
      import numpy as np
      for i in range(2):
        f = plt.figure(i)
        lines = plt.gca().get_lines()
        color=cm.rainbow(np.linspace(0,1,len(lines)))
        for line, c in zip(reversed(lines), color):
          line.set_color(c)
      plt.ioff()
      plt.show()

    if False:
      # validate using http://ccp4wiki.org/~ccp4wiki/wiki/index.php?title=Symmetry%2C_Scale%2C_Merge#Analysis_of_Standard_Deviations
      print >> self.log, "Validating"
      from matplotlib import pyplot as plt
      all_sigmas_normalized = compute_normalized_deviations(self.scaler.ISIGI, self.scaler.miller_set.indices())
      plt.hist(all_sigmas_normalized, bins=100)
      plt.figure()

      binned_rms_normalized_sigmas = []

      for i, sel in enumerate(sels):
        binned_rms_normalized_sigmas.append(math.sqrt(flex.mean(all_sigmas_normalized.select(sel)*all_sigmas_normalized.select(sel))))

      plt.plot(binned_intensities, binned_rms_normalized_sigmas, 'o')
      plt.show()

      all_sigmas_normalized = all_sigmas_normalized.select(all_sigmas_normalized != 0)
      self.normal_probability_plot(all_sigmas_normalized, (-0.5, 0.5), plot = True)
