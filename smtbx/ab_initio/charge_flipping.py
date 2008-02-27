""" Charge flipping algorithm(s) and related data structures

References.

[1] G. Oszl{\'a}nyi and A. S{\"u}t{\H o}.
Ab initio structure solution by charge flipping.
Acta Cryst. A, 60:134--141, 2003.

[2] G. Oszl{\'a}nyi and A. S{\"u}t{\H o}.
Ab initio structure solution by charge flipping.
II. use of weak reflections. Acta Cryst. A, 61:147, 2004.

[3] L. Palatinus and G. Chapuis
SUPERFLIP -- a computer program for the solution of crystal structures
by charge flipping in arbitry dimensions
J. Appl. Cryst., 40:786--790, 2007

[4] M. Shiono and M.M. Woolfson.
Direct-space methods in phase extension and phase determination.
I. low-density elimination. Acta Cryst. A, 48:451-456, 1992.
--> This is a protein paper

[5] H. Takakura, M. Shiono, T.J. Sato, A. Yamamoto, and A.P. Tsai.
Ab initio structure determination of icosahedral zn-mg-ho quasicrystals
by density modification method.
Phys. Rev. Lett., 86:236, 2001
--> This is an elaboration on the method in [4] as well as an application in a
different compartment of crystallography. This is also the method used
in SUPERFLIP circa Sept 2007 to polish the electron density after the charge
flipping method has converged.
"""

from __future__ import division

from libtbx import forward_compatibility
from libtbx import object_oriented_patterns as oop
from libtbx.math_utils import are_equivalent
from libtbx.assert_utils import is_numeric
from libtbx import itertbx
from libtbx import adopt_init_args

from cctbx.array_family import flex
from cctbx import sgtbx
from cctbx import miller
from cctbx import maptbx
from cctbx import translation_search

from smtbx import ab_initio

import math


class _array_extension(oop.injector, miller.array):

  def oszlanyi_suto_phase_transfer(self,
                                   source,
                                   delta_varphi=math.pi/2,
                                   weak_reflection_fraction=0.2,
                                   need_sorting=True):
    """ As per ref. [2] """
    cut = int(weak_reflection_fraction * source.size())
    if need_sorting:
      p = self.sort_permutation(by_value="data", reverse=True)
      target = self.select(p)
      source = source.select(p)
    else:
      target = self
    source_phases = flex.arg(source.data())
    # weak reflections
    phases = source_phases[:cut] + delta_varphi
    moduli = flex.abs(source.data()[:cut])
    # strong ones
    phases.extend(source_phases[cut:])
    moduli.extend(self.data()[cut:])
    return miller.array(self, moduli).phase_transfer(phases)


class _fft_extension(oop.injector, miller.fft_map):
  """ We add those methods to fft_map so that they can be easily reused and
  tested independently of the charge flipping iterators. """

  def flipped_fraction_as_delta(self, fraction):
    rho = self.real_map_unpadded().as_1d()
    p = flex.sort_permutation(rho)
    sorted_rho = rho.select(p)
    return sorted_rho[int(fraction * sorted_rho.size())]
  flipped_fraction_as_delta = oop.memoize_method(flipped_fraction_as_delta)

  def c_flip(self, delta):
    rho = self.real_map_unpadded().as_1d()
    return flex.sum(flex.abs(rho.select(rho < delta)))
  c_flip = oop.memoize_method(c_flip)

  def c_tot(self):
    return flex.sum(self.real_map())
  c_tot = oop.memoize_method(c_tot)


class density_modification_iterator(object):

  def __init__(self, f_obs, f_calc=None, f_000=None,
               starter=miller.array.randomize_phases):
    assert f_obs.data() is not None
    assert are_equivalent(f_calc is None, f_000 is None)
    assert f_calc is None or (is_numeric(f_calc) and is_numeric(f_000))

    self.original_f_obs = f_obs
    self.crystal_gridding = f_obs.crystal_gridding(
      resolution_factor=1/2,
      symmetry_flags=maptbx.use_space_group_symmetry)
    self.crystal_gridding.change_space_group(sgtbx.space_group_info("P1"))
    self.f_obs = f_obs.eliminate_sys_absent() \
                      .expand_to_p1() \
                      .as_non_anomalous_array() \
                      .merge_equivalents().array() \
                      .discard_sigmas()
    self.fft_scale = (self.f_obs.crystal_symmetry().unit_cell().volume()
                      / self.crystal_gridding.n_grid_points())
    self.starter = starter
    self.restart(f_calc, f_000)

  def restart(self, f_calc=None, f_000=None):
    assert are_equivalent(f_calc is None, f_000 is None)
    assert f_calc is None or (is_numeric(f_calc) and is_numeric(f_000))
    if f_calc is None:
      f_calc = self.starter(self.f_obs)
      f_000 = 0
    self.f_calc = f_calc
    self.f_000 = f_000
    self.compute_electron_density_map()

  def __iter__(self):
    return self

  def next(self):
    self.modify_electron_density()
    self.compute_structure_factors()
    self.transfer_phase_to_f_obs()
    self.f_000 = self._g_000
    self.compute_electron_density_map()
    return self # iterator-is-its-own-state trick

  def compute_electron_density_map(self):
    self.rho_map = miller.fft_map(self.crystal_gridding,
                                  self.f_calc,
                                  self.f_000)
    self.rho_map.apply_volume_scaling()

  def compute_structure_factors(self):
    """ This shall compute the structure factors self._g of self.rho_map,
    as well as the 000 component self._g_000, scaling them by the number of
    grid points """
    rho = self.rho_map.real_map()
    self._g_000 = flex.sum(rho) * self.fft_scale
    self._g = self.f_obs.structure_factors_from_map(rho, in_place_fft=True)
    self._g *= self.fft_scale

  def transfer_phase_to_f_obs(self):
    self.f_calc = self.f_obs.phase_transfer(self._g)

  def r1_factor(self):
    return self.f_obs.r1_factor(self._g, assume_index_matching=True)

  def c_tot_over_c_flip(self):
    return self.rho_map.c_tot()/self.rho_map.c_flip(self.delta)

  def search_origin(self,
                    grid_resolution_factor=1/3,
                    return_correlation_map_too=False):
    """ The fast correlation map as per cctbx.translation_search.fast_nv1995
    is computed and its peaks studied.
    Inspiration from phenix.substructure.hyss for the parameters tuning.
    """
    f_obs = self.original_f_obs
    f_calc = self.f_calc
    crystal_gridding = f_obs.crystal_gridding(
      symmetry_flags=translation_search.symmetry_flags(
        is_isotropic_search_model=False,
        have_f_part=False),
      resolution_factor=grid_resolution_factor
    )
    correlation_map = translation_search.fast_nv1995(
      gridding=crystal_gridding.n_real(),
      space_group=f_obs.space_group(),
      anomalous_flag=f_obs.anomalous_flag(),
      miller_indices_f_obs=f_obs.indices(),
      f_obs=f_obs.data(),
      f_part=flex.complex_double(), ## no sub-structure is already fixed
      miller_indices_p1_f_calc=f_calc.indices(),
      p1_f_calc=f_calc.data()).target_map()
    search_parameters = maptbx.peak_search_parameters(
      peak_search_level=1,
      peak_cutoff=0.5,
      interpolate=True,
      min_distance_sym_equiv=1e-6,
      general_positions_only=False,
      min_cross_distance=f_obs.d_min()/2)
    ## The correlation map is not a miller.fft_map, just a 3D flex.double
    result = crystal_gridding.tags().peak_search(
      map=correlation_map,
      parameters=search_parameters)
    if return_correlation_map_too:
      result = (result, correlation_map)
    return result


class basic_iterator(density_modification_iterator):
  """ An iterator over the sequence of electron densities and structure
  factors obtained by repeateadly applying the basic charge flipping
  described in ref. [1].
  """

  def __init__(self, f_obs, delta=None, **kwds):
    super(basic_iterator, self).__init__(f_obs, **kwds)
    self.delta = delta

  def modify_electron_density(self):
    """ This shall modify rho in place """
    ab_initio.ext.flip_charges_in_place(self.rho_map.real_map(), self.delta)


class weak_reflection_improved_iterator(basic_iterator):
  """ The variation described in ref. [2] """

  def __init__(self, f_obs, delta=None,
               delta_varphi=math.pi/2,
               weak_reflection_fraction=0.2,
               **kwds):
    super(weak_reflection_improved_iterator,
          self).__init__(f_obs, delta, **kwds)
    self.delta_varphi = delta_varphi
    self.weak_reflection_fraction = weak_reflection_fraction

    # sort f_obs by increasing amplitudes once and for all
    p = self.f_obs.sort_permutation(by_value="data", reverse=True)
    self.f_obs = self.f_obs.select(p)

  def transfer_phase_from_g_tof_obs(self):
    self.f_calc = self.f_obs.oszlanyi_suto_phase_transfer(
      self._g,
      self.delta_varphi,
      self.weak_reflection_fraction,
      need_sorting=False)


class low_density_elimination_iterator(density_modification_iterator):
  """ A method related to charge flipping.
  C.f. Ref [4].
  """

  def __init__(self, f_obs, rho_c=None, **kwds):
    super(low_density_elimination_iterator, self).__init__(f_obs, **kwds)
    if rho_c is not None: self.rho_c = rho_c

  def modify_electron_density(self):
    ab_initio.ext.low_density_elimination_in_place_tanaka_et_al_2001(
      self.rho_map.real_map(), self.rho_c())

  def rho_c(self):
    """ The rho_c suggested in Ref [4] """
    rho = self.rho_map.real_map_unpadded()
    return 0.2*flex.mean(rho.select(rho >0))


class solving_iterator(object):

  def __init__(self, flipping_iterator,
               delta_guessing_sub_iterations=10,
               initial_flipped_fraction=0.8,
               yield_during_delta_guessing=False,
               max_solving_iterations=500,
               max_attempts=5,
               yield_solving_interval=10,
               phase_transition_tail_len=12,
               polishing_iterations=5):
    adopt_init_args(self, locals())
    self.attempts = []
    self.max_attemps_exceeded = False
    self.state = self.guessing_delta = self._guessing_delta()
    self.solving = self._solving()
    self.polishing = self._polishing()
    self.finished = self._finished()

  def __iter__(self):
    for result, self.state in self.state:
      yield result

  def _finished(self):
    yield self.flipping_iterator, self.finished

  def _guessing_delta(self):
    flipping = self.flipping_iterator
    flipping.delta = flipping.rho_map.flipped_fraction_as_delta(
      self.initial_flipped_fraction)
    while 1:
      for state in itertbx.islice(flipping,
                                  self.delta_guessing_sub_iterations):
        pass
      r = flipping.c_tot_over_c_flip()
      # magic numbers from SUPERFLIP
      ok = False
      if r < 0.8:
        flipping.delta *= 0.9
      elif r > 1:
        flipping.delta *= 1.07
      else:
        ok = True
      if ok:
        yield flipping, self.solving
      elif self.yield_during_delta_guessing:
        yield flipping, self.guessing_delta
      flipping.restart()

  def _solving(self):
    i_attempt = 0
    while i_attempt < self.max_attempts:
      i_attempt += 1
      r1 = observable_evolution(self.phase_transition_tail_len)
      ctot_over_cflip = observable_evolution(self.phase_transition_tail_len)
      for n, flipping in enumerate(
        itertbx.islice(self.flipping_iterator,
                       0, self.max_solving_iterations)):
        self.iteration_index = n
        if n % self.yield_solving_interval == 0:
          yield flipping, self.solving
        r1.append(flipping.r1_factor())
        ctot_over_cflip.append(flipping.c_tot_over_c_flip())
        if n < self.phase_transition_tail_len: continue
        if abs(r1.min_diff_index - ctot_over_cflip.min_diff_index) > 4:
          continue
        r1_transition = r1.had_phase_transition()
        ctot_over_cflip_transition = ctot_over_cflip.had_phase_transition()
        phase_transition = r1_transition and ctot_over_cflip_transition
        if phase_transition:
          self.attempts.append(n)
          yield flipping, self.polishing
      else:
        if i_attempt != self.max_attempts:
          yield flipping, self.guessing_delta
    self.max_attemps_exceeded = True
    yield self.flipping_iterator, self.finished

  def _polishing(self):
    flipping = self.flipping_iterator
    polishing = low_density_elimination_iterator(
      f_obs=flipping.f_obs,
      f_calc=flipping.f_calc,
      f_000=0,
      rho_c=lambda: flipping.delta)
    for state in itertbx.islice(polishing, self.polishing_iterations):
      pass
    yield flipping, self.finished


class observable_evolution(object):

  def __init__(self, phase_transition_tail_len):
    adopt_init_args(self, locals())
    self.values = flex.double()
    self.differences = flex.double()
    self.min_diff = None
    self.min_diff_index = None

  def append(self, x):
    self.values.append(x)
    if len(self.values) > 1:
      diff = self.values[-1] - self.values[-2]
      if self.min_diff is None or diff < self.min_diff:
        self.min_diff = diff
        self.min_diff_index = len(self.differences)
      self.differences.append(diff)

  def had_phase_transition(self):
    if (len(self.differences) - self.min_diff_index
        < self.phase_transition_tail_len): return False
    before = self.min_diff_index - 4
    if before < 0: return False
    after = self.min_diff_index + 4
    indices = flex.double_range(len(self.values)-after)
    tail = self.values[after:]
    p = flex.sort_permutation(tail)
    lc = flex.linear_correlation(indices, tail)
    lr = flex.linear_regression(indices, tail)
    lc_up    = flex.linear_correlation(indices.select(p[-5:]),
                                        tail.select(p[-5:]))
    lc_down = flex.linear_correlation(indices.select(p[:5]),
                                        tail.select(p[:5]))
    lr_up    = flex.linear_regression(indices.select(p[-5:]),
                                       tail.select(p[-5:]))
    lr_down = flex.linear_regression(indices.select(p[:5]),
                                       tail.select(p[:5]))
    max_slope = 0.05
    if abs(lc.coefficient()) > 0.5:
      if abs(lr.slope()) > max_slope:
        return False
    elif abs(lc_down.coefficient()) < 0.5 and abs(lc_up.coefficient()) < 0.5:
      if abs(lr_down.slope()) > max_slope or abs(lr_up.slope()) > max_slope:
        return False
    value_after = lr.y_intercept()
    tail_stats = flex.mean_and_variance(tail)
    m_t = tail_stats.mean()
    v_t = tail_stats.unweighted_sample_variance()
    head = self.values[max(before - self.phase_transition_tail_len//2, 0)
                       : before]
    if len(head) > 1:
      head_stats = flex.mean_and_variance(head)
      m_h = head_stats.mean()
      v_h = head_stats.unweighted_sample_variance()
      fall_significance = abs(m_h - m_t)/math.sqrt(v_h + v_t)
    else:
      fall_significance = abs(head[0] - m_t)/math.sqrt(v_t)
    return fall_significance > 3
